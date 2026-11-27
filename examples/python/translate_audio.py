#!/usr/bin/env python3
"""Transcribe a local audio file and stream translations of confirmed phrases."""
import argparse
import json
import math
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))


def main(control):
    import soundfile as sf
    from file_results import FileResults
    from languages import LANGUAGES, SOURCE_LANGUAGES, target_for
    from pandora_audio8_asr_infinite import ASRModel
    from segmentation import Segmenter
    from translation_service import TranslationService

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, nargs="?", default=ROOT/"components/asr/examples/audio/speech.wav")
    parser.add_argument("--source", choices=SOURCE_LANGUAGES, default="en")
    parser.add_argument("--target", choices=LANGUAGES)
    parser.add_argument("--models", type=Path, default=ROOT/"models/asr")
    parser.add_argument("--translation-models", type=Path, default=ROOT/"models/translation")
    parser.add_argument("--seconds", type=float, help="Read only the initial seconds of the audio")
    parser.add_argument("--realtime", action="store_true", help="Pace audio at its original speed")
    args = parser.parse_args()
    try:
        target = target_for(args.source, args.target)
        if args.seconds is not None and (not math.isfinite(args.seconds) or args.seconds <= 0):
            raise ValueError("--seconds must be finite and positive")
    except ValueError as error:
        parser.error(str(error))

    results = FileResults()
    output_lock = threading.Lock()

    def emit(event):
        results.accept(event)
        with output_lock:
            print(json.dumps(event, ensure_ascii=False), flush=True)

    control.check()
    with sf.SoundFile(args.audio) as audio, ASRModel.from_pretrained(args.models, clock_ms=160) as model:
        service = TranslationService(args.translation_models, emit, stop_event=control.event)
        try:
            service.begin(1, args.source, target)
            phrases = Segmenter(args.source, 0)
            text = ""
            frames = 0
            reason = None
            rate = audio.samplerate
            block_size = max(1, round(rate * .16))
            end = len(audio)
            if args.seconds is not None and args.seconds < end / rate:
                end = min(end, round(rate * args.seconds))
            if end <= 0:
                raise ValueError("Input contains no audio")
            start = time.monotonic()

            def accept(snapshot):
                nonlocal text
                if not snapshot.startswith(text):
                    raise RuntimeError("The ASR result changed previously emitted text")
                delta, text = snapshot[len(text):], snapshot
                if delta:
                    emit({"type": "source", "piece": delta})
                for segment in phrases.push(delta, frames/rate):
                    service.submit(1, segment)

            with model.create_stream(sample_rate=rate, language=args.source) as recording:
                while frames < end:
                    control.check()
                    samples = audio.read(min(block_size, end-frames), dtype="float32", always_2d=True).mean(axis=1)
                    frames += len(samples)
                    if args.realtime:
                        control.wait(start + frames/rate - time.monotonic())
                    update = recording.feed(samples)
                    accept(update.text)
                    if update.is_final:
                        break
                control.check()
                final = recording.finish()
                accept(final.text)
                reason = final.finish_reason
            for segment in phrases.finish():
                service.submit(1, segment)
            deadline = time.monotonic() + 300
            while service.snapshot()["pending"]:
                control.check()
                if service.reload_required.is_set() or time.monotonic() >= deadline:
                    raise RuntimeError("Translation did not finish")
                control.wait(.05)
            control.check()
            rows = results.snapshot()
            if service.reload_required.is_set() or any(row["status"] != "done" for row in rows):
                raise RuntimeError("Translation is incomplete; inspect the translation events")
            if text.strip() != "".join(row["source_text"] for row in rows).strip():
                raise RuntimeError("Source text was lost or duplicated")
            emit({"type": "complete", "source_text": text, "translations": rows, "finish_reason": reason})
            if reason != "stop":
                return 1
        finally:
            service.close()


def entrypoint():
    if "LIVE_TRANSLATE_STOP_FD" not in os.environ:
        from launch import supervise
        return supervise(Path(__file__), sys.argv[1:], return_signal=True)
    from file_control import FileControl, FileStopped

    control = FileControl()
    try:
        return main(control)
    except (FileStopped, InterruptedError):
        if not control.event.is_set():
            raise
        print(json.dumps({"file_stopped": True}), flush=True)
        return 0
    finally:
        control.close()


if __name__ == "__main__":
    raise SystemExit(entrypoint())
