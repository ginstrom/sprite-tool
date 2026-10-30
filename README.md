# sprite-tool

A command-line tool (`sprite`) that turns text sprite definitions into pixel
art for Godot 4 and Phaser games. It is built to be driven by a coding agent
as much as by a person.

The tool fixes the parts that must stay consistent across a game's art: the
palette, the canvas sizes, the style rules, sheet packing, engine metadata and
previews. The drawing itself stays open: each sprite is a small text file
holding a grid of palette keys, one character per pixel.

```toml
canvas = "unit"
[frames]
idle_0 = """
.kkkk.
kbwwbk
kbBBbk
.kkkk.
"""
```

A sprite can also leave the outline to the tool and give only the pixels it
draws, as runs: a row, then `[column, "pixels"]` pairs.

```toml
canvas = "unit"
outline = "auto"
[frames.main.runs]
1 = [[1, "bwwb"]]
2 = [[1, "bBBb"]]
```

## When to use it, and when not

Use it for small, palette-limited sprites (units, tiles, icons) in a
turn-based or otherwise low-frame-count game, where you want the art in
version control as reviewable text and the exported files to be reproducible.

It is not a drawing program. It has no GUI, no drawing helpers beyond the
automatic outline, no watch mode,
no frame trimming or rotation in the packer, no tilemap export, and no engines
other than Godot 4 and Phaser. If the art is drawn in Aseprite or similar,
export from there instead; `sprite import` is for bringing a few existing PNGs
in, not for a round-trip workflow.

## Install

The tool is installed on the machine of whoever draws sprites. The game
itself needs nothing: it uses the exported files, which are committed.

With [uv](https://docs.astral.sh/uv/), which fetches Python 3.11 or later if
it is missing:

```sh
uv tool install git+https://github.com/ginstrom/sprite-tool@v0.6.0
sprite --version         # sprite 0.6.0
```

Name a tag, as above, so that everyone on a game builds the same files; leave
`@v0.6.0` off to follow `main`. To move to a newer release, run the command
again with the new tag and `--force`. The tool is not on PyPI.

Other ways to run it:

```sh
# without installing, for example in CI
uvx --from git+https://github.com/ginstrom/sprite-tool@v0.6.0 sprite build --check

# with pipx
pipx install git+https://github.com/ginstrom/sprite-tool@v0.6.0
```

Install it as a tool, as above, and not as a dependency of a Python game. It
pins Pillow to one minor release to keep its output byte-identical, and that
pin would otherwise have to agree with the game's own.

### Setting up a game repository

```sh
cd my-game
sprite init art          # the art project, in a directory of the game repository
```

- **Point the exports at the game.** In `art/sprite-tool.toml`, set `out` of
  an `[[export]]` block to where the game loads its sprites from (see Export
  targets). Commit `art/` and the exported files.
- **Tell agents.** `sprite init` prints a line to add to the game's
  `AGENTS.md` or `CLAUDE.md`. It names the install command,
  `sprite guide`, which is all an agent needs to find its way in, and how to
  draw: with runs or a grid, and `sprite show` to see the result.
- **Give the build a name** in whatever the game already uses, so nobody has
  to remember the tool's name. In a `package.json`:

  ```json
  "scripts": {
    "sprites": "sprite build --project art",
    "sprites:check": "sprite build --check --project art"
  }
  ```

- **Guard it in CI** (see Commit the output, and guard it). On GitHub Actions:

  ```yaml
  - uses: astral-sh/setup-uv@v6
  - run: uvx --from git+https://github.com/ginstrom/sprite-tool@v0.6.0 sprite build --check --project art
  ```

## Quick start

```sh
sprite init art          # sprite-tool.toml, palette.toml and one example sprite
sprite guide             # the file format, this project's palette and canvas classes
sprite new archer --canvas unit
# draw in art/archer.sprite.toml
sprite check             # list problems; fix them until it prints `ok`
sprite show archer       # print the finished grid as text, with row and column numbers
sprite preview archer --grid   # writes art/.preview/archer.grid.png to look at
sprite build             # check everything, then write the game's files
```

`sprite guide` is the reference for drawing. It prints the sprite file format
(grids, runs, derived frames, animations, palette-swap variants), the
project's palette, its canvas classes and what each export target writes, in
under 90 lines, and it is the only thing an agent needs to read before adding
a sprite.

A project is a directory with `sprite-tool.toml` (canvas classes, preview
settings and export targets), `palette.toml`, and any number of
`<id>.sprite.toml` files in it or its subdirectories. Commands find the
project from the current directory: in it, above it, or, when there is exactly
one, up to three levels below it, so they work from the game repository's
root. `--project <dir>` names it outright. Paths in the output are relative to
the current directory.
[examples/demo/](examples/demo/) is a small complete one.

## Commands

| Command | What it does |
|---|---|
| `sprite init [dir]` | Write a starter project, and print the line that tells agents about it. Refuses if its files already exist. |
| `sprite guide` | Print the format reference, palette and canvas classes. |
| `sprite new <id> --canvas <class> [--dir <subdir>] [--runs]` | Write a blank sprite file: a grid of dots, or with `--runs` a runs table to fill in. |
| `sprite check [<file>...] [--canvas <class>]` | Check every sprite file, or the given sprite files and PNGs. |
| `sprite preview [<id>...] [--grid] [--scale N\|display] [--on <tile-id>] [--sheet] [--anim <name>] [--points]` | Write a preview PNG to `.preview/` (see below). With no id, a contact sheet of every sprite. With `--anim`, an animation as a strip and a GIF. `--points` marks named points. |
| `sprite show <id>... [--frame <name>]... [--all] [--diff [<frame>]]` | Print a sprite's finished grid as text (see below), or with `--diff` only the rows one frame changes. Writes no file. |
| `sprite build [--check] [--adopt [<id>...]]` | Check everything, then write every export target. |
| `sprite import <png> --canvas <class> [--id <id>] [--scale N] [--snap]` | Write a sprite file from a PNG. |
| `sprite --version` | Print the tool's version. |

Output is meant to be cheap to read. Success prints one summary line (`init`
adds the line for agents, and `build --adopt` one line per file it took
over). `guide` and `show` print what was asked for and no summary. Each
problem is one line, `path:line:col: CODE message`. There is no colour and no
progress output. Exit codes are `0` for success, `1` for check failures and
`2` for a usage or configuration error (`error: <message>` on stderr).

### Sprite files

`sprite guide` has the format in full. Three things in it came with 0.3.0:

- **`runs`** in a frame table place pixels by position:
  `runs = { 9 = [[13, "ddsskh"]] }` writes six pixels in row 9 from column
  13, counting from 0. In a frame with `from` they change only those pixels,
  and `.` erases. A frame can also be runs alone, with no grid and no `from`:
  a `[frames.main.runs]` table with one line for each row that has pixels. The
  rest of the canvas stays transparent. `sprite new <id> --canvas <class>
  --runs` starts a file in that form. Runs suit a picture that is mostly
  empty or too wide to count across; they are also the answer to wanting a
  script that places pixels at coordinates, which is what a run does.
- **`outline = "auto"`** at the top of a file: draw the interior only, one
  pixel inside the canvas edge, and the tool draws the outline, with the first
  key in the canvas class's `outline` list. A pixel is outlined from above,
  below, left and right, not diagonally, so corners come out rounded.
- **`build = false`** at the top of a file: the sprite is checked, previewed
  and shown on the contact sheet, and never exported. It is for a reference
  sprite kept beside the real ones. Its file name is still its id, so a
  reference copy of `warrior` needs another name, such as
  `sample_warrior.sprite.toml`, and a fault in it fails the build like any
  other.

Release 0.5.0 added these:

- **`move`** in a frame table moves part of a frame:
  `move = { rows = [0, 27], by = [0, 1] }` takes rows 0 to 27 a pixel down,
  which is a breath with the feet where they were. A move names `rows`,
  `cols` or both, each an inclusive `[first, last]`; a list of moves applies
  in order. It runs before `rows` and `runs`, so they can touch up what it
  leaves. `check` warns (`W006`) when a `move` or a `shift` pushes drawn
  pixels off the canvas.
- **`over = "<id>"`** at the top of a file makes the sprite a layer over
  another sprite of the same canvas class: gear over a body, say. The outline
  rule is then checked on the two together, each frame over the base's frame
  of the same name, so a layer needs an outline only where it sticks out of
  its base; the grounded rule does not apply to it; and every preview draws
  it over its base. It is still exported as a sprite of its own, and the game
  draws the two in the same place.
- **A frame's own length** in an animation:
  `frames = ["base", { frame = "glow", ms = 150 }]`. `ms` on the animation is
  the length of every frame that gives none.
- **`like = "<id>"`** as the only line of an `[anim.<name>]` table takes the
  animation of that name from another sprite: frame names, lengths and
  looping. The frames are this sprite's own. `check` warns (`W007`) when a
  layer's animation and its base's differ in frame count or lengths.
- **`unoutlined = ["w"]`** at the top of a file lists palette keys that take
  no outline, such as smoke: the outline rule passes them and
  `outline = "auto"` draws none around them.

Release 0.6.0 added these:

- **`[points]`** names pixels of the drawing that a game needs, such as where
  a weapon is gripped or where a shot leaves a bow:
  `grip = [25, 18]`, as `[col, row]`. Every frame has them, and a derived
  frame's `move`, `mirror`, `shift` and `flip` carry each point as they carry
  the pixel under it, so a breathing frame lowers the grip with the body. A
  point carried off the canvas is dropped from that frame (`W008`).
  `[frame_points.<frame>]` gives one frame points of its own, in that frame's
  final coordinates (an attack frame's raised arm); frames derived from it
  inherit them. Every target exports them (see below), as the centre of the
  pixel: `[25.5, 18.5]`.
- **`mirror`** in a frame table reverses a rectangle left to right in place,
  taking `rows`, `cols` or both as `move` does:
  `mirror = { rows = [25, 31], cols = [10, 21] }` mirrors the legs and leaves
  the body. It runs after `move` and before `rows` and `runs`, which patch
  what is not symmetric.
- **`rest = true`** as the only line of a layer's `[anim.<name>]` holds the
  layer's default frame for as long as its base's animation of that name
  plays: a shield that does not walk. It is exported as a one-frame animation
  of the base's whole length, so a game can play the same name on every layer
  of a figure. `check` warns (`W009`) of a base animation that a layer
  neither has nor rests through.
- **Effects.** `sprite init` declares an `effect` canvas class: 16x16,
  anchored at its centre, with no outline or grounded rule. Draw an effect
  pointing right, so the game turns it by its angle of flight, name its
  leading pixel `tip`, and make a one-shot effect an animation with
  `loop = false`. The demo has an arrow and a spark burst drawn this way.

### The text view

`sprite show` prints what a sprite file resolves to: the pixels `build` would
export, after `move`, `mirror`, `rows`, `runs`, `shift`, `flip`, the automatic
outline and variant swaps, then one `point <name> <col>,<row>` line for each
of the frame's points. It needs no image viewer and writes no file.

```
$ sprite show icon_ring
icon_ring base  icon 20x20
              1111111111
    01234567890123456789
 0  ....................
 1  ....................
 2  ....................
 3  ........kkkk........
 4  .......kRrrRk.......
 5  ......kRroorRk......
```

(and so on to row 19.) Rows and columns count from 0, the numbers `runs`,
`rows` and the check messages use. It prints the default frame of each id;
`--frame <name>`, which may be repeated, picks others, and `--all` prints
every frame. A variant is shown by its own id (`sprite show warrior_red`).

`--diff` prints only what one frame changes: with one `--frame`, the rows that
differ from its `from` frame (or from the frame named after `--diff`), each
with a line of `^` under the columns that changed.

```
$ sprite show warrior --frame walk_1 --diff
warrior walk_1 vs idle_0  unit 32x32
              1111111111222222222233
    01234567890123456789012345678901
25  ..........kDDDDk..kDDDDk........
                     ^^   ^^
```
Problems are handled as `preview` handles them: style problems are printed
and the grid still shown, any other error stops it with exit code `1`.

The loop is `check` until it prints `ok`, `show` for the shape and for
counting positions, `preview` for colour and game size, then `build`.

### Previews

`sprite preview` writes one image for the ids it is given, each sprite under
the one before, and prints its path. The file name says what kind it is, so
one kind does not overwrite another:

| Command | File in `.preview/` |
|---|---|
| `sprite preview archer` | `archer.plain.png` |
| `sprite preview archer --grid` | `archer.grid.png` |
| `sprite preview archer --on grass` | `archer.on-grass.png` |
| `sprite preview archer warrior --grid` | `archer+warrior.grid.png` |
| `sprite preview`, or `--sheet` | `sheet.png` |
| `sprite preview archer --anim idle` | `archer.anim-idle.png` and `archer.anim-idle.gif` |

`sprite preview archer` draws each frame enlarged by `[preview] scale`, and
beside them the same frames at the class's `display_scale`, which is the size
the game shows. `--scale display` draws only the game-size frames, each sprite
at its own class's scale; it cannot be combined with `--grid`.

`--on` takes any sprite id, not only a tile. A layer (a sprite with `over`)
is drawn over its base in every preview. `--points` draws each named point's
pixel in magenta (`#ff00ff`), in every frame; it goes with `--grid`, `--on`
and `--anim`.

`--anim <name>` writes an animation two ways and prints both paths. The PNG
is a strip: one tile for each entry of the animation in play order, with the
frame's name and length under it, which is the form an agent can read. The
GIF plays it, one file per id, for a person to watch. GIF counts time in
hundredths of a second, so lengths are rounded to 10 ms and none is under
20 ms.

A sprite with only style problems (an outline or grounded fault, an empty
frame) is still drawn: the problems are printed first, then the path, and the
exit code is `0`. A problem that leaves a frame undrawable (a wrong row width,
an unknown palette key) stops the preview with exit code `1`.

### Sprites that are not drawn yet

A sprite whose frames are all empty, which is what `sprite new` writes with
or without `--runs`, is a
warning (`W003`) and not an error. `sprite build` leaves it out and builds the
rest.

## Export targets

Each `[[export]]` block in `sprite-tool.toml` is one target. `out` is relative
to the project directory and normally points into the game repository.

```toml
[[export]]
type = "frames"
out = "../game/public/sprites"

[[export]]
type = "phaser"
out = "../game/public/sprites"
name = "atlas"

[[export]]
type = "godot"
out = "../game/assets/sprites"
name = "atlas"
res_path = "res://assets/sprites"
```

`phaser` and `godot` pack every sprite, whatever its canvas size, into one
sheet with 1 pixel of padding (set `padding` to change it). A variant such as
`warrior_red` is exported as a sprite of its own. A sprite with
`build = false` is in no target.

A target exports every sprite unless it selects some:

```toml
[[export]]
type = "phaser"
out = "../game/public/sprites"
name = "atlas"
canvases = ["unit", "map"]   # only sprites of these canvas classes
include = ["gear_*", "hero"] # only sprites whose id matches a pattern
exclude = ["sample_*"]       # not sprites whose id matches a pattern
```

All three are optional and a sprite must pass each one given. A pattern is
matched against the whole id, with `*`, `?` and `[...]`; a variant is matched
by its own id. A sprite a target no longer selects has its files removed from
that target's directory by the next build. `check` warns of a pattern that
matches nothing (`W004`) and of a sprite no target exports (`W005`; set
`build = false` if that is meant).

### `frames`

Loose PNGs, for any other use: `<id>.png` is the sprite's first frame, and a
sprite with more than one frame also gets `<id>__<frame>.png` for each.

It also writes an index, `sprites.json` (`<name>.json` when the target sets
`name`), so the game can read what it would otherwise repeat by hand:

```json
{
  "goblin": {
    "anchor": [16, 32],
    "anims": {},
    "bounds": [4, 3, 26, 29],
    "canvas": "unit",
    "display_scale": 2,
    "file": "goblin.png",
    "frames": {
      "main": { "bounds": [4, 3, 26, 29], "file": "goblin.png" }
    },
    "size": [32, 32]
  }
}
```

Each exported sprite, variants included, has its canvas class, `size`,
`anchor` and `display_scale` from the config, its file names, and `bounds`:
`[x, y, width, height]` of the drawn pixels on the canvas, from the top left.
A frame's `bounds` covers that frame and the sprite's covers all its frames,
so something placed above a unit does not move with its animation. `anims`
has each animation by name, as
`{"frames": [{"frame": "idle_0", "ms": 400}, ...], "loop": true}`, and a
layer has `"over": "<base id>"`. A sprite with named points has `points`, by
frame then by name, each the centre of its pixel from the canvas's top left:
`"points": {"idle_0": {"grip": [25.5, 18.5]}}`. A game places something at a
point with `(point - anchor) * display_scale` from where it drew the sprite,
negating x when it mirrors the sprite. A change
to `display_scale` or `anchor` in the config changes this file, and
`sprite build --check` reports it until the project is rebuilt.

### `phaser`

Writes `<name>.png`, `<name>.json` (a JSON Hash atlas) and
`<name>.anims.json`.

```js
this.load.atlas('atlas', 'sprites/atlas.png', 'sprites/atlas.json');
this.load.animation('atlas-anims', 'sprites/atlas.anims.json');
// ...
const warrior = this.add.sprite(x, y, 'atlas', 'warrior/idle_0');
warrior.play('warrior/idle');
```

Frames are named `<id>/<frame>` and animations `<id>/<anim>`. The texture key
in the animation file is the target's `name`, so load the atlas under that
key. Each frame carries the canvas anchor as its `pivot`, which Phaser uses as
the sprite's origin, so no `setOrigin` call is needed: a unit anchored at its
feet is placed by its feet. Set `pixelArt: true` in the game config. This was
checked in Phaser 4.2.1.

A frame with named points has them in its atlas entry as `points`, which
Phaser's loader keeps on the frame:

```js
const { grip } = this.textures.getFrame('atlas', 'warrior/idle_0').customData.points;
```

### `godot`

Writes `<name>.png`, one `<id>.tres` (a `SpriteFrames` resource) per sprite,
and `<name>.json`, an index of each sprite's canvas class, size, anchor,
display scale, bounds and points (as in `sprites.json`) and frame rectangles
on the sheet. `res_path` must be the `res://` path of the `out` directory,
because each `.tres` refers to the sheet by that path.

```gdscript
var sprite := AnimatedSprite2D.new()
sprite.sprite_frames = load("res://assets/sprites/warrior.tres")
sprite.play("idle")
```

A sprite with no animations gets one called `default` holding all its frames.
Godot does not read the anchor from the resource; take it from `<name>.json`
and set the node's `offset`. Use nearest-neighbour texture filtering. This was
checked in Godot 4.7.

Do not save a generated `.tres` from the Godot editor. Opening it changes
nothing, but saving rewrites it in Godot's own form (new resource ids, no
`load_steps`), and `sprite build --check` then reports it as stale. Rebuild to
put it back. Godot's `<name>.png.import` file is Godot's own; the tool leaves
it alone, and it is committed as usual.

## Safe writes: the manifest and `--adopt`

Each output directory gets a `.sprite-tool-manifest.json` listing the files
the tool wrote there. The tool only overwrites or deletes files on that list,
so it can share a directory with hand-made assets:

- A sprite that is deleted or renamed has its old exported files removed on
  the next build.
- If a file the tool wants to write already exists and is not on the list, the
  build stops before writing anything and names the file. `--adopt` takes
  ownership of such files, for example after exporting into a directory that
  held an older copy of the art:

  - `sprite build --adopt warrior goblin` takes only the files of those
    sprites: `warrior.png`, `warrior__idle_0.png`, `warrior.tres`. A variant
    is a sprite of its own, so `warrior_red.png` needs `warrior_red` named as
    well. If any other unowned file is in the way, the build still stops and
    writes nothing.
  - `sprite build --adopt` takes every such file. Files shared by all
    sprites (`atlas.png`, `atlas.json`, `sprites.json`) belong to no id and
    need this form.

  Either way the build prints one `adopted <path>` line for each file it took
  over, before the summary line. `--adopt` only ever touches files the build
  is about to write, and `build --check` ignores it.
- If you change a target's `out`, the tool no longer looks at the old
  directory. Delete the generated files there yourself; its manifest lists
  them.

Commit the manifest with the exported files.

## Commit the output, and guard it

Exported files are meant to be committed to the game repository, so the game
builds without this tool installed. The same sources always give
byte-identical files, which makes `sprite build --check` a reliable guard: it
writes nothing, and exits 1 with one `E401` line per file that is missing,
stale or no longer generated. Add it to the game's checks:

```make
check:
	sprite build --check --project art
```

## Upgrading from 0.2.0

Projects load and build unchanged. Two things to do once, after moving the
pin to `v0.3.0`:

- Run `sprite build`. A `frames` target now writes `sprites.json`, so
  `sprite build --check` fails until the project is rebuilt and the new file
  committed.
- If a `sprites.json` made by hand is already in a `frames` directory, the
  build stops at it. Move it away, or run `sprite build --adopt` once to
  replace it; or set `name` on the target to write the index under another
  name.

A sprite file that uses `runs`, `build` or `outline = "auto"` is an error on
0.2.0, so everyone working on the game needs the new version.

## Upgrading from 0.3.0

Projects load, check and build unchanged, and no generated file changes, so
`sprite build --check` stays clean. One thing to do once, after moving the pin
to `v0.4.0`: `sprite init` printed the note for agents when the project was
made, and the game owns that copy. Add the new sentence to it, in the game's
`AGENTS.md` or `CLAUDE.md`:

> Draw with runs (`[frames.main.runs]`, pixels placed by row and column) or a
> grid, never with a script that generates one, and look at the result with
> `sprite show <id>`.

## Upgrading from 0.4.0

Projects load, check and build unchanged. Two things differ after moving the
pin to `v0.5.0`:

- Run `sprite build`. The indexes of the `frames` and `godot` targets gain an
  `anims` key for each sprite, so `sprite build --check` fails until the
  project is rebuilt and the changed files committed. No image and no atlas
  file changes.
- A `shift` that pushes drawn pixels off the canvas now prints a warning
  (`W006`). It does not fail the build.

A sprite file that uses `move`, `over`, `like`, `unoutlined` or a frame's own
`ms`, and a config with `canvases`, `include` or `exclude`, is an error on
0.4.0, so everyone working on the game needs the new version.

## Upgrading from 0.5.0

Projects load, check and build unchanged, and a project with no `[points]`
builds to the same bytes, so `sprite build --check` stays clean after moving
the pin to `v0.6.0`. One warning is new: `W009`, for a layer that has no
animation of a name its base animates. It fails nothing; where the layer is
meant to hold still, add `[anim.<name>]` with `rest = true`. `sprite init`
now declares an `effect` class, but an existing project's config is not
touched: to have one, copy `[canvas.effect]` from the config `sprite init`
writes into a scratch directory.

A sprite file that uses `[points]`, `[frame_points]`, `mirror` or `rest` is an
error on 0.5.0, so everyone working on the game needs the new version.

## More

- [docs/designs/sprite-tool.md](docs/designs/sprite-tool.md) is the design:
  every check code, the config and file formats in full, and the reasons
  behind them.
  [docs/designs/feedback-fixes.md](docs/designs/feedback-fixes.md) is the
  design of what 0.3.0 added,
  [docs/designs/text-view-and-runs-discovery.md](docs/designs/text-view-and-runs-discovery.md)
  of what 0.4.0 added,
  [docs/designs/layers-animation-and-export-selection.md](docs/designs/layers-animation-and-export-selection.md)
  of what 0.5.0 added, and
  [docs/designs/points-and-effect-sprites.md](docs/designs/points-and-effect-sprites.md)
  of what 0.6.0 added.
- [AGENTS.md](AGENTS.md) covers working on the tool itself.

MIT licence.
