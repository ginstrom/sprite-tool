# Step 02: Sprite file parser

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.4, 4.6, 5.4, 5.5

## Objective

Parse `*.sprite.toml` files into `Sprite` objects: literal grids, derived
frames, animations, variants and per-sprite rule overrides, with a file line
and column for every problem found.

## Requirements and context

- **R3.** Each sprite is one text file: a canvas class, one or more frames as character grids, and optional animations.
- **R4.** A frame can be derived from another frame with row overrides, a shift and a horizontal flip.
- **R5.** A sprite can declare palette-swap variants that become additional sprites.
- **R6 (part).** Unknown palette keys and wrong dimensions are reported with file, line and column.
- **A4.** A two-frame animation whose second frame uses `from` + `rows` renders identically to the same frame written as a full grid.
- The parser never raises on bad art. It records a `Problem` and continues with the next frame or file. A frame that failed to resolve is left out of the sprite.

### Sprite file format

```toml
canvas = "unit"            # required; a canvas class from the config
outline = false            # optional; opt out of the canvas outline rule
grounded = false           # optional; opt out of the canvas grounded rule

[frames]
idle_0 = """
................
(one line per pixel row, one character per pixel)
"""

[frames.idle_1]
from = "idle_0"
rows = { 5 = "....kssssssk...." }
shift = [1, 0]
flip = true

[anim.idle]
frames = ["idle_0", "idle_1"]
ms = 400
loop = true                # default true

[variants.red]
swap = { b = "r", B = "R" }
```

- A sprite's id is the file stem before `.sprite.toml` (`warrior`). Subdirectories are only for organisation.
- Frame names match `[a-z0-9_]+`. Frames keep file order; the first is the default frame.
- **Grid.** Exactly canvas-height lines of exactly canvas-width characters. `.` is transparent; every other character must be a palette key. Trailing whitespace is an error. The newline right after the opening `"""` is not a row, and the newline before the closing `"""` does not add a row.
- **Derived frame.** `from` is required and names a frame in the same file, which may itself be derived. Operations apply in this fixed order:
  1. `rows`: zero-based row index to a full replacement row.
  2. `shift = [dx, dy]`: move all pixels; pixels moved off the canvas are dropped; vacated pixels are transparent.
  3. `flip = true`: mirror horizontally.
- **Animations.** `frames` (list of frame names, required), `ms` (positive integer, required), `loop` (boolean, default true).
- **Variants.** `swap` maps palette key to palette key and is applied once, simultaneously (`{a = "b", b = "a"}` exchanges the two). The variant is an ordinary `Sprite` with id `<sprite>_<variant>`, the same frames and animations, swapped rows, and `variant_of` set to the base id.

### Problems this step reports

| Code | Problem |
|---|---|
| E001 | Not valid TOML, or an unknown or wrongly typed field (including a bad frame name). |
| E101 | Unknown canvas class. |
| E102 | Wrong row count for the canvas. |
| E103 | Wrong row width, or trailing whitespace. One per row. |
| E104 | Unknown palette key. One per pixel, at most 10 per frame, then one line giving the remaining count. |
| E105 | Bad frame reference in `from` or `anim`, bad `rows` index, or a `from` cycle. |
| E107 | `swap` names a key (source or target) not in the palette. |

### Source positions (1-based)

`tomllib` reports no positions, so make one extra pass over the raw text.

- For each grid frame, find the line `L` of its opening `"""` (or `'''`). Row `n` is at line `L + n + 1`; a character's column is its index plus 1.
- E103 column: one past the expected width for a long row, one past the last character for a short row, the first trailing whitespace character for trailing whitespace.
- E102 is reported at line `L`, column 1.
- Rows inside `rows = {...}` are reported at the line of the `rows` key, column 1, with the row index in the message.
- If a frame cannot be located, report at line 1. The frame name (and the row index where relevant) is always in the message text.
- Worked example: with `idle_0 = """` on line 5, an unknown key at row 3, character index 13 is reported as `:9:14: E104 unknown palette key 'x'`.

## Dependencies and prerequisites

- **Step 01** provides, in `src/sprite_tool/model.py`:
  - `Canvas(name, width, height, anchor, display_scale, outline: frozenset[str] | None, grounded: bool)`
  - `Frame(name, rows: tuple[str, ...], line: int, literal: bool)`. For a literal grid, `line` is the file line of row 0 and `literal` is true. For a derived frame, `line` is the line of its definition (the `rows` key if present, else the frame's own key or table header) and `literal` is false. `0` means unknown.
  - `Anim(name, frames, ms, loop)`
  - `Sprite(id, source: Path, canvas, frames, anims, outline: bool, grounded: bool, variant_of: str | None)`
  - `Problem(path, line, col, code, message)`
  - `Project(root, palette_path, palette: dict[str, Color], canvases: dict[str, Canvas], preview, exports)`
- Step 01 also provides `project.load(root) -> tuple[Project, list[Problem]]`.

## Scope and implementation guidance

Proposed file: `src/sprite_tool/spritefile.py`.

- `discover(root: Path) -> list[Path]`: every `*.sprite.toml` under the project root, sorted.
- `load_all(project: Project, paths: Sequence[Path] | None = None) -> tuple[list[Sprite], list[Problem]]`: parse the given files (default: `discover`), expand variants, return sprites sorted by id.
- `Sprite.outline` is true when the canvas has an outline rule and the file does not set `outline = false`. `Sprite.grounded` likewise.
- Allowed top-level keys: `canvas`, `frames`, `anim`, `variants`, `outline`, `grounded`. Anything else is E001. Apply the same strictness inside frame, animation and variant tables.
- A grid with the wrong row count (E102) is not resolved, but still report E103 and E104 for the rows it has.
- A frame with any E102, E103 or E104 problem is left out of the sprite. A derived frame whose `from` chain reaches a failed or missing frame is also left out (E105 only for a missing name or a cycle, not for a parent that already has its own problem).
- An animation naming a frame that does not exist in the file is E105. If the frame exists but failed to resolve, drop the animation silently; the frame's own problem is enough.
- A file with an unknown canvas (E101) or invalid TOML (E001) yields no sprite.
- Variants are expanded from resolved frames. A variant with an E107 problem is not produced.
- Do not report duplicate ids here (E003 belongs to step 03). Return every sprite, even when ids clash.

### Exclusions

No outline, grounded, transparency or duplicate-id checks; no rendering; no CLI changes.

## Verification

`make test` (`uv run pytest`). Tests write fixtures under `tmp_path` or read
committed fixture files under `tests/fixtures/`; no network or display.
Proposed `tests/test_spritefile.py`:

- One fixture per code E001, E101, E102, E103 (long, short, trailing whitespace), E104, E105 (bad `from`, bad `anim` frame, bad `rows` index, cycle), E107. Assert code, line and column.
- The worked position example above.
- E104 cap: 12 unknown keys in one frame give 10 lines plus one count line.
- **A4:** `from` + `rows` resolves to the same `rows` tuple as a hand-written grid. Also `shift` (pixels dropped at the edge), `flip`, all three together in the fixed order, and a chain of two derived frames.
- Variants: simple swap; a two-key exchange; `variant_of` and id set correctly; animations carried over.
- `outline = false` and `grounded = false` set the `Sprite` flags.
- A file with one bad frame still returns the sprite with its good frames.
- `load_all` returns sprites sorted by id and finds files in subdirectories.

## Completion criteria

- [ ] `spritefile.load_all` and `discover` exist with the signatures above.
- [ ] Every code in the table has a test asserting line and column.
- [ ] A4 covered at the grid level.
- [ ] Bad input never raises.
- [ ] `make test` passes.
- [ ] Index status and completion log updated.
