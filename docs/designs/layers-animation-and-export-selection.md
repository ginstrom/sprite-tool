# sprite-tool 0.5: layers, animation and what a target exports

- **Date:** 2026-10-12
- **Status:** Ready for planning. No blocking questions; assumptions and
  non-blocking questions are in [section 8](#8-open-questions-and-assumptions).
- **Amends:** [sprite-tool.md](sprite-tool.md) (the base design) and follows
  [feedback-fixes.md](feedback-fixes.md) (release 0.3) and
  [text-view-and-runs-discovery.md](text-view-and-runs-discovery.md)
  (release 0.4). Requirement and criterion ids continue their numbering (the
  last were R23 and A35). Where this document and the base design disagree,
  this document wins; [section 6](#6-consequences) lists the base sections to
  bring in line.
- **Source:** `docs/sprite-tool-feedback.md` in the Yomi repository
  (`~/play/yomi`, commit `3ac8f9f`), notes from a session that used
  sprite-tool 0.4.0 to animate Yomi's units and map sprites and to draw the
  heroes' gear as layers over a body. The file sits outside this repository,
  so each point is restated here.

## 1. Purpose

Until that session every sprite in Yomi was one still frame, loaded as a
loose PNG. The session was the first to use frames, animations and the Phaser
target in earnest, and the first to compose sprites: a hero is now a bare
body (`units/warrior`) with a sprite from `art/gear/` drawn over it for the
weapon and for the shield.

The tool carried that work: the Phaser target needed no glue code, derived
frames and variants did what they promise, and `preview --on` turned out to
compose a layer over a body. Nine points of friction came out of it:

| # | Feedback | What it cost |
|---|---|---|
| 1 | A target exports every sprite. | The build writes some fifty loose PNGs nothing loads, and an atlas that carries every icon and portrait. |
| 2 | `shift` moves the whole canvas. | A breathing frame (the figure a pixel lower, feet where they were) was written out as a second full grid, copied with a script. |
| 3 | The tool does not know a sprite is a layer over another. | Eight gear sprites set `outline = false` and lose the outline check; only the default frame can be previewed over the body; nothing checks that body and gear animate in step. |
| 4 | An animation has one `ms` for all its frames. | A pause is a frame repeated; a blink would take a dozen repeats. |
| 5 | An animation cannot be previewed. | Movement was first seen in the running game. |
| 6 | `shift` drops pixels silently. | `check` reported the consequence (a bare bottom row) and not the cause. |
| 7 | An animation cannot be shared between files. | Eight gear files end with the same lines, and the timing lives in nine places. |
| 8 | `outline = "auto"` outlines detached pixels. | A two-pixel puff of smoke became a four by three dark block. |
| 9 | Small gaps: the index has no animations; the guide does not give the atlas's frame and animation names, or say that `--on` takes any sprite. | Read from the source code. |

The outcome is a 0.5.0 release in which a target says which sprites it
exports, a frame can move part of itself, a sprite can say what it is drawn
over and be checked and previewed that way, and an animation can have frames
of different lengths, be shared, and be looked at before the game runs.

## 2. Requirements and scope

### Functional requirements

| ID | Requirement | Feedback point |
|---|---|---|
| R24 | An `[[export]]` target can select the sprites it exports: by canvas class (`canvases`) and by id pattern (`include`, `exclude`). `check` warns of a pattern that matches nothing and of a sprite no target exports. | 1 |
| R25 | A frame can move a rectangle of itself with `move`: a range of rows, of columns or both, by `[dx, dy]`. | 2 |
| R26 | `check` warns when `shift` or `move` pushes drawn pixels off the canvas, naming the frame and the count. | 6 |
| R27 | A sprite can say `over = "<sprite id>"`: it is a layer drawn over that sprite. The outline rule is then checked on the two together, and the grounded rule does not apply to it. | 3 |
| R28 | Every preview of a layer draws it over its base, each frame over the base frame of the same name. | 3 |
| R29 | An entry of an animation's `frames` can carry its own length: `{ frame = "glow", ms = 150 }`. Every export writes each frame's length. | 4 |
| R30 | `sprite preview <id>... --anim <name>` writes a labelled strip of the animation's frames in play order, and an animated GIF that plays it. | 5 |
| R31 | An animation can take its frame list, lengths and looping from the animation of the same name in another sprite: `like = "<sprite id>"`. `check` warns when a layer's animation and its base's of the same name differ in frame count or lengths. | 7, 3 |
| R32 | A sprite can list palette keys that take no outline (`unoutlined`): the outline rule passes them and `outline = "auto"` draws none around them. | 8 |
| R33 | The `frames` and `godot` indexes carry each sprite's animations and, for a layer, its base. `guide` documents R24 to R32, the Phaser atlas's frame and animation names, and that `--on` takes any sprite. | 9 |

### Quality constraints

The base design's Q1 to Q5 still hold. Two are touched:

- **Q2 (token-friendly output).** `preview --anim` prints one path per file
  written: the strip, then one GIF per id.
- **Q3 (thin).** No new dependency. Pillow writes the GIF. No drawing
  primitive is added: `move` rearranges pixels the author wrote.

**Compatibility.** Every 0.4.0 project loads, checks and builds unchanged,
with two visible differences: the indexes gain an `anims` key per sprite, and
a `shift` that loses pixels now prints a warning. Neither fails a build.
`version = 1` in the config stays.

### Non-goals

- **Exporting a composed image.** A layer is still exported as its own
  sprite; the game draws it over the base. Baking every combination of body
  and gear would multiply the atlas for no gain.
- **`outline = "auto"` on a layer.** It is an error in this release (4.3).
  Drawing an outline only where the composite is transparent means resolving
  another file's frames before this one's outline, and before variant swaps;
  see question 1.
- **Layers of layers.** A base cannot itself have `over`.
- **A text view of a composite.** `sprite show` prints a layer's own pixels.
  In one grid of palette keys the two sprites could not be told apart.
- **Pairing a layer's frame with a base frame of another name.** Frames pair
  by name, else with the base's default frame (4.3). Yomi's gear rests on
  `idle_0` while the body plays `walk_0`; that pair is not checked.
- **A project-level template for frames.** Each gear sprite keeps its own
  `idle_1` (two lines: `from` and `shift`). Only the animation is shared
  (R31).
- **Per-frame `unoutlined`.** The list is per sprite and by key. A key that
  is smoke in one frame and a wall in another needs two keys.
- **Sprite data in the Phaser atlas files.** As in release 0.3, the atlas
  carries a pivot and nothing else about a sprite. With selection, a sprite
  exported only to an atlas is in no index; see question 2.
- **Changing Yomi.** That is work in the Yomi repository;
  [section 6](#6-consequences) lists what it can then drop.

### Acceptance criteria

| ID | Criterion | Covers |
|---|---|---|
| A36 | With `canvases = ["unit"]` on the demo's `phaser` target, `sprite build` writes an atlas whose frames are all of the `unit` class, and the `frames` target still holds every sprite. | R24 |
| A37 | Adding `exclude = ["slime*"]` to a target that has been built removes those sprites' files from its directory on the next build, and `build --check` in between exits 1 naming them. | R24 |
| A38 | `canvases = ["nosuch"]`, `include = []` and `include = "x"` each exit 2 with a message naming the export and the key. | R24 |
| A39 | An `include` pattern that matches no sprite is reported as W004 naming the export and the pattern. A sprite selected by no target is reported as W005 at its file. Neither changes the exit code. | R24 |
| A40 | A frame with `from = "idle_0"` and `move = { rows = [0, 27], by = [0, 1] }` on a 32-row canvas equals `idle_0` with row 0 transparent, rows 1 to 28 holding the old rows 0 to 27, and rows 29 to 31 unchanged. | R25 |
| A41 | A `move` with `rows` and `cols` changes only the pixels of the source and destination rectangles. Two moves in a list apply in order. | R25 |
| A42 | A `move` with a range outside the canvas, a first index above the last, neither `rows` nor `cols`, or no `by`, is reported in one line naming the frame. | R25 |
| A43 | `shift = [0, 1]` on a frame with pixels in its bottom row is reported as W006 with the number of pixels lost; the same shift on a frame with an empty bottom row is not. | R26 |
| A44 | A sprite with `over = "warrior"` whose pixels touch transparency only where `warrior` is drawn passes `check` with the outline rule on. Moving one such pixel to where the base is transparent gives one E201 at that pixel. | R27 |
| A45 | A layer whose bottom row is empty passes `check` on a grounded class without `grounded = false`. | R27 |
| A46 | `over` naming an unknown sprite, the sprite itself, a sprite that has `over`, or a sprite of another canvas class is E108. `over` with `outline = "auto"` is E001. | R27 |
| A47 | `sprite preview <layer>` writes an image in which a pixel the base draws and the layer leaves transparent has the base's colour, in every frame, the second frame over the base's frame of the same name. | R28 |
| A48 | An animation with `frames = ["a", { frame = "b", ms = 150 }]` and `ms = 500` exports to Phaser with durations 500 and 150, and to Godot with `speed` 2.0 and frame durations 1.0 and 0.3. | R29 |
| A49 | The golden files of the demo change only by the `anims` key of the indexes. | R29, R33, Q1 |
| A50 | `sprite preview warrior --anim idle` prints two paths, `warrior.anim-idle.png` and `warrior.anim-idle.gif`. The PNG holds one tile per entry of the animation, in play order. The GIF has as many frames, with those lengths. | R30 |
| A51 | `--anim` naming an animation an id does not have, and `--anim` with `--grid`, `--on`, `--sheet` or no id, each exit 2. | R30 |
| A52 | A sprite with `[anim.idle]` holding only `like = "warrior"` exports the same frame names, lengths and looping as `warrior`'s `idle`. Changing `ms` in `warrior` changes both. | R31 |
| A53 | `like` naming an unknown sprite, a sprite without that animation, an animation that is itself `like`, or frames this sprite lacks, is E105. `like` beside another field is E001. | R31 |
| A54 | A layer whose `idle` has two frames of 600 ms over a base whose `idle` has two of 500 ms is reported as W007 naming both. | R31 |
| A55 | With `outline = "auto"` and `unoutlined = ["w"]`, a `w` pixel standing alone renders as that one pixel, and the rest of the sprite renders as it did. Without auto, a `w` pixel touching transparency is no E201. | R32 |
| A56 | After `sprite build`, the `frames` index entry of the demo's warrior has `anims.idle` with `loop` and a list of `{frame, ms}`; a layer's entry has `over`. | R33 |
| A57 | `sprite guide` names `move`, a per-frame `ms`, `over`, `like`, `unoutlined`, the three selection keys, `--anim`, and the atlas names `<id>/<frame>` and `<id>/<anim>`, in under 110 lines for the demo. | R33 |

## 3. Current system

All of this was inspected in the 0.4.0 source (commit `a28419c`) and in
`~/play/yomi` at commit `3ac8f9f`.

| Point | Finding |
|---|---|
| 1 | `project._load_export` accepts `type`, `out`, `name`, `res_path` and `padding`. `cli._build` hands one list of sprites (those with `build = true` that are not blank) to every exporter. Release 0.3 rejected an `exclude` list as a non-goal because `build = false` said the same thing; that was about leaving a sprite out of every target, which is still `build = false`. |
| 1 | `manifest.Plan.stale` is the owned files no longer generated; `apply` deletes them and `compare` reports them as E401. A sprite dropped from a target is therefore cleaned up with no new code. |
| 2 | `spritefile._Derived.apply` runs `rows`, `runs`, `shift`, `flip` in that order. `shift` maps every pixel; those that leave the canvas are dropped and nothing is said. |
| 2 | Yomi's `idle_1` of `warrior`, `goblin` and `kobold` are full grids equal to `idle_0` with one leg row removed and a blank row added at the top: exactly a move of rows 0 to N down one. |
| 3 | `check._outline_faults` looks at one frame alone. `Sprite` has no link to another sprite. `check.run` already has every sprite at once, so a cross-sprite check has a place to live. |
| 3 | `preview.on_tile` places the sprite's anchor on the bottom centre of the "tile". For two sprites of one canvas class with a bottom-centre anchor that is the same place, which is why `--on warrior` composed gear correctly. It draws default frames only. |
| 3 | Yomi's eight `gear/*.sprite.toml` set `outline = false` and `grounded = false`. |
| 4 | `Anim` is `name`, `frames`, `ms`, `loop`. `export/phaser.py` already writes a `duration` on every frame (all `anim.ms`). `export/godot.py` writes `"duration": 1.0` on every frame and `speed = 1000 / ms`. |
| 4 | Yomi's skull repeats a frame for a pause: `frames = ["base", "base", "glow"]`. |
| 5 | `preview.sprite_preview` draws every frame in file order, unlabelled. Nothing draws an animation's order or timing. Pillow can save a GIF with no further dependency. |
| 6 | `check._check_sprite` reports E202 and E201 for what a lossy shift leaves. `cli.report` counts only `E` codes as errors, so a new `W` code cannot fail a build. |
| 7 | `spritefile._Parser` works on one file. `cli.load_checked` always loads every sprite file in the project, also for `sprite check <file>`, so a reference to another file can always be resolved; `_check` then filters the problems to the files named. |
| 8 | `spritefile.add_outline` puts the key on every transparent pixel next to a drawn one. Yomi's `map_town` smoke is two `w` pixels above the chimney. |
| 9 | `export/index.sprite_entry` has `anchor`, `bounds`, `canvas`, `display_scale`, `size`. `guide._files` describes the Phaser target as three file names. The demo's guide is 86 lines; a test holds it under 90. |

**Relevant structure.** `Frame.shift` and `Frame.flip` exist only so that
`check._inherited_faults` can tell where a parent frame's outline faults land
in a derived frame. Variants are made in the parser from the finished base
sprite (`spritefile._variant`), after the automatic outline. Problems are
`Problem(path, line, col, code, message)`; the config file's path is
`project.root / CONFIG_NAME`.

## 4. Proposed behavior

### 4.1 What a target exports (R24)

```toml
[[export]]
type = "frames"
out = "../public/assets/sprites"
canvases = ["icon", "portrait", "tile"]

[[export]]
type = "phaser"
out = "../public/assets/sprites"
name = "atlas"
canvases = ["unit", "map"]
exclude = ["sample_*"]
```

Three optional keys on any `[[export]]` table:

| Key | Value | Meaning |
|---|---|---|
| `canvases` | list of canvas class names | Only sprites of these classes. |
| `include` | list of id patterns | Only sprites whose id matches one of them. |
| `exclude` | list of id patterns | Not sprites whose id matches one of them. |

- A sprite is exported by a target when it would be built today (`build` is
  not `false`, and it is not blank) **and** its class is in `canvases` if
  that is given **and** its id matches a pattern of `include` if that is
  given **and** its id matches no pattern of `exclude`.
- A pattern is matched against the whole sprite id with
  `fnmatch.fnmatchcase`: `*`, `?` and `[...]`. A variant is matched by its
  own id (`gear_sword_ember`), so `gear_*` takes a sprite and its variants
  and `*_ember` takes only the variant.
- Config errors (exit 2), each naming the export by number and the key: a
  value that is not a list of non-empty strings; an empty `canvases` or
  `include` (it would select nothing); a `canvases` entry that is not a
  canvas class. An empty `exclude` is allowed.
- A target with none of the keys exports what it does today.
- A sprite a target no longer selects has its files removed from that
  target's directory by the next build, through the manifest, and
  `build --check` reports them as E401 until then.
- Two warnings, from `check` and so from `build`:
  - `W004 export 2 (phaser): include pattern 'gaer_*' matches no sprite`, at
    `sprite-tool.toml`, for each pattern of `include` or `exclude` that
    matches no loaded sprite id.
  - `W005 sprite 'warrior' is in no export target; set build = false if that
    is meant`, at the sprite's file, for a sprite that would be built and
    that no target selects. It is given only when the project has at least
    one target. Variants are judged on their own.
- The summary line of `build` counts the sprites and frames exported by at
  least one target.
- `build --adopt <id>` is unchanged: an id is valid when the sprite is built
  by any target.

### 4.2 Moving part of a frame (R25, R26)

```toml
[frames.idle_1]            # a breath: everything above the shins a pixel lower
from = "idle_0"
move = { rows = [0, 27], by = [0, 1] }
```

`move` is a new field of a frame table. Its value is one move or a list of
moves. A move is a table:

| Key | Value | Default |
|---|---|---|
| `rows` | `[first, last]`, inclusive row indices | every row |
| `cols` | `[first, last]`, inclusive column indices | every column |
| `by` | `[dx, dy]`, integers | required |

- At least one of `rows` and `cols` is required. A move of the whole canvas
  is `shift`.
- A move takes the rectangle `rows` × `cols`, makes it transparent, and
  writes it back `dx` to the right and `dy` down. Every cell of the
  rectangle is written, transparent ones too, so the rectangle replaces what
  was at its destination. Cells that land outside the canvas are dropped.
- Moves in a list apply in order, each to the result of the one before.
- The operations of a frame table now apply in this order: `move`, `rows`,
  `runs`, `shift`, `flip`. `move` comes first so that `rows` and `runs` can
  touch up what it leaves.
- `move` counts as content: a frame table needs `from`, `rows`, `runs` or
  `move`. Without `from` it moves a blank canvas, which is allowed and
  useless.
- With `outline = "auto"`, `move` moves the interior like every other
  operation; the outline is drawn afterwards.

Problems, each one line at the `move` key, naming the frame:

| Code | When | Message |
|---|---|---|
| E001 | Not a table or a list of tables; an unknown key; `by` missing or not two integers; `rows` or `cols` not two integers; neither `rows` nor `cols`. | `frame 'idle_1': move needs rows or cols (use shift to move the whole frame)` |
| E105 | An index outside the canvas, or `first` above `last`. | `frame 'idle_1': bad move rows [0, 40] (expected 0 to 31, first <= last)` |

**Lost pixels (R26).** When a `shift` or a `move` drops drawn pixels off the
canvas, the frame gets one warning at its line:

```
units/goblin.sprite.toml:40:1: W006 frame 'idle_1': shift [0, 1] pushes 7 drawn pixels off the canvas
```

For `move` the text names the move's `by` in the same way. Pixels a move
overwrites inside the canvas are not counted: overwriting is what a move is
for. The warning is given once for the sprite, not again for its variants.

### 4.3 Layers (R27, R28)

```toml
# gear/gear_sword.sprite.toml
canvas = "unit"
over = "warrior"
```

`over` at the top of a sprite file names the sprite this one is drawn over:
its **base**. The sprite is then a **layer**.

- **Pairing.** A frame of the layer is paired with the base's frame of the
  same name, else with the base's default frame. The pair is what the checks
  and previews below work on.
- **Outline rule.** For a layer the rule is checked on the pair: a pixel of
  the layer that is not an outline key (nor `unoutlined`, 4.6) is at fault
  when a pixel directly above, below, left or right of it is outside the
  canvas, or transparent in the layer **and** in the paired base frame. Only
  the layer's pixels are judged; the base is judged in its own file. The
  message says what it was checked over:
  `frame 'idle_0' row 18, col 23: 'O' touches transparency over 'warrior', expected outline key 'k'`.
  `outline = false` still switches the rule off.
- **Grounded rule.** It does not apply to a layer: a layer stands on its
  base. `grounded = false` is no longer needed, and is allowed.
- **Variants.** A variant of a layer is a layer over the same base.
- **Exports.** A layer is exported as the sprite it is, unchanged. The
  indexes say what it is over (4.7).
- **Previews (R28).** Wherever a preview draws a frame of a layer, it draws
  the paired base frame first and the layer over it: in
  `sprite preview <id>` with and without `--grid`, in the game-size frames
  beside them, on the contact sheet, as the sprite of `--on`, and in
  `--anim` (4.5). The image sizes of the base design's 4.8 do not change.
  `sprite show` prints the layer alone.

Problems:

| Code | When | Message |
|---|---|---|
| E001 | `over` is not a string. | `over must be a sprite id` |
| E001 | `over` with `outline = "auto"`. | `outline = "auto" cannot be used with over; draw the layer's outline` |
| E108 | The id is unknown, is the sprite's own, names a sprite that has `over`, or names a sprite of another canvas class. | `over names unknown sprite 'warior'`; `over names 'gear_sword', which is itself a layer`; `over names 'ground', which is on canvas class 'tile', not 'unit'` |

A layer with an E108 is checked as a plain sprite would be, so that one bad
id does not also bury the file in outline problems, and is previewed alone.
A base that has `build = false` is allowed: the checks do not need it
exported.

### 4.4 Frame lengths and shared animations (R29, R31)

```toml
[anim.idle]
frames = ["base", { frame = "glow", ms = 150 }]
ms = 1000                  # the length of a frame that gives none
```

- An entry of `frames` is a frame name, or a table with `frame` (a frame
  name) and `ms` (a positive integer), both required. Anything else is E001
  naming the animation and the entry's position:
  `anim 'idle': frames entry 2 must be a frame name or { frame = "...", ms = ... }`.
- The animation's own `ms` is still required. It is the length of every
  entry written as a name.
- **Phaser.** Each frame's `duration` is its own length. An animation with
  no per-frame length exports byte for byte as it does today.
- **Godot.** `speed` stays `1000 / ms`; a frame's `duration` is its length
  divided by `ms`, written with `repr` (`1.0` when equal, as today).

```toml
# gear/gear_sword.sprite.toml
[anim.idle]
like = "warrior"
```

- `like` names a sprite. The animation takes that sprite's animation **of
  the same name**: its entries (frame names and lengths), its `ms` and its
  `loop`. No other field may stand beside `like`.
- The frames it names must exist in this sprite; they are this sprite's own
  frames.
- It is resolved one step: the animation it points at must be written out.
- A variant has the animations of its sprite, resolved ones included.

| Code | When | Message |
|---|---|---|
| E001 | Another field beside `like`, or `like` not a string. | `anim 'idle': like takes no other field` |
| E105 | Unknown sprite; the sprite has no animation of that name; that animation is itself `like`; a frame it names is not in this sprite. | `anim 'idle': like names unknown sprite 'warior'`; `anim 'idle': 'warrior' has no animation 'idle'`; `anim 'idle' like 'warrior': this sprite has no frame 'idle_1'` |

An animation that fails is left out of the sprite, as a failed animation is
today.

**Layers out of step.** For a layer and its base, each animation name both
have is compared after `like` is resolved. If the number of entries or any
length differs, the layer gets, at the animation's line:

```
W007 anim 'idle': 2 frames of 600, 600 ms, but 'warrior' plays 2 of 500, 500 ms; the layers will drift
```

Frame names are not compared: the layer's frames are its own.

### 4.5 Previewing an animation (R30)

```
$ sprite preview gear_sword --anim idle
.preview/gear_sword.anim-idle.png
.preview/gear_sword.anim-idle.gif
```

- **The strip** is what an agent reads: one tile for each entry of the
  animation, left to right in play order, at the preview scale, a repeated
  frame drawn again. Under each tile is the frame's name and, on a second
  line, its length (`600 ms`). A tile's cell is as wide as the wider of the
  tile and its label, as on the contact sheet. Several ids give one image,
  each id's strip under the one before, named as other previews are
  (`<ids>.anim-<name>.png`).
- **The GIF** is what a person watches: one file per id,
  `<id>.anim-<name>.gif`, the same tiles without labels, each shown for its
  length, on the preview background. It loops forever when the animation
  loops and plays once otherwise. GIF counts time in hundredths of a second,
  so a length is rounded to 10 ms, and none is under 20 ms, which is the
  least that viewers honour.
- `--scale` applies to both, with `display` meaning the class's
  `display_scale`.
- A layer is drawn over its base (4.3): entry *i* over the base's frame of
  the same name. That is how a layer out of step with its body is seen.
- Usage errors (exit 2): `--anim` with `--grid`, `--on` or `--sheet`;
  `--anim` with no id; an id that has no animation of that name, with a
  message that lists the ones it has
  (`sprite 'goblin' has no animation 'blink' (animations: idle, walk)`).
- Style problems (E106, E201, E202) do not stop it, as for other previews.

### 4.6 Keys that take no outline (R32)

```toml
canvas = "map"
outline = "auto"
unoutlined = ["w"]         # the smoke
```

`unoutlined` at the top of a sprite file is a list of palette keys.

- **Outline rule.** A pixel of a listed key is never at fault. To its
  neighbours it is a drawn pixel like any other.
- **`outline = "auto"`.** A transparent pixel gets the outline key only when
  a pixel directly above, below, left or right of it is drawn in a key that
  is **not** listed. A listed pixel alone gets no outline; one that touches
  the rest of the shape is outlined on the sides the shape's outline covers
  anyway.
- **Variants.** A variant's list is the base's with the swap applied, so a
  swapped smoke stays smoke.
- A value that is not a list of one-character strings is E001. A key that is
  not in the palette is E107, the code a `swap` with such a key already has:
  `unoutlined key 'x' is not in the palette`.
- On a sprite the outline rule does not apply to, the list is accepted and
  does nothing.

### 4.7 Indexes and guide (R33)

**Indexes.** In `sprites.json` (the `frames` target) and the `godot` index,
each sprite's entry gains:

```json
"anims": {
  "idle": { "frames": [{ "frame": "base", "ms": 1000 }, { "frame": "glow", "ms": 150 }], "loop": true }
},
"over": "warrior"
```

`anims` is always present, `{}` for a sprite with none, with animations
sorted by name. `over` is present only on a layer.

**Guide.** `sprite guide` gains, within a budget of 110 lines for the demo:

- In the example sprite file: a `move` line in the derived frame with its
  place in the order of operations, and a `frames` entry with its own `ms`.
- In the format notes, one line each: `over` (what is checked and previewed
  with it), `like`, `unoutlined`.
- In the EXPORTS section: after a target's files, its selection when it has
  one (`canvases unit, map; exclude sample_*`); and for a `phaser` target
  the names it gives: `frames are named <id>/<frame>, animations
  <id>/<anim>; <name> is the texture key`.
- In COMMANDS: `sprite preview <id> --anim <name>`, and the `--on` line
  reworded to `the sprite standing on another sprite, as in the game`.

## 5. Technical design

All paths exist unless marked proposed.

### 5.1 Data model (`model.py`)

| Type | Change |
|---|---|
| `ExportTarget` | Add `canvases: frozenset[str] \| None = None`, `include: tuple[str, ...] \| None = None`, `exclude: tuple[str, ...] = ()`. |
| `Frame` | Replace `shift` and `flip` with `origins: tuple[tuple[tuple[int, int] \| None, ...], ...] \| None = None`: for a derived frame with a parent, the parent pixel `(row, col)` each pixel of this frame came from, `None` for a pixel that came from nowhere (vacated by a move or a shift). Add `lost: tuple[tuple[str, int], ...] = ()`: for each `shift` or `move` that dropped drawn pixels, its description (`"shift [0, 1]"`) and the count. |
| `Anim` | Add `durations: tuple[int, ...]`, one per entry of `frames`. `ms` stays. |
| `Sprite` | Add `over: str \| None = None`, `unoutlined: frozenset[str] = frozenset()`, and `anim_likes: tuple[tuple[str, str, int], ...] = ()`: animation name, sprite id and file line of each `like` not yet resolved. |

`Frame.origins` is the one structural change. It makes
`check._inherited_faults` independent of which operations exist: a fault of
this frame at `(r, c)` is inherited when `origins[r][c]` is a fault of the
parent. `rows` and `runs` leave a cell's origin as it was, which keeps
today's behaviour: a fault the parent has at a position is not reported
again in a frame that rewrote that position.

### 5.2 Parsing (`spritefile.py`)

- `_FRAME_KEYS` gains `move`; `_TOP_LEVEL_KEYS` gains `over` and
  `unoutlined`; `_ANIM_KEYS` gains `like`.
- `_Derived` gains `moves: tuple[_Move, ...]` (proposed dataclass: `rows`,
  `cols` as resolved inclusive ranges, `by`). `_Derived.apply` runs the
  operations on the rows and, with the same code, on a grid of coordinates,
  and returns rows, origins and the lost counts. One helper that transforms
  a generic grid, called twice, keeps the two from disagreeing.
- `add_outline(rows, key, unoutlined=frozenset())`: a neighbour counts only
  when its key is not in `unoutlined`.
- `_anims` returns the animations written out and the pending `like`s.
- `load_all` gains a pass after every file is parsed (proposed
  `_resolve_likes`): for each sprite with `anim_likes`, look the animation
  up among the loaded sprites by id, check it and this sprite's frame names,
  and replace the sprite with one that has the animation added and
  `anim_likes` emptied. A variant carries its base's pending entries and is
  resolved the same way. Problems go to the sprite's file at the recorded
  line; a variant's are not reported again. The lookup is by id among
  sprites sorted by id, so the result does not depend on file order.
- W006 is reported by the parser from `Frame.lost`, for the sprite and not
  for its variants.

`over` is only recorded by the parser. Whether the id is good needs every
sprite, so E108 is `check`'s.

### 5.3 Checks (`check.py`)

- `run` builds a map from id to sprite and gives each layer its base, or
  `None` with an E108.
- `_outline_faults(sprite, frame, under=None)`: `under` is the paired base
  frame's rows. `is_clear` becomes "outside the canvas, or transparent here
  and in `under`". Keys in `sprite.unoutlined` are skipped like outline
  keys. Every caller (`_check_sprite`, `_check_variant`,
  `_inherited_faults`) passes the pair for the frame it asks about; a
  proposed helper `paired(base, frame_name)` returns the base frame of that
  name or the default.
- `_check_sprite` skips E202 for a layer.
- New `_selection_problems(project, sprites)` for W004 and W005, using the
  same selection function as the build (5.4).
- New `_step_problems` for W007.
- The docstring of `run` lists the new codes.

New codes: **E108** bad `over`; **W004** selection pattern matches nothing;
**W005** sprite in no target; **W006** pixels pushed off the canvas;
**W007** a layer's animation out of step with its base's.

### 5.4 Exports

- `project._load_export` reads the three keys. It is given the canvas
  classes, which `load` has already read, to validate `canvases`.
- Proposed `export.select(sprites, target) -> list[Sprite]` in
  `export/__init__.py`: the rule of 4.1 for sprites that are already
  buildable. `cli._build` calls each exporter with `select(sprites, target)`
  and counts the union for its summary. `render.render_all` still renders
  once, for the union.
- `export/index.sprite_entry` adds `anims` and `over`.
- `export/phaser.py` and `export/godot.py` read `anim.durations`.
- Exporters still return `{relative path: bytes}` and never touch the disk.

### 5.5 Previews (`preview.py`, `cli.py`)

- Proposed `preview.drawn(project, sprite, frame, base)`: the frame's image,
  over the paired base frame's when `base` is given. `_frame_tile` and
  `_display` use it, so every existing preview composes layers with no
  change to its layout. `cli._preview` passes each sprite's base from the
  sprites it has loaded.
- Proposed `preview.anim_strip(project, sprite, anim, base, scale)` and
  `preview.anim_frames(...)`, the latter returning the tiles and lengths the
  GIF is saved from. Label sizes use the existing `CHAR_WIDTH` and
  `LINE_HEIGHT`.
- `cli.build_parser` adds `--anim <name>` to `preview`; `_preview` handles
  the usage errors of 4.5 before loading.

### 5.6 Guide (`guide.py`)

`EXAMPLE` must still check clean on its 6x4 canvas (a test loads it), so the
`move` it shows has to leave the outline whole. Which rows it moves is the
implementer's choice, held to by that test; a move that `runs` then touches
up would also show why `move` comes first. `_files` takes the selection and
the atlas names. The line limit in
`tests/test_init_new_guide.py` goes from 90 to 110.

## 6. Consequences

- **Compatibility.** No 0.4.0 file changes meaning. `Frame.shift` and
  `Frame.flip` go; nothing outside `check.py` reads them.
- **Golden files.** `make golden`, then read the diff: only `sprites.json`
  and the Godot index change, by `anims`. If the demo gains a layer, a
  per-frame length or a selection to exercise the new code (recommended: a
  layer over the demo warrior with a `like` animation), the atlas and
  `.tres` files change too, in the same commit.
- **Performance.** The composite check adds one base lookup per layer frame.
  Q5 holds.
- **Base design sections to bring in line:** 4.3 (the `[[export]]` keys),
  4.4 (`move`, `over`, `unoutlined`, animation entries, `like`), 4.6 (the
  code table: E108, W004 to W007, and E105, E107 and E001 widened), 4.7
  (selection, index keys, per-frame lengths), 4.8 (layers, `--anim`), 5.3
  (the model). Its non-goal "Drawing helpers" is unchanged. `README.md` and
  `AGENTS.md` gain the release note and the layout changes; the note
  `sprite init` prints does not change.
- **Release.** Version 0.5.0, by the steps in `AGENTS.md`.
- **Yomi, afterwards** (not part of this work): give the two targets
  `canvases`, which deletes the fifty unused PNGs and takes icons and
  portraits out of the atlas; replace the three full-grid `idle_1` frames
  with a `move`; add `over = "warrior"` to the gear sprites and drop their
  `outline = false` and `grounded = false`; replace their `[anim.idle]`
  bodies with `like = "warrior"`; give the skull's glow its own `ms`; set
  `unoutlined` for the town's smoke; move the pin to `v0.5.0`.

## 7. Verification

`make check`. Tests follow the existing constraints: no display, no network,
writes only under `tmp_path`.

| Area | Test | Criteria |
|---|---|---|
| Selection | `export.select` for each key alone and all three together; a variant matched by its own id. Config errors for each bad value. A build with a `canvases` target beside an unrestricted one. A sprite dropped from a target: `build --check` exits 1, the next build removes its files and leaves the other target's. W004 and W005, and no W005 in a project with no selection. The summary counts the union. | A36 to A39 |
| Move | Row range, column range, both, a list of two. Cells leaving the canvas. Order with `rows`, `runs`, `shift`, `flip`. With `outline = "auto"`. Each problem of 4.2. `origins`: an outline fault of the parent is not reported again where it was moved to, and a fault the move creates is. | A40 to A42 |
| Lost pixels | W006 for `shift` and for `move`, with the count; none when only transparent pixels leave; once for a sprite with variants. | A43 |
| Layers | A layer that passes over its base and fails alone. A fault where the base is transparent, with line and column in a grid frame and row and column in a runs frame. Pairing by name and by default frame. Grounded waived. A variant of a layer. Each E108 and the E001. A layer with E108 checked as a plain sprite. | A44 to A46 |
| Layer previews | Pixel colours of a composed tile, plain and gridded, for two frames; the contact sheet; `--on`. Image sizes unchanged from the existing tests. | A47 |
| Frame lengths | Parse of mixed entries; each malformed entry. Phaser durations. Godot `speed` and `duration`. W002 still counts a frame named in a table entry as used. | A48 |
| `like` | Resolution across files in both file orders; a variant; a change of `ms` in the source; each E105 and the E001; `sprite check <one file>` resolving a `like` into a file not named. W007 for count and for length, and none when they agree. | A52 to A54 |
| `--anim` | Strip size for a known animation and scale; tile count with a repeated frame; label present. GIF frame count, lengths (rounded, floored at 20 ms) and loop flag, read back with Pillow. A layer's strip composed. Each usage error. | A50, A51 |
| `unoutlined` | `add_outline` with a lone listed pixel, one touching the shape, and none. The rule with and without auto. A variant swapping the key. E001 and E107. | A55 |
| Index and guide | `anims` and `over` in both indexes. Presence of each fact of 4.7 in the guide, for zero, one and three targets; the demo under 110 lines; `EXAMPLE` still checks clean. | A56, A57 |
| Golden and determinism | Existing tests, against regenerated golden files. | A49, Q1 |

**Manual acceptance.** In a scratch copy of Yomi's `art/`, make the changes
listed under "Yomi, afterwards". `sprite check` should print `ok` with the
gear's outline rule on; `sprite build` should leave only icons, portraits
and tiles as loose PNGs; `sprite preview gear_bow --anim idle` should show
the bow sinking with the body in the second tile; and the rebuilt atlas
should hold the same pixels for `warrior/idle_1`, `goblin/idle_1` and
`kobold/idle_1` as before.

## 8. Open questions and assumptions

Nothing here blocks planning.

### Assumptions

- **A layer shares its base's canvas class.** That guarantees one size and
  one anchor, so the pair lines up with no offset to state. Yomi's gear is
  drawn on the `unit` canvas for that reason.
- **Frames pair by name.** It fits Yomi, where body and gear both have
  `idle_0` and `idle_1`. A project that names a layer's frames differently
  gets every frame checked against the base's default frame, which is still
  a better check than none.
- **A move writes its transparent cells.** Copying a rectangle whole is the
  rule that is easy to predict. The breathing frame needs it either way: the
  rows it overwrites are equal to the ones moved onto them.
- **`ms` stays required on an animation.** It keeps Godot's `speed` defined
  and old files unchanged, at the price of one line in an animation whose
  every entry has its own length.
- **W005 is wanted.** A sprite no target takes is more likely a mistake in a
  pattern than a choice, and `build = false` is the way to say it is a
  choice.
- **A strip and a GIF are both worth writing.** The session's agent could
  only have used the strip; the feedback asked for the GIF.

### Questions (non-blocking)

1. **`outline = "auto"` on a layer.** The wanted rule is clear (outline only
   where the composite is transparent) and would have let the gear be drawn
   as interiors. It needs the base's finished frames while this file is
   still being resolved, and an answer for a variant that swaps the outline
   key. Worth its own small design once layers have been used for a while.
2. **An index without the PNGs.** With icons leaving Yomi's atlas and units
   leaving its loose PNGs, `sprites.json` covers only what the `frames`
   target selects. A game that wants scale, bounds and animations as data
   for atlas sprites has no file for them. An `index` target type, or
   `<name>.sprites.json` beside the atlas, would close that; no game reads
   the index yet, so it is left out again.
3. **Pairing other than by name.** If a later game needs a layer's rest
   frame checked against several base frames, a per-frame `over` (a frame
   table naming the base frame it pairs with) is the natural extension.
4. **`--alone` for previews of a layer.** `sprite show` gives a layer's own
   pixels as text. If a layer's hidden pixels turn out to need looking at as
   an image, a flag that skips the base is a few lines.
