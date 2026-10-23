"""Route OS stop requests over a pipe, protecting vendor initialization from EINTR."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

def supervise(script, arguments, return_signal=False):
    """Run a native-free signal owner and request ordinary child cleanup by pipe."""
    requested = 0
    def stop(signum, _frame):
        nonlocal requested
        if not requested:
            requested = signum
    previous = {s:signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM)}
    read_fd, write_fd = os.pipe()
    environment = dict(os.environ, LIVE_TRANSLATE_STOP_FD=str(read_fd))
    child = None
    sent = False
    try:
        child = subprocess.Popen([sys.executable, '-u', str(script), *arguments],
                                 env=environment, pass_fds=(read_fd,))
        os.close(read_fd)
        read_fd = None
        while child.poll() is None:
            if requested and not sent:
                try:
                    os.write(write_fd, b'S')
                except BrokenPipeError:
                    pass  # The child has already retired its stop reader.
                sent = True
            time.sleep(.05)
        return 128 + requested if return_signal and requested and child.returncode == 0 else child.returncode
    finally:
        if read_fd is not None:
            os.close(read_fd)
        os.close(write_fd)
        if child is not None and child.poll() is None:
            # EOF requests normal cleanup even when the supervisor has an error.
            child.wait()
        for number, handler in previous.items():
            signal.signal(number, handler)

def main():
    return supervise(Path(__file__).with_name('demo_server.py'), sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
