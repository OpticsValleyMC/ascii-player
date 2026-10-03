# Repository Guidelines

## Project Structure & Module Organization

This Python 3.12+ terminal video player streams video through PyAV, converts frames with NumPy/Pillow, and renders through Rich.

- `main.py` and `cli/commands.py`: source entry point, Typer options, and CLI errors.
- `player/`: decoding, playback timing, rendering, and ffplay audio management.
- `ascii/`: character sets and RGB-to-ASCII conversion.
- `terminal/`: console setup and Windows/Linux keyboard input.
- `config/settings.py`: typed playback settings.
- `docs/images/`: README screenshots and animation assets.

Keep changes in the responsible module. `tests/` contains playback regression tests.

## Build, Test, and Development Commands

Run commands from the repository root in a virtual environment:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
ruff check .
python main.py --help
python main.py video.mp4 --mute --width 80
ascii-player video.mp4 --style block --color
```

Editable installation registers `ascii-player`; the development extra installs Ruff. `ruff check .` runs configured lint and import-order checks. Playback commands require a local video file; `video.mp4` is not tracked. Audio requires `ffplay` on `PATH`. Packaging uses setuptools through `pyproject.toml`; runtime dependencies also appear in `requirements.txt`.

## Coding Style & Naming Conventions

Use four-space indentation and a 100-character line limit, matching Ruff's Python 3.12 configuration. Use `snake_case` for functions and variables, `PascalCase` for classes, and uppercase names for constants. Follow existing type annotations, module docstrings, and dataclass patterns. Keep pixel operations vectorized and decoding streaming; preserve context-manager cleanup for terminal state and audio processes.

## Testing Guidelines

Run `python -m unittest discover -s tests -v` for standard-library regression tests. These use simulated time and processes; no video file, terminal, or ffplay is required. No coverage threshold is configured. Use descriptive `test_*.py` filenames under `tests/`. Run lint and CLI help checks, then manually verify affected playback modes in an ANSI-capable terminal, including resizing, exit cleanup, and audible synchronization.

## Commit & Pull Request Guidelines

Git history contains only `first commit`, so no established message convention exists. Use concise imperative subjects, such as `Fix audio synchronization after replay`. PRs should explain the behavior changed, include validation commands and results, and link relevant issues. Include terminal screenshots or recordings for rendering changes and identify the tested platform. Update the README when CLI options or setup requirements change.
