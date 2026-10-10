"""Frames to images, and the one place PNGs are encoded for export."""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence

from PIL import Image

from sprite_tool.model import Color, Frame, Sprite

TRANSPARENT = (0, 0, 0, 0)

# Fixed so that output bytes do not follow Pillow's default.
COMPRESS_LEVEL = 6


def render(frame: Frame, palette: Mapping[str, Color]) -> Image.Image:
    """One RGBA pixel per character. Assumes a checked frame: every row the
    same width, palette keys and '.' only."""
    image = Image.new("RGBA", (len(frame.rows[0]), len(frame.rows)), TRANSPARENT)
    image.putdata(
        [TRANSPARENT if key == "." else palette[key].rgba for row in frame.rows for key in row]
    )
    return image


def render_all(
    sprites: Sequence[Sprite], palette: Mapping[str, Color]
) -> dict[tuple[str, str], Image.Image]:
    """Every frame of every sprite, keyed by (sprite id, frame name)."""
    return {
        (sprite.id, frame.name): render(frame, palette)
        for sprite in sprites
        for frame in sprite.frames
    }


def png_bytes(image: Image.Image) -> bytes:
    """Deterministic PNG bytes: RGBA, fixed compression, pixel data only."""
    # A copy made from the pixels alone carries none of `image.info`, which
    # Pillow would otherwise write out as metadata chunks.
    pixels = image.convert("RGBA")
    clean = Image.frombytes("RGBA", pixels.size, pixels.tobytes())
    buffer = io.BytesIO()
    clean.save(buffer, format="PNG", optimize=False, compress_level=COMPRESS_LEVEL)
    return buffer.getvalue()
