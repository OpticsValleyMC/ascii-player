"""Audio playback through the FFmpeg companion program ffplay."""

import os
import shutil
import subprocess
from pathlib import Path


class AudioPlayer:
    """Manage a disposable ffplay process synchronized to video media time.

    Recreating ffplay on pause, replay, or speed changes is intentionally simple
    and portable. It also leaves video decoding entirely in the main PyAV process.
    """

    def __init__(self, source: Path, *, enabled: bool = True) -> None:
        self.source = source
        self.enabled = enabled
        self.executable = shutil.which("ffplay") if enabled else None
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def available(self) -> bool:
        return self.enabled and self.executable is not None

    def start(self, position: float = 0.0, speed: float = 1.0) -> None:
        self.stop()
        if not self.available:
            return
        command = [
            self.executable or "ffplay",
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "quiet",
            "-ss",
            f"{max(0.0, position):.3f}",
            "-i",
            str(self.source),
            "-vn",
        ]
        if abs(speed - 1.0) > 1e-6:
            command.extend(["-af", f"atempo={speed:.2f}"])

        startup_info = None
        creation_flags = 0
        if os.name == "nt":
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creation_flags = subprocess.CREATE_NO_WINDOW
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startup_info,
                creationflags=creation_flags,
            )
        except OSError:
            self.executable = None
            self._process = None

    def restart(self, position: float, speed: float) -> None:
        self.start(position, speed)

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)

    def __enter__(self) -> "AudioPlayer":
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()

