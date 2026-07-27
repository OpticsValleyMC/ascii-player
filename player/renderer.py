"""Flicker-free terminal frame rendering using Rich Live."""

from types import TracebackType

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.text import Text

from ascii.converter import ConvertedFrame


class TerminalRenderer:
    def __init__(self, console: Console) -> None:
        self.console = console
        self._live: Live | None = None
        self._layout = Layout()
        self._layout.split_column(
            Layout(name="header", size=1),
            Layout(name="video", ratio=1),
            Layout(name="footer", size=2),
        )
        self._layout["header"].update(
            Text("OpticsValley ASCII Player", style="bold bright_cyan")
        )

    def __enter__(self) -> "TerminalRenderer":
        # screen=True uses the alternate screen and restores terminal contents on exit.
        self._live = Live(
            self._layout,
            console=self.console,
            screen=True,
            auto_refresh=False,
            transient=True,
        )
        self._live.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._live is not None:
            self._live.__exit__(exc_type, exc_value, traceback)
        self._live = None

    @property
    def available_size(self) -> tuple[int, int]:
        return max(1, self.console.width), max(1, self.console.height - 3)

    def render(
        self,
        frame: ConvertedFrame,
        *,
        position: float,
        duration: float | None,
        speed: float,
        paused: bool,
        audio: bool,
    ) -> None:
        if self._live is None:
            raise RuntimeError("TerminalRenderer must be used as a context manager")
        # Parsing ANSI into a Rich Text object keeps Live in control of cursor movement.
        text = Text.from_ansi(frame.ansi)
        text.no_wrap = True
        text.overflow = "crop"
        self._layout["video"].update(text)
        self._layout["footer"].update(
            Group(
                Text(
                    self._progress_line(position, duration, speed, paused, audio),
                    style="bright_white",
                    no_wrap=True,
                    overflow="crop",
                ),
                Text(
                    "[SPACE] Play/Pause   [R] Replay   [-/+] Speed   [Q] Quit",
                    style="bold bright_cyan",
                    no_wrap=True,
                    overflow="crop",
                ),
            )
        )
        self._live.update(self._layout, refresh=True)

    def render_status(
        self,
        frame: ConvertedFrame,
        *,
        position: float,
        duration: float | None,
        speed: float,
        paused: bool,
        audio: bool,
    ) -> None:
        self.render(
            frame,
            position=position,
            duration=duration,
            speed=speed,
            paused=paused,
            audio=audio,
        )

    def _progress_line(
        self,
        position: float,
        duration: float | None,
        speed: float,
        paused: bool,
        audio: bool,
    ) -> str:
        suffix = (
            f" {self._format_time(position)}/{self._format_time(duration)}"
            f"  SPEED:{speed:.2f}x  {'PAUSED' if paused else 'PLAYING'}"
            f"  AUDIO:{'ON' if audio else 'OFF'}"
        )
        bar_width = max(5, self.console.width - len(suffix) - 2)
        ratio = min(1.0, position / duration) if duration and duration > 0 else 0.0
        complete = min(bar_width, round(bar_width * ratio))
        return f"[{'=' * complete}{' ' * (bar_width - complete)}]{suffix}"

    @staticmethod
    def _format_time(seconds: float | None) -> str:
        if seconds is None:
            return "--:--"
        value = max(0, int(seconds))
        hours, remainder = divmod(value, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
