# sprite-tool 0.6: named points, effect sprites and editing frames

- **Date:** 2026-10-30
- **Status:** Implemented in 0.6.0. Assumptions and non-blocking questions
  are in [section 8](#8-open-questions-and-assumptions). Where the build
  differs from the text below: the demo warrior's `grip` is `[25, 18]`, the
  pixel of its fist on the blade (A58 and A65 use Yomi's `[25, 19]` as their
  example); W008 is not reported for a point the frame's own
  `[frame_points]` puts back; and `show --diff` on equal frames still lists
  the frame's points after `no rows differ`.
- **Amends:** [sprite-tool.md](sprite-tool.md) (the base design), after
  [feedback-fixes.md](feedback-fixes.md) (0.3),
  [text-view-and-runs-discovery.md](text-view-and-runs-discovery.md) (0.4) and
  [layers-animation-and-export-selection.md](layers-animation-and-export-selection.md)
  (0.5). Requirement and criterion ids continue their numbering (the last
  were R33 and A57). Where this document and an earlier one disagree, this
  one wins.
- **Source:** a session in the Yomi repository (`~/personal/yomi`, branch
  `battle-animations`, commit `314ef72`) that added battle animations:
  weapon swings, arrows, spell missiles and impacts. The art came from
  sprite-tool 0.5.0; the new effects were drawn in code. A second session
  (commit `d68a54e`, same branch) drew every unit a four-beat walk with the
  tool: two new frames per unit, each lifting one foot. What both cost is
  restated below, as the commits sit outside this repository.

## 1. Purpose

Yomi's heroes are a body sprite (`units/warrior`) with a weapon sprite from
`art/gear/` laid over it. To swing the weapon the game turns that layer
about the fist. Where the fist is was written down only as prose in Yomi's
`art/CLAUDE.md` ("the fist is at rows 18 to 20, columns 22 to 27 … gripped at
column 25"), so the game hard-codes it:

```ts
// yomi src/scenes/unitLook.ts
export const GRIP_FROM_FEET = { x: 25.5 - 16, y: 19.5 - 32 }
```

That constant is a fact about the drawing, kept in the code. Redraw the body
with the fist a pixel higher and the swing pivots in the wrong place, with
nothing to say so. The same gap shows wherever a game needs a place on a
sprite other than its anchor: where a shot leaves a bow, where a spell
leaves a hand, where a hit lands on a chest. Yomi uses a third of the
figure's height for the chest, again in code.

The second gap is effects. Arrows, wand bolts, sparks and impact bursts were
drawn with Phaser's shape primitives rather than as pixel art, partly because
no canvas class fits them. A unit's class is anchored at the feet, must be
outlined and must touch the bottom row; an effect is small, turns about its
centre, glows and floats. A project can declare such a class today, but
nothing in the tool, the template or the guide says how to draw a sprite
that a game will rotate, or which end of it points forward.

The third gap showed while drawing the walk. Each new frame changed a few
pixels in each of seven leg rows, but `rows` replaces a whole row, so every
row was written out at full width, with the dots counted by hand and the
lengths checked by a throwaway script. Three things would have saved most of
that:

- The right-foot frame is nearly the left-foot frame mirrored about the gap
  between the legs, but `flip` mirrors the whole canvas, and with it the
  body, the shield and the spear.
- The work was read back by comparing a new frame with `idle_0` row by row in
  two `sprite show` blocks. Only the rows that differ mattered.
- `move` with both `rows` and `cols` can lift a foot two pixels in one line.
  The guide's only example of `move` takes whole rows down, so it was not
  tried until afterwards.

And one thing the tool could not catch: a gear layer has `idle` but no
`walk`, by design, so it rests on its default frame while the body walks.
Nothing tells that apart from a `walk` someone forgot to draw.

The outcome is a 0.6.0 release in which:

1. A sprite can name points on itself. Points follow a derived frame's
   `move`, `mirror`, `shift` and `flip`, can differ from frame to frame, and
   are exported where each engine can read them.
2. Effect sprites have a documented convention and a canvas class in the
   template, with an example in the demo.
3. A frame can mirror a rectangle of itself, `sprite show` can print only
   what a frame changes, and the guide shows `move` lifting part of a figure.
4. A layer says which of its base's animations it rests through, and `check`
   warns of one it neither plays nor rests through.

## 2. Requirements and scope

### Functional requirements

| ID | Requirement |
|---|---|
| R34 | A sprite file can declare named points in a top-level `[points]` table: `<name> = [col, row]`, each naming one pixel of the canvas. Every frame that is not derived from another frame has these points. |
| R35 | A derived frame inherits its parent's points, carried by its `move`, `mirror`, `shift` and `flip` as the pixels are. A point pushed off the canvas is dropped from that frame, with a warning. |
| R36 | A `[frame_points.<frame>]` table sets points on one frame, in that frame's final coordinates. It replaces inherited points of the same name and may add new ones. Frames derived from that frame inherit the result. |
| R37 | A variant has its base sprite's points, frame for frame. |
| R38 | Every export carries the points: on each frame of the Phaser atlas, where Phaser exposes them as `frame.customData.points`, and in the `frames` and `godot` indexes, keyed by frame. A point is exported as the centre of its pixel, in canvas pixels from the top left. |
| R39 | `sprite show` lists a frame's points under its grid. `sprite preview --points` marks them on the image. |
| R40 | `check` reports malformed points: a bad name, a value that is not two integers, a pixel outside the canvas, and a `[frame_points]` table naming a frame the sprite does not have. |
| R41 | The template config written by `sprite init` declares an `effect` canvas class (centred anchor, no outline rule, not grounded), and the guide states the effect convention: drawn pointing right (+x), turned by the game about the anchor, its leading pixel named `tip`. |
| R42 | The demo has an arrow and a spark burst drawn to that convention, so the golden files show what an effect exports. `guide` documents R34 to R41. |
| R43 | A derived frame can mirror a rectangle of itself left to right, in place, with `mirror`: a range of rows, of columns or both, as `move` takes them. Pixels, origins and points inside the rectangle are mirrored about its centre column. |
| R44 | `sprite show <id> --frame <name> --diff [<other>]` prints only the rows of the frame that differ from another frame of the sprite (its `from` parent by default), each with a line marking the changed columns. |
| R45 | A layer's animation can be `rest = true`: the layer holds its default frame for as long as the base's animation of the same name plays. It is exported as a one-entry animation of that length and looping. `check` warns (W009) of an animation of the base that a layer neither has nor rests through. |
| R46 | The guide shows `move` with `rows` and `cols` lifting part of a figure, and `mirror` beside it. `guide` documents R43 to R45. |

### Quality constraints

The base design's Q1 to Q5 hold. Two are touched:

- **Q1 (determinism).** Points are written in sorted order of frame name, then
  point name. Values are JSON numbers ending in `.5`, which `json_bytes`
  writes identically every run.
- **Q2 (token-friendly output).** `show` adds one line per point and nothing
  for a frame without points. `preview --points` prints the same one path per
  image as `preview` does. `show --diff` prints the rows that changed and no
  others: for the walk frames above, seven rows instead of thirty-two.

**Compatibility.** A 0.5.0 project with no `[points]` and no
`[frame_points]` checks and builds to byte-identical files: no export gains a
key when a sprite has no points. One check is new and may fire on an
existing project: W009, for a layer missing one of its base's animations
(Yomi's gear and the body's `walk`). It is a warning and fails nothing; one
`rest = true` line per layer silences it. `version = 1` in the config stays. The
`effect` class is added only to the template that `sprite init` writes; an
existing project's config is never touched.

### Non-goals

- **Points on a canvas class.** A class holds sprites of different shapes: in
  Yomi the `unit` class holds the warrior, goblins and a horror, and a grip
  means something only for the warrior. Points belong to the drawing. The
  class keeps its single anchor.
- **Sharing points between files** (as `like` shares an animation). Yomi's
  gear does not need the grip: the body has it, and the game reads it there.
  See [question Q-3](#questions-non-blocking).
- **A layer reading its base's points.** A game that knows a layer is over a
  base (the index's `over`) can read the base's points itself.
- **Points off the canvas, or between pixels.** A point names a pixel. A
  corner or a place outside the drawing is not needed by anything seen so
  far.
- **Pre-rotated frames.** The tool does not render an effect at eight or
  sixteen angles. A game turns it at run time with nearest-neighbour
  filtering. Pixel-art rotation (such as RotSprite) is a project of its own.
- **Particle systems, blend modes, or any engine-side behaviour.** The tool
  makes images and data. How a game spawns, tints, adds or fades an effect is
  the game's business.
- **Mirroring top to bottom, or rotating a rectangle.** Nothing drawn so far
  needed either. `mirror` is left to right because sprites are drawn facing
  right and limbs pair across a vertical line.
- **A diff between sprites.** `--diff` compares two frames of one sprite,
  which is what deriving frames needs.
- **Shorthand rows (padding a short row, or writing only the changed span).**
  `runs` already write a span, and `--diff` makes counting checkable. A third
  way to write a row would be one more thing to learn.

### Acceptance criteria

| ID | Criterion | Covers |
|---|---|---|
| A58 | A sprite with `[points] grip = [25, 19]` and one literal frame exports `points: {"grip": [25.5, 19.5]}` on that frame in the Phaser atlas JSON, and `points: {"<frame>": {"grip": [25.5, 19.5]}}` in its `frames` and `godot` index entries. | R34, R38 |
| A59 | A frame with `from = "idle_0"` and `shift = [0, 1]` has `grip` at `[25, 20]`. With `flip = true` on a 32-wide canvas it is at `[6, 19]`. With `move = { rows = [0, 23], by = [0, 1] }`, a point at row 19 moves to row 20 and a point at row 28 stays where it was. | R35 |
| A60 | A `shift = [0, 1]` that takes a point from row 31 off the canvas drops it from the frame and reports W008 naming the frame and the point. Its pixels' W006 is reported as before. | R35 |
| A61 | With `[frame_points.attack_0] grip = [27, 17]`, `attack_0` has `grip` at `[27, 17]` whether it is literal or derived, the other frames keep the sprite's `grip`, and a frame derived from `attack_0` with `shift = [1, 0]` has it at `[28, 17]`. A `[frame_points]` point not in `[points]` appears only on that frame and the frames derived from it. | R36 |
| A62 | The variant `warrior_red` exports the same points as `warrior` for every frame. | R37 |
| A63 | Point names, values and frame names that are wrong each give one E109 naming the point: `Grip = [1, 1]`, `grip = [1]`, `grip = [1.5, 2]`, `grip = [32, 0]` on a 32-wide canvas, and `[frame_points.nosuch]`. The sprite still loads, without the bad point. | R40 |
| A64 | A 0.5.0 project with no points builds byte-identical output under 0.6.0. | Compatibility |
| A65 | `sprite show warrior` prints, after the grid of a frame with points, one line `point grip 25,19` per point in name order, and nothing extra for a frame without. | R39 |
| A66 | `sprite preview warrior --points` writes an image in which the pixel of each point is drawn in the marker colour, in every frame tile; without `--points` the image is as before. | R39 |
| A67 | `sprite init` writes a config with `[canvas.effect]`: `size = [16, 16]`, `anchor = [8, 8]`, no `outline`, `grounded` false. | R41 |
| A68 | The demo builds `arrow` (one frame, `tip` point at its rightmost drawn pixel) and `spark` (a `burst` animation with `loop = false`) on the `effect` class, and the golden files change by those sprites, the demo warrior's `grip`, and nothing else. | R42, Q1 |
| A69 | `sprite guide` documents `[points]`, `[frame_points]`, how points follow `move`, `shift` and `flip`, the exported coordinates, `--points`, and the effect convention, and stays under 130 lines for the demo. | R42 |
| A70 | On a frame whose row 5 is `..ab.cd..`, `mirror = { rows = [5, 5], cols = [2, 6] }` gives `..dc.ba..`, and leaves every other row and the columns outside 2 to 6 as they were. Without `rows` it mirrors those columns in every row; without `cols`, the whole width of those rows. Two mirrors in a list apply in order. | R43 |
| A71 | A point at `(3, 5)` inside that rectangle moves to `(5, 5)`; one at `(3, 6)` does not move. An outline fault in a mirrored pixel is reported at the parent pixel it came from, through `origins`, as for `move`. | R43, R35 |
| A72 | `mirror` with a range outside the canvas, a first index above the last, neither `rows` nor `cols`, or an unknown key is one E105 naming the frame. | R43 |
| A73 | For a frame that changes rows 25 to 31 of its parent, `sprite show warrior --frame walk_1 --diff` prints the header `warrior walk_1 vs idle_0  unit 32x32`, the column rulers, and for each of those seven rows the numbered row and under it a line with `^` under each changed column. `--diff idle_1` compares with `idle_1` instead. | R44 |
| A74 | `--diff` on a frame with no parent and no argument, naming an unknown frame, without `--frame`, or with `--all`, each exit 2. Two equal frames print the header and `no rows differ`. | R44 |
| A75 | A layer over `warrior` with `[anim.walk] rest = true`, whose base plays four frames of 140 ms with `loop = true`, exports to Phaser an animation `<layer>/walk` of one frame, its default frame, lasting 560 ms, repeating; the indexes list it with that frame and length. `rest` beside another field, or on a sprite that is not a layer, is E001. | R45 |
| A76 | A layer over `warrior` with `idle` and no `walk`, while `warrior` has `walk`, is reported as W009 naming the layer, the base and `walk`; with `rest = true` for `walk` it is not, and no W007 is reported for a resting animation. | R45 |
| A77 | `sprite guide` shows a `move` with `rows`, `cols` and `by` lifting a foot, `mirror`, `show --diff` and `rest`, and stays under 140 lines for the demo. | R46 |

## 3. Current system

Inspected in this repository at `697e606` (0.5.0) unless marked otherwise.

- **Sprite files** are parsed by [`spritefile.py`](../../src/sprite_tool/spritefile.py).
  `_TOP_LEVEL_KEYS` lists what a file may hold (`canvas`, `frames`, `anim`,
  `variants`, `outline`, `grounded`, `build`, `over`, `unoutlined`); anything
  else is E001. A frame is a literal grid (a string) or a derived table
  (`from`, `move`, `rows`, `runs`, `shift`, `flip`).
- **Derived frames already track where each pixel came from.**
  `_Derived._transform` runs the operations on any grid, and `apply` runs it
  a second time on a grid of `(row, col)` positions to get `Frame.origins`,
  which the outline check uses. Points can ride the same code: whatever moves
  a pixel moves a point on it.
- **The model** ([`model.py`](../../src/sprite_tool/model.py)): `Frame` holds
  `rows`, `origins` and `lost`; `Sprite` holds its frames, anims and flags;
  `Canvas` holds one `anchor`. Nothing holds a position other than the anchor.
- **Variants** (`spritefile._variant`) copy the base sprite's frames with
  colours swapped, so anything stored on `Frame` reaches them unchanged.
- **Exports.** [`export/index.py`](../../src/sprite_tool/export/index.py)'s
  `sprite_entry` builds the keys the `frames` and `godot` indexes share.
  [`export/phaser.py`](../../src/sprite_tool/export/phaser.py) writes a JSON
  Hash atlas whose frame entries hold `frame`, `pivot`, `rotated`,
  `sourceSize`, `spriteSourceSize` and `trimmed`.
  [`export/godot.py`](../../src/sprite_tool/export/godot.py) writes a
  `SpriteFrames` `.tres` per sprite, which has no place for extra data, and a
  JSON index whose `frames` maps each frame to its region `[x, y, w, h]`.
- **Phaser keeps unknown frame keys.** Phaser's JSON Hash parser copies each
  frame's whole entry onto the frame as `customData` (inspected in Phaser
  4.2.1, `src/textures/parsers/JSONHash.js`: `newFrame.customData =
  Clone(src)`). A `points` key on a frame entry is therefore readable in a
  game as `textures.getFrame(key, name).customData.points`, with no loader
  change.
- **Problem codes** in use: E001 to E003, E101 to E108, E201, E202, E301,
  E302, E401 and W001 to W007. This design adds E109, W008 and W009.
- **`move`'s rectangle** is parsed by `_Parser._moves` into `_Move(rows,
  cols, by)`, with a missing `rows` or `cols` meaning the whole height or
  width; its problems are E105 naming the frame. `mirror` can take the same
  rectangle with the same parser and the same messages.
- **`show`** (`cli._show`) takes ids, `--frame` (repeatable) and `--all`, and
  prints `textview.frame_text` for each frame chosen.
- **Layer animations.** `check._step_problems` reports W007 for an animation a
  layer and its base both have whose lengths differ. A base's animation the
  layer lacks is not reported. In Yomi, `UnitFigure.play` already rests a
  layer on its default frame when its sprite has no animation of that name,
  which is exactly what `rest = true` would export.
- **Text and previews.** [`textview.py`](../../src/sprite_tool/textview.py)
  prints a header, column rulers and numbered rows; it is the only output of
  `show`. [`preview.py`](../../src/sprite_tool/preview.py)'s `drawn` is the
  one place a frame becomes a preview image.
- **The template** ([`templates/sprite-tool.toml`](../../src/sprite_tool/templates/sprite-tool.toml))
  declares `unit` (32×32, anchored at the feet, outlined, grounded) and
  `tile`. The demo ([`examples/demo/`](../../examples/demo/)) has `units/` and
  `tiles/`.
- **In Yomi** (inspected at `314ef72`), the swing pivot is `GRIP_FROM_FEET`,
  the chest is `UNIT_HEIGHT / 3` above the feet, and the arrow, bolts,
  sparks, slash, clouds and rings are Phaser `Graphics` drawn in
  `BattleScene.ts`.

## 4. Proposed behavior

### 4.1 Declaring points (R34, R36)

```toml
# units/warrior.sprite.toml
canvas = "unit"

[points]
grip = [25, 19]          # [col, row]: the pixel the weapon turns about
chest = [16, 15]

[frames]
idle_0 = """
...
"""

[frames.idle_1]
from = "idle_0"
move = { rows = [0, 23], by = [0, 1] }    # grip and chest sink with the body

[frames.attack_0]
from = "idle_0"
rows = { 17 = "...", 18 = "..." }

[frame_points.attack_0]
grip = [27, 17]          # the arm is raised in this frame
```

- A point's name matches `[a-z0-9_]+`, as frame and animation names do. Its
  value is `[col, row]`, two integers, the same order as `runs` and `move`'s
  `by`, naming a pixel inside the canvas.
- `[points]` gives every **root frame** its points: a literal grid, or a
  derived table with no `from`.
- `[frame_points.<frame>]` gives one frame points of its own, in the frame's
  final coordinates (after its operations). A name already present is
  replaced; a new name is added. It works for literal and derived frames
  alike, which is why it is a top-level table and not a key of a frame
  table: a literal frame is a string and has nowhere to hold it.
- A sprite with neither table has no points, and exports nothing new.

### 4.2 Points in derived frames (R35)

A derived frame starts from its parent's resolved points (its own
`[frame_points]` not yet applied) and carries each through the frame's
operations, in their order, exactly as the pixel under it would move:

| Operation | A point at `(c, r)` |
|---|---|
| `move` | moves by `by` if inside the move's rectangle; otherwise stays. A point outside the rectangle is not overwritten by pixels moved onto it: a point is not a pixel. |
| `mirror` | goes to `(first + last - c, r)` if inside the rectangle (section 4.8); otherwise stays. |
| `rows`, `runs` | stays. They change what a pixel holds, not where anything is. |
| `shift` | moves by the shift. |
| `flip` | goes to `(width - 1 - c, r)`. |

A point that leaves the canvas is dropped from that frame and from the frames
derived from it, and `check` reports W008: `frame 'idle_1': shift [0, 1]
takes point 'grip' off the canvas`. Then the frame's `[frame_points]` apply,
which can put a dropped point back.

### 4.3 Variants (R37)

A variant is its base with colours swapped, so it has its base's points for
every frame. A variant table cannot declare points.

### 4.4 Exports (R38)

A point is exported as the **centre of its pixel**, in canvas pixels from the
top left of the canvas: `[25, 19]` becomes `[25.5, 19.5]`. That is the number
a game turns or places things about; for the anchor, which is a corner of the
pixel grid and an integer, the game already knows the convention.

A game converts a point to a position relative to where it drew the sprite
with `(point - anchor) * display scale`, flipping x when it mirrors the
sprite: `x = -(point.x - anchor.x) * scale`.

**Phaser** (`atlas.json`): each frame entry with points gains a key, which
Phaser exposes on the loaded frame as `customData.points`.

```json
"warrior/idle_0": {
  "frame": {"h": 32, "w": 32, "x": 0, "y": 0},
  "pivot": {"x": 0.5, "y": 1.0},
  "points": {"chest": [16.5, 15.5], "grip": [25.5, 19.5]},
  "rotated": false,
  ...
}
```

```ts
// In Yomi this replaces GRIP_FROM_FEET:
const { grip } = scene.textures.getFrame('atlas', 'warrior/idle_0').customData.points
```

**Index** (`frames` target's `sprites.json`, `godot` target's
`<name>.json`): `sprite_entry` gains a `points` key, by frame then by point,
present only when the sprite has points. Only frames with points appear in
it. The same key in both indexes keeps one shape for both engines, and leaves
the `godot` index's `frames` (regions) as they are.

```json
"warrior": {
  "anchor": [16, 32],
  ...
  "points": {
    "attack_0": {"chest": [16.5, 15.5], "grip": [27.5, 17.5]},
    "idle_0": {"chest": [16.5, 15.5], "grip": [25.5, 19.5]},
    "idle_1": {"chest": [16.5, 16.5], "grip": [25.5, 20.5]}
  },
  ...
}
```

The `.tres` files do not change: a `SpriteFrames` has no place for points,
and a Godot game reads them from the index as it already reads the anchor.

### 4.5 Seeing points (R39)

`sprite show` prints a frame's points after its grid, one line each, sorted
by name, in the `col,row` the author wrote:

```
warrior idle_1  unit 32x32
...
31  ...........kNNnkNNnnk...........
point chest 16,16
point grip 25,20
```

`sprite preview <id>... --points` draws each point's pixel in a marker
colour, in every tile, over the frame (and over a layer's base). The marker
is a fixed, saturated magenta (`#ff00ff`), chosen because muted palettes
like the demo's never use it. The flag combines with `--grid`, `--on` and
`--anim`; the file names are unchanged, as previews are not exported and
`--grid` already keeps its own name.

### 4.6 Checks (R40)

| Code | When | Effect |
|---|---|---|
| E109 | A point's name does not match `[a-z0-9_]+`; its value is not a list of two integers; its pixel is outside the canvas; `[frame_points.<frame>]` names a frame the sprite does not have; `[frame_points]` or `[frame_points.<frame>]` is not a table. | The bad point (or table) is left out; the sprite still loads, as with other art problems. |
| W008 | A derived frame's operations take a point off the canvas. | The point is dropped from that frame and those derived from it. |
| W009 | A layer neither has nor rests through an animation its base has (section 4.10). | None; a warning. |

`[points]` and `[frame_points]` join `_TOP_LEVEL_KEYS`; anything else at the
top level is still E001.

### 4.7 Effect sprites (R41, R42)

The template config gains a class:

```toml
[canvas.effect]          # arrows, bolts, sparks: anything a game moves, turns or spawns
size = [16, 16]
anchor = [8, 8]          # the centre: the game turns the sprite about it
display_scale = 2
```

No `outline` (an effect is often a glow, and `unoutlined` cannot opt a whole
sprite in; a sprite that wants an outline sets `outline = "auto"`) and no
`grounded` (it floats).

The convention, stated in the guide:

- **Draw it pointing right** (+x). A game turns it by the angle of its flight,
  `atan2(dy, dx)`, with no offset. Draw it flat, not seen from above: the game
  adds any arc.
- **The anchor is what it turns about**, the centre of the class. An effect
  that should turn about another pixel (a sword trail about the hilt) needs a
  class anchored there.
- **Name the leading pixel `tip`**: where an arrow strikes, where a bolt's
  head is. A game lands the effect when the `tip`, not the anchor, reaches the
  target. Other names are the game's own (a burst's `centre` is its anchor and
  needs no point).
- **A one-shot effect is an animation with `loop = false`.** Glows use
  translucent palette colours (`#rrggbbaa`) or keys listed in `unoutlined`.
  The game destroys the sprite when the animation completes.

The demo gains `examples/demo/effects/arrow.sprite.toml` (one frame: shaft,
head, fletching; `[points] tip`) and `examples/demo/effects/spark.sprite.toml`
(a `burst` animation of four frames, `loop = false`, the last frame's lengths
shorter). The demo's warrior gains `[points] grip`, its fist pixel. The
demo's config gains `[canvas.effect]` as in the template.

### 4.8 Mirroring part of a frame (R43)

```toml
# The right foot lifted is the left foot lifted, mirrored about the legs.
[frames.walk_2]
from = "walk_1"
mirror = { rows = [25, 31], cols = [10, 21] }
rows = { 31 = "............kkk................." }   # then patch what is not symmetric
```

- `mirror` is a table or a list of tables, each with `rows`, `cols` or both,
  as `move` takes them, and no `by`. Each reverses the pixels of every row of
  its rectangle within the rectangle's columns.
- The operations run in the order `move`, `mirror`, `rows`, `runs`, `shift`,
  `flip`: after `move` so a moved part can be mirrored in its new place, and
  before `rows` and `runs` so they can patch the result, which is what an
  author nearly always does next.
- Origins and points ride the same operation (R35): a pixel or point at
  column `c` inside the rectangle goes to `first + last - c`.
- A mirror never moves anything off the canvas, so it has no W006 or W008.

### 4.9 Showing what a frame changes (R44)

```
$ sprite show warrior --frame walk_1 --diff
warrior walk_1 vs idle_0  unit 32x32
              1111111111222222222233
    01234567890123456789012345678901
25  ..........kDdlkkddlk............
              ^^^^^
26  ..........kDdlkkddlk............
              ^^^^^
...
31  ................kkkk............
                ^^^
```

- `--diff` takes an optional frame name. Without one it compares with the
  frame's `from` parent; a literal frame, or a derived one with no `from`,
  needs the name.
- Rows are the final rows, outline included, as `show` prints them; the marker
  line has `^` under each column whose key differs, and no trailing spaces.
  Points are listed after the rows as in R39, for the frame shown.
- `--diff` needs exactly one `--frame` and cannot be used with `--all`.
  Several ids are allowed when every one has that frame and a parent to
  compare with (or the named frame).
- Equal frames print the header and the line `no rows differ`.

### 4.10 A layer resting through an animation (R45)

```toml
# gear/gear_sword.sprite.toml
over = "warrior"

[anim.idle]
like = "warrior"        # breathes with the body

[anim.walk]
rest = true             # holds idle_0 while the body walks
```

- `rest = true` is the only field the animation table holds. It is allowed
  only in a layer (a sprite with `over`), and only for a name its base
  animates; otherwise E001 (and E105 for an unknown base animation, as `like`
  reports it).
- It resolves after `like` (`spritefile._resolve_likes`), to an `Anim` of one
  entry, the layer's default frame, lasting the sum of the base animation's
  lengths, looping as it does. Every target exports it as any other
  animation, so a game can play the same name on every layer of a figure and
  stay in step.
- W009 (check): for each animation of a layer's base that the layer neither
  has nor rests through: `anim 'walk': 'warrior' animates it and this layer
  does not; add [anim.walk] with like or rest = true`. W007 skips resting
  animations, as their single entry is meant to differ.

### 4.11 Guide (R46)

The FRAMES section gains, beside the existing `move` line:

```toml
move = { rows = [27, 30], cols = [10, 15], by = [-1, -2] }  # lift a foot: only that rectangle moves
mirror = { rows = [25, 31], cols = [10, 21] }               # mirror the legs, not the body
```

and one line each for `show --diff` (under COMMANDS) and `rest = true` (under
layers).

## 5. Technical design

### 5.1 Data model (`model.py`)

- `Frame` gains `points: tuple[tuple[str, tuple[int, int]], ...] = ()`,
  sorted by name, each `(name, (col, row))`. A tuple of pairs, not a dict,
  keeps `Frame` frozen and hashable as it is now. Default empty, so every
  existing constructor call and test stays valid.
- `Frame` gains `points_lost: tuple[str, ...] = ()`, the names of the points
  its own operations took off the canvas, for W008, beside `lost` for W006.
- `Anim` gains `rest: bool = False` (R45).
- `Sprite` gains `anim_rests: tuple[tuple[str, int], ...] = ()`, the name and
  file line of each `rest = true` not yet resolved, as `anim_likes` holds
  each `like`.
- `_Derived` (in `spritefile.py`, not the model) gains `mirrors`.

### 5.2 Parsing (`spritefile.py`)

Frame editing (R43):

- `_FRAME_KEYS` gains `"mirror"`. `_Derived` gains `mirrors: tuple[_Move, ...]`,
  parsed by `_moves` with `by` forbidden for this key (a `by` is E105 "mirror
  has no by"), so ranges and messages are shared.
- A function `_mirrored(grid, rect)` beside `_moved` reverses each row's slice.
  `_transform` applies the mirrors after the moves, so rows and origins are
  mirrored by the same code, and the outline check needs no change.

Rest (R45):

- `_ANIM_KEYS` gains `"rest"`. A table with `rest` and any other key is E001.
  `_anims` records it like a `like`, as a pending entry on the sprite
  (`anim_rests: tuple[tuple[str, int], ...]`, name and line), since its
  length needs the base.
- `load_all` resolves rests after likes: the base is `sprite.over`, its
  animation of that name must exist (else E105), and the result is an `Anim`
  with `frames = (default frame,)`, `ms` = the base's total, `loop` = the
  base's, and `rest=True` (a new `Anim` field, default False, compared like
  the others), which W007 and W009 read.

Points (R34 to R37):

- `_TOP_LEVEL_KEYS` gains `"points"` and `"frame_points"`.
- `_Parser._points(raw, canvas, where) -> dict[str, tuple[int, int]]`
  validates one table (E109 per bad entry) and returns the good points. It
  is called for `[points]` and for each `[frame_points.<frame>]`; frame
  names not among the file's frames are E109.
- In `_frames` / `_resolve`: a root frame starts with `[points]`. A derived
  frame starts with its parent's final points (after the parent's own
  `[frame_points]`), which is why resolution keeps producing frames in
  dependency order as it does now.
- `_Derived` gains a method `carry(points, canvas) -> (points, lost names)`
  that moves each point through `self.moves`, `self.shift` and `self.flip` in
  the order `_transform` applies them. It cannot reuse `_transform`'s grid
  (a point is not a cell, and `move` must not overwrite it), but it uses the
  same `_Move` values and the same order, and a test checks that a point
  lands where `origins` says its pixel went (section 7).
- After carrying, the frame's `[frame_points]` are merged in, and the frame
  is built with sorted `points` and `points_lost`.
- `_variant` needs no change: it replaces `rows` only, so `points` carry over.
- `parse` reports W008 for each name in each frame's `points_lost`, at the
  frame's line, after the W006 loop.

### 5.3 Checks (`check.py`)

- `_step_problems` skips an animation with `rest`, and adds W009: each name
  in the base's anims that the layer's anims lack.
- E109 and W008 come from parsing (section 4.6), not from here.

### 5.4 Exports

- `export/index.py`: a helper `point_json(col, row) -> [col + 0.5, row + 0.5]`,
  and `sprite_entry` adds `"points": {frame.name: {name: point_json(...)}}`
  for the frames that have any, only when one does.
- `export/phaser.py`: `_frame` adds `"points"` the same way when the frame has
  any. `_frame` is given the `Frame`, not only the `Placement`.
- `export/frames.py` and `export/godot.py` get `points` through
  `sprite_entry`, with no other change.

### 5.5 Text and previews

- `textview.frame_text` appends `point <name> <col>,<row>` lines.
- `textview.diff_text(sprite, frame, other)` prints the `--diff` block: the
  header with `vs <other>`, the same rulers, and for each differing row the
  numbered row and its marker line. `cli._show` validates the flags as in
  section 4.9 and picks `other` (`frame.parent` by default).
- `preview.drawn` takes `points: bool` and, when set, writes the marker
  colour into each point's pixel of the drawn frame image before scaling, so
  the marker is exactly one sprite pixel at every scale and lines up with the
  `--grid` lines. `cli.py` adds `--points` to `preview` and passes it down.

### 5.6 Template, demo and guide

- `templates/sprite-tool.toml` and `examples/demo/sprite-tool.toml` gain
  `[canvas.effect]`. (The existing test that compares template and demo
  copies covers the palette and warrior only; the config copies differ by
  design and stay that way.)
- `examples/demo/effects/arrow.sprite.toml` and `spark.sprite.toml`;
  `[points] grip` in `examples/demo/units/warrior.sprite.toml`, which
  also gives the template warrior a point, as the two must stay equal.
- `guide.py`: a POINTS section (declaration, inheritance table in short,
  export coordinates, `--points`), EFFECTS (the convention in four lines),
  `effect` in the canvas list it prints from the project, and section 4.11's
  lines for `move`, `mirror`, `--diff` and `rest`.
- The demo gains no layer, so `rest` and W009 are covered by tests that build
  small projects under `tmp_path`, not by the golden files.
- `make golden`, with the diff limited to A68's list.

### 5.7 Release

0.6.0: `pyproject.toml`, `uv lock`, the README's install tag, as in
`AGENTS.md`'s release steps.

## 6. Consequences

- **Compatibility.** Projects without points are unaffected (A64). A game that
  reads `atlas.json` with Phaser gains `customData.points` on frames that have
  points and nothing on frames that do not; Phaser already copied the other
  keys into `customData`, so nothing new is exposed by surprise.
- **Base design sections to bring in line:** 4.4 (sprite file: `[points]`,
  `[frame_points]`), 4.6 (E109, W008), 4.7 (the `points` keys of each
  target), 4.8 (`--points`), 5.3 (`Frame.points`).
- **Why per sprite and per frame, and not per class.** See the first non-goal.
  Yomi's grip is the warrior's alone; per frame because an attack frame
  raises the arm, and inherited through operations because the breathing
  frame (`idle_1`, the body a pixel lower) must lower the grip too, which the
  author should not have to restate.
- **Why pixel centres.** Authors name pixels in every other part of the file
  (`runs`, `move`, check messages, `show`'s rulers), so a point is a pixel.
  Games need a position, and the centre is the honest one: Yomi's
  `GRIP_FROM_FEET` already adds `0.5` by hand.
- **Why canvas coordinates and not offsets from the anchor.** One frame of
  reference for every point and the bounds, which are already canvas
  coordinates; the anchor is beside them in every export. Offsets would also
  differ from what `show` prints.
- **Performance.** Points are a few pairs a frame; carrying them is
  negligible against the 200-sprite speed test.
- **Why `mirror` and not a partial `flip`.** `flip` stays what it is (the
  whole frame, last), so existing frames are untouched; a rectangle needs a
  table, and `move`'s table is already the shape authors know.
- **Why `rest` exports an animation rather than nothing.** A game that plays
  one name on every layer of a figure needs no fallback. Yomi has such a
  fallback already, and keeps working either way.
- **Base design sections to bring in line (frame editing):** 4.4 (`mirror`,
  `rest`), 4.5 (`show --diff`), 4.6 (W009).
- **Effect class in existing projects.** Not added: the tool never edits a
  project's config. The guide's convention applies to any class a project
  declares, so Yomi adds its own `[canvas.effect]` when it draws one.

## 7. Verification

Tests follow `AGENTS.md`: pytest under `tmp_path`, no display, no network,
`make check` before each commit.

- `tests/test_points.py` (proposed):
  - parsing: A58's literal frame; A61 for literal and derived frames, and
    the frame-only point; A63, one case per bad form, each one E109 and the
    sprite still loading.
  - carrying (A59, A60): each operation alone and `move` + `shift` + `flip`
    together. A property-style test over every operation in the demo and a
    few hand-made frames: for each point, `Frame.origins` at the point's new
    position is its old position, which ties `carry` to `_transform`
    whenever the point's pixel is not overwritten.
  - W008 alongside W006.
  - variants (A62).
- `tests/test_export_*.py`: the `points` keys of A58, their absence for a
  sprite without points (A64 in small), sorted order.
- `tests/test_move.py` or a new `tests/test_mirror.py`: A70 to A72, with a
  test that a pixel's `origins` after a mirror name the parent pixel it came
  from.
- `tests/test_show.py`: A73 and A74, with A65.
- `tests/test_layers.py`: A75 and A76, building a two-sprite project (base
  and layer) under `tmp_path` and reading the Phaser animation JSON. `tests/test_preview.py`: A66, reading the
  marker pixel's colour at a known scale.
- `tests/test_init_new_guide.py`: A67, A69 and A77 (guide length and the
  names it must mention).
- `tests/test_golden.py`: A68 through `make golden`. A64 is a unit test that
  no export of a sprite without points has a `points` key, plus, by hand,
  building Yomi's `art/` project (which has no points) with 0.6.0 and seeing
  `sprite build --check` report nothing stale.
- **In a game.** Not part of this repository's tests, but the check that the
  feature does its job: in Yomi, replace `GRIP_FROM_FEET` with the atlas's
  `customData.points.grip` and confirm the swing is unchanged, then draw the
  arrow on an `effect` class and fly it in place of the `Graphics` arrow.
  Redraw one unit's `walk_2` as `mirror` of its `walk_1` plus a patch, and
  check `show --diff` against the committed frame; add `rest = true` for
  `walk` to Yomi's gear and see W009 go.

## 8. Open questions and assumptions

### Assumptions

- Games load the Phaser atlas with Phaser's JSON Hash loader, which keeps
  unknown frame keys in `customData` (checked in Phaser 4.2.1). Other loaders
  of the same format may drop the key; the index carries the same data.
- One marker colour is enough for `--points`; points are few and `show`
  names them.
- 16×16 at 2× suits arrows, bolts and sparks for a 32-pixel unit at 2× or 3×.
  Yomi shows its units at 2× and its board scales them further; the effect
  class there would match.

### Questions (non-blocking)

- **Q-1.** Should `[frame_points]` be able to remove an inherited point (for
  example `muzzle = false` on a frame where the bow is lowered)? Proposed:
  not in 0.6; a game can treat a point as meaningful only in the frames it
  uses. Easy to add later as a value form.
- **Q-2.** Should the marker colour be configurable under `[preview]`?
  Proposed: not until a palette uses magenta.
- **Q-3.** Should gear layers share a point list with `points_like = "<id>"`?
  Yomi's gear sprites are all drawn to the same grip but do not need it, as
  the game reads the body's. Revisit if a game turns a layer about a point of
  its own.
- **Q-4.** Should `mirror` also take `axis` (a column to mirror about) for a
  rectangle whose contents are not centred? Proposed: no; choose the
  rectangle so its centre is the axis, which `show`'s rulers make easy.
- **Q-5.** Should `--diff` accept a frame of another sprite (`--diff
  goblin/idle_0`), for comparing two units' gaits? Proposed: not in 0.6; see
  the non-goal.
