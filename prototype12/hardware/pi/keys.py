"""keys -- one keypress at a time, with a timeout, over SSH or on Windows.

`with Keys() as k: ch = k.read(0.1)` returns a character, or None if nothing was
pressed in that time. The timeout is what lets a held motion stop by itself.
"""

import sys

try:
    import msvcrt
except ImportError:
    msvcrt = None


class Keys:
    def __enter__(self):
        if msvcrt is None:
            import termios
            import tty
            self._fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        return self

    def __exit__(self, *exc):
        if msvcrt is None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)

    def read(self, timeout):
        if msvcrt is not None:
            import time
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                if msvcrt.kbhit():
                    return msvcrt.getwch()
                time.sleep(0.01)
            return None
        import select
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        return sys.stdin.read(1) if ready else None
