# Step 09: `init`, `new` and `guide`

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.5, 4.10, 8 (decisions)

## Objective

Implement the three commands an agent uses to start work: `init` scaffolds a
project, `new` scaffolds a blank sprite file, and `guide` prints the compact
reference that is the only thing an agent reads before drawing.

## Requirements and context

- **R10 (part).** `new` scaffolds a blank sprite file for a canvas class.
- **R11.** `guide` prints a compact reference: file format, the project's palette legend and its canvas classes.
- **R12.** `init` scaffolds a project (config, starter palette, one example sprite).
- **Q2.** Success output is one line (or, for `guide`, the guide).
- **A1.** In an empty directory, `sprite init` followed by `sprite build` exits 0 and writes at least one PNG.
- **A13.** `sprite guide` output for the example project is under 60 lines.
- Author decisions: `init` writes a starter palette (Sweetie 16, mnemonic keys) that the game then edits. Character sprites are 32x32 and tiles 16x16.

### `sprite init [dir]`

- Writes `sprite-tool.toml`, `palette.toml`, one example sprite and a `.gitignore` containing `.preview/`.
- `dir` defaults to `.` and is created if missing (plan decision P3).
- Refuses (exit 2, message on stderr) if `sprite-tool.toml` already exists there. Writes nothing in that case.
- Output: `created <dir> (3 files)`. The `.gitignore` is not counted (plan decision P2). If a `.gitignore` already exists, leave it alone.
- Template config: `version = 1`; `palette = "palette.toml"`; `[canvas.unit]` with `size = [32, 32]`, `anchor = [16, 32]`, `display_scale = 2`, `outline = ["k"]`, `grounded = true`; `[canvas.tile]` with `size = [16, 16]`, `anchor = [0, 0]`, `display_scale = 4`; `[preview]` with `scale = 6`, `background = "#3a3a3a"`; one `[[export]]` with `type = "frames"`, `out = "out"`. Add short comments, and commented-out `phaser` and `godot` blocks as hints.
- Template palette and example sprite: copies of `examples/demo/palette.toml` and `examples/demo/units/warrior.sprite.toml`, written to `palette.toml` and `units/warrior.sprite.toml`.

### `sprite new <id> --canvas <class> [--dir <subdir>]`

- Writes `<project root>/<subdir>/<id>.sprite.toml` (`subdir` defaults to the root) with `canvas = "<class>"` and one all-transparent frame named `main` at the class's size.
- Refuses to overwrite an existing file, an id that does not match `[a-z0-9_]+`, an id already used by another sprite in the project, and an unknown canvas class: exit 2.
- Output: the path.
- The new file fails `sprite check` with E106 (fully transparent frame) until drawn. That is intended.

### `sprite guide`

Prints, for the current project:

1. The sprite file format: grids, `.` for transparent, derived frames (`from`, `rows`, `shift`, `flip` and their order), animations, variants, per-sprite `outline = false` / `grounded = false`.
2. The palette legend: key, hex and name for every colour.
3. The canvas classes: size, anchor, display scale and rules.
4. The workflow commands: `new`, `check`, `preview --grid`, `build`.

Keep it terse: plain text, no decoration, well under 60 lines for the demo
project (16 colours, 2 classes). Zero-based row and column indexing must be
stated, since `rows` overrides and check messages depend on it.

## Dependencies and prerequisites

- **Step 01** provides `cli.py` with stub handlers for `init`, `guide` and `new` (flags declared; `init` takes no `--project`), the project-loading helper (exit 2 on config errors), `project.load`, and `model.py` with `Project(root, palette: dict[str, Color], canvases: dict[str, Canvas], ...)`, `Color(key, rgba, name)` and `Canvas(name, width, height, anchor, display_scale, outline: frozenset[str] | None, grounded)`.
- **Step 02** provides `spritefile.discover(root) -> list[Path]`, for finding ids already in use.
- **Step 03** created `examples/demo/` with `palette.toml` (Sweetie 16) and `units/warrior.sprite.toml` (32x32, checks clean), and a working `sprite check`.
- **Step 05** provides a working `sprite build` with the `frames` target, needed for the A1 test.

## Scope and implementation guidance

- `src/sprite_tool/templates/` (proposed): `sprite-tool.toml`, `palette.toml`, `warrior.sprite.toml`, `gitignore`. Load them with `importlib.resources`. Make sure the hatchling build includes them in the wheel.
- `src/sprite_tool/guide.py` (proposed): `guide_text(project) -> str`.
- `src/sprite_tool/cli.py` (exists): replace the three stubs.
- A test must fail if the template palette or example sprite drifts from the demo's copies.

### Exclusions

No interactive prompts. `init` does not edit an existing project.

## Verification

`make test` (`uv run pytest`). All commands run inside `tmp_path`; no network
or display. Proposed `tests/test_init_new_guide.py`:

- **A1:** in an empty directory, `init` then `build` exit 0; at least one PNG exists under `out/`; `init` stdout is `created . (3 files)`.
- `init sprites` creates `sprites/` with the four files.
- A second `init` exits 2 and changes nothing.
- A freshly initialised project passes `sprite check`.
- Template palette and sprite equal the demo's.
- The built wheel contains the templates (build with `uv build` into `tmp_path` and inspect the archive, or assert `importlib.resources` can read each file).
- `new kobold --canvas unit --dir units` writes the file and prints its path; the file has 32 rows of 32 dots and parses; `sprite check` on it reports E106 only.
- `new` with `--canvas tile` gives 16 rows of 16.
- `new` refuses an existing file, a duplicate id elsewhere in the project, a bad id and an unknown class, each with exit 2.
- **A13:** `guide` on the demo project is under 60 lines, contains every palette key with its hex, and names both canvas classes with their sizes.
- `guide` outside a project exits 2.

## Completion criteria

- [ ] `init`, `new` and `guide` behave as specified.
- [ ] Templates ship in the package.
- [ ] A1 and A13 have tests.
- [ ] `make test` passes.
- [ ] Index status and completion log updated.
