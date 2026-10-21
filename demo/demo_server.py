#!/usr/bin/env python3
"""Live transcription with phrase-aligned, streaming translation on the board.

The browser resamples its video audio to 16 kHz PCM16 and posts it to the ASR
worker. Original text is emitted through SSE while the business-layer segmenter
collects sentence, semantic-turn and pause boundaries. An independent persistent
process invokes the delivered translation Python SDK and streams each text chunk
back through SSE. Session IDs reject obsolete results; per-phrase revisions make
snapshot replay idempotent. Stop finishes accepted audio and the remaining phrase.

The ASR and translation model algorithms stay in their existing component SDKs.
The composite uses the verified 160 ms ASR configuration. Each launch uses this
project's .venv; native AidLite/AidGen/QNN runtimes remain system dependencies.
"""
import argparse
import atexit
import codecs
import collections
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, f"{ROOT}/sdk/python")

import numpy as np  # noqa: E402

from live_transcribe_01 import Engine, LT01Error, extra_file  # noqa: E402
from model_package_check import PackageVerifier
from reset_policy import ResetPolicy  # noqa: E402
from vad_gate import SileroGate  # noqa: E402
from segmentation import Segmenter
from paragraphs import ParagraphTracker
from languages import LANGUAGES, SOURCE_LANGUAGES, target_for
from translation_service import TranslationService

MODELS = None                         # resolved after argument parsing; --help needs no installed package
TRANSLATION_MODELS = None

MEDIA = f"{HERE}/media"
UPLOADS = f"{MEDIA}/uploads"
STATIC = f"{HERE}/static"
MAX_POS, STOP_MARGIN = 480, 8
BACKLOG_WARN_S = 30          # log when the engine falls this far behind the page's audio (e.g. the NPU is shared)
# unlimited length: the engine's LM rolls a 30 s context; without rolling (roll_s 0) the per-run capacity guard applies
VIDEO_EXT = (".mp4", ".m4v", ".mov", ".webm", ".mkv")
CLOCKS, LANGS = ("160",), ("en", "zh")


def media_path(vid):
    """Video id (path relative to media/) -> absolute path, or None if it escapes media/ or does not exist."""
    p = os.path.normpath(os.path.join(MEDIA, vid))      # lexical check (media files may be symlinks, e.g. a dev checkout)
    return p if p.startswith(os.path.normpath(MEDIA) + os.sep) and os.path.isfile(p) else None


def meta_of(path):
    return os.path.splitext(path)[0] + ".json"


def video_lang(path):
    """Transcription language of a video (sidecar <stem>.json {"lang": "zh" | "en"}, written at upload; default zh)."""
    try:
        lang = json.load(open(meta_of(path))).get("lang", "zh")
    except (OSError, ValueError):
        lang = "zh"
    return lang if lang in LANGS else "zh"


def has_audio(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                              path], capture_output=True, text=True, timeout=60).stdout.strip()
        return bool(out)
    except subprocess.SubprocessError:
        return False


def duration_s(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return round(float(out), 1)
    except (ValueError, subprocess.SubprocessError):
        return None


class Session:
    def __init__(self):
        self.lock = threading.Lock()
        self.subs = []
        self.translations = TranslationService(TRANSLATION_MODELS,
                                              os.path.join(ROOT, "components/translation/sdk/python"), self.broadcast)
        atexit.register(self.translations.close)
        self.worker_sid = None
        self.segmenter = None
        self.paragraph_tracker = None
        self.translation_paragraph = None
        self.paragraph_options = dict(enabled=True, horizon=2.0, threshold=0.6)
        self.stopping = threading.Event()
        self.sid, self.state, self.video = 0, "idle", None
        self.offset_s, self.jump = 0.0, False            # start position of the current run in the video
        self.audio = collections.deque()                # (sid, float32 16 kHz chunk) posted by the page
        self.ended, self.pending = False, None
        self.durs = {}
        self.off_s = 0.0
        self.sys_hist = collections.deque(maxlen=240)      # last 120 s of [t, dram_used_mb], sent to new pages
        self.package = PackageVerifier(MODELS)
        print("[demo] verifying model package files before loading", flush=True)
        self.clocks, self.clock_errors = self.package.available()
        self.clocks = [c for c in self.clocks if c in CLOCKS]
        if not self.clocks:
            raise SystemExit("no verified model package: " + "; ".join(
                f"{clock} ms: {error}" for clock, error in self.clock_errors.items()))
        self.gate = SileroGate(extra_file(MODELS, "silero_vad"))
        c = os.environ.get("LT01_CLOCK_MS")
        if c and c not in self.clocks:
            print(f"[demo] the {c} ms clock is not installed, using {self.clocks[0]} ms", flush=True)
        self.clock = c if c in self.clocks else self.clocks[0]
        self.lang = os.environ.get("LT01_LANG", "en")
        self.target = target_for(self.lang)
        self.asr = None
        self.load_engine()
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)
        self.worker_thread.start()
        threading.Thread(target=self.sysmon, daemon=True).start()

    def load_engine(self):
        t = time.time()
        self.asr = Engine(MODELS, clock_ms=int(self.clock), lang=self.lang)
        self.policy = ResetPolicy(self.asr)
        self.init_s = time.time() - t
        self.fs = self.asr.sampling_rate
        self.spt = self.asr.samples_per_token
        self.clock_ms = 1000.0 * self.spt / self.fs
        self.n_gen = 0

    def close_engine(self):
        if self.asr is not None:
            self.asr.close()
        self.asr = None

    # ------------------------------------------------------------ events
    def broadcast(self, ev):
        for q in list(self.subs):
            q.put(ev)

    def info(self):
        a = self.asr
        if a is None:
            return {"type": "info", "state": self.state}
        roll = a.info["roll_s"]
        return {"type": "info", "sid": self.sid, "paragraph_options": dict(self.paragraph_options), "translation_target": self.target, "translation_enabled": self.translations.enabled, "translation_epoch": self.translations.epoch, "translation_active": self.translations.worker_active, "languages": LANGUAGES, "source_languages": list(SOURCE_LANGUAGES), "clocks": list(self.clocks), "clock_errors": dict(self.clock_errors), "lang": self.lang, "clock_ms": round(self.clock_ms),
                "delay_ms": round(self.clock_ms * a.info["num_delay_tokens"]),
                "max_audio_s": None if roll else round((MAX_POS - STOP_MARGIN) * self.clock_ms / 1000, 1),
                "roll_s": round(roll, 1) if roll else None,
                "init_s": round(self.init_s, 1), "state": self.state, "video": self.video, "vad": self.gate.enabled,
                "vad_params": self.gate.params, "eot_horizons_s": a.info["eot_horizons_s"]}

    def videos(self):
        out = []
        for d, builtin in ((MEDIA, True), (UPLOADS, False)):
            if not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                p = f"{d}/{f}"
                if f.lower().endswith(VIDEO_EXT):
                    if p not in self.durs:
                        self.durs[p] = duration_s(p)
                    out.append({"id": os.path.relpath(p, MEDIA), "name": f, "builtin": builtin, "duration_s": self.durs[p],
                                "lang": video_lang(p)})
        return out

    def sysmon(self):
        """Board DRAM every 0.5 s: system used = MemTotal - MemAvailable."""
        while not self.stopping.is_set():
            m = {}
            for line in open("/proc/meminfo"):
                k, v = line.split(":", 1)
                m[k] = int(v.split()[0]) // 1024
            ev = {"type": "sys", "t": round(time.time(), 2), "dram_total_mb": m["MemTotal"],
                  "dram_used_mb": m["MemTotal"] - m["MemAvailable"]}
            self.dram_total = m["MemTotal"]
            self.sys_hist.append([ev["t"], ev["dram_used_mb"]])
            self.broadcast(ev)
            self.stopping.wait(0.5)

    # ------------------------------------------------------------ control (HTTP threads)
    def start(self, vid, offset_s=0.0, jump=False, target=None, translation_enabled=None):
        """New run of `vid` from offset_s (a fresh engine session at that point of the video). jump = the page moved the
        playhead during a run (source and translation start a new shared session)."""
        p = media_path(vid)
        if p is None:
            return None, "unknown video"
        with self.lock:
            if self.state in ("reload",):
                return None, "engine is loading"
        if video_lang(p) != self.lang:                   # the page switches the language when a video is selected
            return None, f"this video is {video_lang(p)}, the engine is {self.lang}: switch first"
        if translation_enabled is not None and not isinstance(translation_enabled, bool):
            return None, "Translation enabled must be a boolean"
        try:
            selected_target = target_for(self.lang, target if target is not None else self.target)
        except ValueError as error:
            return None, str(error)
        with self.lock:
            self.target = selected_target
            self.sid += 1
            self.translations.begin(self.sid, self.lang, self.target, enabled=translation_enabled)
            self.video, self.offset_s, self.jump = vid, max(0.0, float(offset_s)), bool(jump)
            self.ended = False
            self.audio = collections.deque(c for c in self.audio if c[0] == self.sid)
            self.state = "reset"                         # the worker resets the engine, then runs
        return self.sid, None

    def push_audio(self, sid, pcm16):
        """100 ms of 16 kHz PCM16 from the page (its own audio capture of the playing video)."""
        x = np.frombuffer(pcm16, "<i2").astype(np.float32) / 32768.0
        with self.lock:
            if sid == self.sid and self.state in ("reset", "running") and not self.ended:
                self.audio.append((sid, x))

    def end(self, sid):
        """The video reached its end: drain the remaining audio, then finish."""
        with self.lock:
            if sid == self.sid:
                self.ended = True

    def stop(self):
        with self.lock:
            if self.state == "reload":
                return
            # Finish accepted audio and translate its last phrase before stopping.
            if self.state in ("reset", "running"):
                self.ended = True
                return
        self.broadcast({"type": "state", "state": "idle"})

    def set_vad(self, b):
        if "enabled" in b:
            self.gate.enabled = bool(b["enabled"])        # live: read by the gate on every frame it releases
        self.gate.configure(b.get("threshold"), b.get("preroll_s"), b.get("hangover_s"))   # from the next Start
        self.broadcast({"type": "vad", "enabled": self.gate.enabled, "params": self.gate.params})

    def set_paragraphs(self, options):
        try:
            enabled = options.get("enabled", self.paragraph_options["enabled"])
            horizon = float(options.get("horizon", self.paragraph_options["horizon"]))
            threshold = float(options.get("threshold", self.paragraph_options["threshold"]))
            if not isinstance(enabled, bool) or horizon not in self.asr.info["eot_horizons_s"] or not 0.2 <= threshold <= 0.95:
                return "invalid paragraph options"
        except (TypeError, ValueError, AttributeError):
            return "invalid paragraph options"
        with self.lock:
            self.paragraph_options = dict(enabled=enabled, horizon=horizon, threshold=threshold)
            if self.paragraph_tracker:
                self.paragraph_tracker.configure(**self.paragraph_options)
        self.broadcast({"type": "paragraph_options", **self.paragraph_options})
        return None

    def snapshot(self):
        with self.lock:
            result = self.translations.snapshot()
            if self.worker_sid == self.sid and result["sid"] == self.sid and self.paragraph_tracker:
                result["paragraphs"] = self.paragraph_tracker.snapshot()
            else:
                result.update(sid=self.sid, segments=[], paragraphs=[], pending=0,
                              target=self.target)
            return result

    def set_translation_enabled(self, enabled):
        with self.lock:
            try:
                self.translations.set_enabled(enabled)
            except (ValueError, RuntimeError) as error:
                return str(error)
        return None

    def set_target(self, target):
        try:
            target = target_for(self.lang, target)
        except ValueError as error:
            return str(error)
        with self.lock:
            if self.state in ("running", "reset", "reload") or self.translations.snapshot()["pending"]:
                return "Stop and wait for translation to finish before changing languages"
            if self.target == target:
                return None
            self.target = target
            self.sid += 1
            self.state = "idle"
            self.translations.begin(self.sid, self.lang, target)
        self.broadcast(self.info())
        return None

    def set_video_language(self, video, language):
        path = media_path(video)
        if path is None or language not in SOURCE_LANGUAGES:
            return "Unknown video or unsupported source language"
        with self.lock:
            if self.state in ("running", "reset", "reload") or self.translations.snapshot()["pending"]:
                return "Stop and wait for translation to finish before changing languages"
            try:
                with open(meta_of(path)) as f:
                    metadata = json.load(f)
            except (OSError, ValueError):
                metadata = {}
            metadata["lang"] = language
            temp = meta_of(path)+".tmp"
            with open(temp, "w") as f:
                json.dump(metadata, f)
            os.replace(temp, meta_of(path))
        return None

    def configure(self, clock, lang):
        if clock not in CLOCKS or lang not in LANGS:
            return "bad audio clock / language"
        with self.lock:
            if self.state == "reload":
                return "engine is loading"
        error = self.package.error(clock)             # verify before scheduling a reload or releasing the old engine
        with self.lock:
            if error:
                self.clock_errors[clock] = error
                self.clocks = [c for c in self.clocks if c != clock]
            else:
                self.clock_errors.pop(clock, None)
                self.clocks = [c for c in CLOCKS if c in self.clocks or c == clock]
        if error:
            return f"the {clock} ms model package is unavailable: {error}"
        with self.lock:
            if self.state == "reload":
                return "engine is loading"
            if (clock, lang) == (self.clock, self.lang):
                return None
            self.sid += 1
            self.translations.cancel()
            self.pending, self.state = (clock, lang), "reload"
        self.broadcast({"type": "translation_reset", "sid": self.sid, "target": self.target})
        self.broadcast({"type": "loading", "on": True, "clock_ms": clock, "lang": lang})
        return None

    def upload(self, name, rfile, length, lang="zh"):
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(name)).strip("._") or "video.mp4"
        stem, ext = os.path.splitext(base)
        if ext.lower() not in VIDEO_EXT:
            return None, f"unsupported file type {ext or '(none)'}; use {', '.join(VIDEO_EXT)}"
        os.makedirs(UPLOADS, exist_ok=True)
        dst, k = f"{UPLOADS}/{stem}{ext}", 1
        while os.path.exists(dst):
            dst, k = f"{UPLOADS}/{stem}-{k}{ext}", k + 1
        tmp = dst + ".part"
        left = length
        with open(tmp, "wb") as f:
            while left > 0:
                chunk = rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left:
            os.remove(tmp)
            return None, "upload interrupted"
        os.replace(tmp, dst)
        if not has_audio(dst):
            os.remove(dst)
            return None, "no audio track"
        json.dump({"lang": lang if lang in LANGS else "zh"}, open(meta_of(dst), "w"))
        return {"id": os.path.relpath(dst, MEDIA), "duration_s": duration_s(dst)}, None

    def delete(self, vid):
        p = media_path(vid)
        if p is None or not p.startswith(os.path.normpath(UPLOADS) + os.sep):
            return "only uploaded videos can be deleted"
        if self.video == vid:
            self.stop()
        for f in (p, meta_of(p)):
            if os.path.exists(f):
                os.remove(f)
        self.durs.pop(p, None)
        return None

    # ------------------------------------------------------------ engine (worker thread only)
    def worker(self):
        while not self.stopping.is_set():
            try:
                self.work()
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                with self.lock:
                    self.sid += 1
                    self.state = "idle"
                    self.translations.cancel()
                self.broadcast({"type": "state", "state": "idle", "error": f"{type(e).__name__}: {e}"})

    def work(self):
        # pend = gated samples not yet fed; fed = samples fed to the engine in this run. The audio arrives from the page in
        # 100 ms chunks (self.audio) while the video plays.
        dec, fed, pend, steps, t_start, first_char = None, 0, np.zeros(0, np.float32), [], 0.0, None
        flushed, warned = False, False
        while not self.stopping.is_set():
            with self.lock:
                state, sid, ended = self.state, self.sid, self.ended
                chunks = []
                if state == "running":
                    while self.audio:
                        c = self.audio.popleft()
                        if c[0] == sid:
                            chunks.append(c[1])
            if state == "reload":
                self.reload()
                continue
            asr = self.asr
            if state == "reset":
                asr.reset(); self.policy.reset(); self.gate.reset(); self.n_gen = 0
                self.worker_sid = sid
                self.segmenter = Segmenter(self.lang, asr.info["num_delay_tokens"])
                self.paragraph_tracker = ParagraphTracker(asr.info["num_delay_tokens"], **self.paragraph_options)
                self.translation_paragraph = None
                with self.lock:
                    off_s, jump = self.offset_s, self.jump
                self.off_s = off_s
                dec, fed, pend, steps, t_start, first_char = (codecs.getincrementaldecoder("utf-8")(errors="replace"), 0,
                                                              np.zeros(0, np.float32), [], time.time(), None)
                flushed, warned = False, False
                with self.lock:
                    if self.sid == sid and self.state == "reset":
                        self.state = "running"
                self.broadcast({"type": "reset", "sid": sid, "offset_s": round(off_s, 2), "jump": jump})
                self.broadcast({"type": "state", "state": "running"})
                continue
            if state != "running":
                time.sleep(0.02)
                continue
            for block in chunks:                          # page audio -> VAD gate (output lags by the gate look-ahead)
                pend = np.concatenate([pend, self.gate.process(block)])
            if not warned and pend.size > BACKLOG_WARN_S * self.fs:   # audio is kept (never drop speech), only reported
                print(f"[demo] the engine is {pend.size / self.fs:.0f} s behind the video (NPU busy?)", flush=True)
                warned = True
            if ended and not flushed and not chunks:      # end of the video: release the gate's look-ahead
                pend = np.concatenate([pend, self.gate.flush()]); flushed = True
            done, reason = False, None
            if not asr.info["roll_s"] and asr.stats()["lm_pos"] >= MAX_POS - STOP_MARGIN:
                done, reason = True, "limit"
            elif pend.size:                               # at most one token of audio per call so the guard above holds
                t = time.time()
                chunk, pend = pend[:self.spt], pend[self.spt:]
                toks = self.policy.check(*self.gate.segment())    # soft-reset trigger (business layer) before the next row
                new = asr.feed(chunk)
                self.policy.observe(new)
                toks += new
                fed += chunk.size
                if toks:
                    steps.append((time.time() - t) / len(toks))
                if first_char is None and any(asr.token_bytes(k.id) for k in toks):
                    first_char = time.time() - t_start
                self.emit(toks, dec, fed, steps, first_char, eot=self.eot(toks))
                continue
            elif ended and flushed:
                done, reason = True, "end"
            if done:
                toks = asr.finish()
                self.policy.observe(toks)
                self.emit(toks, dec, fed, steps, first_char, final=True, eot=self.eot(toks))
                with self.lock:
                    if self.sid == sid:
                        self.state = "done"
                if self.sid == sid:
                    self.broadcast({"type": "state", "sid": sid, "state": "done", "reason": reason, "audio_s": round(self.off_s + fed / self.fs, 2)})
                continue
            time.sleep(0.01)

    def reload(self):
        clock, lang = self.pending
        old = (self.clock, self.lang)
        err = None
        self.close_engine()
        for c, l in ((clock, lang), old):                # fall back to the previous config if the new one fails
            try:
                self.clock, self.lang = c, l              # audio clock / language are chosen at engine creation
                self.load_engine()
                break
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {e}"
                print(f"[demo] engine load {c} ms/{l} failed: {err}", flush=True)
        with self.lock:
            if self.target == self.lang:
                self.target = target_for(self.lang)
            self.pending, self.video, self.state = None, None, "idle"
            self.translations.begin(self.sid, self.lang, self.target)
        print(f"[demo] engine reloaded in {self.init_s:.1f}s, {self.clock} ms clock, lang {self.lang}", flush=True)
        self.broadcast(self.info())
        self.broadcast({"type": "loading", "on": False, "error": err})

    def close(self):
        self.stopping.set()
        self.worker_thread.join(15)
        self.translations.close()
        if not self.worker_thread.is_alive():
            self.close_engine()

    @staticmethod
    def eot(toks):
        """P(class 0 = no speech within each horizon) after the newest token (semantic VAD, computed by the SDK)."""
        return [round(float(v), 3) for v in toks[-1].eot] if toks else None

    def emit(self, toks, dec, fed, steps, first_char, final=False, eot=None):
        a = self.asr
        if self.worker_sid != self.sid:
            return
        previous_count = self.n_gen
        self.n_gen += len(toks)
        pieces = []
        display_parts, translation_jobs = [], []
        horizons = a.info["eot_horizons_s"]
        horizon = min(range(len(horizons)), key=lambda i: abs(horizons[i]-1.0))
        paragraph_horizon = min(range(len(horizons)), key=lambda i: abs(horizons[i]-self.paragraph_options["horizon"]))
        # VAD is sampled on incoming audio. Ignore its pause indication when it
        # is ahead of the ASR worker, rather than committing unfinished text.
        aligned = abs(self.gate.n_in*512/16000-fed/self.fs) < 0.4
        silence = self.gate.silence_run*512/16000 if aligned and not self.gate.speech_on else 0.0
        def collect(segments):
            translation_jobs.extend((segment, self.translation_paragraph) for segment in segments)

        def accept(raw, audio_time, probability, count, paragraph_probability):
            timestamp = self.off_s+max(0.0, audio_time-self.clock_ms*a.info["num_delay_tokens"]/1000)
            with self.lock:
                parts = self.paragraph_tracker.push(raw, count, paragraph_probability,
                                                    len(self.policy.resets), timestamp)
            display_parts.extend(parts)
            for part in parts:
                if self.translation_paragraph != part["id"]:
                    # Close the internal job at the same boundary as the original
                    # transcript. No translated job can straddle two paragraphs.
                    collect(self.segmenter.finish())
                    self.translation_paragraph = part["id"]
                collect(self.segmenter.push(part["piece"], audio_time, probability, silence))
            if not parts:
                collect(self.segmenter.push("", audio_time, probability, silence))

        for index, k in enumerate(toks):
            part = dec.decode(a.token_bytes(k.id))
            pieces.append(part)
            accept(part, float(k.audio_t), float(k.eot[horizon]), previous_count+index+1,
                   float(k.eot[paragraph_horizon]))
        piece = "".join(pieces)
        collect(self.segmenter.tick(fed/self.fs, silence))
        if final:
            tail = dec.decode(b"", final=True)
            piece += tail
            if tail:
                accept(tail, fed/self.fs, 0.0, self.n_gen, None)
            collect(self.segmenter.finish())
        ms = 1000 * np.array(steps[-200:]) if steps else np.zeros(1)
        # video time of the first text token of this piece (its row time minus the model delay), for paragraph timestamps
        t_first = None
        for k in toks:
            if a.token_bytes(k.id).strip():
                t_first = round(self.off_s + max(0.0, k.audio_t - self.clock_ms * a.info["num_delay_tokens"] / 1000), 2); break
        self.broadcast({"type": "text", "sid": self.worker_sid, "piece": piece, "parts": display_parts, "audio_s": round(self.off_s + fed / self.fs, 2), "t_first": t_first, "tokens": self.n_gen,
                        "lm_pos": a.stats()["lm_pos"], "step_ms": round(float(ms[-1]), 1), "step_ms_median": round(float(np.median(ms)), 1),
                        "rtf": round(float(ms[-1]) / self.clock_ms, 3), "rtf_median": round(float(np.median(ms)) / self.clock_ms, 3),
                        "first_char_s": None if first_char is None else round(first_char, 2), "eot": eot, "resets": len(self.policy.resets), **self.gate.stats()})
        for segment, paragraph_id in translation_jobs:
            self.translations.submit(self.worker_sid, segment, paragraph_id)


S = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self._file(f"{STATIC}/index.html", "text/html; charset=utf-8")
        if p in ("/pandora-mark.svg", "/favicon.ico"):
            return self._file(f"{STATIC}/pandora-mark.svg", "image/svg+xml")
        if p == "/logo.png":
            return self._file(f"{STATIC}/logo.png", "image/png")
        if p == "/pcm-worklet.js":
            return self._file(f"{STATIC}/pcm-worklet.js", "text/javascript; charset=utf-8")
        if p in ("/translation.js", "/views.js"):
            return self._file(f"{STATIC}{p}", "text/javascript; charset=utf-8")
        if p == "/api/videos":
            return self._json({"videos": S.videos(), **S.info()})
        if p == "/api/events":
            return self._events()
        if p.startswith("/media/"):
            f = media_path(urllib.parse.unquote(p[len("/media/"):]))
            if f and f.lower().endswith(VIDEO_EXT):
                ext = os.path.splitext(f)[1].lower()
                return self._file(f, {".webm": "video/webm", ".mkv": "video/x-matroska", ".mov": "video/quicktime"}.get(ext, "video/mp4"))
        self.send_error(404)

    def do_PUT(self):
        p, q = self.path.split("?")[0], urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if p == "/api/upload":
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0:
                return self._json({"error": "empty upload"}, 400)
            res, err = S.upload(q.get("name", ["video.mp4"])[0], self.rfile, n, q.get("lang", ["zh"])[0])
            return self._json(res if err is None else {"error": err}, 200 if err is None else 400)
        self.send_error(404)

    def do_POST(self):
        p = self.path.split("?")[0]
        if p == "/api/audio":                           # raw PCM16 body, ?sid=<run>
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            n = int(self.headers.get("Content-Length") or 0)
            data = self.rfile.read(n) if n > 0 else b""
            try:
                sid = int(q.get("sid", ["-1"])[0])
            except ValueError:
                sid = -1
            if data and len(data) % 2 == 0:
                S.push_audio(sid, data)
            return self._json({})
        b = self._body()
        if p == "/api/start":
            if "paragraph_options" in b:
                error = S.set_paragraphs(b["paragraph_options"])
                if error:
                    return self._json({"error": error}, 400)
            sid, err = S.start(b.get("video", ""), b.get("offset_s", 0.0), b.get("jump", False), b.get("target"), b.get("translation_enabled"))
            return self._json({"sid": sid} if err is None else {"error": err}, 200 if err is None else 409)
        if p == "/api/end":
            S.end(b.get("sid"))
            return self._json({})
        if p == "/api/stop":
            S.stop()
            return self._json({})
        if p == "/api/config":
            err = S.configure(str(b.get("clock_ms")), str(b.get("lang")))
            return self._json({} if err is None else {"error": err}, 200 if err is None else 409)
        if p == "/api/translation-enabled":
            error = S.set_translation_enabled(b.get("enabled"))
            return self._json({"error": error} if error else {"enabled": S.translations.enabled, "epoch": S.translations.epoch, "active": S.translations.worker_active}, 409 if error else 200)
        if p == "/api/translation-target":
            error = S.set_target(b.get("target"))
            return self._json({"error": error} if error else {}, 409 if error else 200)
        if p == "/api/video-language":
            error = S.set_video_language(b.get("video", ""), b.get("lang"))
            return self._json({"error": error} if error else {}, 409 if error else 200)
        if p == "/api/vad":
            S.set_vad(b)
            return self._json({})
        if p == "/api/paragraphs":
            error = S.set_paragraphs(b)
            return self._json({"error": error} if error else {}, 400 if error else 200)
        if p == "/api/delete":
            err = S.delete(b.get("video", ""))
            return self._json({} if err is None else {"error": err}, 200 if err is None else 400)
        self.send_error(404)

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        q = queue.Queue()
        S.subs.append(q)
        try:
            self.wfile.write(f"data: {json.dumps(S.info())}\n\n".encode())
            self.wfile.write(f"data: {json.dumps(S.snapshot(), ensure_ascii=False)}\n\n".encode())
            if S.state == "reload":
                self.wfile.write(f"data: {json.dumps({'type': 'loading', 'on': True})}\n\n".encode())
            if S.sys_hist:
                h = {"type": "sys_hist", "dram_total_mb": S.dram_total, "pts": list(S.sys_hist)}
                self.wfile.write(f"data: {json.dumps(h)}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    ev = q.get(timeout=10)
                    self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            S.subs.remove(q)

    def _file(self, path, ctype):
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            start = int(a) if a else max(0, size - int(b))
            end = int(b) if a and b else size - 1
            end = min(end, size - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    global S, MODELS, TRANSLATION_MODELS
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--models", default=os.environ.get("LT01_MODELS"),
                    help="package root containing manifest.json; default: discover this demo models directory")
    ap.add_argument("--translation-models", default=os.environ.get("LIVE_TRANSLATE_MODELS"),
                    help="Translation package root containing manifest.json")
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(ROOT, "components/translation/sdk/python"))
    from multilingual_translation import TranslationError
    from model_paths import resolve_packages
    try:
        MODELS, TRANSLATION_MODELS = resolve_packages(a.models, a.translation_models)
    except (LT01Error, TranslationError) as error:
        ap.error(str(error))
    print(f"[demo] model package: {MODELS}", flush=True)
    S = Session()
    print(f"[demo] engine ready in {S.init_s:.1f}s, {S.clock} ms clock, lang {S.lang}; http://0.0.0.0:{a.port}/", flush=True)
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    srv.daemon_threads = True
    def interrupt(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        S.close()


if __name__ == "__main__":
    main()
