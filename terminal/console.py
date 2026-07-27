"""Rich console construction and Windows ANSI initialization."""

from colorama import just_fix_windows_console
from rich.console import Console


def create_console() -> Console:
    """Create the single application console with TrueColor capability."""
    just_fix_windows_console()
    return Console(color_system="truecolor", highlight=False, soft_wrap=True)

