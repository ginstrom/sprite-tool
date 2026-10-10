# sprite-tool design

- **Date:** 2026-10-10
- **Revised:** 2026-10-10, after a review of the finished tool: project
  discovery from above, id rules, W003, de-duplicated outline faults, and
  preview naming and behaviour (4.1, 4.5, 4.6, 4.8).
- **Status:** Ready for planning. No blocking questions; assumptions and
  non-blocking questions are listed in [section 8](#8-open-questions-and-assumptions).

## 1. Purpose

`sprite-tool` is a small command-line tool that turns text sprite definitions
into game-ready pixel art for 2D turn-based games. It is built to be driven by
a coding agent.

**Problem.** When an agent draws each sprite with a one-off script, it
re-decides the palette, outline style, canvas size and proportions on every
request. The sprites drift apart visually, and every request spends tokens on
regenerating a whole script.

**Outcome.** The tool owns everything that must stay consistent (palette,
canvas sizes, style checks, packing, engine metadata, previews). The drawing
stays open: each sprite is a small text file holding a character grid, which
an agent writes or edits per request. Art lives as diffable text in the game
repository, and a palette change re-renders everything with one command.

**When not to use it.** For a game jam or a handful of placeholder sprites,
one-shot generation is still cheaper than the setup.

## 2. Requirements and scope

### Functional requirements

| ID | Requirement |
|---|---|
| R1 | A project has one **palette file** mapping single-character keys to colours. All sprites draw only from it. |
| R2 | A project config defines named **canvas classes** (for example `unit`, `tile`), each with its own fixed size, an anchor point, a display scale and optional style rules. Classes of different sizes (32x32 units, 16x16 tiles) coexist in one project, one palette and one atlas. |
| R3 | Each sprite is one **text file**: a canvas class, one or more frames given as character grids, and optional animations. The tool contains no sprite definitions. |
| R4 | A frame can be **derived** from another frame (row overrides, shift, horizontal flip) so an animation does not repeat a full grid per frame. |
| R5 | A sprite can declare **palette-swap variants** (for example team colours) that render as additional sprites. |
| R6 | `check` reports **unknown palette keys, wrong dimensions, and style-rule violations** with file, line and column. It also checks existing PNG files for off-palette pixels and wrong dimensions. |
| R7 | `build` renders every sprite and writes each configured **export target**: loose frame PNGs, a Phaser atlas, and a Godot atlas with `SpriteFrames` resources. |
| R8 | Atlas export **packs** all frames into one sheet deterministically, with padding between frames. |
| R9 | `preview` writes an **upscaled PNG** of one sprite (all frames, optional pixel grid), optionally standing on a tile sprite, and a **contact sheet** of all sprites, so an agent can look at the result. |
| R10 | `new` scaffolds a blank sprite file for a canvas class; `import` converts an existing PNG into a sprite file. |
| R11 | `guide` prints a compact reference: file format, the project's palette legend and its canvas classes. This is the only thing an agent needs to read before drawing. |
| R12 | `init` scaffolds a project (config, starter palette, one example sprite). |

### Quality constraints

| ID | Constraint |
|---|---|
| Q1 | **Deterministic output.** The same inputs produce byte-identical PNG, JSON and `.tres` files, so generated files can be committed and diffed. |
| Q2 | **Token-friendly output.** Success prints one summary line. Each problem is one line. No banners, progress bars or colour codes when stdout is not a terminal. |
| Q3 | **Thin.** One runtime dependency (Pillow). No plugin system, no GUI, no drawing primitives. |
| Q4 | **Safe writes.** The tool only creates, overwrites or deletes files it generated itself (tracked by a manifest per output directory). |
| Q5 | A full build of 200 sprites completes in under 2 seconds on a laptop. |

### Non-goals

- Drawing helpers (lines, fills, shading, auto-outline). The agent writes the grid.
- An image editor, a GUI, or a watch mode.
- Trimming frames to their opaque bounding box. Frames always export at full
  canvas size; that is what keeps proportions consistent.
- Tilemap or level export, nine-slice metadata, collision shapes.
- Rotation or advanced bin packing. Sprites are small and near-uniform.
- Engines other than Godot 4 and Phaser. The loose-PNG target works anywhere.
- Changing either game to consume the tool. That is separate work in each game repository.

### Acceptance criteria

| ID | Criterion | Covers |
|---|---|---|
| A1 | In an empty directory, `sprite init` followed by `sprite build` exits 0 and writes at least one PNG. | R1, R2, R3, R7, R12 |
| A2 | Changing one colour in the palette and re-running `sprite build` changes the pixels of every sprite that uses that key and nothing else. | R1, R7 |
| A3 | A grid with one row too long, one unknown key, and a missing outline pixel makes `sprite check` exit 1 and print three lines, each with the correct `file:line:col`. | R6 |
| A4 | A two-frame animation whose second frame is defined with `from` + `rows` renders identically to the same frame written as a full grid. | R4 |
| A5 | A sprite with a `red` variant produces sprite `<name>_red` in every export target, with swapped colours. | R5 |
| A6 | The Phaser export loads with `this.load.atlas` and `this.load.animation` in Phaser 4, and frames show the expected art. | R7, R8 |
| A7 | The Godot export loads in Godot 4.7 as a `SpriteFrames` resource with the expected animation names and frame counts. | R7, R8 |
| A8 | Running `sprite build` twice produces byte-identical output directories. | Q1 |
| A9 | `sprite preview warrior` writes one PNG at the configured scale and prints only its path. | R9, Q2 |
| A10 | `sprite import` on a canvas-sized PNG whose colours are all in the palette writes a sprite file that renders back to the identical image. | R10 |
| A11 | `sprite check some.png --canvas unit` reports off-palette pixels by coordinate and a size mismatch. | R6 |
| A12 | After a sprite is deleted, `sprite build` removes its generated files and leaves unrelated files in the output directory untouched. | Q4 |
| A14 | A project with a 32x32 `unit` sprite and a 16x16 `tile` sprite builds; both appear in one atlas at their own sizes, and a 16-wide row in the unit sprite is reported as E103. | R2, R8 |
| A15 | `sprite preview warrior --on ground_light` writes one PNG showing the unit on the tile, each at its class's display scale. | R9 |
| A13 | `sprite guide` output for the example project is under 60 lines. | R11, Q2 |

## 3. Current system

The repository is new and empty apart from this design. There is no existing
code to fit. The facts below were inspected in the two sibling game
repositories that will consume the tool (paths are on the author's machine,
outside this repository).

**`~/play/fantasy-tactics` (Godot 4.7, GDScript)**

- Placeholder art is 11 loose PNGs under `assets/art/placeholders/`, taken
  from two CC0 packs. Unit and tile canvases are 16x16; four unit sprites were
  trimmed to smaller sizes (10x9 to 12x13).
- `scripts/presentation/sprite_catalog.gd` preloads each PNG as a `Texture2D`
  by stable name (`player_warrior`, `enemy_goblin`, `ground_light`, ...).
- Sprites and tiles are drawn at an integer 4x scale (`Vector2(4, 4)`) with
  nearest-neighbour filtering (`default_texture_filter=0`).
- `assets/sprites/` exists and is empty (`.gitkeep`), reserved for final art.
- Its placeholder README records that mismatched canvas sizes already caused a
  rendering bug that needed manual trimming.

**`~/play/yomi` (Phaser 4, TypeScript, Vite)**

- Five loose PNGs under `public/assets/sprites/`, copied from the same packs.
- `src/scenes/BattleScene.ts` loads one image per unit kind
  (`assets/sprites/<kind>.png`), draws it with origin `(0.5, 1)` (bottom
  centre), and flips it horizontally for facing. Sprites are drawn facing right.
- `pixelArt: true` is set in `src/main.ts`.
- The dev toolchain runs Node inside a Podman container. Python is not part of it.

**Machine:** Python 3.11, `uv` 0.12 and Pillow 12 are available.

**Implications for this design**

- Both games draw 16 px art at 4x today, giving a 64 px cell. The author has
  chosen **32x32 for character sprites and 16x16 for environment tiles**.
  The `init` template defines `unit` as 32x32 (anchor bottom-centre) and
  `tile` as 16x16 (anchor top-left).
- Both games load loose PNGs by stable name today, so the loose-PNG target is
  the drop-in path. Atlas targets are for animation later.
- Neither game should need Python at build time. Generated files are
  committed to the game repository (see [section 6](#6-consequences)).

## 4. Proposed behavior

### 4.1 Project layout in a game repository

The art sources live in the game repository, in one directory:

```
sprites/                    # any name; holds sprite-tool.toml
  sprite-tool.toml          # project config
  palette.toml              # the palette
  units/warrior.sprite.toml
  units/goblin.sprite.toml
  tiles/ground_light.sprite.toml
  .preview/                 # preview PNGs (gitignored)
```

Commands find the project by walking up from the current directory to the
first `sprite-tool.toml`, or take `--project <dir>`. When there is none at or
above the current directory, a single project up to three levels below it is
used (hidden directories and `node_modules` are not searched), so commands
work from the game repository's root; more than one is an error. Paths in
command output are relative to the current directory.

A sprite's **id** is its file stem (`warrior`) and must match `[a-z0-9_]+`,
as must a variant name, since both end up in file names and engine keys.
Subdirectories are only for organisation. Two files with the same stem are an
error, and so is an id of the form `<other id>__<frame>` that would export to
the same loose PNG as a frame of another sprite.

### 4.2 Palette file (R1)

```toml
# palette.toml
[colors]
k = { hex = "#1a1c2c", name = "outline" }
w = "#f4f4f4"
s = { hex = "#e8b796", name = "skin" }
S = { hex = "#c28569", name = "skin shadow" }
b = { hex = "#3b5dc9", name = "team mid" }
B = { hex = "#29366f", name = "team dark" }
r = "#b13e53"
R = "#5d275d"
```

- A key is exactly one printable ASCII character. Not allowed: `.`,
  whitespace, `"`, `'`, `\`.
- `.` is always fully transparent and is not declared.
- A value is a hex string (`#rrggbb` or `#rrggbbaa`) or a table with `hex` and
  an optional `name`. Names appear in `sprite guide`.
- Two keys with the same colour is a warning, not an error.

### 4.3 Project config (R2, R7)

```toml
# sprite-tool.toml
version = 1
palette = "palette.toml"

[canvas.unit]
size = [32, 32]          # width, height in pixels
anchor = [16, 32]        # pixel point exported as the pivot; here bottom centre
display_scale = 2        # how much the game enlarges this class; default 1
outline = ["k"]          # optional style rule, see 4.6
grounded = true          # optional style rule, see 4.6

[canvas.tile]
size = [16, 16]
anchor = [0, 0]
display_scale = 4

[preview]
scale = 6                # default upscale for `sprite preview`
background = "#3a3a3a"

[[export]]
type = "frames"
out = "../assets/sprites"

[[export]]
type = "phaser"
out = "../public/assets/sprites"
name = "atlas"           # atlas.png, atlas.json, atlas.anims.json

[[export]]
type = "godot"
out = "../assets/sprites"
name = "atlas"
res_path = "res://assets/sprites"   # where `out` sits inside the Godot project
```

Each canvas class has its own size, so one project mixes sizes freely. A
sprite's size comes only from its class; there is no per-sprite size.

`display_scale` records the integer factor the game draws that class at. The
tool never resizes exported art. It uses the value in previews (4.8) and
writes it to the Godot index file (4.7) so the game can read it instead of
hard-coding it. In the template, a 16 px tile at 4x and a 32 px unit at 2x
both cover a 64 px cell.

All paths are relative to the config file. `[[export]]` may appear any number
of times, including zero. Unknown keys anywhere in the config are an error
(this catches typos).

### 4.4 Sprite file (R3, R4, R5)

The example is drawn on a 16x16 canvas to keep it short. A real `unit`
sprite has 32 rows of 32 characters.

```toml
# units/warrior.sprite.toml
canvas = "unit"

[frames]
idle_0 = """
................
................
.....kkkkkk.....
....kwwwwwwk....
....kwsssswk....
....kskssksk....
....kssssssk....
.....kSSSSk.....
....kkbbbbkk....
...kbkbbbbkbk...
...kskbbbbksk...
...kskBBBBksk...
....kkbbbbkk....
....kbbkkbbk....
....kbBk.kbBk...
....kkkk.kkkk...
"""

[frames.idle_1]
from = "idle_0"
rows = { 5 = "....kssssssk...." }     # blink

[anim.idle]
frames = ["idle_0", "idle_1"]
ms = 400                 # duration of each frame
loop = true              # default true

[variants.red]
swap = { b = "r", B = "R" }
```

**Frames.** `[frames]` holds one entry per frame, in file order. The first
frame is the sprite's **default frame**. A frame name matches
`[a-z0-9_]+`. A frame is either:

- a **grid**: a multi-line string, one line per pixel row, one character per
  pixel. It must have exactly the canvas height in lines and the canvas width
  in characters per line. Trailing whitespace on a line is an error. The
  newline directly after the opening `"""` is not a row (standard TOML).
- a **derived frame**: a table with `from` (required, another frame in the
  same file) and any of the operations below, applied in this fixed order:

  1. `rows`: a table from zero-based row index to a full replacement row.
  2. `shift = [dx, dy]`: move all pixels; pixels moved off the canvas are
     dropped and vacated pixels are transparent.
  3. `flip = true`: mirror horizontally.

  `from` may point at another derived frame. A cycle is an error.

**Animations.** `[anim.<name>]` lists frame names and a per-frame duration in
milliseconds. Animations are optional; a sprite with none is a set of still
frames.

**Variants.** `[variants.<name>]` with `swap` (a table from palette key to
palette key) renders an extra sprite with id `<sprite>_<variant>`, with the
same frames and animations. Swaps apply once, simultaneously (`{a="b", b="a"}`
exchanges the two). A variant id that collides with another sprite id is an
error.

**Per-sprite rule overrides.** A sprite may set `outline = false` or
`grounded = false` at top level to opt out of a canvas rule. Effects, items
and projectiles need this.

### 4.5 Commands

All commands share: `--project <dir>`, exit code `0` success, `1` check
failures, `2` usage or config error.

| Command | Behavior | Output on success |
|---|---|---|
| `sprite init [dir]` | Write `sprite-tool.toml`, `palette.toml`, one example sprite and a `.gitignore` for `.preview/`. Refuses if `sprite-tool.toml` exists. | `created <dir> (3 files)` |
| `sprite guide` | Print the format reference, palette legend (key, hex, name) and canvas classes with their rules. | The guide |
| `sprite new <id> --canvas <class> [--dir <subdir>]` | Write a sprite file with one all-transparent frame named `main`. Refuses to overwrite. | The path |
| `sprite check [paths...]` | Check all sprite files, or only the given files. `.png` paths are checked as images and need `--canvas <class>`. | `ok: 12 sprites, 31 frames` |
| `sprite preview [id...] [--scale N] [--grid] [--on <tile-id>] [--sheet]` | Write one image of the given ids to `.preview/` (names in 4.8). With no id or with `--sheet`, write `.preview/sheet.png`. Runs `check` on the sprites involved first; style problems (E106, E201, E202) are printed and the image is still written. | One path per line |
| `sprite build [--check]` | Run `check` on everything, then write every export target. With `--check`, write nothing and exit 1 if any generated file is missing or differs. | `built: 12 sprites, 31 frames, 3 targets` |
| `sprite import <png> --canvas <class> [--id <id>] [--scale N] [--snap]` | Write a sprite file from a PNG. Refuses to overwrite. | The path |

`sprite build` never writes partial output: if `check` fails, no file is
touched. A blank sprite (W003) is not a failure; it is left out of the build.

### 4.6 Checks (R6)

Each problem is one line on stdout:

```
units/warrior.sprite.toml:9:14: E104 unknown palette key 'x'
```

Line and column point into the sprite file (1-based). `E` codes fail the
check; `W` codes are printed but do not change the exit code. The run ends
with one summary line, for example `2 errors, 1 warning in 2 files`.

| Code | Problem |
|---|---|
| E001 | File is not valid TOML, or has an unknown or wrongly typed field. |
| E002 | Palette invalid: bad key, bad hex value. |
| E003 | Duplicate sprite id (including variant ids), or an id that exports to the same loose PNG as another sprite's frame. |
| E101 | Unknown canvas class. |
| E102 | Wrong row count for the canvas. |
| E103 | Wrong row width, or trailing whitespace. Reported per row. |
| E104 | Unknown palette key. Reported per pixel, at most 10 per frame, then a count. |
| E105 | Bad frame reference in `from` or `anim`, bad `rows` index, or `from` cycle. |
| E106 | Frame is fully transparent. |
| E107 | `swap` names a key not in the palette. |
| E201 | Outline rule violated at a pixel. At most 10 per frame, then a count. |
| E202 | Grounded rule violated. |
| E301 | PNG size does not match the canvas. |
| E302 | PNG pixel colour not in the palette. Reported as `file.png:x,y`. At most 10 per file, then a count. |
| E401 | `build --check`: generated file missing or stale. |
| W001 | Two palette keys share one colour. |
| W002 | Sprite has frames not used by any animation, when it declares at least one animation. |
| W003 | Sprite is blank: every frame is fully transparent, as `sprite new` writes it. It is left out of the build. |

E106 is for an empty frame in a sprite that has drawn frames. An outline
fault that a derived frame only carries over from its `from` frame is
reported once, in the frame it comes from.

**Outline rule** (`outline = ["k", ...]` on a canvas class). Every
non-transparent pixel that touches a transparent pixel on one of its four
sides must use one of the listed keys. The area outside the canvas counts as
transparent. This is checked on the final frame, after derivation and after
variant swaps (a swap that recolours the outline to a non-listed key fails).

**Grounded rule** (`grounded = true`). The bottom row of every frame has at
least one non-transparent pixel. This keeps all units standing on the same
baseline.

**PNG checks.** A pixel with alpha 0 is transparent whatever its RGB. Any
other pixel must match a palette colour exactly, including alpha.

### 4.7 Export targets (R7, R8)

Every target exports all sprites, including variants. Frames are always full
canvas size.

**`frames` — loose PNGs.**

- `<id>.png`: the default frame. Always written, so a game can refer to a
  sprite by a stable name whether or not it later gains frames.
- `<id>__<frame>.png`: every frame, written only when the sprite has more
  than one frame.

**`phaser` — atlas for Phaser 3/4.**

- `<name>.png`: the packed sheet.
- `<name>.json`: Phaser "JSON Hash" atlas. Frame key is `<id>/<frame>`. Each
  entry has `frame` (`x`, `y`, `w`, `h`), `rotated: false`, `trimmed: false`,
  `spriteSourceSize`, `sourceSize`, and `pivot` (anchor divided by canvas
  size). `meta` has `image`, `size`, `scale: "1"` and `app: "sprite-tool"`.
  No version or timestamp.
- `<name>.anims.json`: Phaser animation JSON (`{"anims": [...]}`), one entry
  per sprite animation. Animation key is `<id>/<anim>`. Each frame entry has
  `key` (the atlas name), `frame` and `duration` in ms; `repeat` is `-1` for
  looping animations and `0` otherwise.

**`godot` — atlas for Godot 4.**

- `<name>.png`: the packed sheet.
- `<id>.tres`: one text `SpriteFrames` resource per sprite. It references the
  sheet as `ExtResource` at `<res_path>/<name>.png` and has one `AtlasTexture`
  sub-resource per frame. Each sprite animation becomes a `SpriteFrames`
  animation with the same name, `speed = 1000 / ms`, and `loop` as declared.
  A sprite with no animations gets one animation named `default` holding all
  frames at speed 1.
- `<name>.json`: a plain index, `{"<id>": {"anchor": [x, y], "size": [w, h], "display_scale": n,
  "frames": {"<frame>": [x, y, w, h]}}}`, because `SpriteFrames` cannot carry
  an anchor.
- The tool does not write `.import` files or `uid`s. Godot creates those on
  first import, and they belong to the game repository.

**Packing.** One shelf packer for both atlas targets:

1. Order frames by height descending, then sprite id, then frame order in the file.
2. Place left to right on a shelf; start a new shelf when the next frame
   would pass the sheet width.
3. Sheet width is the smallest power of two, at least 64, that makes the
   sheet no taller than it is wide. Sheet height is the used height (not
   rounded up).
4. `padding` (default 1) transparent pixels separate frames and the sheet edge.

Identical frames are not merged. The order is fully determined by the inputs.

**Manifest and cleanup (Q4).** Each output directory gets
`.sprite-tool-manifest.json` listing the files the tool wrote there, by
target. On build, files listed in the old manifest and not produced this time
are deleted. Before writing a file that exists and is not in the manifest, the
build stops with exit 2 and names the file. This is what happens the first
time a target points at a directory holding hand-placed PNGs with the same
names; `sprite build --adopt` takes ownership of those files.

Two targets may share an output directory if they produce no file in common;
otherwise it is a config error (exit 2). The example config in 4.3 shows
`frames` and `godot` sharing a directory, which is valid.

### 4.8 Previews (R9)

- `sprite preview <id>` renders all frames of the sprite left to right,
  nearest-neighbour upscaled by `scale`, on the configured background, with a
  gap between frames. Variants of the sprite follow on further rows.
- `--grid` draws one-pixel lines between art pixels and marks every fourth
  row and column in the margin with its zero-based index, so a viewer can name
  a pixel by `row, col`. Those are the same indices used by `rows` and by
  check messages.
- `--on <tile-id>` draws each requested sprite's default frame standing on
  the named sprite, the way the game would: each is enlarged by its own
  class's `display_scale` times a common factor (`--scale`, default 2), and
  the sprite's anchor is placed at the bottom-centre of the tile. This is the
  check that characters and tiles read well together. `--grid` is ignored
  with `--on`.
- The contact sheet shows every sprite's default frame at its class's
  `display_scale`, grouped by
  canvas class and sorted by id, with the id under each sprite. It is the
  consistency check: everything side by side at one scale.
- Several ids give one image, each sprite's preview under the one before, so
  a new sprite can be compared with an existing one in a single look.
- File names say what kind of preview it is, so one kind does not overwrite
  another: `<ids>.plain.png`, `<ids>.grid.png`, `<ids>.on-<tile-id>.png` and
  `sheet.png`, where `<ids>` is the ids joined with `+` (`kobold+warrior`).
- A sprite with style problems only (E106, E201, E202) is still drawn; the
  problems are printed before the path and the exit code is 0. Seeing the
  sprite is how those problems get fixed. Any other error stops the preview.
- Preview files go to `.preview/` in the project and are not committed.
  Previews are for looking, so they are exempt from Q1.

### 4.9 Import (R10)

`sprite import` reads a PNG and writes a single-frame sprite file.

- `--scale N` (integer, default 1) enlarges the PNG by nearest neighbour
  first. `--scale 2` brings the current 16 px placeholders up to the 32 px
  canvas as a starting point for redrawing.
- If the PNG is smaller than the canvas, it is placed so its bottom-centre
  sits on the canvas anchor (for an anchor of `[0, 0]`, top-left). If it is
  larger in either dimension, the import fails with E301.
- Each pixel maps to the palette key with exactly that colour. If any pixel
  has no exact match, the import fails and lists them as E302.
- With `--snap`, unmatched pixels map to the nearest palette colour (squared
  distance in RGB; alpha below 128 becomes transparent), and the command
  prints one line per distinct source colour, `#aabbcc -> k (#1a1c2c) x14`.
- The result is not checked against style rules; run `sprite check` next.

### 4.10 Agent workflow

The intended loop for an agent asked to "add a kobold":

1. `sprite guide` (once per session).
2. `sprite new kobold --canvas unit --dir units`, then edit the grid.
3. `sprite check units/kobold.sprite.toml` until clean.
4. `sprite preview kobold warrior --grid` and read the PNG to compare against
   an existing sprite. This works before step 3 is clean, as long as the
   grid has the right size and keys.
5. `sprite build`.

Editing an existing sprite is an edit to a few rows of text followed by steps
3 to 5.

## 5. Technical design

### 5.1 Stack

- Python, minimum 3.11 (`tomllib` is in the standard library).
- One runtime dependency: Pillow, for PNG read/write and scaling.
- `argparse` for the CLI. No CLI framework.
- Packaged with `pyproject.toml` (hatchling backend), console script
  `sprite = "sprite_tool.cli:main"`.
- Development and tests through `uv`; `pytest` as the only dev dependency.
- Installed in a game checkout with
  `uv tool install git+https://github.com/ginstrom/sprite-tool`.

### 5.2 Proposed repository layout

```
pyproject.toml
Makefile                    # make test, make check
README.md
AGENTS.md
src/sprite_tool/
  cli.py                    # argument parsing, command dispatch, exit codes
  project.py                # find and load sprite-tool.toml and palette.toml
  model.py                  # dataclasses shared by all modules
  spritefile.py             # parse *.sprite.toml, resolve derived frames, track source positions
  check.py                  # all checks; returns Problem list
  render.py                 # resolved frame + palette -> RGBA image
  pack.py                   # shelf packer
  preview.py                # sprite preview and contact sheet
  importer.py               # PNG -> sprite file
  manifest.py               # manifest read/write, stale-file cleanup, ownership check
  guide.py                  # text for `sprite guide`
  export/
    frames.py
    phaser.py
    godot.py
  templates/                # files written by `sprite init`
examples/demo/              # a complete small project; also the golden-test fixture
tests/
docs/designs/sprite-tool.md
```

### 5.3 Data model (`model.py`)

```python
@dataclass(frozen=True)
class Color:      key: str; rgba: tuple[int, int, int, int]; name: str | None

@dataclass(frozen=True)
class Canvas:     name: str; width: int; height: int; anchor: tuple[int, int]
                  outline: frozenset[str] | None; grounded: bool

@dataclass(frozen=True)
class Frame:      name: str; rows: tuple[str, ...]     # resolved: full grid, keys only

@dataclass(frozen=True)
class Anim:       name: str; frames: tuple[str, ...]; ms: int; loop: bool

@dataclass(frozen=True)
class Sprite:     id: str; source: Path; canvas: Canvas
                  frames: tuple[Frame, ...]; anims: tuple[Anim, ...]
                  outline: bool; grounded: bool          # after per-sprite overrides

@dataclass(frozen=True)
class Problem:    path: Path; line: int; col: int; code: str; message: str

@dataclass(frozen=True)
class Placement:  sprite_id: str; frame: str; x: int; y: int; w: int; h: int
```

A variant is expanded into an ordinary `Sprite` (with swapped rows and id
`<sprite>_<variant>`) before checks and export. Nothing downstream knows about
variants.

### 5.4 Pipeline and boundaries

```
project.load ─► spritefile.load_all ─► check.run ─► render ─► pack ─► export/*
   config,          Sprite list          Problem     images    Placement   files +
   palette        (variants expanded)     list                  list       manifest
```

- **`project`** owns config and palette validation. It is the only module
  that reads those two files.
- **`spritefile`** owns parsing and frame derivation. It returns sprites plus
  the problems it found (E001, E101–E105, E107). It never raises on bad art;
  it records a `Problem` and continues with the next frame or file. A frame
  that failed to resolve is omitted from the sprite and from later checks.
- **`check`** owns rules that need a resolved grid (E003, E106, E201, E202,
  W001, W002) and PNG checks (E301, E302).
- **`render`** is a pure function `(Frame, palette) -> PIL.Image`. It assumes
  checked input.
- **`pack`** is a pure function `(list of (sprite_id, frame, w, h), padding)
  -> (sheet_w, sheet_h, list[Placement])`. It knows nothing about images.
- **Exporters** each expose `export(sprites, images, target_config) ->
  dict[relative_path, bytes]`. They return content and never touch the disk.
  `cli` hands the dictionaries to `manifest`, which does the ownership check,
  writes files whose bytes changed, deletes stale files and rewrites the
  manifest. `build --check` uses the same dictionaries and only compares.

That exporter contract is the one extension point: adding an engine is one
new module returning a dictionary.

### 5.5 Source positions

Check messages need a line and column in the sprite file, and `tomllib` does
not report positions. `spritefile` does one extra pass over the raw text:
for each `[frames]` key, find the line of its opening `"""`; row *n* of that
grid is that line plus *n* plus 1, and the column is the character index plus
1. Rows given inside `rows = {...}` are reported at the line of the `rows`
key, column 1, with the row index in the message. If the pass cannot locate a
frame, the problem is reported at line 1 with the frame name in the message.
Positions are best effort; the frame name and row index are always in the
message text.

### 5.6 Determinism (Q1)

- PNGs are written by Pillow with fixed parameters (`optimize=False`, fixed
  `compress_level`, no metadata chunks) from RGBA mode.
- JSON is written with sorted keys, two-space indent, `\n` line endings and a
  trailing newline.
- `.tres` sub-resource ids are derived from sprite id and frame name, not
  from random ids.
- No timestamps, absolute paths or tool version appear in any generated file.
- File iteration always uses sorted order.

Byte-identical PNGs are only promised for one Pillow version. `pyproject.toml`
pins Pillow to a minor range and `uv.lock` is committed.

### 5.7 Godot resource format

The exporter writes this shape (format 3 text resource):

```
[gd_resource type="SpriteFrames" load_steps=4 format=3]

[ext_resource type="Texture2D" path="res://assets/sprites/atlas.png" id="1"]

[sub_resource type="AtlasTexture" id="warrior_idle_0"]
atlas = ExtResource("1")
region = Rect2(1, 1, 32, 32)

[sub_resource type="AtlasTexture" id="warrior_idle_1"]
atlas = ExtResource("1")
region = Rect2(34, 1, 32, 32)

[resource]
animations = [{
"frames": [{
"duration": 1.0,
"texture": SubResource("warrior_idle_0")
}, {
"duration": 1.0,
"texture": SubResource("warrior_idle_1")
}],
"loop": true,
"name": &"idle",
"speed": 2.5
}]
```

`load_steps` is the number of sub-resources plus two.

## 6. Consequences

- **Generated files are committed to the game repository.** Neither game's
  build then needs Python (yomi builds in a Node container; fantasy-tactics
  runs Godot directly). The cost is generated binaries in git history; at
  these sizes the files are tiny. `sprite build --check` in each game's `make check`
  guards against sources and outputs drifting apart.
- **Sprites are capped at one character per colour**, so a palette holds at
  most about 90 colours. That is a deliberate limit: small palettes are a
  large part of visual consistency.
- **A 32x32 unit grid costs about four times the tokens of 16x16 per full grid** (1,024
  characters a frame). Derived frames (R4) and variants (R5) matter more at
  this size: an animation should be one full grid plus small row overrides.
- **Adopting the tool changes unit sizes in both games.** Both currently
  scale 16 px art by 4 (fantasy-tactics in code, yomi through per-unit
  `displayHeight` in `BattleScene.ts`). With 32 px full-canvas unit frames,
  fantasy-tactics scales units by 2 instead, and yomi's display heights need
  resetting because its current sprites are trimmed to different sizes. Tiles
  stay 16 px, so tile drawing code is unaffected.
- **The outline rule is strict** (four-sided, single list of keys). It will
  reject some legitimate styles such as coloured outlines unless those keys
  are listed, or the sprite opts out. Strict by default is the point; the
  opt-out keeps it from blocking effects and items.
- **TOML for sprite files** costs a little punctuation compared with a custom
  format, and buys a standard parser, editor support and no format to
  document beyond the field list. The grid itself, which is nearly all of the
  file, is identical either way.
- **Security.** The tool reads local files and writes only inside configured
  output directories and `.preview/`. It runs no code from project files and
  makes no network calls. `import` reads PNGs through Pillow.
- **Compatibility.** `version = 1` in the config lets a later format change
  be detected and refused with a clear message. There is nothing to migrate.

## 7. Verification

Tests use `pytest`, run with `make test` (`uv run pytest`). No test needs a
display or network.

| Area | Test | Criteria |
|---|---|---|
| Init and build | `init` into a temp directory, `build`, assert exit 0 and expected files. | A1 |
| Palette re-render | Build `examples/demo`, change one colour, rebuild, compare pixels per sprite. | A2 |
| Parser and checks | One fixture file per error code; assert code, line and column. A combined fixture for A3. | A3 |
| Derived frames | `from` with `rows`, `shift`, `flip` and chains, compared against hand-written full grids; cycle detection. | A4 |
| Variants | Swap including a two-key exchange; id collision; outline rule after swap. | A5 |
| Packer | Property-style test: no overlaps, padding respected, everything inside the sheet, stable order under shuffled input. | R8 |
| Phaser export | Validate JSON structure and that each frame rectangle cut from the sheet equals the rendered frame. | A6 (structure) |
| Godot export | Parse the `.tres` text and check regions against rendered frames. If `godot` is on `PATH`, also load each `.tres` headlessly and assert animation names and frame counts; otherwise skip. | A7 |
| Determinism | Build twice into two directories; compare all bytes. | A8 |
| Preview | Output size equals canvas × scale × frame count plus gaps; stdout is exactly the path. | A9 |
| Import | Render a demo sprite, import the PNG, re-render, compare; `--snap` report; oversize failure. | A10 |
| PNG check | Fixture PNGs with one off-palette pixel and a wrong size. | A11 |
| Manifest | Delete a sprite and rebuild; pre-existing unowned file blocks the build; `--adopt`; shared-directory conflict. | A12 |
| Mixed sizes | Demo project has a 32x32 unit and a 16x16 tile; assert atlas regions, per-class dimension errors, and the `--on` preview size. | A14, A15 |
| Guide | Line count and presence of every palette key and canvas class. | A13 |
| Golden files | `examples/demo` output is committed under `tests/golden/`; `build --check` against it must pass. | Q1 |

**Manual acceptance (once, at the end).**

1. A6 in practice: point a `phaser` target at a scratch copy of yomi, load the
   atlas and play one animation.
2. A7 in practice: point a `godot` target at a scratch copy of
   fantasy-tactics, open the `.tres` in the editor and play one animation in
   an `AnimatedSprite2D`.
3. Agent trial: in a fresh session, ask an agent to add one new unit to
   `examples/demo` using only `sprite guide`. It should reach a clean `build`
   without reading this design or the source.

## 8. Open questions and assumptions

None of these block planning.

### Assumptions

- **Engines.** Godot 4.7 and Phaser 4, taken from the two sibling game
  repositories rather than stated by the author. If only one matters, drop
  the other exporter; nothing else changes.
- **Scale.** Units are drawn at 2x and tiles at 4x, so both cover the 64 px
  cell the games use today. That means a tile pixel is twice the size of a
  character pixel on screen. The alternative is one scale for both (a unit is
  then two tiles wide and tall). This is `display_scale` in the config, so it
  can change at any time without touching the tool or the art; see question 2.
- **Units face right** in source art and games flip them, as yomi does.
- **Phaser reads `pivot` from JSON Hash frames.** Believed true for Phaser 3
  and 4; the implementer should confirm against Phaser 4 during A6 and fall
  back to documenting `setOrigin` from the anchor if not.
- **The Godot text resource shape in 5.7** matches what Godot 4.7 writes
  today; the headless load test is the check.
- **Python is acceptable on the author's machine** as the tool's runtime even
  though neither game uses it.

### Decisions made by the author (2026-10-10)

- **Licence:** MIT.
- **Sprite size:** 32x32 for character sprites, 16x16 for environment tiles.
- **Palette:** each game has its own palette file. `init` writes a starter
  palette (Sweetie 16, free to use, keys chosen as mnemonics) that the game
  then edits.

### Questions (non-blocking)

1. **Larger units.** Bosses on a 48x48 or 64x64 canvas work today as another
   canvas class. Whether they need a different outline or grounded rule is an
   art decision for later.
2. **Pixel density.** With tiles at 4x and units at 2x, the two do not share
   a pixel size, which some find visually inconsistent. Drawing both at one
   scale fixes that but makes a unit cover 2x2 tiles, which changes board
   layout in the games. `sprite preview --on` exists to judge this by eye
   before committing to either.
