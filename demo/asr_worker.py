"""Process boundary for the synchronous Audio8 recording API."""
import multiprocessing as mp
import signal
import time

SAMPLE_RATE = 16_000
CALL_TIMEOUT_S = 120


def serve(channel, model_dir):
    recording = None
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    try:
        import numpy as np
        from asr_recovery import RecoveringStream
        from pandora_audio8_asr_infinite import ASRModel

        with ASRModel.from_pretrained(model_dir, clock_ms=160) as model:
            try:
                channel.send((True, None))
                while True:
                    operation, value = channel.recv()
                    if operation in ("start", "discard", "close", "finish"):
                        result = None
                        if recording is not None:
                            if operation == "finish":
                                result = recording.finish()
                            recording.close()
                            recording = None
                        if operation == "start":
                            recording = RecoveringStream(model, sample_rate=SAMPLE_RATE, language=value)
                        if operation == "close":
                            break
                    else:
                        pcm = np.frombuffer(value, dtype="<i2").astype(np.float32) / 32768.0
                        result = recording.feed(pcm)
                    channel.send((True, result))
            finally:
                if recording is not None:
                    recording.close()
        channel.send((True, None))
    except EOFError:
        return
    except Exception as error:
        channel.send((False, f"{type(error).__name__}: {error}"))
        raise
    finally:
        channel.close()


class ASRWorker:
    def __init__(self, model_dir, stopping):
        ctx = mp.get_context("spawn")
        self.channel, child = ctx.Pipe()
        self.process = ctx.Process(target=serve, args=(child, model_dir), name="audio8-asr")
        self.closed = False
        self.process.start()
        child.close()
        try:
            self.receive(stopping)
        except BaseException:
            self.close(allow_failed_worker=True)
            raise

    def receive(self, stopping=None):
        deadline = time.monotonic() + CALL_TIMEOUT_S
        while not self.channel.poll(0.1):
            if stopping is not None and stopping.is_set():
                raise InterruptedError("Stopped during transcription model initialization")
            if not self.process.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Transcription worker stopped or timed out")
        try:
            success, result = self.channel.recv()
        except EOFError as error:
            raise RuntimeError("Transcription worker channel closed") from error
        if not success:
            raise RuntimeError(result)
        return result

    def call(self, operation, value=None):
        self.channel.send((operation, value))
        return self.receive()

    def close(self, *, allow_failed_worker=False):
        if self.closed:
            return
        self.closed = True
        try:
            if self.process.is_alive():
                self.channel.send(("close", None))
                # An interrupted startup or timed-out call can leave a reply pending.
                # Drain it so the worker can finish cleanup and exit.
                deadline = time.monotonic() + CALL_TIMEOUT_S
                while self.process.is_alive() and time.monotonic() < deadline:
                    if self.channel.poll(0.1):
                        try:
                            self.channel.recv()
                        except EOFError:
                            break
        except (BrokenPipeError, OSError):
            pass
        finally:
            self.channel.close()
            self.process.join(1)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
                raise RuntimeError("Transcription worker cleanup timed out")
            exitcode = self.process.exitcode
            self.process.close()
            if exitcode and not allow_failed_worker:
                raise RuntimeError(f"Transcription worker closed with exit status {exitcode}")
