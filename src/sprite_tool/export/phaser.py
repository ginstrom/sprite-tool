"""The `phaser` target: a packed sheet, a JSON Hash atlas and an animation file."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PIL import Image

from sprite_tool.manifest import json_bytes
from sprite_tool.model import ExportTarget, Placement, Sprite

from .atlas import compose_sheet


def export(
    sprites: Sequence[Sprite], images: Mapping[tuple[str, str], Image.Image], target: ExportTarget
) -> dict[str, bytes]:
    """`<name>.png`, `<name>.json` and `<name>.anims.json`. Frames are keyed
    `<id>/<frame>` and animations `<id>/<anim>`; `<name>` is the texture key
    the animations refer to."""
    sprites = sorted(sprites, key=lambda sprite: sprite.id)
    sheet, (width, height), placements = compose_sheet(sprites, images, target.padding)
    by_id = {sprite.id: sprite for sprite in sprites}
    atlas = {
        "frames": {
            _key(placement.sprite_id, placement.frame): _frame(placement, by_id[placement.sprite_id])
            for placement in placements
        },
        "meta": {
            "app": "sprite-tool",
            "image": f"{target.name}.png",
            "scale": "1",
            "size": {"h": height, "w": width},
        },
    }
    anims = [
        {
            "frames": [
                {"duration": ms, "frame": _key(sprite.id, frame), "key": target.name}
                for frame, ms in zip(anim.frames, anim.durations)
            ],
            "key": _key(sprite.id, anim.name),
            "repeat": -1 if anim.loop else 0,
        }
        for sprite in sprites
        for anim in sprite.anims
    ]
    anims.sort(key=lambda anim: anim["key"])
    return {
        f"{target.name}.png": sheet,
        f"{target.name}.json": json_bytes(atlas),
        f"{target.name}.anims.json": json_bytes({"anims": anims}),
    }


def _key(sprite_id: str, name: str) -> str:
    return f"{sprite_id}/{name}"


def _frame(placement: Placement, sprite: Sprite) -> dict[str, object]:
    """Full canvas size, never trimmed or rotated. `pivot` is the canvas
    anchor as a fraction of the canvas."""
    size = {"h": placement.h, "w": placement.w}
    canvas = sprite.canvas
    return {
        "frame": {**size, "x": placement.x, "y": placement.y},
        "pivot": {"x": canvas.anchor[0] / canvas.width, "y": canvas.anchor[1] / canvas.height},
        "rotated": False,
        "sourceSize": size,
        "spriteSourceSize": {**size, "x": 0, "y": 0},
        "trimmed": False,
    }
