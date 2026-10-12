"""The `godot` target: a packed sheet, a `SpriteFrames` resource per sprite and a JSON index."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PIL import Image

from sprite_tool.manifest import json_bytes
from sprite_tool.model import Anim, ExportTarget, Placement, Sprite

from .atlas import compose_sheet
from .index import sprite_entry

# The animation a sprite gets when it declares none: every frame, once a second.
DEFAULT_ANIM = "default"
DEFAULT_MS = 1000


def export(
    sprites: Sequence[Sprite], images: Mapping[tuple[str, str], Image.Image], target: ExportTarget
) -> dict[str, bytes]:
    """`<name>.png`, `<name>.json` and one `<id>.tres` per sprite. The index
    carries what a `SpriteFrames` cannot: anchor, canvas, display scale and bounds."""
    sprites = sorted(sprites, key=lambda sprite: sprite.id)
    sheet, _, placements = compose_sheet(sprites, images, target.padding)
    regions = {(placement.sprite_id, placement.frame): placement for placement in placements}
    separator = "" if target.res_path.endswith("/") else "/"
    texture = f"{target.res_path}{separator}{target.name}.png"
    files = {
        f"{target.name}.png": sheet,
        f"{target.name}.json": json_bytes({sprite.id: _index_entry(sprite, regions) for sprite in sprites}),
    }
    for sprite in sprites:
        files[f"{sprite.id}.tres"] = _sprite_frames(sprite, regions, texture).encode("utf-8")
    return files


def _index_entry(sprite: Sprite, regions: Mapping[tuple[str, str], Placement]) -> dict[str, object]:
    return {
        **sprite_entry(sprite),
        "frames": {frame.name: _rect(regions[sprite.id, frame.name]) for frame in sprite.frames},
    }


def _rect(placement: Placement) -> list[int]:
    return [placement.x, placement.y, placement.w, placement.h]


def _sprite_frames(sprite: Sprite, regions: Mapping[tuple[str, str], Placement], texture: str) -> str:
    """A format 3 text resource, laid out as Godot saves one. Sub-resource ids
    come from the sprite id and frame name, and there is no `uid`, so the text
    depends on nothing but the sprite and the sheet layout."""
    anims = sorted(sprite.anims, key=lambda anim: anim.name) or [
        Anim(name=DEFAULT_ANIM, frames=tuple(frame.name for frame in sprite.frames), ms=DEFAULT_MS, loop=True)
    ]
    blocks = [
        f'[gd_resource type="SpriteFrames" load_steps={len(sprite.frames) + 2} format=3]\n',
        f'[ext_resource type="Texture2D" path={_quote(texture)} id="1"]\n',
    ]
    for frame in sprite.frames:
        x, y, w, h = _rect(regions[sprite.id, frame.name])
        blocks.append(
            f'[sub_resource type="AtlasTexture" id={_quote(_sub_id(sprite, frame.name))}]\n'
            'atlas = ExtResource("1")\n'
            f"region = Rect2({x}, {y}, {w}, {h})\n"
        )
    blocks.append(f"[resource]\nanimations = [{', '.join(_animation(sprite, anim) for anim in anims)}]\n")
    return "\n".join(blocks)


def _animation(sprite: Sprite, anim: Anim) -> str:
    # `speed` is frames a second at the animation's `ms`; a frame of another
    # length lasts that many of those.
    frames = ", ".join(
        f'{{\n"duration": {ms / anim.ms!r},\n"texture": SubResource({_quote(_sub_id(sprite, frame))})\n}}'
        for frame, ms in zip(anim.frames, anim.durations)
    )
    return (
        f'{{\n"frames": [{frames}],\n'
        f'"loop": {"true" if anim.loop else "false"},\n'
        f'"name": &{_quote(anim.name)},\n'
        f'"speed": {1000 / anim.ms!r}\n}}'
    )


def _sub_id(sprite: Sprite, frame: str) -> str:
    return f"{sprite.id}_{frame}"


def _quote(text: str) -> str:
    """A double-quoted string as Godot's resource parser reads it."""
    escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    return '"' + "".join(escapes.get(char, char) for char in text) + '"'
