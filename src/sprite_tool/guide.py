"""The reference text an agent reads before drawing (`sprite guide`)."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

from .model import Canvas, ExportTarget, Project, hex_colour

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
from = "idle_0"            #    optional: the frame to start from; without it, a blank canvas
rows = { 1 = "kbbbbk" }    # 1. replace whole rows, by row index
runs = { 2 = [[2, "ww"]] } # 2. replace pixels: row = [[column, "pixels"], ...]; '.' erases
shift = [1, 0]             # 3. move by [dx, dy]; pixels pushed off the canvas are lost
flip = true                # 4. mirror left to right
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
Frame names are free; `<anim>_<n>` is only a habit. A replacement row is a full row. `rows` can
also be a table, one row per line: `[frames.idle_1.rows]`, then `1 = "kbbbbk"`.
A whole frame can be runs alone, with no grid: `[frames.main.runs]`, then one line for each row
that has pixels, such as `9 = [[12, "kwwk"], [20, "k"]]`. The rest stays transparent.
The default frame is what a game shows when no animation plays, and what the contact sheet shows.
Sprite files may be anywhere in the project; `sprite new` writes to the root unless given `--dir`.
`build = false` at the top of a file: the sprite is checked and previewed, never exported.
"""

_RULES = """\
anchor x,y: the pixel a game places the sprite by; the bottom centre is where a unit stands.
display scale: how much the game enlarges the class. Draw units facing right; games mirror them.
outline <keys>: a pixel with a transparent pixel or the canvas edge directly above, below, left
  or right of it must use one of the keys. Diagonals do not count, so a part 1 or 2 pixels
  wide is all outline.
grounded: the bottom row of every frame must have a pixel.
A sprite opts out with `outline = false` or `grounded = false` at the top of its file.
`outline = "auto"` at the top of a file: draw the interior only, one pixel inside the canvas edge;
  the tool draws the outline with the first key listed for the class.
"""

_PALETTE = """\
A key is one printable ASCII character except . " ' \\ and space, so a palette holds up to 90
colours. Removing or renaming a key breaks every sprite that uses it: check reports each use as
E104 and build writes nothing until they are fixed.
"""

_COMMANDS = """\
COMMANDS
sprite new <id> --canvas <class> [--dir <subdir>]   write a blank sprite file to draw in
sprite check [<file>...]                            list problems; fix them until it prints `ok`
sprite preview <id>... [--grid]                     write one image of those sprites and print its
                                                    path; it is drawn even with outline problems;
                                                    --grid labels every 4th row and column
sprite preview <id> --on <tile-id>                  the sprite standing on a tile, as in the game
sprite preview                                      contact sheet of every sprite
sprite import <png> --canvas <class> [--snap]       write a sprite file from a PNG
sprite build                                        check everything, then write the game's files
sprite build --adopt [<id>...]                      also take over files already in an export
                                                    directory: those of the given sprites, or all
"""

_WIDTH = 100
# An export directory longer than this gets its files on the lines below it.
_MAX_EXPORT_PREFIX = 50

_LEGEND_COLUMNS = 2


def guide_text(project: Project) -> str:
    """The sprite file format, this project's palette, canvas classes and exports, and the commands."""
    sections = [
        "SPRITE FILE  <id>.sprite.toml; the file name is the sprite id. Example on a 6x4 canvas:\n"
        + EXAMPLE
        + _FORMAT,
        "PALETTE  key, hex, name\n" + _legend(project) + _PALETTE,
        "CANVAS CLASSES\n" + _classes(project) + _RULES,
        _exports(project),
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
        # The key `outline = "auto"` draws with comes first.
        others = sorted(canvas.outline - {canvas.outline_key})
        rules.append("outline " + " ".join(filter(None, [canvas.outline_key, *others])))
    if canvas.grounded:
        rules.append("grounded")
    return ", ".join(rules) or "no rules"


def _exports(project: Project) -> str:
    if not project.exports:
        return "EXPORTS  none configured\n"
    rows = [
        (target.type, Path(os.path.relpath(target.out, project.root)).as_posix(), _files(target))
        for target in project.exports
    ]
    widths = [max(map(len, column)) for column in zip(*rows)]
    lines = ["EXPORTS  sprite build writes these; do not edit them by hand"]
    for kind, directory, files in rows:
        prefix = f"{kind.ljust(widths[0])}  {directory.ljust(widths[1])}  "
        if len(prefix) > _MAX_EXPORT_PREFIX:
            lines.append(prefix.rstrip())
            prefix = indent = "  "
        else:
            indent = " " * len(prefix)
        lines += textwrap.wrap(
            files,
            _WIDTH,
            initial_indent=prefix,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
    return "".join(line + "\n" for line in lines)


def _files(target: ExportTarget) -> str:
    """What `sprite build` writes for `target`, as the exporters name the files."""
    name = target.name
    if target.type == "frames":
        return (
            "<id>.png (the default frame), <id>__<frame>.png when a sprite has several frames, "
            f"{name}.json (size, anchor, scale, bounds)"
        )
    if target.type == "phaser":
        return f"{name}.png, {name}.json, {name}.anims.json"
    return f"{name}.png, {name}.json (the index), one <id>.tres per sprite"
