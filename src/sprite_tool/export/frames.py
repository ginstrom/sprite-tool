"""The `frames` target: loose PNGs, one per frame, at full canvas size, and a JSON index."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PIL import Image

from sprite_tool.manifest import json_bytes
from sprite_tool.model import ExportTarget, Sprite
from sprite_tool.render import png_bytes

from .index import bounds, sprite_entry


def export(
    sprites: Sequence[Sprite], images: Mapping[tuple[str, str], Image.Image], target: ExportTarget
) -> dict[str, bytes]:
    """`<id>.png` is the default frame. A sprite with more than one frame also
    gets `<id>__<frame>.png` for each of them. `<name>.json` says which file
    each frame is in, and carries anchor, canvas, display scale and bounds."""
    files: dict[str, bytes] = {}
    index: dict[str, object] = {}
    for sprite in sprites:
        default = f"{sprite.id}.png"
        files[default] = png_bytes(images[sprite.id, sprite.frames[0].name])
        frame_files = {frame.name: default for frame in sprite.frames}
        if len(sprite.frames) > 1:
            for frame in sprite.frames:
                frame_files[frame.name] = f"{sprite.id}__{frame.name}.png"
                files[frame_files[frame.name]] = png_bytes(images[sprite.id, frame.name])
        index[sprite.id] = {
            **sprite_entry(sprite),
            "file": default,
            "frames": {
                frame.name: {"bounds": bounds(frame.rows), "file": frame_files[frame.name]}
                for frame in sprite.frames
            },
        }
    files[f"{target.name}.json"] = json_bytes(index)
    return files
