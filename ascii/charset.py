"""Built-in luminance ramps, ordered from darkest to brightest."""

from typing import Final

DEFAULT: Final = "@%#*+=-:. "
DENSE: Final = r"$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,^`."
BLOCK: Final = " ░▒▓█"

CHARSETS: Final[dict[str, str]] = {
    "default": DEFAULT,
    "dense": DENSE,
    "block": BLOCK,
}


def get_charset(name: str) -> str:
    """Return a named charset or raise a useful error."""
    try:
        return CHARSETS[name]
    except KeyError as exc:
        choices = ", ".join(CHARSETS)
        raise ValueError(f"Unknown charset {name!r}; choose one of: {choices}") from exc

