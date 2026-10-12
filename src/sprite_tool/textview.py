"""A frame as text, for `sprite show`. No image code: the rows printed are `Frame.rows` unchanged."""

from __future__ import annotations

from .model import Frame, Sprite

# Between the row numbers and the grid, and between the two halves of the header.
_GAP = "  "


def frame_text(sprite: Sprite, frame: Frame) -> str:
    """The frame's grid under a header and a column ruler, each row after its number.

    Rows and columns count from 0, as they do in `runs`, `rows` and check
    messages. No line has trailing whitespace.
    """
    canvas = sprite.canvas
    number_width = len(str(canvas.height - 1))
    indent = " " * number_width + _GAP
    lines = [f"{sprite.id} {frame.name}{_GAP}{canvas.name} {canvas.width}x{canvas.height}"]
    if canvas.width > 10:
        tens = "".join(" " if column < 10 else str(column // 10 % 10) for column in range(canvas.width))
        lines.append(indent + tens)
    lines.append(indent + "".join(str(column % 10) for column in range(canvas.width)))
    lines += [f"{index:>{number_width}}{_GAP}{row}" for index, row in enumerate(frame.rows)]
    return "".join(line + "\n" for line in lines)
