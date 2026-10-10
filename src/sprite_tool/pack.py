"""Shelf packer for atlas sheets. Works on sizes only; knows nothing about images."""

from __future__ import annotations

from collections.abc import Sequence

from sprite_tool.model import Placement

MIN_WIDTH = 64


def pack(
    items: Sequence[tuple[str, str, int, int]], padding: int = 1
) -> tuple[int, int, list[Placement]]:
    """Place `(sprite_id, frame_name, w, h)` items; returns `(sheet_w, sheet_h, placements)`.

    Each sprite's frames must be passed in file order. The order of different
    sprites does not matter: items are sorted stably by height descending,
    then sprite id. The sheet width is the smallest power of two, at least 64,
    that holds every frame and makes the sheet no taller than wide. `padding`
    transparent pixels separate frames from each other and from the sheet edge.
    An empty input gives a 64-wide sheet with no placements, at least 1 high.
    """
    if padding < 0:
        raise ValueError(f"padding must be 0 or more, got {padding}")
    ordered = sorted(items, key=lambda item: (-item[3], item[0]))
    widest = max((w for _, _, w, _ in ordered), default=0)
    width = MIN_WIDTH
    while True:
        if widest + 2 * padding <= width:
            height, placements = _shelves(ordered, padding, width)
            if height <= width:
                return width, max(height, 1), placements
        width *= 2


def _shelves(
    ordered: Sequence[tuple[str, str, int, int]], padding: int, width: int
) -> tuple[int, list[Placement]]:
    """Fill shelves left to right on a sheet `width` wide; returns the used height."""
    placements = []
    x = y = padding
    # Items come tallest first, so a shelf is as high as its first item.
    shelf_h = 0
    for sprite_id, frame, w, h in ordered:
        if x + w + padding > width:
            x = padding
            y += shelf_h + padding
            shelf_h = 0
        placements.append(Placement(sprite_id=sprite_id, frame=frame, x=x, y=y, w=w, h=h))
        shelf_h = max(shelf_h, h)
        x += w + padding
    return y + shelf_h + padding, placements
