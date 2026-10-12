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
.kkk..
kbwbk.
kbBbk.
.kkk..
"""
[frames.idle_1]            # a derived frame; its operations apply in this order:
from = "idle_0"            #    optional: the frame to start from; without it, a blank canvas
move = { rows = [1, 1], by = [0, 1] } # 1. move a rectangle (rows, cols or both) by [dx, dy]
rows = { 1 = "kbbbk." }    # 2. replace whole rows, by row index
runs = { 2 = [[2, "B"]] }  # 3. replace pixels: row = [[column, "pixels"], ...]; '.' erases
shift = [1, 0]             # 4. move the whole frame by [dx, dy]
flip = true                # 5. mirror left to right
[frames.idle_2.runs]       # a whole frame as runs, no grid: one line per row that has pixels
0 = [[1, "kkk"]]           #    row = [[column, "pixels"], ...]; the rest stays transparent
1 = [[0, "kbwbk"]]
2 = [[0, "k"], [1, "bBb"], [4, "k"]]
3 = [[1, "kkk"]]
[anim.idle]                # optional; a game plays it as <id>/idle
frames = ["idle_0", { frame = "idle_1", ms = 150 }, "idle_2"]  # an entry can give its own length
ms = 400                   # length of every other frame; add `loop = false` to play once
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
Write a grid when the picture fills the canvas, runs when it is mostly empty or too wide to count
across. `sprite show <id>` prints either as the finished grid, outline included.
Do not write a script to generate a grid: placing pixels at a row and column is what runs do.
The default frame is what a game shows when no animation plays, and what the contact sheet shows.
Sprite files may be anywhere in the project; `sprite new` writes to the root unless given `--dir`.
`build = false` at the top of a file: the sprite is checked and previewed, never exported.
`move` takes its rectangle (`rows` and `cols` are `[first, last]`) whole, transparent pixels too,
and leaves transparency behind; a list of moves applies in order. `check` warns when `move` or
`shift` pushes pixels off the canvas.
`over = "<id>"` at the top of a file: the sprite is a layer, drawn over that sprite (its base) of
the same class. The outline rule then counts the base's pixels as drawn, each frame over the base
frame of the same name, else its default frame; grounded does not apply; previews draw the pair.
`[anim.<name>]` holding only `like = "<id>"` plays as that sprite's animation of the same name:
its frame names, lengths and looping. The frames are this sprite's own.
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
`unoutlined = ["w"]` at the top of a file: pixels of those keys (smoke, sparks) take no outline;
  the outline rule passes them and `outline = "auto"` draws none around them.
"""

_PALETTE = """\
A key is one printable ASCII character except . " ' \\ and space, so a palette holds up to 90
colours. Removing or renaming a key breaks every sprite that uses it: check reports each use as
E104 and build writes nothing until they are fixed.
"""

_COMMANDS = """\
COMMANDS
sprite new <id> --canvas <class> [--dir <subdir>] [--runs]
                                                    write a blank sprite file to draw in; --runs
                                                    starts it as runs, not a grid of dots
sprite check [<file>...]                            list problems; fix them until it prints `ok`
sprite show <id>... [--frame <name>] [--all]        print the finished grid as text, with row and
                                                    column numbers; the default frame unless told
sprite preview <id>... [--grid]                     write one image of those sprites and print its
                                                    path; it is drawn even with outline problems;
                                                    --grid labels every 4th row and column
sprite preview <id> --on <other-id>                 the sprite standing on another sprite, as in
                                                    the game
sprite preview <id>... --anim <name>                the animation's frames in play order with their
                                                    lengths, and a GIF that plays it for each id
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
        return "EXPORTS  none configured\n" + _SELECTION
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
    return "".join(line + "\n" for line in lines) + _SELECTION


# How an `[[export]]` table says which sprites it takes.
_SELECTION = """\
A target exports every sprite unless its [[export]] table in sprite-tool.toml selects some:
  `canvases = ["unit"]` by class, `include = ["gear_*"]` and `exclude = ["sample_*"]` by id pattern.
"""


def _files(target: ExportTarget) -> str:
    """What `sprite build` writes for `target`, as the exporters name the files,
    and which sprites it takes when it does not take them all."""
    name = target.name
    if target.type == "frames":
        files = (
            "<id>.png (the default frame), <id>__<frame>.png when a sprite has several frames, "
            f"{name}.json (size, anchor, scale, bounds, animations)"
        )
    elif target.type == "phaser":
        files = (
            f"{name}.png, {name}.json, {name}.anims.json; frames are named <id>/<frame>, "
            f"animations <id>/<anim>; {name} is the texture key"
        )
    else:
        files = f"{name}.png, {name}.json (the index), one <id>.tres per sprite"
    selection = _selection(target)
    return f"{files}; only {selection}" if selection else files


def _selection(target: ExportTarget) -> str:
    """`canvases unit, map; exclude sample_*`, or nothing for a target that takes every sprite."""
    keys = (
        ("canvases", sorted(target.canvases or ())),
        ("include", target.include or ()),
        ("exclude", target.exclude),
    )
    return "; ".join(f"{key} {', '.join(values)}" for key, values in keys if values)
