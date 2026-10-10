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

## When to use it, and when not

Use it for small, palette-limited sprites (units, tiles, icons) in a
turn-based or otherwise low-frame-count game, where you want the art in
version control as reviewable text and the exported files to be reproducible.

It is not a drawing program. It has no GUI, no drawing helpers, no watch mode,
no frame trimming or rotation in the packer, no tilemap export, and no engines
other than Godot 4 and Phaser. If the art is drawn in Aseprite or similar,
export from there instead; `sprite import` is for bringing a few existing PNGs
in, not for a round-trip workflow.

## Install

Python 3.11 or later, with [uv](https://docs.astral.sh/uv/):

```sh
uv tool install git+https://github.com/ginstrom/sprite-tool
```

## Quick start

```sh
sprite init art          # sprite-tool.toml, palette.toml and one example sprite
cd art
sprite guide             # the file format, this project's palette and canvas classes
sprite new archer --canvas unit
# draw in archer.sprite.toml
sprite check             # list problems; fix them until it prints `ok`
sprite preview archer --grid   # writes .preview/archer.grid.png to look at
sprite build             # check everything, then write the game's files
```

`sprite guide` is the reference for drawing. It prints the sprite file format
(grids, derived frames, animations, palette-swap variants), the project's
palette and its canvas classes in under 60 lines, and it is the only thing an
agent needs to read before adding a sprite.

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
| `sprite init [dir]` | Write a starter project. Refuses if its files already exist. |
| `sprite guide` | Print the format reference, palette and canvas classes. |
| `sprite new <id> --canvas <class> [--dir <subdir>]` | Write a blank sprite file. |
| `sprite check [<file>...] [--canvas <class>]` | Check every sprite file, or the given sprite files and PNGs. |
| `sprite preview [<id>...] [--grid] [--scale N] [--on <tile-id>] [--sheet]` | Write a preview PNG to `.preview/` (see below). With no id, a contact sheet of every sprite. |
| `sprite build [--check] [--adopt]` | Check everything, then write every export target. |
| `sprite import <png> --canvas <class> [--id <id>] [--scale N] [--snap]` | Write a sprite file from a PNG. |

Output is meant to be cheap to read. Success prints one summary line. Each
problem is one line, `path:line:col: CODE message`. There is no colour and no
progress output. Exit codes are `0` for success, `1` for check failures and
`2` for a usage or configuration error (`error: <message>` on stderr).

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

A sprite with only style problems (an outline or grounded fault, an empty
frame) is still drawn: the problems are printed first, then the path, and the
exit code is `0`. A problem that leaves a frame undrawable (a wrong row width,
an unknown palette key) stops the preview with exit code `1`.

### Sprites that are not drawn yet

A sprite whose frames are all empty, which is what `sprite new` writes, is a
warning (`W003`) and not an error. `sprite build` leaves it out and builds the
rest.

## Export targets

Each `[[export]]` block in `sprite-tool.toml` is one target. `out` is relative
to the project directory and normally points into the game repository.

```toml
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
`warrior_red` is exported as a sprite of its own.

### `frames`

Loose PNGs, for any other use: `<id>.png` is the sprite's first frame, and a
sprite with more than one frame also gets `<id>__<frame>.png` for each.

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

### `godot`

Writes `<name>.png`, one `<id>.tres` (a `SpriteFrames` resource) per sprite,
and `<name>.json`, an index of each sprite's size, anchor, display scale and
frame rectangles. `res_path` must be the `res://` path of the `out` directory,
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
  build stops before writing anything. Run `sprite build --adopt` once to take
  ownership of such files, for example after exporting into a directory that
  held an older copy of the art.

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

## More

- [docs/designs/sprite-tool.md](docs/designs/sprite-tool.md) is the design:
  every check code, the config and file formats in full, and the reasons
  behind them.
- [AGENTS.md](AGENTS.md) covers working on the tool itself.

MIT licence.
