# Step 10: Import

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.5, 4.9

## Objective

Implement `sprite import`, which converts an existing PNG into a single-frame
sprite file, so current placeholder art can be brought into a project.

## Requirements and context

- **R10 (part).** `import` converts an existing PNG into a sprite file.
- **Q2.** Output on success is the path (plus the `--snap` report lines).
- **A10.** `sprite import` on a canvas-sized PNG whose colours are all in the palette writes a sprite file that renders back to the identical image.

### Command

`sprite import <png> --canvas <class> [--id <id>] [--scale N] [--snap] [--project <dir>]`

- Writes `<project root>/<id>.sprite.toml` with `canvas = "<class>"` and one frame named `main`. `--id` defaults to the PNG's file stem.
- Refuses to overwrite an existing file, an id not matching `[a-z0-9_]+`, and an unknown canvas class: exit 2.
- `--scale N` (integer, default 1) enlarges the PNG by nearest neighbour first. `--scale 2` brings 16 px placeholders up to a 32 px canvas.
- **Placement.** If the (scaled) PNG is smaller than the canvas, place it so its bottom-centre sits on the canvas anchor. For an anchor of `[0, 0]`, place it at the top-left. The rest is transparent. If it is larger than the canvas in either dimension, fail with E301.
- **Colour mapping.** A pixel with alpha 0 is transparent (`.`) whatever its RGB. Every other pixel maps to the palette key with exactly that colour, including alpha. If any pixel has no exact match, fail and list them as E302 (`file.png:x,y: E302 ...`, zero-based source coordinates, at most 10, then a count).
- **`--snap`.** Unmatched pixels map to the nearest palette colour by squared distance in RGB; alpha below 128 becomes transparent. Print one line per distinct snapped source colour: `#aabbcc -> k (#1a1c2c) x14`, sorted by source colour, before the path.
- E301 and E302 failures exit 1 and write nothing.
- The result is not checked against style rules; the user runs `sprite check` next.
- If two palette keys share a colour (W001), use the first in palette file order.

## Dependencies and prerequisites

- **Step 01** provides `cli.py` with a stub `import` handler (flags declared), the project-loading helper (exit 2 on config errors), and `model.py` with `Project(root, palette: dict[str, Color] in file order, canvases: dict[str, Canvas], ...)`, `Color(key, rgba, name)`, `Canvas(name, width, height, anchor, ...)`, `Problem(path, line, col, code, message)`.
- **Step 02** provides `spritefile.load_all(project, paths) -> tuple[list[Sprite], list[Problem]]`, used by tests to read the written file back.
- **Step 03** provides `check.check_png(project, path, canvas)` and the `path:x,y:` formatting for E302 (`Problem.col` is x, `Problem.line` is y), plus `cli.report(problems, root) -> int` for printing problems and the summary. Reuse the palette-matching logic from `check_png` if it is factored out; otherwise factor it out here without changing its behaviour. Step 03 also created `examples/demo/`.
- **Step 04** provides `render.render(frame, palette) -> PIL.Image.Image`, used by the round-trip test.

## Scope and implementation guidance

- `src/sprite_tool/importer.py` (proposed): a function from `(image, canvas, palette, snap)` to grid rows plus problems and the snap report, and a function that formats the sprite file text.
- `src/sprite_tool/cli.py` (exists): replace the `import` stub.
- Write the grid with `"""` delimiters, one row per line, no trailing whitespace, so the file passes the parser's format rules.
- Convert the PNG to RGBA before reading pixels, so palette-mode and RGB files work.

### Exclusions

No multi-frame or sprite-sheet import. No palette generation from the image.

## Verification

`make test` (`uv run pytest`). Tests copy `examples/demo/` to `tmp_path` and
create PNGs there with Pillow; no network or display. Proposed
`tests/test_import.py`:

- **A10:** render the demo `goblin` to a PNG, import it as a new id, load the new file, render it, and compare pixel for pixel. Stdout is exactly the path.
- A 16x16 PNG with `--scale 2` into `unit` fills the 32x32 canvas with each source pixel doubled.
- A 10x12 PNG into `unit` (anchor `[16, 32]`) is placed bottom-centre; into `tile` (anchor `[0, 0]`) top-left.
- A 40x32 PNG into `unit` fails with E301, exit 1, and no file is written.
- An off-palette pixel without `--snap`: exit 1, an E302 line with the right coordinates, no file written.
- `--snap`: the file is written; the report has one line per distinct source colour in the stated format with correct counts; a pixel with alpha 100 becomes `.`.
- An alpha-0 pixel with arbitrary RGB becomes `.`.
- An RGB (no alpha) PNG and a palette-mode PNG import correctly.
- Refuses an existing target file, a bad id and an unknown canvas class with exit 2.

## Completion criteria

- [ ] `sprite import` behaves as specified, including `--scale` and `--snap`.
- [ ] A10 has a test.
- [ ] `make test` passes.
- [ ] Index status and completion log updated.
