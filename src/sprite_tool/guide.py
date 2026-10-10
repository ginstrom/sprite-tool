"""The reference text an agent reads before drawing (`sprite guide`)."""

from __future__ import annotations

from .model import Canvas, Project, hex_colour

# A complete sprite file. It checks clean on a 6x4 canvas whose palette has k, w, b, B, r and R.
EXAMPLE = '''\
canvas = "unit"            # a canvas class from the list below
[frames]                   # the first frame is the default frame; names match [a-z0-9_]+
idle_0 = """
.kkkk.
kbwwbk
kbBBbk
.kkkk.
"""
[frames.idle_1]            # a derived frame; its operations apply in this order:
from = "idle_0"            #    required: another frame in this file
rows = { 1 = "kbbbbk" }    # 1. replace whole rows, by row index
shift = [1, 0]             # 2. move by [dx, dy]; pixels pushed off the canvas are lost
flip = true                # 3. mirror left to right
[anim.idle]                # optional
frames = ["idle_0", "idle_1"]
ms = 400                   # duration of each frame; add `loop = false` to play once
[variants.red]             # optional: also makes the sprite <id>_red with these keys swapped
swap = { b = "r", B = "R" }
'''

_FORMAT = """\
A grid has one line per pixel row and one character per pixel. Each character is a palette key;
'.' is transparent. The grid must be exactly the canvas size, with no trailing spaces. Rows and
columns count from 0 at the top left, in `rows` and in check messages (`row 2, col 4`).
Positions written `file:line:col` count from 1.
"""

_RULES = """\
outline <keys>: a pixel with a transparent pixel or the canvas edge directly above, below, left
  or right of it must use one of the keys.
grounded: the bottom row of every frame must have a pixel.
A sprite opts out with `outline = false` or `grounded = false` at the top of its file.
"""

_COMMANDS = """\
COMMANDS
sprite new <id> --canvas <class> [--dir <subdir>]   write a blank sprite file to draw in
sprite check [<file>...]                            list problems; fix them until it prints `ok`
sprite preview <id> --grid                          write .preview/<id>.png to look at
sprite build                                        check everything, then write the game's files
"""

_LEGEND_COLUMNS = 2


def guide_text(project: Project) -> str:
    """The sprite file format, this project's palette and canvas classes, and the commands."""
    sections = [
        "SPRITE FILE  <id>.sprite.toml; the file name is the sprite id. Example on a 6x4 canvas:\n"
        + EXAMPLE
        + _FORMAT,
        "PALETTE  key, hex, name\n" + _legend(project),
        "CANVAS CLASSES\n" + _classes(project) + _RULES,
        _COMMANDS,
    ]
    return "\n".join(sections)


def _legend(project: Project) -> str:
    entries = [
        " ".join(filter(None, (color.key, hex_colour(color.rgba), color.name)))
        for color in project.palette.values()
    ]
    width = max(map(len, entries), default=0) + 3
    lines = [
        "".join(entry.ljust(width) for entry in entries[start : start + _LEGEND_COLUMNS]).rstrip()
        for start in range(0, len(entries), _LEGEND_COLUMNS)
    ]
    return "".join(line + "\n" for line in lines)


def _classes(project: Project) -> str:
    rows = [
        (
            canvas.name,
            f"{canvas.width}x{canvas.height}",
            f"anchor {canvas.anchor[0]},{canvas.anchor[1]}",
            f"display scale {canvas.display_scale}",
            _rules(canvas),
        )
        for canvas in project.canvases.values()
    ]
    widths = [max(map(len, column)) for column in zip(*rows)]
    return "".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() + "\n" for row in rows
    )


def _rules(canvas: Canvas) -> str:
    rules = []
    if canvas.outline:
        rules.append("outline " + " ".join(sorted(canvas.outline)))
    if canvas.grounded:
        rules.append("grounded")
    return ", ".join(rules) or "no rules"
