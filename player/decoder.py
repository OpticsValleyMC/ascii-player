"""Streaming video decoder backed by PyAV/FFmpeg."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

import av
import numpy as np


class DecoderError(RuntimeError):
    """Raised when a media source cannot be opened or decoded."""


@dataclass(frozen=True, slots=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    duration: float | None
    has_audio: bool


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    frame: av.VideoFrame
    timestamp: float

    @property
    def rgb(self) -> np.ndarray:
        """Convert only frames selected for display to a full-resolution RGB array."""
        try:
            return self.frame.to_ndarray(format="rgb24")
        except (av.error.FFmpegError, OSError) as exc:
            raise DecoderError(f"Video frame conversion failed: {exc}") from exc


class VideoDecoder:
    """Decode one video stream at a time without buffering the full file."""

    def __init__(self, source: Path) -> None:
        self.source = source
        self._container: av.container.InputContainer | None = None
        self._stream: av.video.stream.VideoStream | None = None

    def __enter__(self) -> "VideoDecoder":
        try:
            self._container = av.open(str(self.source))
            self._stream = self._container.streams.video[0]
            # AUTO lets FFmpeg use frame threading where the codec supports it.
            self._stream.thread_type = "AUTO"
        except (av.error.FFmpegError, IndexError, OSError) as exc:
            self.close()
            raise DecoderError(f"Unable to open a video stream in {self.source}: {exc}") from exc
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def info(self) -> VideoInfo:
        if self._container is None or self._stream is None:
            raise RuntimeError("VideoDecoder must be opened before reading metadata")
        rate = self._stream.average_rate or self._stream.guessed_rate
        fps = float(rate) if rate else 30.0
        duration = (
            float(self._stream.duration * self._stream.time_base)
            if self._stream.duration is not None and self._stream.time_base is not None
            else (
                float(self._container.duration / av.time_base)
                if self._container.duration is not None
                else None
            )
        )
        return VideoInfo(
            self._stream.width,
            self._stream.height,
            fps,
            duration,
            bool(self._container.streams.audio),
        )

    def frames(self) -> Iterator[DecodedFrame]:
        if self._container is None or self._stream is None:
            raise RuntimeError("VideoDecoder must be used as a context manager")

        fallback_fps = self.info.fps
        try:
            for index, frame in enumerate(self._container.decode(self._stream)):
                if frame.pts is not None and frame.time_base is not None:
                    timestamp = float(frame.pts * frame.time_base)
                else:
                    timestamp = index / fallback_fps
                yield DecodedFrame(frame, timestamp)
        except (av.error.FFmpegError, OSError) as exc:
            raise DecoderError(f"Video decoding failed: {exc}") from exc

    def close(self) -> None:
        if self._container is not None:
            self._container.close()
        self._container = None
        self._stream = None

    def seek(self, seconds: float = 0.0) -> None:
        """Seek to the nearest keyframe at or before ``seconds``."""
        if self._container is None or self._stream is None:
            raise RuntimeError("VideoDecoder must be used as a context manager")
        offset = int(max(0.0, seconds) / float(self._stream.time_base))
        self._container.seek(offset, stream=self._stream, backward=True)
