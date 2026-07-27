"""Typed playback settings shared by the CLI and player."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

StyleName = Literal["default", "block"]
CharsetName = Literal["default", "dense", "block"]


@dataclass(frozen=True, slots=True)
class PlaybackSettings:
    source: Path
    width: int | None = None
    fps: float | None = None
    color: bool = False
    audio: bool = True
    style: StyleName = "default"
    charset: CharsetName = "default"
    # Most terminal cells are approximately twice as tall as they are wide.
    cell_aspect_ratio: float = 0.5

    def __post_init__(self) -> None:
        if self.width is not None and self.width < 1:
            raise ValueError("width must be at least 1")
        if self.fps is not None and self.fps <= 0:
            raise ValueError("fps must be greater than 0")
        if not 0 < self.cell_aspect_ratio <= 1:
            raise ValueError("cell_aspect_ratio must be between 0 and 1")
