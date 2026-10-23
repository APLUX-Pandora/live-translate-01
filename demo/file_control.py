"""Deferred stop requests for the finite-file application, without native calls."""
import os
import select
import signal
import threading


class FileStopped(Exception):
    pass


class FileControl:
    def __init__(self):
        self.event = threading.Event()
        self.done = threading.Event()
        self.fd = int(os.environ['LIVE_TRANSLATE_STOP_FD'])
        self.previous = {s: signal.signal(s, signal.SIG_IGN)
                         for s in (signal.SIGTERM, signal.SIGINT)}
        self.receiver = threading.Thread(target=self._receive, name='file-stop-pipe')
        self.receiver.start()

    def _receive(self):
        while not self.done.is_set():
            ready, _, _ = select.select([self.fd], [], [], .2)
            if ready and os.read(self.fd, 1) in (b'S', b''):
                self.event.set()
                return

    def check(self):
        if self.event.is_set():
            raise FileStopped()

    def wait(self, seconds):
        self.event.wait(max(0, seconds))
        self.check()

    def close(self):
        self.done.set()
        self.receiver.join()
        os.close(self.fd)
        for signum, handler in self.previous.items():
            signal.signal(signum, handler)
