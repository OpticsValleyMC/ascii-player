"""Vectorized RGB-to-ASCII conversion and terminal escape generation."""

from dataclasses import dataclass

import numpy as np
from PIL import Image

from ascii.charset import get_charset

_RESET = "\x1b[0m"


@dataclass(frozen=True, slots=True)
class ConvertedFrame:
    """A terminal-ready frame plus its visible dimensions."""

    ansi: str
    width: int
    height: int


class AsciiConverter:
    """Convert RGB arrays to monochrome or ANSI TrueColor ASCII frames."""

    def __init__(
        self,
        charset: str = "default",
        *,
        color: bool = False,
        style: str = "default",
        cell_aspect_ratio: float = 0.5,
    ) -> None:
        self.characters = get_charset(charset)
        self._character_array = np.asarray(tuple(self.characters), dtype="<U1")
        self.color = color
        self.style = style
        self.cell_aspect_ratio = cell_aspect_ratio

    def target_size(
        self,
        source_width: int,
        source_height: int,
        width: int,
        max_rows: int,
    ) -> tuple[int, int]:
        """Fit output to both terminal axes while preserving visual aspect."""
        sample_multiplier = 2 if self.style == "block" else 1
        sample_height = max(
            sample_multiplier,
            round(
                source_height
                / source_width
                * width
                * self.cell_aspect_ratio
                * sample_multiplier
            ),
        )
        visible_rows = max(1, (sample_height + sample_multiplier - 1) // sample_multiplier)
        if visible_rows > max_rows:
            width = max(
                1,
                int(width * max_rows / visible_rows),
            )
            sample_height = max(
                sample_multiplier,
                round(
                    source_height
                    / source_width
                    * width
                    * self.cell_aspect_ratio
                    * sample_multiplier
                ),
            )
        if self.style == "block" and sample_height % 2:
            sample_height += 1
        return width, sample_height

    def convert(self, rgb: np.ndarray, width: int, max_rows: int) -> ConvertedFrame:
        """Resize and convert an ``H×W×3`` uint8 RGB array."""
        if rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("Expected an H×W×3 RGB array")
        target_width, sample_height = self.target_size(
            rgb.shape[1], rgb.shape[0], width, max_rows
        )
        resized = np.asarray(
            Image.fromarray(rgb, mode="RGB").resize(
                (target_width, sample_height),
                resample=Image.Resampling.BILINEAR,
            )
        )
        if self.style == "block":
            return self._convert_half_blocks(resized)
        return self._convert_characters(resized)

    @staticmethod
    def _grayscale(rgb: np.ndarray) -> np.ndarray:
        # Integer BT.601 approximation avoids a large temporary float array.
        values = rgb.astype(np.uint16, copy=False)
        return (
            values[..., 0] * 77 + values[..., 1] * 150 + values[..., 2] * 29
        ) >> 8

    def _convert_characters(self, rgb: np.ndarray) -> ConvertedFrame:
        grayscale = self._grayscale(rgb)
        indices = grayscale * (len(self._character_array) - 1) // 255
        mapped = self._character_array[indices]
        if self.color:
            lines = [
                self._color_character_row(chars, colors)
                for chars, colors in zip(mapped, rgb, strict=True)
            ]
        else:
            lines = ["".join(row.tolist()) for row in mapped]
        return ConvertedFrame("\n".join(lines), rgb.shape[1], rgb.shape[0])

    @staticmethod
    def _color_character_row(characters: np.ndarray, colors: np.ndarray) -> str:
        # Escape generation is necessarily textual; all pixel math above remains vectorized.
        return "".join(
            f"\x1b[38;2;{int(r)};{int(g)};{int(b)}m{char}"
            for char, (r, g, b) in zip(characters, colors, strict=True)
        ) + _RESET

    def _convert_half_blocks(self, rgb: np.ndarray) -> ConvertedFrame:
        upper = rgb[0::2]
        lower = rgb[1::2]
        if self.color:
            lines = [
                self._color_half_block_row(top, bottom)
                for top, bottom in zip(upper, lower, strict=True)
            ]
        else:
            top_on = self._grayscale(upper) >= 128
            bottom_on = self._grayscale(lower) >= 128
            glyph_index = top_on.astype(np.uint8) + bottom_on.astype(np.uint8) * 2
            glyphs = np.asarray((" ", "▀", "▄", "█"), dtype="<U1")[glyph_index]
            lines = ["".join(row.tolist()) for row in glyphs]
        return ConvertedFrame("\n".join(lines), rgb.shape[1], upper.shape[0])

    @staticmethod
    def _color_half_block_row(upper: np.ndarray, lower: np.ndarray) -> str:
        return "".join(
            (
                f"\x1b[38;2;{int(tr)};{int(tg)};{int(tb)}m"
                f"\x1b[48;2;{int(br)};{int(bg)};{int(bb)}m▀"
            )
            for (tr, tg, tb), (br, bg, bb) in zip(upper, lower, strict=True)
        ) + _RESET
