"""Typer command-line entry point."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ascii.charset import CHARSETS
from config.settings import PlaybackSettings
from player.decoder import DecoderError
from player.player import VideoPlayer
from terminal.console import create_console

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
    help="Play videos as real-time ASCII art in your terminal.",
)


@app.command()
def play(
    video: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Video file to play (for example MP4, MKV, or WebM).",
        ),
    ],
    width: Annotated[
        int | None,
        typer.Option(
            "--width",
            "-w",
            min=1,
            help="Maximum output width; defaults to terminal width.",
        ),
    ] = None,
    fps: Annotated[
        float | None,
        typer.Option("--fps", min=0.1, help="Cap rendered FPS while preserving playback speed."),
    ] = None,
    color: Annotated[
        bool,
        typer.Option("--color/--no-color", help="Render ANSI 24-bit color."),
    ] = False,
    audio: Annotated[
        bool,
        typer.Option("--audio/--mute", help="Play the video audio track through ffplay."),
    ] = True,
    style: Annotated[
        str,
        typer.Option("--style", help="Rendering style: default or block (half-height cells)."),
    ] = "default",
    charset: Annotated[
        str,
        typer.Option("--charset", help="Luminance ramp: default, dense, or block."),
    ] = "default",
) -> None:
    """Play VIDEO as ASCII art."""
    console = create_console()
    if style not in {"default", "block"}:
        raise typer.BadParameter("must be 'default' or 'block'", param_hint="--style")
    if charset not in CHARSETS:
        raise typer.BadParameter(
            f"must be one of: {', '.join(CHARSETS)}",
            param_hint="--charset",
        )

    settings = PlaybackSettings(
        source=video,
        width=width,
        fps=fps,
        color=color,
        audio=audio,
        style=style,  # type: ignore[arg-type]
        charset=charset,  # type: ignore[arg-type]
    )
    try:
        VideoPlayer(settings, console).play()
    except KeyboardInterrupt:
        pass
    except DecoderError as exc:
        _exit_with_error(console, str(exc))
    except OSError as exc:
        _exit_with_error(console, f"I/O error: {exc}")


def _exit_with_error(console: Console, message: str) -> None:
    console.print(f"[bold red]Error:[/] {message}", markup=True)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
