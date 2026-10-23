"""Route OS stop requests over a pipe, protecting vendor initialization from EINTR."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

def main():
    requested = False
    def stop(*_):
        nonlocal requested
        requested = True
    previous = {s:signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM)}
    read_fd, write_fd = os.pipe()
    environment = dict(os.environ, LIVE_TRANSLATE_STOP_FD=str(read_fd))
    child = None
    sent = False
    try:
        child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).with_name('demo_server.py')), *sys.argv[1:]],
                                 env=environment, pass_fds=(read_fd,))
        os.close(read_fd)
        read_fd = None
        while child.poll() is None:
            if requested and not sent:
                os.write(write_fd, b'S')
                sent = True
            time.sleep(.05)
        return child.returncode
    finally:
        if read_fd is not None:
            os.close(read_fd)
        os.close(write_fd)
        if child is not None and child.poll() is None:
            # EOF requests normal cleanup even when the supervisor has an error.
            child.wait()
        for number, handler in previous.items():
            signal.signal(number, handler)

if __name__ == '__main__':
    raise SystemExit(main())
