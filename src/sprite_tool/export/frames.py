"""The `frames` target: loose PNGs, one per frame, at full canvas size."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PIL import Image

from sprite_tool.model import ExportTarget, Sprite
from sprite_tool.render import png_bytes


def export(
    sprites: Sequence[Sprite], images: Mapping[tuple[str, str], Image.Image], target: ExportTarget
) -> dict[str, bytes]:
    """`<id>.png` is the default frame. A sprite with more than one frame also
    gets `<id>__<frame>.png` for each of them."""
    files: dict[str, bytes] = {}
    for sprite in sprites:
        files[f"{sprite.id}.png"] = png_bytes(images[sprite.id, sprite.frames[0].name])
        if len(sprite.frames) > 1:
            for frame in sprite.frames:
                files[f"{sprite.id}__{frame.name}.png"] = png_bytes(images[sprite.id, frame.name])
    return files
