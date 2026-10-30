# sprite-tool 0.7: tints

- **Date:** 2026-10-30
- **Status:** Implemented in 0.7.0. Assumptions and non-blocking questions
  are in [section 8](#8-open-questions-and-assumptions). Where the build
  differs from the text below: W010 names keys in palette order, so the
  demo palette gives `o, y`, not `y, o` as in the 4.4 example; the demo
  orb's `pulse` is 100 ms a frame; a panel's label sits at its image's left
  margin; and the guide's COMMANDS entry is `--tint <colour>,...` with
  `--tint-mode fill` in its description.
- **Amends:** [sprite-tool.md](sprite-tool.md) (the base design), after
  [feedback-fixes.md](feedback-fixes.md) (0.3),
  [text-view-and-runs-discovery.md](text-view-and-runs-discovery.md) (0.4),
  [layers-animation-and-export-selection.md](layers-animation-and-export-selection.md)
  (0.5) and [points-and-effect-sprites.md](points-and-effect-sprites.md)
  (0.6). Requirement and criterion ids continue their numbering (the last
  were R46 and A77). Where this document and an earlier one disagree, this
  one wins. In particular it narrows 0.6's non-goal "how a game … tints … an
  effect is the game's business": the tint is still applied by the game, but
  the tool can now show it and record which tints a sprite is drawn for.
- **Source:** GitHub issue #1, "preview: --tint to show a sprite as the game
  tints it", and the owner's comment on it ("Generalising beyond Phaser").
  Scope decided with the owner on 2026-10-30: the core `--tint`, plus
  `--tint-mode fill`, tints declared in the sprite file (and exported), and a
  warning for tinted sprites drawn in strong colours. A layer's tint covers
  the layer only.

## 1. Purpose

Games often draw an effect once, in pale greys, and tint it at run time:
Yomi's `fx_dart`, `fx_orb` and `fx_burst` are drawn in `W`, `w` and `l` and
tinted by about eight spell colours. Phaser's `setTint` multiplies each pixel
by the tint colour; Godot's `modulate`, Unity's `SpriteRenderer.color`,
LÖVE's `setColor`, GameMaker's `image_blend`, MonoGame's `SpriteBatch.Draw`
colour and Defold's `tint` constant all do the same.

`sprite preview` draws only the palette colours. Whether the greys hold up
under a dark tint (purple, olive) or wash out under a light one can be judged
only in the game; checking Yomi's effects meant scripted, slowed-down browser
screenshots. Which colours an effect is meant for lives in game code, apart
from the drawing.

After 0.7:

1. `sprite preview fx_orb --tint "#ff7a1a,#7ee07e"` writes one image with the
   orb under each tint, side by side and labelled.
2. `--tint-mode fill` shows the hit-flash silhouette (Phaser's
   `TintModes.FILL`): every drawn pixel becomes the tint colour.
3. A sprite file can declare its tints by name. `preview` draws them without
   a flag, and the `frames` and `godot` indexes export them, so a game can
   read a sprite's tints instead of keeping its own table.
4. `check` warns when a sprite meant to be tinted is drawn in strong colours,
   which multiplying muddies.

## 2. Requirements and scope

### Functional requirements

| ID | Requirement |
|---|---|
| R47 | `sprite preview <id>... --tint <colour>[,<colour>...]` draws each sprite tinted by each colour. A colour is `#rrggbb`, `#rrggbbaa`, a palette key, or `none` (untinted). |
| R48 | A multiply tint sets each channel, alpha included, to `round(pixel × tint / 255)` on 8-bit values. Transparent pixels stay transparent. Outline pixels are tinted like the rest. |
| R49 | `--tint-mode fill` makes every drawn pixel the tint's colour, its alpha the pixel's alpha times the tint's (same rounding). `multiply` is the default. |
| R50 | With tints, each sprite is drawn once per tint, left to right in a labelled panel. The tint applies to the sprite (and its variants' rows) only: never to the preview background, the grid, the tile under `--on`, the base under a layer, or the `--points` marker. |
| R51 | Tints work with `--grid`, `--scale` (including `display`), `--on`, `--points` and `--anim`. With `--anim` the strip has one panel per tint and each GIF plays every tint side by side in step. |
| R52 | A tint that is not a valid colour, a palette key or `none`, `--tint` without a sprite id, and `--tint-mode` without `--tint` exit 2 with a message naming the problem. |
| R53 | A sprite file can declare `tints`: a table of name to a colour (multiply) or to a table `{ colour = ..., mode = "multiply" \| "fill" }`. Variants have their base sprite's tints. |
| R54 | Without `--tint`, `preview` draws a sprite with declared tints untinted (`none`) and then under each declared tint by name. The contact sheet adds one cell per declared tint after the sprite's own. `--tint` replaces the declared tints for that run. |
| R55 | The `frames` and `godot` indexes list a sprite's declared tints, with the colour resolved to hex and the mode. A sprite without tints gains no key. |
| R56 | `check` reports a malformed `tints` table (E110) and leaves the bad tint out. It warns (W010) when a sprite with a multiply tint draws with a palette colour whose chroma is over a fixed limit. |
| R57 | `sprite guide` documents `--tint`, `--tint-mode`, declared tints, W010 and the colour-space caveat, next to the effect convention. |

### Quality constraints

The base design's Q1 to Q5 hold. These are the ones affected:

- **Q1 (determinism).** The tint formula uses integer arithmetic with fixed
  rounding, so a tinted preview is the same every run. (Previews are exempt
  from byte-stability across Pillow versions, as before.) Exported `tints`
  are sorted by name and written through `json_bytes`.
- **Q2 (token-friendly output).** `preview --tint` prints one path per file,
  as `preview` does: one PNG, or with `--anim` the strip and one GIF per id.
  `AGENTS.md`'s output rule ("one GIF per id") still holds, because the tints
  of one id share a GIF.

**Compatibility.** A 0.6.0 project with no `tints` builds byte-identical
files, and its previews are the same images: no panel and no label appear
unless a tint is asked for or declared. W010 fires only for sprites that
declare tints, so no existing project gains a warning. `version = 1` in the
config stays.

### Non-goals

- **Other blend modes** (Phaser's `ADD`, `SCREEN`, `OVERLAY`; additive
  particles). Multiply and fill cover the two common uses; add a mode when a
  game asks for it.
- **Linear-light tinting.** Unity in linear colour space and Godot with HDR
  2D multiply after converting to linear light, so their mid-tones come out
  somewhat lighter. The preview is exact for sRGB engines (Phaser, Godot's
  default 2D) and close elsewhere; the guide says so.
- **Tints in the Phaser atlas.** The issue asks for the `frames` and `godot`
  indexes. Phaser exposes no sprite-level data from a JSON Hash atlas, and
  copying tints into every frame's `customData` would repeat them per frame.
  See [question Q-1](#questions-non-blocking).
- **Godot metadata on the `SpriteFrames` resource.** The Godot target's JSON
  index already carries what a `SpriteFrames` cannot (anchor, points); tints
  join them there. The `.tres` files are unchanged.
- **Naming a declared tint on the command line** (`--tint fire`). Tint names
  and one-letter palette keys could collide. Declared tints are drawn by
  default; `--tint` takes colours.
- **Tints in `sprite show`.** It is text; a tint changes no key.
- **Animated tints** (a flicker between colours) and **parent tints**. A
  game's inherited `modulate` is a product of colours; the author can preview
  the product as one colour.
- **Tinted exports.** The tool never writes a tinted copy of a sprite into
  an export. A palette swap that should be baked in is a variant.

### Acceptance criteria

| ID | Criterion | Covers |
|---|---|---|
| A78 | With the demo palette, `sprite preview orb --tint "#ff7a1a"` writes `.preview/orb.plain.tint-ff7a1a.png` and prints its path. Every pixel drawn in `w` (`#f4f4f4`) is `(244, 117, 25, 255)` in the tinted panel; background pixels are the preview background. | R47, R48 |
| A79 | `--tint "#ffffff80"` gives every drawn pixel half its alpha (a pixel of alpha 255 becomes 128) and unchanged colour; `--tint "#ffffff"` gives an image whose panel equals the untinted drawing. | R48 |
| A80 | `--tint "#ff7a1a,C,none"` writes `orb.plain.tints.png` with three panels left to right, labelled `#ff7a1a`, `C #73eff7` and `none`; the `C` panel equals `--tint "#73eff7"`'s panel and `none` equals the untinted drawing. | R47, R50 |
| A81 | `--tint "#ffffff" --tint-mode fill` draws every drawn pixel white with its own alpha, writes `orb.plain.tint-ffffff-fill.png`, and labels the panel `#ffffff fill`. | R49 |
| A82 | `--tint "#ff7a1a" --on ground_light` tints the orb and leaves every pixel of the tile as without `--tint`. `--grid` lines, `--points` markers and, for a layer, the base's pixels are also untinted. | R50, R51 |
| A83 | `sprite preview orb --anim pulse --tint "#ff7a1a,#7ee07e"` prints two paths: `orb.anim-pulse.tints.png` (two labelled strips side by side) and `orb.anim-pulse.tints.gif`, whose frames each show both tints side by side with the animation's frame lengths. | R51, Q2 |
| A84 | `--tint "#ff7a1"`, `--tint "zz"` and `--tint "?"` (no such palette key) each exit 2 with `error: bad tint '<text>': expected #rrggbb, #rrggbbaa, a palette key or none`. `sprite preview --tint "#ff7a1a"` (no id) and `sprite preview orb --tint-mode fill` (no `--tint`) each exit 2. Nothing is written. | R52 |
| A85 | A sprite with `tints = { fire = "#ff7a1a", frost = "C", flash = { colour = "#ffffff", mode = "fill" } }` loads with three tints in name order: `fire` multiply `#ff7a1a`, `flash` fill `#ffffff`, `frost` multiply `#73eff7`. Its variant has the same tints. | R53 |
| A86 | `sprite preview orb` (orb declares those three tints) writes `orb.plain.png` with four panels, `none`, `fire`, `flash fill` and `frost`; `sprite preview` (the contact sheet) shows the orb's cell followed by cells labelled `fire`, `flash` and `frost`. `--tint "#ffffff"` draws one panel and ignores the declared tints. | R54 |
| A87 | The `frames` index (`sprites.json`) and the Godot `atlas.json` entry for `orb` have `"tints": {"fire": {"colour": "#ff7a1a", "mode": "multiply"}, "flash": {"colour": "#ffffff", "mode": "fill"}, "frost": {"colour": "#73eff7", "mode": "multiply"}}`. No other sprite's entry gains a key. | R55, Q1 |
| A88 | Each of these is one E110 naming the tint, and the sprite still loads without it: `tints = "fire"`; `Fire = "#ff7a1a"`; `fire = "#ff7a1"`; `fire = "?"` (not in the palette); `fire = 3`; `fire = { colour = "#ff7a1a", mode = "add" }`; `fire = { mode = "fill" }`; `fire = { colour = "#ff7a1a", alpha = 1 }`; `fire = "none"`. | R56 |
| A89 | A sprite with a multiply tint whose frames use `y` (`#ffcd75`, chroma 138) and `w` gets one W010 at the `tints` line naming `y` and not `w`. With only fill tints, or no tints, it gets none. The demo checks clean. | R56 |
| A90 | A 0.6.0 project with no `tints` builds byte-identical output under 0.7.0, and its `preview` images equal 0.6.0's. | Compatibility |
| A91 | The demo builds `orb` (effect class, drawn in `w`, `l` and `d`, a looping `pulse` animation, the three tints of A85), and the golden files change by that sprite and nothing else. | R53, R55, Q1 |
| A92 | `sprite guide` mentions `--tint`, `--tint-mode fill`, `tints`, W010 and that linear-light engines come out lighter, and stays under 130 lines for the demo. | R57 |

## 3. Current system

Inspected at `6b364fd` (0.6.0):

- [`src/sprite_tool/preview.py`](../../src/sprite_tool/preview.py): every
  preview image goes through `drawn(project, sprite, frame, base, points)`,
  which renders the frame, composites it over a layer's base frame, then
  writes the `--points` marker. `sprite_preview`, `on_tile` (through
  `_display`), `contact_sheet`, `anim_frames` and `anim_strip` build on it;
  `stack` puts several ids' images one under another. Labels use Pillow's
  built-in bitmap font (`CHAR_WIDTH`, `LINE_HEIGHT`, `_ink`).
- [`src/sprite_tool/cli.py`](../../src/sprite_tool/cli.py) `_preview`:
  validates flag combinations (`--anim` with `--grid`, `--on` or `--sheet` is
  a usage error), loads through `_load_drawable`, picks the file stem
  (`<ids>.plain`, `.grid`, `.on-<tile>`, `.anim-<name>`, `sheet`), saves to
  `.preview/` and prints one path per file. Usage errors go through
  `_usage_error` (exit 2).
- [`src/sprite_tool/project.py`](../../src/sprite_tool/project.py)
  `_parse_hex` parses `#rrggbb` and `#rrggbbaa` to RGBA for the palette and
  `[preview] background`. It is private.
- [`src/sprite_tool/spritefile.py`](../../src/sprite_tool/spritefile.py):
  `_TOP_LEVEL_KEYS` lists the keys a sprite file may have; `_unoutlined` and
  the `[points]` parser show how a top-level key is validated and reported
  (`self.report(code, message, *key)`); `_variant` builds a variant with
  `dataclasses.replace`, so new `Sprite` fields carry over unchanged. The
  last parser codes are E109 and W008.
- [`src/sprite_tool/check.py`](../../src/sprite_tool/check.py) `run`: checks
  on resolved sprites; per-sprite checks are not repeated for variants. The
  last warning is W009.
- [`src/sprite_tool/export/index.py`](../../src/sprite_tool/export/index.py)
  `sprite_entry`: the keys the `frames` and `godot` indexes share. Optional
  keys (`over`, `points`) appear only when the sprite has them.
- [`src/sprite_tool/guide.py`](../../src/sprite_tool/guide.py): the EFFECTS
  section (lines 76 to 78) and the COMMANDS table. The guide prints 125 lines
  for the demo; `tests/test_init_new_guide.py` holds it under 130.
- The demo palette (Sweetie 16) has no neutral greys except `w`; `l`, `d`, `D`
  and `k` are blue-greys with chroma (max channel minus min channel) 46, 48,
  36 and 18. The coloured keys have chroma 54 (`R`) to 152 (`o`).
- The demo has two effects, `arrow` (drawn in `r`, `o`, `d`, `l`) and `spark`
  (`y`, `o`, `w`), both coloured and neither meant to be tinted.

## 4. Proposed behavior

### 4.1 `--tint` (R47 to R52)

```
sprite preview <id>... --tint <colour>[,<colour>...] [--tint-mode multiply|fill]
```

Each comma-separated item, trimmed of spaces, is one of:

| Form | Meaning |
|---|---|
| `#rrggbb`, `#rrggbbaa` | that colour; case-insensitive; alpha `ff` when omitted |
| a palette key | that key's colour, alpha included |
| `none` | untinted |

Items are drawn in the order given; a repeated item is drawn once. A palette
key `,` cannot be named (it is the separator), and keys are one character,
so neither `none` nor a hex colour is ever a key.

Errors (exit 2, nothing written):

- `error: bad tint '<item>': expected #rrggbb, #rrggbbaa, a palette key or none`
- `error: --tint needs a sprite id`
- `error: --tint-mode needs --tint`

`--tint-mode` applies to every colour of `--tint`; it has no effect on
`none`. The tint is checked after the project loads (palette keys need the
palette) and before anything is drawn.

**Formulas.** On 8-bit channels, for a pixel `p` and tint `t`:

- multiply: `out[c] = (p[c] * t[c] + 127) // 255` for each of R, G, B, A.
- fill: `out.rgb = t.rgb`, `out.a = (p.a * t.a + 127) // 255`.

`(x + 127) // 255` is `round(x / 255)` exactly: `x / 255` is never halfway
between integers, since `2x` is even and `255 × (2k + 1)` is odd. A pixel
with alpha 0 has alpha 0 after either mode. Multiplying by white
(`#ffffff`) changes nothing. This is Phaser's default tint and Godot's
`modulate` in the default (non-HDR) 2D renderer, up to the GPU's own
rounding.

**What is tinted.** The sprite's own pixels, before anything else is drawn
with them. Not tinted: the preview background, grid lines and labels, the
tile under `--on` (so contrast against the real ground can be judged), the
base under a layer (a game tints the layer's node, not the body under it),
and the `--points` marker (it must stay findable). Variant rows of a plain
preview are tinted like the sprite's own row.

**Panels.** With tints, each id's image is a row of panels, one per tint,
left to right. A panel is the image the same command draws without tints
(the `sprite_preview`, `on_tile` or `anim_strip` image), with one label line
above it. Several ids are stacked one under another as now, each with its own
row of panels. Labels:

| Tint | Label |
|---|---|
| hex from `--tint` | `#ff7a1a` (lower-case, as `hex_colour` writes it) |
| palette key from `--tint` | `C #73eff7` |
| declared | its name, `fire` |
| `none` | `none` |
| fill mode | the above followed by ` fill` |

**File names.** The stem and kind are as today, followed by a tint part:

| Tints | Part | Example |
|---|---|---|
| none given, none declared | nothing | `orb.plain.png` |
| declared, no `--tint` | nothing | `orb.plain.png` |
| one from `--tint` | `.tint-<hex>`, `-fill` for fill, `.tint-none` for `none` | `orb.plain.tint-ff7a1a.png`, `orb.on-ground_light.tint-ffffff-fill.png` |
| several from `--tint` | `.tints` | `orb.plain.tints.png`, `orb.anim-pulse.tints.gif` |

`<hex>` is the resolved colour without `#`, eight digits when not opaque,
so `--tint C` and `--tint "#73eff7"` write the same file.

**With `--anim`.** The strip has one panel per tint, side by side, each the
strip as drawn now. Each id's GIF has, per frame, that frame's tile under
every tint side by side with the panel labels above, so all tints play in
step. Frame lengths are unchanged.

**With `--sheet` or no ids.** `--tint` does not touch the contact sheet; see
4.3 for declared tints there.

### 4.2 Declared tints (R53 to R55)

```toml
# effects/orb.sprite.toml
canvas = "effect"
tints = { fire = "#ff7a1a", frost = "C", flash = { colour = "#ffffff", mode = "fill" } }
```

or as a table:

```toml
[tints]
fire = "#ff7a1a"
frost = "C"
flash = { colour = "#ffffff", mode = "fill" }
```

- A name matches `[a-z0-9_]+`, like a point.
- A string value is a colour (`#rrggbb`, `#rrggbbaa` or a palette key) with
  mode `multiply`. `none` is not a colour here.
- A table value has `colour` (required, same forms) and `mode` (`multiply`,
  the default, or `fill`), and no other key.
- A palette key is resolved when the file is parsed. A variant has its
  base's resolved tints: a variant's `swap` does not change them.
- `tints = {}` is the same as no `tints`.

**Exports.** `sprite_entry` adds, only when the sprite has tints:

```json
"tints": {
  "fire": {"colour": "#ff7a1a", "mode": "multiply"},
  "flash": {"colour": "#ffffff", "mode": "fill"},
  "frost": {"colour": "#73eff7", "mode": "multiply"}
}
```

Colours are written by `model.hex_colour`: `#rrggbb`, or `#rrggbbaa` when
not opaque. The key is spelled `colour`, as in the sprite file. The Phaser
atlas and the `.tres` files are unchanged.

### 4.3 Previewing declared tints (R54)

Without `--tint`, a sprite with declared tints is drawn in panels: `none`
first, then each tint by name. The file name has no tint part, as the panels
are what that sprite's preview is. A sprite without tints is drawn exactly as
in 0.6, with no panel and no label. When several ids are previewed, each
row of panels is that sprite's own. With `--on`, it is the sprite's tints
that are drawn, never the tile's; with a layer, the layer's, never the
base's.

`--tint` replaces the declared tints for that run, for every id: `--tint
none` gives one `none` panel.

The contact sheet keeps one cell per sprite and adds, right after a sprite
with tints, one cell per tint in name order: the default frame tinted,
labelled with the tint's name. Those cells count toward `SHEET_COLUMNS` and
wrap like any other.

### 4.4 Checks (R56)

| Code | When | Effect |
|---|---|---|
| E110 | `tints` is not a table; a tint name does not match `[a-z0-9_]+`; a value is neither a string nor a table; a colour is not `#rrggbb`, `#rrggbbaa` or a palette key; a table has no `colour`, a key other than `colour` and `mode`, or a `mode` other than `multiply` or `fill`. | The bad tint (or the whole `tints` when it is not a table) is left out; the sprite still loads, as with E109. |
| W010 | A sprite with at least one multiply tint draws, in any frame, with a palette key whose colour's chroma (max of R, G, B minus min) is over `TINT_CHROMA_LIMIT` (64). | None; a warning. |

W010's message names the keys in palette order and the limit:

```
effects/fx_orb.sprite.toml:3:1: W010 tinted sprite draws with coloured keys y, o (chroma over 64); multiplying muddies them: draw tinted art in greys
```

It is reported at the line of `tints`, once per sprite, not again for each
variant. Chroma and not saturation, because a dark colour's tint stays dark
whatever its hue (`k`, chroma 18, has HSV saturation 0.41), while a pale
strong colour shifts the tint visibly. With the demo palette, `w`, `l`, `d`,
`D`, `k` and `R` pass and the rest fail; the test of A89 pins that.

### 4.5 Guide (R57)

In the EFFECTS section, about three lines:

> Draw an effect a game tints in greys; `tints = { fire = "#ff7a1a", flash =
> { colour = "#ffffff", mode = "fill" } }` names its tints for preview and the
> indexes; check warns (W010) of coloured keys. Linear-light engines (Unity
> linear, Godot HDR 2D) come out lighter than the preview.

(The implementer may reword it to fit the line budget.) In
COMMANDS, one entry for `sprite preview <id>... --tint <colour>,... [--tint-mode
fill]`: "each sprite under each tint, side by side; a colour is #rrggbb, a
palette key or none". The guide stays under 130 lines for the demo; if the
new lines push it over, tighten existing wording rather than raise the limit.

## 5. Technical design

### 5.1 Data model (`model.py`)

```python
TINT_MODES = ("multiply", "fill")

@dataclass(frozen=True)
class Tint:
    """A colour a game draws a sprite in. `label` is what preview prints over its panel."""
    colour: tuple[int, int, int, int]
    mode: str = "multiply"
    label: str = ""
```

`Sprite` gains `tints: tuple[tuple[str, Tint], ...] = ()`, sorted by name,
and `tints_line: int = 0`, the file line of `tints` (for W010), documented
in the class docstring like `over_line`. `None` stands for "untinted"
wherever a tint is optional; the declared-tint panel list is built as
`[None, *tints]`.

### 5.2 Colours (`project.py`)

`_parse_hex` becomes public as `parse_hex` (same behaviour), and a new
`resolve_colour(text, palette) -> tuple[int, int, int, int] | None` returns
the hex colour, else the palette key's colour, else `None`. The palette
loader keeps using `parse_hex`; the sprite file parser and `cli._preview`
use `resolve_colour`. `project.py` stays the only reader of config files;
these are pure functions on strings.

### 5.3 Parsing (`spritefile.py`)

- `"tints"` joins `_TOP_LEVEL_KEYS`.
- `_tints(data)` validates as in 4.4, reporting E110 with the key path
  `("tints", name)` (or `("tints",)`), and returns the sorted tuple. Labels
  of declared tints are their names.
- `Sprite(..., tints=..., tints_line=...)`; `_variant` needs no change, as
  `replace` keeps both fields.

### 5.4 Checks (`check.py`)

`TINT_CHROMA_LIMIT = 64` and `_tint_problems(project, sprite)` for W010,
called from `run` for each sprite that is not a variant. Keys come from every
frame's `rows` (so an auto outline's key counts); the transparent key is
skipped. A sprite whose tints are all `fill` is skipped.

### 5.5 Exports (`export/index.py`)

`sprite_entry` adds `tints` as in 4.2 after `points`, only when
`sprite.tints` is not empty. No exporter changes beyond that: `frames` and
`godot` already spread `sprite_entry`.

### 5.6 Previews (`preview.py`)

- `tinted(image, tint) -> Image` applies 4.1's formula to an RGBA image
  through per-band lookup tables (`Image.point` with a 256-entry table per
  band, built from the integer formula), not `ImageChops.multiply`, whose
  rounding is not the one specified. Fill sets R, G, B bands to constants
  and maps A through the table.
- `drawn(..., tint: Tint | None = None)` tints the rendered frame, then
  composites it over the (untinted) base, then writes point markers.
- `sprite_preview`, `on_tile` (`_display` for the figure only), `anim_frames`
  and `anim_strip` take `tint: Tint | None = None` and pass it to `drawn`.
- `panels(project, [(label, image), ...]) -> Image`: images left to right
  on the preview background, each under one label line (`LINE_HEIGHT` plus
  `LABEL_GAP`), a panel as wide as the wider of its image and its label plus
  `2 * MARGIN`. One function serves the PNGs and each GIF frame.
- `contact_sheet` adds the tint cells of 4.3; its cell width already allows
  for the longest label in a class.
- `anim_frames` is called once per tint and the per-tint tile lists are
  zipped frame by frame into `panels`, so `save_gif` is unchanged.

### 5.7 CLI (`cli.py`)

- `preview` gains `--tint <colour>[,...]` (`metavar="<colour>[,...]"`) and
  `--tint-mode {multiply,fill}` (default `None`, so "given without `--tint`"
  can be detected).
- `_preview` checks R52's errors: `--tint-mode` without `--tint` and `--tint`
  without ids before loading; each item after loading, through
  `resolve_colour`, building `Tint`s with the 4.1 labels.
- For each id, the tints are the `--tint` list if given, else `[None,
  *declared]` if the sprite declares any, else none (drawn as now, no
  panels). It draws one image per tint and joins them with `panels`, then
  `stack`s the ids as now.
- The file name gets 4.1's tint part.

### 5.8 Demo, guide and help

- `examples/demo/effects/orb.sprite.toml` (proposed): `canvas = "effect"`, a
  round orb in `w`, `l` and `d` (chroma 0, 46, 48), two or three frames
  growing and shrinking, `[anim.pulse]` looping, and A85's three tints.
  `make golden`; the diff is the orb's files, its place in the sheets
  (packing moves other sprites' regions, as when `arrow` and `spark` were
  added), and its index entries.
- The template that `sprite init` writes is unchanged.
- `guide.py` as in 4.5; help strings for both flags.
- Base design sections to bring in line: 4.4 (`tints`), 4.6 (E110, W010),
  4.7 (the `tints` index key), 4.8 (`--tint`, `--tint-mode`, panels and file
  names), 5.3 (`Tint`, `Sprite.tints`).
- `AGENTS.md`: the `preview.py` and `project.py` lines of Layout gain
  `tinted`/`panels` and `resolve_colour`.

### 5.9 Release

0.7.0: `pyproject.toml`, `uv lock`, the README's install tag, as in
`AGENTS.md`'s release steps.

## 6. Consequences

- **Compatibility.** Projects without `tints` build and preview as before
  (A90). Games reading `sprites.json` or the Godot `atlas.json` see a new
  `tints` key only on sprites that declare it.
- **Why multiply by default and fill as the only other mode.** Multiply is
  what every engine in the issue's table does by default; fill is the
  hit-flash, the next most common use, and costs a lookup table. Additive and
  screen modes wait for a game that needs them.
- **Why the tint covers only the sprite.** The panels exist to judge the
  sprite in the game's colours against what is really around it: the
  untinted ground, the untinted body under a weapon.
- **Why `none` first in declared panels.** The drawing is in greys and is
  edited as such; seeing it beside its tints shows which greys carry the
  shape.
- **Why tints in the indexes.** The same reasoning as named points: which
  colours an effect is drawn for is a fact about the drawing, and a game
  should read it rather than keep a second table in step.
- **Why a fixed chroma limit and no opt-out.** It is a warning; a sprite that
  keeps one coloured part on purpose lives with one line in `check`, as with
  W002. Q-2 revisits this if it proves noisy.
- **Performance.** Tinting is a lookup per band of small images; no effect
  on build, which never tints.

## 7. Verification

Tests follow `AGENTS.md`: pytest under `tmp_path`, no display, no network,
`make check` before each commit.

- `tests/test_tint.py` (proposed):
  - formula: `tinted` on a one-pixel image for A78's and A79's values, white
    as identity, alpha 0 staying 0, fill (A81); a brute-force check over all
    `(p, t)` in 0..255 that the table equals `round(p * t / 255)`.
  - `resolve_colour`: hex six and eight digits, upper case, palette key,
    unknown key, `none` rejected.
  - parsing (A85, A88): each bad form one E110, the sprite still loading;
    the variant's tints.
  - W010 (A89), including the fill-only and variant cases.
- `tests/test_preview.py`: A78 to A84 and A86 through the CLI on a copy of
  the demo, reading pixels at known positions using the layout constants
  (`MARGIN`, `LINE_HEIGHT`, `LABEL_GAP`); A82's untinted tile, grid, marker
  and layer base (a small two-sprite project); A83's GIF read back with
  Pillow (frame count and durations, both panels in a frame); file names and
  printed paths; A90 as "no tints declared or given → image equal to the
  0.6 code path" (same function, no panel).
- `tests/test_export_index.py`: A87, and no `tints` key on a sprite without.
- `tests/test_init_new_guide.py`: A92 (names present, under 130 lines).
- `tests/test_golden.py`: A91 through `make golden`; `make check` keeps the
  demo free of W010.
- **In a game.** Outside this repository's tests: in Yomi, declare the
  spell colours on `fx_dart`, `fx_orb` and `fx_burst`, compare `preview`
  against an in-game screenshot under two tints, and read the colours from
  `sprites.json` in place of the game's table if it loads that index.

## 8. Open questions and assumptions

### Assumptions

- The rounding of A78 is close enough to engines' GPU rounding that one step
  of difference in a channel does not matter for judging art.
- Labels in the 6-pixel bitmap font fit over panels; a panel widens to its
  label when the sprite is narrower.
- Yomi's palette greys (`W`, `w`, `l`) have chroma under 64, like the demo's.
  If not, W010 would fire on the motivating sprites and the limit needs
  revisiting before release (check by running 0.7's `check` on Yomi's `art/`).

### Questions (non-blocking)

- **Q-1.** Should the Phaser target carry tints too, for games that load only
  the atlas? Options: a `tints` key in each frame's `customData` (repeated per
  frame), or a key in the animation JSON. Proposed: not in 0.7; revisit if
  Yomi needs it, which depends on whether it reads `sprites.json`.
- **Q-2.** Should W010 have an opt-out (`tint_keys = ["y"]` for a part meant
  to stay coloured), or a configurable limit? Proposed: not until it is
  noisy in a real project.
- **Q-3.** Should `--tint` accept a declared tint's name? Proposed: no (see
  non-goals); if wanted, a prefix such as `@fire` avoids the clash with
  palette keys.
