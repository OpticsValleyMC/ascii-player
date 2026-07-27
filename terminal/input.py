"""Non-blocking single-key terminal input for Windows and POSIX."""

import os
import sys
from enum import Enum, auto
from types import TracebackType

if os.name == "nt":
    import msvcrt
else:
    import select
    import termios
    import tty


class Action(Enum):
    TOGGLE_PAUSE = auto()
    REPLAY = auto()
    FASTER = auto()
    SLOWER = auto()
    QUIT = auto()


_KEYS = {
    " ": Action.TOGGLE_PAUSE,
    "r": Action.REPLAY,
    "R": Action.REPLAY,
    "+": Action.FASTER,
    "=": Action.FASTER,
    "-": Action.SLOWER,
    "_": Action.SLOWER,
    "q": Action.QUIT,
    "Q": Action.QUIT,
}


class TerminalInput:
    """Put POSIX terminals in cbreak mode and poll keys without blocking."""

    def __init__(self) -> None:
        self._old_attributes: list[object] | None = None
        self._interactive = True

    def __enter__(self) -> "TerminalInput":
        self._interactive = sys.stdin.isatty()
        if os.name != "nt" and self._interactive:
            self._old_attributes = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        return self

    @property
    def interactive(self) -> bool:
        return self._interactive

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if os.name != "nt" and self._old_attributes is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_attributes)

    def poll(self) -> Action | None:
        if not self._interactive:
            return None
        if os.name == "nt":
            if not msvcrt.kbhit():
                return None
            key = msvcrt.getwch()
            if key in {"\x00", "\xe0"} and msvcrt.kbhit():
                msvcrt.getwch()
                return None
        else:
            readable, _, _ = select.select([sys.stdin], [], [], 0)
            if not readable:
                return None
            key = sys.stdin.read(1)
        return _KEYS.get(key)
