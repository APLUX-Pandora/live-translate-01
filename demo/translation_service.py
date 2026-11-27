"""Session-scoped translation tasks through the delivered Python SDK."""
import json
import multiprocessing as mp
import queue
import signal
import threading
import time
from dataclasses import asdict

from languages import LANGUAGES, target_for
from translation_input import translation_input

MAX_PENDING = 32
WAITING = ("queued", "started", "chunk", "paused")
TERMINAL = ("done", "length", "cancelled", "error")

CHINESE_NAMES = {"en": "英语", "zh": "中文", "ja": "日语", "ko": "韩语",
                 "fr": "法语", "de": "德语", "es": "西班牙语", "ar": "阿拉伯语", "th": "泰语"}


def message_for(task):
    target = target_for(task["source"], task["target"])
    if "zh" in (task["source"], target):
        prompt = f"将以下文本翻译为{CHINESE_NAMES[target]}，注意只需要输出翻译后的结果，不要额外解释："
    else:
        prompt = (f"Translate the following text into {LANGUAGES[target]}. "
                  "Note that you should only output the translated result without any additional explanation:")
    return [{"role": "user", "content": f"{prompt}\n\n{task['text']}"}]


def _worker(commands, events, epoch, model_dir):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)

    def send(kind, task, **values):
        events.put(dict(kind=kind, sid=task["sid"], epoch=task["epoch"], id=task["id"], **values))

    try:
        from pandora_hy_mt2_1_8b import InferenceError, LanguageModel

        with LanguageModel.from_pretrained(model_dir) as engine:
            events.put({"kind": "ready"})
            while True:
                task = commands.get()
                if task["kind"] == "close":
                    break
                if task["epoch"] != epoch.value:
                    events.put({"kind": "available"})
                    continue
                start = time.monotonic()
                first = None
                send("started", task, queue_ms=1000 * (start-task["submitted"]))
                try:
                    with engine.generate_stream(message_for(task)) as stream:
                        for update in stream:
                            if task["epoch"] != epoch.value:
                                break
                            if update.delta:
                                now = time.monotonic()
                                first = first if first is not None else now
                                send("chunk", task, piece=update.delta, elapsed_ms=1000 * (now-start))
                    if task["epoch"] == epoch.value:
                        result = stream.result
                        kind = "done" if result.finish_reason == "stop" else result.finish_reason
                        send(kind, task, text=result.text,
                             first_ms=1000 * (first-task["submitted"]) if first is not None else None,
                             complete_ms=1000 * (time.monotonic()-task["submitted"]))
                except Exception as error:
                    fatal = isinstance(error, InferenceError)
                    send("error", task, error=str(error), reload_required=fatal)
                    if fatal:
                        raise
                finally:
                    events.put({"kind": "available"})
    except Exception as error:
        events.put({"kind": "load_error", "error": f"{type(error).__name__}: {error}"})
        raise
    finally:
        events.put({"kind": "closed"})


class TranslationService:
    def __init__(self, model_dir, broadcast, stop_event=None, replay_limit=256):
        self.broadcast = broadcast
        self.reload_required = threading.Event()
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.sid, self.language, self.target = None, "en", "zh"
        self.records = {}
        self.enabled, self.epoch, self.worker_active = True, 0, False
        self.closed = False
        self.cancelled = False
        self.in_flight = False
        self.stop_event = stop_event
        self.replay_limit = replay_limit
        self.closing = False
        context = mp.get_context("spawn")
        self.commands, self.events = context.Queue(maxsize=2), context.Queue(maxsize=128)
        self.worker_epoch = context.Value("q", 0)
        # CPython3.10-3.12 Queue feeder: a reaped worker may have no reader.
        # Permit an intentional broken pipe when discarding that failed channel.
        self.commands._ignore_epipe = True
        self.process = context.Process(target=_worker, name="hy-translation",
                                       args=(self.commands, self.events, self.worker_epoch, str(model_dir)))
        self.process.start()
        try:
            deadline = time.monotonic()+120
            while True:
                if stop_event is not None and stop_event.is_set():
                    raise InterruptedError('Stopped during translation initialization')
                try:
                    event = self.events.get(timeout=.2)
                    break
                except queue.Empty:
                    if not self.process.is_alive() or time.monotonic()>deadline:
                        raise RuntimeError('Translation worker initialization failed or timed out')
            if event["kind"] != "ready":
                raise RuntimeError(event.get("error", "Translation worker failed to load"))
        except BaseException:
            self.commands.put({'kind':'close'})
            self.process.join(150)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
                print('{"translation_close_failed": "initialization timeout"}', flush=True)
            self._close_queues(discard_commands=self.process.exitcode != 0)
            raise
        self.listener = threading.Thread(target=self._listen)
        self.listener.start()

    def _reset_worker(self):
        self.epoch += 1
        self.worker_epoch.value = self.epoch
        self.worker_active = False
        self.changed.notify_all()

    def begin(self, sid, language, target=None, enabled=None):
        if self.reload_required.is_set():
            raise RuntimeError("Translation model requires reload")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("Translation enabled must be a boolean")
        with self.lock:
            if enabled is not None:
                self.enabled = enabled
            self.sid, self.language, self.records = sid, language, {}
            self.cancelled = False
            self.target = target or ("en" if language == "zh" else "zh")
            self._reset_worker()
            self.broadcast({"type": "translation_reset", "sid": sid, "source": language,
                            "target": self.target, "enabled": self.enabled, "epoch": self.epoch})

    def cancel(self):
        with self.lock:
            self.cancelled = True
            for record in self.records.values():
                if record["status"] in ("queued", "started", "chunk", "paused"):
                    record["status"] = "cancelled"
                    record["revision"] += 1
                    self.broadcast({"type": "translation", "kind": "cancelled", "sid": self.sid,
                                        "id": record["id"], "revision": record["revision"], "pending": 0})
            self._reset_worker()

    def _dispatch(self):
        if self.in_flight or self.cancelled or not self.enabled or self.reload_required.is_set():
            return
        record = next((r for r in self.records.values() if r["status"] in ("queued", "paused")), None)
        if record is None:
            return
        # Resume one paused record at a time, in the original submission order.
        if record["status"] == "paused":
            record.update(status="queued", translation="", revision=record["revision"]+1)
            self.broadcast(dict(type="translation", kind="queued", sid=self.sid,
                                **record, pending=self._pending()))
        self.commands.put_nowait({"kind": "translate", "sid": self.sid, "epoch": self.epoch,
                                      "id": record["id"], "text": record["translation_input"],
                                      "source": self.language, "target": self.target, "submitted": record["submitted"]})
        self.in_flight = True

    def set_enabled(self, enabled):
        if not isinstance(enabled, bool):
            raise TypeError("Translation enabled must be a boolean")
        with self.lock:
            if self.enabled == enabled:
                return
            if enabled and not self.process.is_alive():
                raise RuntimeError("Translation worker is unavailable")
            self.enabled = enabled
            self._reset_worker()
            if not enabled:
                for record in self.records.values():
                    if record["status"] in ("queued", "started", "chunk"):
                        record["status"] = "paused"
                        record["revision"] += 1
                        self.broadcast(dict(type="translation", kind="paused", sid=self.sid,
                                            **record, pending=0))
            else:
                self._dispatch()
            self.broadcast({"type": "translation_mode", "sid": self.sid, "enabled": enabled, "epoch": self.epoch,
                                "pending": self._pending()})

    def submit(self, sid, segment, paragraph_id=1):
        with self.lock:
            while sid == self.sid and not self.cancelled and not self.closed and not self.reload_required.is_set():
                if self.stop_event is not None and self.stop_event.is_set():
                    return
                if self._pending() < MAX_PENDING:
                    break
                self.changed.wait(timeout=.2)
            else:
                return
            status = "queued" if self.enabled else "paused"
            record = dict(asdict(segment), paragraph_id=paragraph_id, source_text=segment.text,
                          translation_input=translation_input(segment.text, self.language),
                          source_language=self.language, target_language=self.target,
                          translation="", status=status, revision=0, submitted=time.monotonic())
            self.records[segment.id] = record
            # File mode collects the full result separately. Web keeps the current session.
            if self.replay_limit is not None and len(self.records) > self.replay_limit:
                oldest = next((key for key, row in self.records.items() if row["status"] in TERMINAL), None)
                if oldest is not None:
                    del self.records[oldest]
            self.broadcast(dict(type="translation", kind=status, sid=sid, **record,
                                pending=self._pending()))
            self._dispatch()

    def _pending(self):
        return sum(r["status"] in WAITING for r in self.records.values()) if self.enabled else 0

    def snapshot(self):
        with self.lock:
            return {"type": "translation_snapshot", "sid": self.sid,
                        "target": self.target, "enabled": self.enabled, "epoch": self.epoch, "active": self.worker_active,
                        "reload_required": self.reload_required.is_set(),
                        "segments": [dict(r) for r in self.records.values()], "pending": self._pending()}

    def _handle_event(self, event):
        with self.lock:
            if event["kind"] == "available":
                self.in_flight = False
                self._dispatch()
                return
            if event.get("reload_required"):
                self.worker_active = False
                self.changed.notify_all()
                self.reload_required.set()
                for record in self.records.values():
                    if record["status"] in ("queued", "started", "chunk", "paused"):
                        record["status"] = "error"
                        record["revision"] += 1
                        self.broadcast({"type": "translation", "kind": "error", "sid": self.sid,
                            "id": record["id"], "revision": record["revision"], "pending": 0,
                            "reload_required": True, "error": "Translation failed; reload models before starting again"})
            if (event.get("sid"), event.get("epoch")) != (self.sid, self.epoch) or not self.enabled or event.get("id") not in self.records:
                return
            record = self.records[event["id"]]
            record["status"] = event["kind"]
            self.worker_active = event["kind"] in ("started", "chunk")
            self.broadcast({"type": "translation_activity", "sid": self.sid, "epoch": self.epoch,
                                "active": self.worker_active, "enabled": self.enabled})
            self.changed.notify_all()
            record["revision"] += 1
            if event["kind"] == "chunk":
                record["translation"] += event["piece"]
            if event["kind"] in ("done", "length", "cancelled"):
                record["translation"] = event.get("text", record["translation"])
            for key in ("error", "first_ms", "complete_ms", "stats"):
                if key in event:
                    record[key] = event[key]
            self.broadcast(dict(type="translation", **event, revision=record["revision"], pending=self._pending()))

    def _listen(self):
        while not self.closed:
            try:
                event = self.events.get(timeout=0.5)
            except queue.Empty:
                if not self.process.is_alive():
                    self.reload_required.set()
                    self.broadcast({"type": "state", "state": "error", "reload_required": True,
                                        "error": "Translation worker stopped; reload models"})
                    with self.lock:
                        self.worker_active = False
                        for row in self.records.values():
                            if row["status"] in WAITING:
                                row["status"] = "error"
                                self.broadcast({"type": "translation", "kind": "error", "sid": self.sid,
                                                    "id": row["id"], "error": "Translation worker stopped", "pending": 0})
                        self.changed.notify_all()
                    return
                continue
            if event["kind"] == "closed":
                if not self.closing:
                    self.reload_required.set()
                    with self.lock:
                        self.changed.notify_all()
                return
            self._handle_event(event)

    def _close_queues(self, *, discard_commands=False):
        if discard_commands:
            # Only after process.join(): no live child can own this endpoint.
            # Close our otherwise-unused reader so a full feeder pipe gets EPIPE
            # and can join. Queue.cancel_join_thread alone leaves blocked feeders.
            self.commands._reader.close()
        for channel in (self.commands, self.events):
            channel.close()
            channel.join_thread()

    def close(self, *, allow_failed_worker=False):
        if self.closed:
            return
        if self.closing:
            raise RuntimeError('Translation cleanup is already in progress')
        self.closing = True
        forced = False
        if self.process.is_alive():
            self.cancel()
            self.commands.put({"kind": "close"})
            self.process.join(150)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
                forced = True
        else:
            self.process.join()
        self.closed = True
        self.listener.join(2)
        failed = self.process.exitcode != 0
        self._close_queues(discard_commands=failed)
        if forced:
            raise RuntimeError('Translation close timed out; forced termination is not a passing cleanup')
        if self.listener.is_alive():
            raise RuntimeError('Translation listener did not close cleanly')
        if failed:
            print(json.dumps({"translation_worker_failed": True,
                              "exitcode": self.process.exitcode,
                              "failed_worker_reaped": True}), flush=True)
            if not allow_failed_worker:
                raise RuntimeError('Translation worker did not close cleanly')
