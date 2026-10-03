"""Interactive real-time playback and component orchestration."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from rich.console import Console

from ascii.converter import AsciiConverter, ConvertedFrame
from config.settings import PlaybackSettings
from player.audio import AudioPlayer
from player.decoder import VideoDecoder, VideoInfo
from player.renderer import TerminalRenderer
from terminal.input import Action, TerminalInput


@dataclass(slots=True)
class _PlaybackState:
    speed: float = 1.0
    paused: bool = False
    quit: bool = False
    replay: bool = False


@dataclass(slots=True)
class _PlaybackClock:
    """Map elapsed wall time to media time, preserving position across controls."""

    clock_anchor: float
    media_anchor: float = 0.0
    speed: float = 1.0
    paused: bool = False

    def position(self, now: float) -> float:
        if self.paused:
            return self.media_anchor
        return self.media_anchor + max(0.0, now - self.clock_anchor) * self.speed


class VideoPlayer:
    """Stream, convert, render, and interact against a monotonic clock."""

    def __init__(
        self,
        settings: PlaybackSettings,
        console: Console,
        *,
        clock: Callable[[], float] = time.perf_counter,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.console = console
        self._clock = clock
        self._sleep = sleep

    def play(self) -> None:
        converter = AsciiConverter(
            self.settings.charset,
            color=self.settings.color,
            style=self.settings.style,
            cell_aspect_ratio=self.settings.cell_aspect_ratio,
        )
        state = _PlaybackState()

        with (
            VideoDecoder(self.settings.source) as decoder,
            TerminalRenderer(self.console) as renderer,
            TerminalInput() as keyboard,
            AudioPlayer(self.settings.source, enabled=self.settings.audio) as audio,
        ):
            info = decoder.info
            while not state.quit:
                state.replay = False
                state.paused = False
                decoder.seek(0)
                self._play_once(
                    decoder,
                    info,
                    converter,
                    renderer,
                    keyboard,
                    audio,
                    state,
                )
                audio.stop()
                if state.quit:
                    break
                if state.replay:
                    continue
                # EOF is terminal: Replay remains available throughout playback,
                # while scripts and IDE consoles can rely on automatic completion.
                break

    def _play_once(
        self,
        decoder: VideoDecoder,
        info: VideoInfo,
        converter: AsciiConverter,
        renderer: TerminalRenderer,
        keyboard: TerminalInput,
        audio: AudioPlayer,
        state: _PlaybackState,
    ) -> tuple[ConvertedFrame | None, float]:
        timeline: _PlaybackClock | None = None
        first_timestamp: float | None = None
        next_sample = 0.0
        sample_interval = 1 / self.settings.fps if self.settings.fps else None
        last_frame: ConvertedFrame | None = None
        last_position = 0.0

        for decoded in decoder.frames():
            if first_timestamp is None:
                first_timestamp = decoded.timestamp
                if info.has_audio:
                    audio.start(0, state.speed)
                timeline = _PlaybackClock(self._clock(), speed=state.speed)
            media_time = max(0.0, decoded.timestamp - first_timestamp)
            assert timeline is not None

            if sample_interval is not None:
                if media_time + 1e-9 < next_sample:
                    continue
                next_sample = media_time + sample_interval

            should_render = self._wait_for_media_time(
                timeline,
                media_time,
                info,
                renderer,
                keyboard,
                audio,
                state,
                last_frame,
            )
            if state.quit or state.replay:
                break
            if not should_render:
                continue

            terminal_width, terminal_height = renderer.available_size
            requested_width = self.settings.width or terminal_width
            frame = converter.convert(
                decoded.rgb,
                width=min(requested_width, terminal_width),
                max_rows=terminal_height,
            )
            renderer.render(
                frame,
                position=media_time,
                duration=info.duration,
                speed=state.speed,
                paused=state.paused,
                audio=info.has_audio and audio.available,
            )
            last_frame = frame
            last_position = media_time

        return last_frame, last_position

    def _wait_for_media_time(
        self,
        timeline: _PlaybackClock,
        media_time: float,
        info: VideoInfo,
        renderer: TerminalRenderer,
        keyboard: TerminalInput,
        audio: AudioPlayer,
        state: _PlaybackState,
        last_frame: ConvertedFrame | None,
    ) -> bool:
        """Wait responsively while processing playback control keys."""
        while True:
            action = keyboard.poll()
            if action is not None:
                position = timeline.position(self._clock())
                old_paused = state.paused
                old_speed = state.speed
                self._apply_action(action, state)

                if state.quit or state.replay:
                    audio.stop()
                    return False
                if state.paused and not old_paused:
                    audio.stop()
                elif not state.paused and old_paused:
                    if info.has_audio:
                        audio.start(position, state.speed)
                elif state.speed != old_speed and info.has_audio and not state.paused:
                    audio.restart(position, state.speed)

                if state.paused != old_paused or state.speed != old_speed:
                    # Process teardown/startup can block; freeze media time during it.
                    timeline.media_anchor = position
                    timeline.clock_anchor = self._clock()
                    timeline.speed = state.speed
                    timeline.paused = state.paused

                if last_frame is not None:
                    renderer.render_status(
                        last_frame,
                        position=position,
                        duration=info.duration,
                        speed=state.speed,
                        paused=state.paused,
                        audio=info.has_audio and audio.available and not state.paused,
                    )

            if state.paused:
                self._sleep(0.02)
                continue

            delay = (media_time - timeline.position(self._clock())) / state.speed
            if delay <= 0:
                # Skip badly late video frames; ffplay remains the audible timeline.
                return delay >= -0.25
            self._sleep(min(delay, 0.02))

    @staticmethod
    def _apply_action(action: Action, state: _PlaybackState) -> None:
        if action is Action.TOGGLE_PAUSE:
            state.paused = not state.paused
        elif action is Action.REPLAY:
            state.replay = True
        elif action is Action.FASTER:
            state.speed = min(2.0, state.speed + 0.25)
        elif action is Action.SLOWER:
            state.speed = max(0.5, state.speed - 0.25)
        elif action is Action.QUIT:
            state.quit = True
