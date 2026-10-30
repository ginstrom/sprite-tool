"""Sprite data for the JSON indexes: what a game needs and an image cannot hold."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sprite_tool.model import Frame, Sprite, hex_colour

TRANSPARENT = "."


def bounds(rows: Sequence[str]) -> list[int]:
    """`[x, y, width, height]` of the smallest box holding every drawn pixel,
    in canvas pixels from the top left. All zero when nothing is drawn."""
    drawn_rows = [y for y, row in enumerate(rows) if row.strip(TRANSPARENT)]
    if not drawn_rows:
        return [0, 0, 0, 0]
    left = min(len(rows[y]) - len(rows[y].lstrip(TRANSPARENT)) for y in drawn_rows)
    right = max(len(rows[y].rstrip(TRANSPARENT)) for y in drawn_rows)
    return [left, drawn_rows[0], right - left, drawn_rows[-1] - drawn_rows[0] + 1]


def union(boxes: Iterable[Sequence[int]]) -> list[int]:
    """The smallest box holding every box that has any width."""
    drawn = [box for box in boxes if box[2] > 0]
    if not drawn:
        return [0, 0, 0, 0]
    left = min(x for x, _, _, _ in drawn)
    top = min(y for _, y, _, _ in drawn)
    right = max(x + w for x, _, w, _ in drawn)
    bottom = max(y + h for _, y, _, h in drawn)
    return [left, top, right - left, bottom - top]


def point_json(col: int, row: int) -> list[float]:
    """A point as exported: the centre of its pixel, in canvas pixels from the top left."""
    return [col + 0.5, row + 0.5]


def frame_points(frame: Frame) -> dict[str, list[float]]:
    """A frame's points by name, as exported."""
    return {name: point_json(col, row) for name, (col, row) in frame.points}


def sprite_entry(sprite: Sprite) -> dict[str, object]:
    """The keys every index has for a sprite. `bounds` covers all its frames,
    so it does not move with the animation. `anims` has each frame's own
    length. `over` is there only for a layer: the id of the sprite it is
    drawn over. `points` is there only for a sprite with points: each frame
    that has any, by frame name, with its points. `tints` is there only for
    a sprite with tints: each one's colour and mode, by name."""
    canvas = sprite.canvas
    entry: dict[str, object] = {
        "anchor": list(canvas.anchor),
        "anims": {
            anim.name: {
                "frames": [{"frame": frame, "ms": ms} for frame, ms in zip(anim.frames, anim.durations)],
                "loop": anim.loop,
            }
            for anim in sorted(sprite.anims, key=lambda anim: anim.name)
        },
        "bounds": union(bounds(frame.rows) for frame in sprite.frames),
        "canvas": canvas.name,
        "display_scale": canvas.display_scale,
        "size": [canvas.width, canvas.height],
    }
    if sprite.over is not None:
        entry["over"] = sprite.over
    points = {frame.name: frame_points(frame) for frame in sprite.frames if frame.points}
    if points:
        entry["points"] = points
    if sprite.tints:
        entry["tints"] = {name: {"colour": hex_colour(tint.colour), "mode": tint.mode} for name, tint in sprite.tints}
    return entry
