"""Session-scoped translation tasks through the delivered Python SDK."""
from collections import deque
from dataclasses import asdict
import multiprocessing as mp
import signal
from pathlib import Path
import queue
import sys
import threading
import time
from translation_input import translation_input
from languages import LANGUAGES, target_for


def _worker(commands, events, model_dir, sdk_dir, library=None):
    sys.path.insert(0, sdk_dir)
    from hy_mt2 import LLMModel
    try:
        engine = LLMModel.from_pretrained(model_dir, library=library, max_input_tokens=512)
    except Exception as exc:
        events.put({"kind": "load_error", "error": str(exc)})
        return
    condition = threading.Condition()
    pending = deque()
    state = {"sid": None, "epoch": 0, "current": None, "closing": False}

    def send(kind, task, **values):
        events.put(dict(kind=kind, sid=task["sid"], epoch=task["epoch"], id=task["id"], **values))

    def generate():
        while True:
            with condition:
                condition.wait_for(lambda: state["closing"] or pending)
                if state["closing"]:
                    return
                task = pending.popleft()
                if (task["sid"], task["epoch"]) != (state["sid"], state["epoch"]):
                    continue
                state["current"] = task
            events.put({"kind": "worker_activity", "active": True})
            start = time.monotonic()
            send("started", task, queue_ms=1000*(start-task["submitted"]))
            first = []

            def on_chunk(piece):
                if (task["sid"], task["epoch"]) != (state["sid"], state["epoch"]):
                    return
                now = time.monotonic()
                if not first:
                    first.append(now)
                send("chunk", task, piece=piece, elapsed_ms=1000*(now-start))

            try:
                # Translation instructions are application policy, not an LLM API.
                target = target_for(task["source"], task["target"])
                prompt = (f"Translate the following text into {LANGUAGES[target]}. Note that you should only "
                          f"output the translated result without any additional explanation:\n{task['text']}")
                if engine.count_messages([{"role": "user", "content": prompt}]) > 512:
                    raise ValueError("Phrase exceeds the translation input limit; reduce the phrase length")
                if (task["sid"], task["epoch"]) != (state["sid"], state["epoch"]):
                    continue
                with engine.generate_stream(prompt) as stream:
                    for update in stream:
                        if update.delta:
                            on_chunk(update.delta)
                        with condition:
                            obsolete = state["closing"] or (task["sid"], task["epoch"]) != (state["sid"], state["epoch"])
                        if obsolete:
                            break
                result = stream.result
                if result.finish_reason not in ("stop", "cancelled"):
                    raise RuntimeError(f"Incomplete translation: {result.finish_reason}")
                end = time.monotonic()
                send("cancelled" if result.finish_reason == "cancelled" else "done", task, text=result.text,
                     first_ms=1000*(first[0]-task["submitted"]) if first else None,
                     complete_ms=1000*(end-task["submitted"]), stats=engine.stats)
            except Exception as exc:
                send("error", task, error=str(exc))
            finally:
                with condition:
                    state["current"] = None
                    events.put({"kind": "worker_activity", "active": False})
                    condition.notify_all()

    def cancel_obsolete():
        # Retry across the SDK start/generate transition. A completed old job must
        # never cause an abort of a subsequent session's job.
        while True:
            with condition:
                current = state["current"]
                if state["closing"] and current is None:
                    return
                if current and (state["closing"] or (current["sid"], current["epoch"]) != (state["sid"], state["epoch"])):
                    try:
                        engine.abort()
                    except Exception:
                        pass
            time.sleep(0.01)

    generator = threading.Thread(target=generate)
    canceller = threading.Thread(target=cancel_obsolete, daemon=True)
    generator.start()
    canceller.start()
    events.put({"kind": "ready", "info": engine.info})
    try:
        while True:
            message = commands.get()
            with condition:
                if message["kind"] in ("reset", "close"):
                    state["sid"] = message.get("sid")
                    state["epoch"] = message.get("epoch", state["epoch"]+1)
                    pending.clear()
                elif message["kind"] == "translate" and (message["sid"], message["epoch"]) == (state["sid"], state["epoch"]):
                    pending.append(message)
                if message["kind"] == "close":
                    state["closing"] = True
                    condition.notify_all()
                    break
                condition.notify_all()
    finally:
        with condition:
            state['closing'] = True
            pending.clear()
            condition.notify_all()
        generator.join()
        canceller.join()
        engine.close()
        print('{"translation_engine_closed": true}', flush=True)
        events.put({'kind': 'closed'})


class TranslationService:
    def __init__(self, model_dir, sdk_dir, broadcast, library=None, stop_event=None):
        self.broadcast = broadcast
        self.lock = threading.RLock()
        self.sid, self.language, self.target = None, "en", "zh"
        self.records = {}
        self.enabled, self.epoch, self.worker_active = True, 0, False
        self.closed = False
        self.closing = False
        context = mp.get_context("spawn")
        self.commands, self.events = context.Queue(maxsize=128), context.Queue(maxsize=512)
        self.process = context.Process(target=_worker, args=(self.commands, self.events, str(model_dir), str(sdk_dir), str(library) if library else None))
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
            self.info = event.get("info", {})
        except BaseException:
            self.commands.put({'kind':'close'})
            self.process.join(150)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
                print('{"translation_close_failed": "initialization timeout"}', flush=True)
            self._close_queues()
            raise
        self.listener = threading.Thread(target=self._listen)
        self.listener.start()

    def _reset_worker(self):
        self.epoch += 1
        self.commands.put({"kind": "reset", "sid": self.sid, "epoch": self.epoch})

    def begin(self, sid, language, target=None, enabled=None):
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("Translation enabled must be a boolean")
        with self.lock:
            if enabled is not None:
                self.enabled = enabled
            self.sid, self.language, self.records = sid, language, {}
            self.target = target or ("en" if language == "zh" else "zh")
            self._reset_worker()
            self.broadcast({"type": "translation_reset", "sid": sid, "source": language,
                            "target": self.target, "enabled": self.enabled, "epoch": self.epoch})

    def cancel(self):
        with self.lock:
            for record in self.records.values():
                if record["status"] in ("queued", "started", "chunk", "paused"):
                    record["status"] = "cancelled"
                    record["revision"] += 1
                    self.broadcast(dict(type="translation", kind="cancelled", sid=self.sid,
                                        id=record["id"], revision=record["revision"], pending=0))
            self.sid = None
            self._reset_worker()

    def _queue_task(self, record):
        source = translation_input(record['source_text'], self.language)
        record['translation_input'] = source
        self.commands.put(dict(kind="translate", sid=self.sid, epoch=self.epoch,
                               id=record["id"], text=source, source=self.language,
                               target=self.target, submitted=time.monotonic()))

    def set_enabled(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("Translation enabled must be a boolean")
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
                paused = [record for record in self.records.values() if record["status"] == "paused"]
                for record in paused:
                    record.update(status="queued", translation="", revision=record["revision"]+1)
                for record in paused:
                    self.broadcast(dict(type="translation", kind="queued", sid=self.sid,
                                        **record, pending=self._pending()))
                    self._queue_task(record)
            self.broadcast(dict(type="translation_mode", sid=self.sid, enabled=enabled, epoch=self.epoch,
                                pending=self._pending()))

    def submit(self, sid, segment, paragraph_id=1):
        with self.lock:
            if sid != self.sid or self.closed:
                return
            status = "queued" if self.enabled else "paused"
            record = dict(asdict(segment), paragraph_id=paragraph_id, source_text=segment.text,
                          translation_input=translation_input(segment.text, self.language),
                          source_language=self.language, target_language=self.target,
                          translation="", status=status, revision=0)
            self.records[segment.id] = record
            # Keep pending work; expire only completed replay history.
            for key in list(self.records):
                if len(self.records) <= 256:
                    break
                if self.records[key]['status'] in ('done', 'cancelled', 'error'):
                    del self.records[key]
            self.broadcast(dict(type="translation", kind=status, sid=sid, **record,
                                pending=self._pending()))
            if self.enabled:
                self._queue_task(record)

    def _pending(self):
        return sum(r["status"] in ("queued", "started", "chunk") for r in self.records.values())

    def snapshot(self):
        with self.lock:
            return dict(type="translation_snapshot", sid=self.sid,
                        target=self.target, enabled=self.enabled, epoch=self.epoch, active=self.worker_active,
                        segments=[dict(r) for r in self.records.values()], pending=self._pending())

    def _handle_event(self, event):
        with self.lock:
            if event["kind"] == "worker_activity":
                self.worker_active = event["active"]
                self.broadcast(dict(type="translation_activity", sid=self.sid,
                                    active=self.worker_active, enabled=self.enabled))
                return
            if (event.get("sid"), event.get("epoch")) != (self.sid, self.epoch) or not self.enabled or event.get("id") not in self.records:
                return
            record = self.records[event["id"]]
            record["status"] = event["kind"]
            record["revision"] += 1
            if event["kind"] == "chunk":
                record["translation"] += event["piece"]
            if event["kind"] in ("done", "cancelled"):
                record["translation"] = event["text"]
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
                    with self.lock:
                        self.worker_active = False
                        for row in self.records.values():
                            if row["status"] in ("queued", "started", "chunk"):
                                row["status"] = "error"
                                self.broadcast(dict(type="translation", kind="error", sid=self.sid,
                                                    id=row["id"], error="Translation worker stopped", pending=0))
                    return
                continue
            if event['kind'] == 'closed':
                return
            self._handle_event(event)

    def _close_queues(self):
        for channel in (self.commands, self.events):
            channel.close()
            channel.join_thread()

    def close(self):
        if self.closed or self.closing:
            return
        self.closing = True
        self.cancel()
        self.commands.put({"kind": "close"})
        self.process.join(150)
        if self.process.is_alive():
            self.process.kill()
            self.process.join()
            raise RuntimeError('Translation close timed out; forced termination is not a passing cleanup')
        self.closed = True
        self.listener.join(2)
        if self.listener.is_alive() or self.process.exitcode != 0:
            raise RuntimeError('Translation worker/listener did not close cleanly')
        self._close_queues()
