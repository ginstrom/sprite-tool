"""Sheet composition shared by the atlas targets, so they have one layout."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PIL import Image

from sprite_tool.model import Placement, Sprite
from sprite_tool.pack import pack
from sprite_tool.render import TRANSPARENT, png_bytes


def compose_sheet(
    sprites: Sequence[Sprite],
    images: Mapping[tuple[str, str], Image.Image],
    padding: int,
) -> tuple[bytes, tuple[int, int], list[Placement]]:
    """Pack every frame of `sprites` onto one transparent sheet.

    `images` is keyed by (sprite id, frame name), as `render.render_all`
    returns it. Returns `(png_bytes, (sheet_w, sheet_h), placements)`.
    """
    items = [
        (sprite.id, frame.name, *images[(sprite.id, frame.name)].size)
        for sprite in sprites
        for frame in sprite.frames
    ]
    width, height, placements = pack(items, padding)
    sheet = Image.new("RGBA", (width, height), TRANSPARENT)
    for placement in placements:
        # Pasting without a mask copies the pixels, alpha included.
        sheet.paste(images[(placement.sprite_id, placement.frame)], (placement.x, placement.y))
    return png_bytes(sheet), (width, height), placements
