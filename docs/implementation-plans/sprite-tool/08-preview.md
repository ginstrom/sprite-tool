# Step 08: Preview

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.5, 4.8

## Objective

Implement `sprite preview`: an upscaled PNG per sprite, an optional pixel
grid, a sprite-on-tile composite, and a contact sheet, so an agent can look at
its work.

## Requirements and context

- **R9.** `preview` writes an upscaled PNG of one sprite (all frames, optional pixel grid), optionally standing on a tile sprite, and a contact sheet of all sprites.
- **Q2.** Output is one path per line and nothing else.
- **A9.** `sprite preview warrior` writes one PNG at the configured scale and prints only its path.
- **A15.** `sprite preview warrior --on ground_light` writes one PNG showing the unit on the tile, each at its class's display scale.
- Previews are for looking, so they are exempt from byte-identical output (Q1). They are not exports and do not go through the manifest.

### Command

`sprite preview [id...] [--scale N] [--grid] [--on <tile-id>] [--sheet] [--project <dir>]`

- Writes `.preview/<id>.png` in the project root for each id. With no id, or with `--sheet`, writes `.preview/sheet.png` (ids and `--sheet` together write both).
- Runs the checks on the sprites involved first. If any has an error, print the problems and summary, exit 1, and write nothing.
- An unknown id (including for `--on`) is a usage error: exit 2.
- Prints each written path, one per line, relative to the current directory where possible.

### Layouts

- **Sprite preview.** All frames of the sprite left to right, nearest-neighbour upscaled by `scale` (`--scale`, default `[preview].scale` from the config), on the configured background colour, with a gap between frames. Variants of the sprite follow on further rows, one row per variant, sorted by id. Previewing a variant id directly shows only that variant.
- **`--grid`.** One-pixel lines between art pixels, and a margin in which every fourth row and column is marked with its zero-based index, so a viewer can name a pixel by `row, col`. These are the same indices used by `rows` overrides and check messages.
- **`--on <tile-id>`.** For each requested sprite, draw its default frame standing on the named sprite's default frame, the way the game would: each is enlarged by its own class's `display_scale` times a common factor (`--scale`, default 2 in this mode), and the sprite's anchor is placed at the bottom-centre of the tile. `--grid` is ignored. The image must be large enough to show both whole.
- **Contact sheet.** Every sprite's default frame (variants included) at its class's `display_scale`, grouped by canvas class and sorted by id, with the id drawn under each sprite.

## Dependencies and prerequisites

- **Step 01** provides `model.py`: `Sprite(id, source, canvas, frames, anims, outline, grounded, variant_of: str | None)` where `frames[0]` is the default frame and `variant_of` names the base sprite of a variant; `Canvas(name, width, height, anchor, display_scale, ...)`; `Project(root, ..., palette, canvases, preview: PreviewConfig(scale, background), ...)`. `cli.py` has a stub `preview` handler with all flags declared.
- **Step 03** provides `cli.load_checked(args) -> tuple[Project, list[Sprite], list[Problem]]` and `cli.report(problems, root) -> int`. Problems carry a `path`, so they can be filtered to the source files of the sprites involved. It also created `examples/demo/` with `warrior` (32x32 `unit`, frames `idle_0` and `idle_1`, variant `red`), `goblin` (32x32) and `ground_light` (16x16 `tile`); `unit` has `display_scale = 2` and `tile` has `display_scale = 4`.
- **Step 04** provides `render.render(frame, palette) -> PIL.Image.Image` (RGBA).
- `.preview/` is already in the repository `.gitignore` and the demo's.

## Scope and implementation guidance

- `src/sprite_tool/preview.py` (proposed): functions returning `PIL.Image` for the sprite preview, the on-tile composite and the contact sheet. Keep layout arithmetic (gap, margin) in named constants so tests can compute expected sizes.
- `src/sprite_tool/cli.py` (exists): replace the `preview` stub.
- Text (grid indices, ids on the contact sheet) uses Pillow's built-in default bitmap font. Do not add a font file or a dependency.
- Upscale with nearest neighbour only.

### Exclusions

No watch mode, no animation playback (GIF), no image viewer integration.

## Verification

`make test` (`uv run pytest`). Tests copy `examples/demo/` to `tmp_path`; no
display or network. Proposed `tests/test_preview.py`:

- **A9:** `preview goblin` writes `.preview/goblin.png`; stdout is exactly the path and a newline; image size is `32 * 6` high and `32 * 6` wide plus the fixed margins.
- `preview warrior`: width is `canvas width * scale * 2` plus gaps; height covers two rows (base and `red` variant).
- `--scale 3` changes the size accordingly.
- A sampled pixel in the middle of an upscaled art pixel has the palette colour; the background colour appears in the gap.
- `--grid`: image is larger by the margin; a grid-line pixel differs from the art colour.
- **A15:** `preview warrior --on ground_light` writes one PNG; the tile occupies `16 * 4 * 2` pixels square and the unit `32 * 2 * 2`; the unit's anchor column lines up with the tile's centre and its anchor row with the tile's bottom edge.
- Contact sheet: no ids writes `.preview/sheet.png` and prints one path; the sheet contains every sprite (check size against the count) and classes are grouped.
- `--sheet` with an id writes both files and prints two lines.
- A sprite with a check error: exit 1, problem lines, no file written.
- Unknown id: exit 2.

Manual check: open `.preview/warrior.png` and `.preview/sheet.png` from the
demo and confirm they are legible.

## Completion criteria

- [ ] All four layouts implemented.
- [ ] A9 and A15 have tests.
- [ ] Output is paths only.
- [ ] `make test` passes.
- [ ] Index status and completion log updated.
