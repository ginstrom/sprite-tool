# sprite-tool 0.3: fixes from the Yomi session

- **Date:** 2026-10-10
- **Status:** Ready for planning. No blocking questions; assumptions and
  non-blocking questions are in [section 8](#8-open-questions-and-assumptions).
- **Amends:** [sprite-tool.md](sprite-tool.md) (the base design). Requirement
  and criterion ids continue its numbering. Where the two disagree, this
  document wins; [section 6](#6-consequences) lists the base sections to bring
  in line.
- **Source:** `sprite-improve.md`, notes from one session that used
  sprite-tool 0.2.0 to redraw every sprite in Yomi. The file sits outside this
  repository (`~/play/sprite-improve.md`), so each point is restated here.

## 1. Purpose

Seven points came out of that session. Two of them made the user write a
generator script instead of sprite files, which is the thing the tool exists
to prevent: outlines had to be drawn by hand, and pixels could only be placed
by counting dots in a 32-character row. The others are smaller gaps: data the
game had to repeat by hand, a flag that reads wider than it is, no way to keep
a reference sprite out of the build, missing facts in `guide`, and a preview
scale that hides what the game will show.

The outcome is a 0.3.0 release in which an agent can draw a unit as a short
list of pixel runs with no outline, see it at game size, and have the game
read scale, anchor and bounds from a generated file.

## 2. Requirements and scope

### Functional requirements

| ID | Requirement | Feedback point |
|---|---|---|
| R13 | A sprite can set `outline = "auto"`. Its source holds the interior only and the tool adds the one-pixel outline. | 1 |
| R14 | A frame can place pixels by coordinate with `runs`: a row index mapped to `[column, "pixels"]` pairs. This works in a derived frame and, without `from`, as a whole frame on a transparent canvas. | 2 |
| R15 | The `frames` target writes a JSON index with, per sprite: canvas class, size, anchor, display scale, file names and the bounding box of its drawn pixels. The `godot` index gains the canvas class and bounding box. | 3 |
| R16 | `build --adopt` accepts sprite ids and then takes over only those sprites' files. Every adopted file is named in the output. | 4 |
| R17 | A sprite file can set `build = false`. It is checked and previewed like any sprite and is left out of every export. | 5 |
| R18 | `guide` states the palette key rules and size limit, what each configured export target writes and where, and what removing a palette key does. It documents R13, R14 and R17. | 6 |
| R19 | A sprite preview shows the game-size rendering beside the enlarged one, and `--scale display` draws at game size only. | 7 |

### Quality constraints

The base design's Q1 to Q5 still hold. Two are touched:

- **Q2 (one summary line).** `build --adopt` adds one line per adopted file
  before the summary. `AGENTS.md` gains this exception next to the one for
  `init`.
- **Q3 (thin).** No new dependency. The base non-goal "drawing helpers (lines,
  fills, shading, auto-outline)" loses auto-outline and keeps the rest.

**Compatibility.** Every 0.2.0 project loads and builds unchanged, apart from
the new index file in a `frames` target. `version = 1` in the config stays.

### Non-goals

- A `sprite outline` command that rewrites a grid. The per-sprite option keeps
  the source small and needs no second step after a shape edit.
- A canvas-wide auto-outline switch. Turning it on would double the outline of
  every hand-outlined sprite in the class.
- An `exclude` list in `sprite-tool.toml`. `build = false` says the same thing
  in the file it applies to.
- A column ruler in the file `sprite new` writes. `preview --grid` already
  labels every fourth row and column (inspected in `preview.py`); the guide
  will say so. Runs remove most of the need to count columns.
- Sprite data in the Phaser atlas files (see question 1).
- Changing Yomi to read the index. That is work in the Yomi repository;
  [section 6](#6-consequences) lists what it can then drop.

### Acceptance criteria

| ID | Criterion | Covers |
|---|---|---|
| A16 | An interior-only sprite with `outline = "auto"` on a class with `outline = ["k"]` passes `check`, and renders identically to the same sprite with the outline written by hand. | R13 |
| A17 | In that sprite, an interior pixel in column 0 is reported as E201 at its own line and column, with a message that names the canvas edge. | R13 |
| A18 | A frame given as `runs` with no `from` renders identically to the same frame written as a full grid. | R14 |
| A19 | A derived frame with `runs = { 9 = [[13, "ddsskh"]] }` differs from its `from` frame in exactly those six pixels. | R14 |
| A20 | A run that passes the right edge, and a run with an unknown key, are each reported in one line naming frame, row and column. | R14 |
| A21 | After `sprite build`, the `frames` directory holds `sprites.json`. The goblin entry has `canvas`, `size`, `anchor`, `display_scale`, `file`, and a `bounds` smaller than its canvas. | R15 |
| A22 | Changing `display_scale` in the config and running `sprite build --check` exits 1 naming `sprites.json`. | R15 |
| A23 | With unowned `warrior.png` and `goblin.png` in the output directory, `sprite build --adopt warrior` stops, naming `goblin.png`, and writes nothing. `--adopt warrior goblin` builds and prints one `adopted` line for each. | R16 |
| A24 | `sprite build --adopt nosuch` exits 2. | R16 |
| A25 | A sprite with `build = false` is counted by `sprite check`, drawn by `sprite preview <id>`, and has no file in any export directory or index. A fault in it fails `check`. | R17 |
| A26 | `sprite guide` for the demo names the forbidden key characters, the key limit, each export directory with its file pattern, and E104 for a removed key, in under 80 lines. | R18 |
| A27 | `sprite preview warrior` writes an image whose width is the enlarged frames plus the same frames at `display_scale`. `--scale display` writes only the game-size frames. | R19 |

## 3. Current system

All of this was inspected in the 0.2.0 source (commit `61fa765`) and in
`~/play/yomi`.

**What the feedback got right, and what is already there**

| Point | Finding |
|---|---|
| 1 | `check._outline_faults` only reports. Nothing writes an outline. The rule is four-sided and counts the canvas edge as transparent. |
| 2 | `spritefile._derived` accepts `from`, `rows`, `shift`, `flip`; `from` is required and a `rows` value is a full row. |
| 2 | `preview._frame_tile` already labels every fourth row and column under `--grid`. The guide does not mention it. |
| 3 | `export/frames.py` returns PNGs only. `export/godot.py` writes `anchor`, `size`, `display_scale` and atlas rectangles per sprite. `export/phaser.py` writes `pivot` per frame and nothing else about the class. Nothing writes bounds. |
| 3 | Yomi hard-codes `displayHeight: 96` (`src/scenes/BattleScene.ts`), `ITEM_ICON_SCALE = 2` (`src/scenes/itemIcons.ts`) and origin `(0.5, 1)`. |
| 4 | `--adopt` is a boolean that skips `manifest.check_ownership`. It only ever affects files the build is about to write (`Plan.unowned`), so `README.md` was never at risk. The observation is correct: the behaviour is narrow, and the flag does not say so or report what it took. |
| 5 | `spritefile.discover` takes every `*.sprite.toml`. There is no opt-out. Two files with one stem are E003. |
| 6 | A palette may hold any number of keys. A key is one printable ASCII character other than `.` `"` `'` `\` (`project._is_palette_key`), which allows 90. |
| 6 | A sprite that uses a removed key gets E104 per pixel and its frame is dropped; `build` then writes nothing. A `swap` naming it is E107. A canvas `outline` key missing from the palette is a config error (exit 2). |
| 6 | `guide` prints 58 lines for the demo and 65 for Yomi's 28-colour palette. A test holds the demo under 60. |
| 7 | `[preview] scale` is one number. The contact sheet and `--on` use `display_scale`; `sprite preview <id>` does not. |

**Relevant structure.** `Canvas.outline` is a `frozenset`, so the order of the
keys in the config is lost. `Sprite.outline` is a bool: whether the rule
applies. A `Frame` is either `literal` (written as a grid, with a file line
per row) or derived. Exporters return `{relative path: bytes}` with no link
from a file to the sprite it came from. The manifest's owned set is the union
of every target's list (`manifest._read_owned`).

## 4. Proposed behavior

### 4.1 Automatic outline (R13)

```toml
canvas = "unit"
outline = "auto"
```

`outline` at the top of a sprite file now takes `true` (default), `false`, or
`"auto"`. With `"auto"`:

- The outline key is the **first** key in the canvas class's `outline` list.
  A class with no `outline` rule, or an empty list, makes this E001:
  `outline = "auto" needs an outline rule on canvas class 'tile'`.
- Every transparent pixel that has a drawn pixel directly above, below, left
  or right of it becomes the outline key. This is one pass over the frame as
  written: new outline pixels do not grow further outlines. Diagonals do not
  count, so corners come out rounded.
- A transparent hole inside the shape is outlined too, as the rule already
  demands. A one-pixel hole fills completely.
- It runs once per frame, on the final interior: after `rows`, `runs`,
  `shift` and `flip`, and before variant swaps. A derived frame therefore
  edits its parent's interior, never its parent's outline.
- The outline rule is then checked as usual. The only fault an auto sprite
  can have is an interior pixel on the canvas edge, where there is no room
  for the outline. It is reported as E201 at that pixel:
  `'b' is on the canvas edge; with outline = "auto" keep the interior 1 pixel inside`.
- With `grounded`, the interior stops one row above the bottom and the
  outline supplies the bottom row.

Variants are unchanged: a swap that recolours the outline key to one not in
the class's list is still E201 for the variant.

### 4.2 Runs (R14)

```toml
[frames.idle_1]
from = "idle_0"
runs = { 9 = [[13, "ddsskh"]] }         # row 9, starting at column 13

[frames.main.runs]                      # a whole frame, no `from`
9  = [[13, "ddsskh"]]
10 = [[12, "dssssskh"], [24, "kk"]]
```

- `runs` maps a zero-based row index to a list of runs. A run is
  `[column, "pixels"]`: a zero-based column and one or more characters, each a
  palette key or `.`. It replaces exactly those pixels; `.` writes
  transparency, which is how a derived frame erases.
- Runs in a row apply in list order, so a later run wins an overlap.
- A frame table's operations now apply in the order `rows`, `runs`, `shift`,
  `flip`.
- `from` becomes optional. A frame table without it starts fully transparent.
  A table with none of `from`, `rows` and `runs` is E001:
  `frame 'x': needs from, rows or runs`.
- TOML inline tables are one line, so a frame with several rows uses the
  table form shown above, one row per line.

Problems:

| Case | Report |
|---|---|
| Row index not `0` to height − 1 | E105, as for `rows` |
| A value that is not a list of `[integer, string]` pairs, or an empty string | E001 |
| Column outside the canvas, or the run passes the right edge | E103 `frame 'main' row 9: run at col 30 is 6 wide, canvas is 32 wide` |
| Unknown key | E104 `unknown palette key 'x' in frame 'main' row 9, col 15` (the column on the canvas). Shares the frame's cap of 10. |

Each is reported at the line of that row's key in the table form, or the line
of `runs` in the inline form, column 1. A runs frame is not `literal`, so
style problems in it carry `row r, col c` in the message. Those are the same
numbers the author wrote.

### 4.3 Sprite data in exports (R15)

The `frames` target also writes `<name>.json`. `name` is now accepted on a
`frames` target and defaults to `sprites`.

```json
{
  "goblin": {
    "anchor": [16, 32],
    "bounds": [5, 10, 22, 22],
    "canvas": "unit",
    "display_scale": 3,
    "file": "goblin.png",
    "frames": {
      "main": { "bounds": [5, 10, 22, 22], "file": "goblin.png" }
    },
    "size": [32, 32]
  }
}
```

- One entry per exported sprite, variants included.
- `bounds` is `[x, y, width, height]` in canvas pixels, top-left origin: the
  smallest rectangle holding every pixel that is not `.`. A frame's `bounds`
  covers that frame; the sprite's covers all its frames, so a game placing
  something above a unit gets one number that does not move with the
  animation.
- `file` on the sprite is `<id>.png`. A frame's `file` is `<id>__<frame>.png`
  when the sprite has more than one frame, else `<id>.png`.
- Written through `manifest.json_bytes`, so keys are sorted and the file is
  deterministic.

The `godot` index gains two keys per sprite, `canvas` and `bounds` (the
sprite-level box). Its existing keys keep their shape.

`build --check` compares the index like any generated file, which is what
flags a config change the exports have not caught up with.

### 4.4 Adopt by id (R16)

`sprite build --adopt [id ...]`

| Form | Effect |
|---|---|
| no flag | As now: an existing file not in the manifest stops the build (exit 2). |
| `--adopt` | As now: every such file is overwritten and added to the manifest. |
| `--adopt warrior goblin` | Only files belonging to those ids are taken. Any other unowned file still stops the build, and nothing is written. |

- A file belongs to an id when its name up to the first `.` is the id, or
  starts with the id followed by `__`. That covers `warrior.png`,
  `warrior__idle_0.png` and `warrior.tres`. It does not cover
  `warrior_red.png`: a variant is named separately.
- Shared files (`atlas.png`, `atlas.json`, `sprites.json`) belong to no id and
  need the bare flag.
- Each id must be a sprite in this build. Otherwise exit 2:
  `error: unknown sprite id 'nosuch' (sprites: goblin, warrior, ...)`.
- After writing, one line per adopted file, before the summary, with the path
  as the user would type it:

  ```
  adopted ../public/assets/sprites/goblin.png
  adopted ../public/assets/sprites/warrior.png
  built: 8 sprites, 8 frames, 1 target
  ```

- The stop message becomes
  `<path> and 2 more already exist and were not written by sprite-tool (use --adopt <id>... for those sprites, or --adopt for all)`.
- Help text: `overwrite existing files the tool did not write: all of them, or only those of the given sprite ids`.
- `--check` still ignores `--adopt`.

### 4.5 `build = false` (R17)

```toml
canvas = "unit"
build = false
```

- Default `true`. Any other type is E001.
- The sprite and its variants are parsed, checked, listed by `check`, drawn by
  `preview` and shown on the contact sheet. A fault in it fails `check` and
  therefore `build`, like any sprite. Being checked is what was asked for.
- `build` leaves it out of every target and index, and out of the counts in
  the `built:` line. Exported files it had before are removed as stale.
- Its id is still its file stem and must be unique. A reference copy of a
  sprite the game also has needs its own name, for example
  `sample_warrior.sprite.toml`.

### 4.6 Guide (R18)

New or changed text, in the guide's existing sections:

- **Palette.** `A key is one printable ASCII character except . " ' \ and space, so a palette holds up to 90 colours.`
  and `Removing or renaming a key breaks every sprite that uses it: check reports each use as E104 and build writes nothing until they are fixed.`
- **Sprite file example.** One `runs` line in the derived frame, and the order
  comment renumbered (`rows`, `runs`, `shift`, `flip`).
- **Format notes.** The table form of `runs` for a whole frame; `build = false`.
- **Rules.** `outline = "auto"`: draw the interior only, one pixel inside the
  canvas edge.
- **Exports**, a new section generated from the config, one line per target:

  ```
  EXPORTS  sprite build writes these; do not edit them by hand
  frames  ../public/assets/sprites  <id>.png (the default frame), <id>__<frame>.png when a sprite
                                    has several frames, sprites.json (size, anchor, scale, bounds)
  ```

  The directory is shown relative to the project. A project with no targets
  prints `EXPORTS  none configured`.
- **Commands.** `preview --grid` gains "labels every 4th row and column";
  `build --adopt [<id>...]` is listed.

The line limit for the demo's guide rises from 60 to 80 (A13 in the base
design becomes A26 here).

### 4.7 Preview at game size (R19)

- `sprite preview <id>` without `--grid` or `--on`: each row (the sprite, then
  each variant) shows its frames enlarged by the preview scale, then a gap,
  then the same frames at the class's `display_scale`, top-aligned. The
  game-size frames are left out when the two scales are equal.
- `--scale` takes a positive integer or the word `display`. `display` uses
  each sprite's own class's `display_scale`, so the image holds only the
  game-size frames, and several ids of different classes each get their own
  scale.
- With `--on`, `--scale display` means a common factor of 1: the pair exactly
  as the game draws them.
- `--scale display --grid` is a usage error (exit 2). A grid at 2x or 3x
  cannot be read.
- File names are unchanged.

Image width for one sprite with `n` frames of width `W`, preview scale `s` and
display scale `d ≠ s`:
`2·MARGIN + n·W·s + (n−1)·GAP + GAP + n·W·d + (n−1)·GAP`. Height is unchanged,
set by the enlarged frames.

## 5. Technical design

Paths are relative to the repository root. Files marked *proposed* do not
exist yet.

### 5.1 Model (`src/sprite_tool/model.py`)

- `Canvas.outline_key: str | None`: the first key of the config's `outline`
  list; `None` with no rule or an empty list. Set in `project._load_canvas`.
- `Sprite.auto_outline: bool` and `Sprite.build: bool`. Variants inherit both
  through `dataclasses.replace`.
- `ExportTarget.name` is `"sprites"` by default for a `frames` target.

`Frame` is unchanged. A runs frame without `from` has `literal=False`,
`parent=None`.

### 5.2 Parsing (`src/sprite_tool/spritefile.py`)

- `_TOP_LEVEL_KEYS` gains `build`; `_FRAME_KEYS` gains `runs`.
- `outline` is parsed by a new helper returning `(applies, auto)`.
- `_Derived.parent` becomes `str | None` and gains
  `runs: dict[int, list[tuple[int, str]]]`. `apply` writes runs after rows.
  With no parent, `_resolve` starts from `canvas.height` rows of `.`.
- Run validation reuses `_RowCheck` for the E104 cap; it needs a way to check
  a fragment at a column offset without the width test.
- **Outline pass.** `_frames` resolves every frame on interior rows as today.
  Only then, for an auto sprite, each resolved frame's `rows` are replaced by
  `add_outline(rows, canvas.outline_key)`. Doing it earlier would let a
  derived frame inherit its parent's outline. `add_outline` is a pure function
  on row tuples and is the only new drawing code.
- Invariant: after parsing, `Frame.rows` is always the final grid that is
  checked, rendered and exported. Nothing downstream knows about runs or auto
  outlines, apart from the E201 wording in 5.3.

### 5.3 Checks (`src/sprite_tool/check.py`)

- `_outline_problems` uses the canvas-edge wording from 4.1 when
  `sprite.auto_outline` and the sprite is not a variant.
- No other change. `_inherited_faults` still holds: an edge fault moves with
  `shift` and `flip` exactly as a hand-drawn one does.

### 5.4 Exports

- `src/sprite_tool/export/index.py` (*proposed*): `bounds(rows)` returning
  `[x, y, w, h]`, `union(boxes)`, and `sprite_entry(sprite)` returning the keys
  both indexes share (`anchor`, `bounds`, `canvas`, `display_scale`, `size`).
  Bounds come from the text rows, not from images.
- `export/frames.py` adds `<name>.json` built from `sprite_entry` plus `file`
  and `frames`.
- `export/godot.py` builds its entry from `sprite_entry` plus its `frames`
  rectangles.
- `project._load_export` allows `name` for `frames`.
- The manifest key for a frames target changes from `frames` to
  `frames:sprites`, because `manifest.target_key` includes the name. Ownership
  is unaffected: owned files are the union across keys.

### 5.5 Build and adopt (`src/sprite_tool/cli.py`, `src/sprite_tool/manifest.py`)

- `--adopt` becomes `nargs="*"`, default `None`. `None` is no flag, `[]` is
  all, a non-empty list is those ids. `build` has no positional arguments, so
  this parses cleanly.
- `_build` filters `sprite.build` where it already filters blank sprites, and
  validates adopt ids against the sprites that remain.
- `manifest.check_ownership(plans, adopt_ids)` takes
  `frozenset[str] | None` and raises for unowned files not covered. A new
  `manifest.belongs_to(name, ids)` holds the naming rule from 4.4.
- `_build` collects each plan's `unowned` list before `manifest.apply`, and
  prints the `adopted` lines after it. The manifest module still does all
  writing.

### 5.6 Preview (`src/sprite_tool/preview.py`, `cli.py`)

- `sprite_preview` gains `display: bool`. When set and
  `scale != canvas.display_scale`, each row is its enlarged tiles followed by
  plain tiles at `display_scale`. Column positions are per row, since the two
  groups have different tile sizes.
- A new argparse type for `--scale` returns an `int` or the string
  `"display"`. `_preview` resolves it per sprite.

### 5.7 Guide, templates and demo

- `guide.py`: text from 4.6 and an `_exports(project)` section.
- `templates/sprite-tool.toml`: the `outline` comment says the first key is
  the one `outline = "auto"` draws with.
- `examples/demo/`: one new unit drawn with `[frames.main.runs]` and
  `outline = "auto"`, and one sprite with `build = false`. These put R13, R14
  and R17 under the golden test. The warrior stays as it is, since the
  template copy must match it.

## 6. Consequences

- **Golden files change** in all three targets: the new demo sprite, the
  frames index, the godot index keys and the frames manifest key. Run
  `make golden` once, in the commit that makes the last of those changes, and
  review the diff.
- **Games on 0.2.0** see `build --check` fail after upgrading until they
  rebuild, because of the new index file. If `sprites.json` already exists by
  hand in a `frames` directory, the build stops and needs one bare `--adopt`.
- **A sprite file that uses `runs`, `build` or `outline = "auto"`** is E001 on
  0.2.0. Games install by tag, so this only bites a checkout that has not
  updated its pin.
- **Auto-outline is now a drawing helper**, against the base design's
  non-goal. It is the one helper that enforces a rule the tool already owns,
  and without it the user left the tool for a script. Lines, fills and shading
  stay out.
- **A faulty `build = false` sprite blocks the build.** The alternative,
  ignoring its problems during `build`, needs the parser to report the flag
  for files too broken to yield a sprite, and makes `check` and `build`
  disagree. If a reference sprite stops fitting the palette, delete it.
- **Default previews get wider** by the game-size frames. The agent sees what
  the game shows without knowing to ask.
- **Base design sections to update** when this is implemented: 2 (non-goals,
  A9, A13), 4.3 (`name` on frames), 4.4 (frame tables, `outline`, `build`),
  4.5 (`build`, `preview` rows), 4.6 (E103, E104, E201 wording), 4.7 (frames
  and godot index), 4.8, 5.3. Also `README.md` (the `--adopt` section and
  command table), `AGENTS.md` (the output rule, `export/index.py` in the
  layout) and the version in `pyproject.toml`.
- **Yomi, afterwards** (not part of this work): load `sprites.json` and derive
  unit display height, icon scale, origin and the banner position from it;
  redraw sources as runs with `outline = "auto"`; rename the sample to
  `sample_warrior.sprite.toml` with `build = false`; move the pin to `v0.3.0`.

## 7. Verification

`make check`. Tests follow the existing constraints: no display, no network,
writes only under `tmp_path`.

| Area | Test | Criteria |
|---|---|---|
| Auto outline | `add_outline` on small grids: plain shape, hole, one-pixel hole, shape at the edge. An auto sprite against its hand-outlined twin, compared as rendered PNG bytes. E001 on a class with no rule. Edge-pixel E201 with line and column. Derived frame of an auto sprite edits the interior. Variant swap of the outline key still E201. | A16, A17 |
| Runs | Runs-only frame against a full grid. Derived frame changes only the run's pixels. `.` erases. Overlap, later wins. Order with `rows`, `shift`, `flip`. Each problem row in 4.2 with code, line and message, in both the inline and table forms. Table with no `from`, `rows` or `runs`. | A18, A19, A20 |
| Index | Structure and values of `sprites.json` for the demo; frame `file` for one-frame and several-frame sprites; sprite `bounds` is the union. Godot index has the two new keys and its old ones unchanged. `build --check` after a `display_scale` edit. `name` on a frames target; `frames` and `godot` both named `sprites` in one directory is a config error. | A21, A22 |
| Adopt | Manifest-level: `belongs_to` for id, `id__frame`, variant, shared file. CLI-level: the three forms in 4.4, the `adopted` lines, nothing written on a partial match, unknown id. | A23, A24 |
| `build = false` | Counted by `check`; previewed; absent from all three targets and both indexes; previously exported files removed; duplicate id still E003; fault fails `build`. | A25 |
| Guide | Presence of each fact in 4.6; exports section for zero, one and three targets; demo under 80 lines. | A26 |
| Preview | Image size with and without the game-size frames, for equal and unequal scales; `--scale display` for two ids of different classes; `--scale display --grid` exits 2; `--on --scale display`. | A27 |
| Golden and determinism | Existing tests, against regenerated golden files. | Q1 |

**Manual acceptance.** In a scratch copy of Yomi's `art/`, redraw one unit as
runs with `outline = "auto"`, using only `sprite guide`. It should reach a
clean `build` without a generator script, and the preview should show the unit
at 3x beside the 6x view.

## 8. Open questions and assumptions

Nothing here blocks planning.

### Assumptions

- **The first key of `outline` is the auto key.** Yomi and the demo list one
  key, so this is untested against a class with several.
- **Four-neighbour outlines are the wanted look.** The user's own script added
  a "1px `k` border" without saying which neighbours. Four-neighbour is the
  least that satisfies the rule; a square-cornered outline would need the
  author to draw the corner pixels.
- **Sprite-level `bounds` as the union of all frames** suits the banner case
  in the feedback. Per-frame boxes are there for anything else.
- **Reference sprites belong on the contact sheet.** If the sample clutters
  Yomi's sheet, hiding `build = false` sprites there is a one-line change.

### Questions (non-blocking)

1. **Phaser atlas users.** The Phaser target still carries only `pivot`. A
   game using it has no `display_scale` or bounds. Writing the same index as
   `<name>.sprites.json` there is a small addition; it is left out because no
   game uses the Phaser target yet.
2. **`sprite new --runs`.** A blank file in runs form (an empty
   `[frames.main.runs]` table) would be a better starting point than 32 rows
   of dots once runs are the usual way to draw. Worth deciding after the
   manual acceptance run shows which form an agent reaches for.
