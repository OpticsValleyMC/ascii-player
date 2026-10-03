"""Regression checks using simulated time; no terminal or ffplay is required."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from rich.console import Console
from rich.text import Text

from ascii.converter import ConvertedFrame
from config.settings import PlaybackSettings
from player.decoder import DecodedFrame, VideoInfo
from player.player import VideoPlayer, _PlaybackClock, _PlaybackState
from player.renderer import TerminalRenderer
from terminal.input import Action


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class PlaybackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.player = VideoPlayer(
            PlaybackSettings(Path("sample.mp4")),
            Console(),
            clock=self.clock,
            sleep=self.clock.sleep,
        )
        self.info = VideoInfo(16, 16, 30.0, 10.0, True)
        self.frame = ConvertedFrame("x", 1, 1)

    def wait_with_actions(self, events, *, speed=1.0, restart_delay=0.0):
        events = list(events)
        keyboard = Mock()

        def poll():
            if events and self.clock.now + 1e-9 >= events[0][0]:
                return events.pop(0)[1]
            return None

        keyboard.poll.side_effect = poll
        renderer, audio = Mock(), Mock()
        audio.restart.side_effect = lambda *args: self.clock.sleep(restart_delay)
        state = _PlaybackState(speed=speed)
        timeline = _PlaybackClock(0.0, speed=speed)
        rendered = self.player._wait_for_media_time(
            timeline, 1.0, self.info, renderer, keyboard, audio, state, self.frame
        )
        return rendered, timeline, renderer, audio

    def test_pause_resume_keeps_position_before_pending_frame(self):
        rendered, timeline, renderer, audio = self.wait_with_actions(
            [(0.2, Action.TOGGLE_PAUSE), (1.2, Action.TOGGLE_PAUSE)]
        )
        self.assertTrue(rendered)
        self.assertAlmostEqual(audio.start.call_args.args[0], 0.2)
        self.assertAlmostEqual(self.clock.now, 2.0)
        self.assertAlmostEqual(timeline.position(self.clock.now), 1.0)
        for call in renderer.render_status.call_args_list:
            self.assertAlmostEqual(call.kwargs["position"], 0.2)

    def test_speed_change_preserves_current_position(self):
        rendered, _, _, audio = self.wait_with_actions([(0.2, Action.FASTER)])
        self.assertTrue(rendered)
        self.assertAlmostEqual(audio.restart.call_args.args[0], 0.2)
        self.assertEqual(audio.restart.call_args.args[1], 1.25)
        self.assertAlmostEqual(self.clock.now, 0.84)

    def test_speed_change_while_paused_keeps_frozen_position(self):
        _, _, _, audio = self.wait_with_actions(
            [(0.2, Action.TOGGLE_PAUSE), (0.6, Action.FASTER),
             (1.2, Action.TOGGLE_PAUSE)]
        )
        audio.restart.assert_not_called()
        self.assertAlmostEqual(audio.start.call_args.args[0], 0.2)
        self.assertEqual(audio.start.call_args.args[1], 1.25)
        self.assertAlmostEqual(self.clock.now, 1.84)

    def test_speed_limit_does_not_restart_audio(self):
        _, _, _, audio = self.wait_with_actions([(0.2, Action.FASTER)], speed=2.0)
        audio.restart.assert_not_called()
        self.assertAlmostEqual(self.clock.now, 0.5)

    def test_consecutive_speed_changes_preserve_elapsed_media_time(self):
        _, _, _, audio = self.wait_with_actions(
            [(0.2, Action.FASTER), (0.4, Action.SLOWER)]
        )
        calls = audio.restart.call_args_list
        self.assertAlmostEqual(calls[0].args[0], 0.2)
        self.assertAlmostEqual(calls[1].args[0], 0.45)
        self.assertAlmostEqual(self.clock.now, 0.95)

    def test_audio_restart_delay_does_not_advance_video_clock(self):
        _, timeline, _, _ = self.wait_with_actions(
            [(0.2, Action.FASTER)], restart_delay=0.3
        )
        self.assertAlmostEqual(timeline.media_anchor, 0.2)
        self.assertAlmostEqual(timeline.clock_anchor, 0.5)
        self.assertAlmostEqual(self.clock.now, 1.14)

    def test_lazy_rgb_conversion_preserves_friendly_errors(self):
        raw = Mock()
        raw.to_ndarray.side_effect = OSError("bad frame")
        from player.decoder import DecoderError

        with self.assertRaisesRegex(DecoderError, "bad frame"):
            _ = DecodedFrame(raw, 0.0).rgb

    def test_quit_and_replay_stop_wait_without_rendering(self):
        for action in (Action.QUIT, Action.REPLAY):
            self.clock.now = 0.0
            rendered, _, _, audio = self.wait_with_actions([(0.2, action)])
            self.assertFalse(rendered)
            audio.stop.assert_called_once()

    def test_dropped_frames_do_not_convert_to_rgb(self):
        self.player.settings = PlaybackSettings(Path("sample.mp4"), fps=10)
        raw_frames = [Mock() for _ in range(4)]
        decoder = Mock()

        def frames():
            for index, timestamp in enumerate((0.0, 0.01, 0.1, 0.2)):
                if index == 3:
                    self.clock.now = 1.0  # Decode stalls: this frame is too late.
                yield DecodedFrame(raw_frames[index], timestamp)

        decoder.frames.side_effect = frames
        renderer = Mock()
        renderer.available_size = (80, 20)
        converter = Mock()
        converter.convert.return_value = self.frame
        keyboard = Mock()
        keyboard.poll.return_value = None
        self.player._play_once(
            decoder, self.info, converter, renderer, keyboard, Mock(), _PlaybackState()
        )
        for index in (0, 2):
            raw_frames[index].to_ndarray.assert_called_once_with(format="rgb24")
        for index in (1, 3):
            raw_frames[index].to_ndarray.assert_not_called()
        self.assertEqual(renderer.render.call_count, 2)

    def test_status_updates_reuse_parsed_frame_and_parse_new_frames(self):
        renderer = TerminalRenderer(Console(width=80, height=24))
        renderer._live = MagicMock()
        options = dict(position=0.0, duration=10.0, speed=1.0, paused=False, audio=False)
        with patch("player.renderer.Text.from_ansi", wraps=Text.from_ansi) as parse:
            renderer.render(self.frame, **options)
            renderer.render_status(self.frame, **(options | {"paused": True}))
            renderer.render_status(self.frame, **(options | {"speed": 1.25}))
            self.assertEqual(parse.call_count, 1)
            renderer.render(ConvertedFrame("y", 1, 1), **options)
            self.assertEqual(parse.call_count, 2)
        self.assertEqual(renderer._live.update.call_count, 4)
        renderer.__exit__(None, None, None)
        self.assertIsNone(renderer._last_frame)


if __name__ == "__main__":
    unittest.main()
