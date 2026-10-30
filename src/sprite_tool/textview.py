"""A frame as text, for `sprite show` and `sprite show --diff`. No image code: the rows printed are `Frame.rows` unchanged."""

from __future__ import annotations

from .model import Frame, Sprite

# Between the row numbers and the grid, and between the two halves of the header.
_GAP = "  "


def frame_text(sprite: Sprite, frame: Frame) -> str:
    """The frame's grid under a header and a column ruler, each row after its
    number, then one line per point.

    Rows and columns count from 0, as they do in `runs`, `rows` and check
    messages. No line has trailing whitespace.
    """
    lines = [_header(sprite, frame.name), *_rulers(sprite)]
    lines += [_numbered(sprite, index, row) for index, row in enumerate(frame.rows)]
    lines += _points(frame)
    return "".join(line + "\n" for line in lines)


def diff_text(sprite: Sprite, frame: Frame, other: Frame) -> str:
    """The rows of `frame` that differ from the same rows of `other`, each
    numbered and followed by a line with `^` under every column that differs,
    then the points of `frame`. Two equal frames give the header and
    `no rows differ`."""
    changed = [
        (index, row, theirs) for index, (row, theirs) in enumerate(zip(frame.rows, other.rows)) if row != theirs
    ]
    lines = [_header(sprite, f"{frame.name} vs {other.name}")]
    if not changed:
        lines.append("no rows differ")
    else:
        indent = " " * (_number_width(sprite) + len(_GAP))
        lines += _rulers(sprite)
        for index, row, theirs in changed:
            marks = "".join("^" if mine != old else " " for mine, old in zip(row, theirs))
            lines += [_numbered(sprite, index, row), (indent + marks).rstrip()]
    lines += _points(frame)
    return "".join(line + "\n" for line in lines)


def _header(sprite: Sprite, what: str) -> str:
    canvas = sprite.canvas
    return f"{sprite.id} {what}{_GAP}{canvas.name} {canvas.width}x{canvas.height}"


def _number_width(sprite: Sprite) -> int:
    return len(str(sprite.canvas.height - 1))


def _rulers(sprite: Sprite) -> list[str]:
    """The tens of each column when the canvas is wider than 10, then the units."""
    width = sprite.canvas.width
    indent = " " * _number_width(sprite) + _GAP
    lines = []
    if width > 10:
        lines.append(indent + "".join(" " if column < 10 else str(column // 10 % 10) for column in range(width)))
    lines.append(indent + "".join(str(column % 10) for column in range(width)))
    return lines


def _numbered(sprite: Sprite, index: int, row: str) -> str:
    return f"{index:>{_number_width(sprite)}}{_GAP}{row}"


def _points(frame: Frame) -> list[str]:
    """`point <name> <col>,<row>`, in name order."""
    return [f"point {name} {col},{row}" for name, (col, row) in frame.points]
