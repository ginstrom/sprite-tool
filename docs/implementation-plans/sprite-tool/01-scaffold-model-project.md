# Step 01: Scaffold, model and project loading

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.1 to 4.3, 4.5, 5.1 to 5.3

## Objective

Create the installable Python package, the `sprite` command with every
subcommand declared, the shared data model, and loading and validation of
`sprite-tool.toml` and `palette.toml`. After this step `uv run sprite --help`
works and other steps can build on stable interfaces.

## Requirements and context

- **R1.** A project has one palette file mapping single-character keys to colours.
- **R2.** The config defines named canvas classes, each with a fixed size, anchor, display scale and optional style rules.
- **Q2.** No banners, colour or progress output. Problems are one line each on stdout.
- **Q3.** One runtime dependency (Pillow). `argparse`, no CLI framework. `pytest` is the only dev dependency.
- Exit codes for all commands: `0` success, `1` check failures, `2` usage or config error.
- Commands find the project by walking up from the current directory to the first `sprite-tool.toml`, or take `--project <dir>`.

## Dependencies and prerequisites

- No earlier steps.
- **Existing in the repository:** `README.md`, `LICENSE` (MIT), `.gitignore` (already ignores `.venv/`, `__pycache__/`, `.pytest_cache/`, `dist/`, `.preview/`), and the design.
- **Machine:** Python 3.11.10, `uv` 0.12.10, Pillow 12.3.0 were found when planning.

## Scope and implementation guidance

All paths below are proposed; none exists yet.

### Packaging

- `pyproject.toml`: project `sprite-tool`, `requires-python = ">=3.11"`, licence MIT, dependency `pillow>=12.3,<12.4`, build backend hatchling, package at `src/sprite_tool`, console script `sprite = "sprite_tool.cli:main"`, dev dependency group containing only `pytest`.
- Commit `uv.lock`.
- `Makefile` with `test` (`uv run pytest`) and `check` (for now the same as `test`).
- `AGENTS.md`: how to run the tests, and the shared constraints from the plan index.

### `src/sprite_tool/model.py`

Frozen dataclasses. Later steps depend on these names and fields exactly.

```python
Color(key: str, rgba: tuple[int, int, int, int], name: str | None)

Canvas(name: str, width: int, height: int, anchor: tuple[int, int],
       display_scale: int, outline: frozenset[str] | None, grounded: bool)

Frame(name: str, rows: tuple[str, ...], line: int, literal: bool)
#   rows: the resolved full grid, palette keys and '.' only
#   literal=True: the frame was written as a grid; `line` is the 1-based file
#     line of row 0, so row r, column c is at (line + r, c + 1)
#   literal=False: derived frame; `line` is the line of its definition
#   line=0: position unknown

Anim(name: str, frames: tuple[str, ...], ms: int, loop: bool)

Sprite(id: str, source: Path, canvas: Canvas, frames: tuple[Frame, ...],
       anims: tuple[Anim, ...], outline: bool, grounded: bool,
       variant_of: str | None)
#   outline / grounded: whether the canvas rule applies after per-sprite opt-out
#   frames[0] is the default frame
#   variant_of: the base sprite id for a variant, else None

Problem(path: Path, line: int, col: int, code: str, message: str)
Placement(sprite_id: str, frame: str, x: int, y: int, w: int, h: int)

ExportTarget(type: str, out: Path, name: str | None, res_path: str | None, padding: int)
#   out is absolute, resolved against the config file's directory
PreviewConfig(scale: int, background: tuple[int, int, int, int])
Project(root: Path, palette_path: Path, palette: dict[str, Color],
        canvases: dict[str, Canvas], preview: PreviewConfig,
        exports: tuple[ExportTarget, ...])
#   palette and canvases keep file order
```

Also in `model.py`: `format_problem(problem, root) -> str`.

- With a position: `units/warrior.sprite.toml:9:14: E104 unknown palette key 'x'`.
- With `line == 0`: `path: CODE message`.
- Paths inside the project root are printed relative to it with `/` separators; other paths are printed as given.

### `src/sprite_tool/project.py`

The only module that reads the config and palette files.

- `find_project(start: Path) -> Path | None`: walk up to the first directory holding `sprite-tool.toml`.
- `load(root: Path) -> tuple[Project, list[Problem]]`.
- `ConfigError(Exception)`: raised for any problem in `sprite-tool.toml` and for a missing palette file. The CLI prints `error: <message>` on stderr and exits 2.

Config rules (`sprite-tool.toml`):

- `version` must be `1`; any other value is refused with a clear message.
- `palette`: path, default `palette.toml`.
- `[canvas.<name>]`, at least one: `size = [w, h]` (positive integers, required), `anchor = [x, y]` (required, within `0..w` and `0..h`), `display_scale` (integer of 1 or more, default 1), `outline` (optional list of palette keys; each must exist in the palette), `grounded` (boolean, default false).
- `[preview]`: `scale` (integer of 1 or more, default 6), `background` (hex colour, default `#3a3a3a`).
- `[[export]]`, zero or more: `type` is `frames`, `phaser` or `godot`; `out` required; `name` for `phaser` and `godot` (default `atlas`); `res_path` required for `godot`; `padding` (integer of 0 or more, default 1) for `phaser` and `godot` only.
- All paths are relative to the config file.
- An unknown key anywhere is a `ConfigError`.
- Do not check here whether two targets collide in one directory; step 05 does that.

Palette rules (`palette.toml`), reported as `Problem`s and not raised:

- Only a `[colors]` table. Invalid TOML or an unknown field is E001.
- A key is exactly one printable ASCII character and is not `.`, whitespace, `"`, `'` or `\`. Otherwise E002.
- A value is `#rrggbb` or `#rrggbbaa`, or a table with `hex` and optional `name`. Otherwise E002.
- Report the line of the offending key when it can be found in the raw text, else line 0.
- Do not report duplicate colours here (W001 belongs to step 03).
- When the palette has problems, still return a `Project` holding the valid colours. Callers stop before checking sprites when any palette problem is an error.

### `src/sprite_tool/cli.py`

- `main(argv: list[str] | None = None) -> int`.
- Declare every subcommand and flag now, each with a stub handler that prints `error: not implemented` on stderr and returns 2. Later steps replace only their handler.

| Subcommand | Arguments |
|---|---|
| `init` | `[dir]` |
| `guide` | none |
| `new` | `<id> --canvas <class> [--dir <subdir>]` |
| `check` | `[paths...] [--canvas <class>]` |
| `preview` | `[id...] [--scale N] [--grid] [--on <tile-id>] [--sheet]` |
| `build` | `[--check] [--adopt]` |
| `import` | `<png> --canvas <class> [--id <id>] [--scale N] [--snap]` |

- Every subcommand except `init` accepts `--project <dir>`.
- Provide one helper that later handlers call to resolve the project (from `--project` or `find_project(cwd)`), load it, and turn `ConfigError` or "no project found" into exit 2.
- `argparse` usage errors already exit 2; keep that.

### Exclusions

No sprite parsing, checks, rendering or export in this step.

## Verification

- `make test` passes. Proposed tests in `tests/test_project.py` and `tests/test_cli.py`:
  - `find_project` finds a config two directories up and returns `None` when there is none.
  - A valid config loads to the expected `Project` (two canvas classes of different sizes, three exports, resolved `out` paths).
  - Each config rule above has a failing case that raises `ConfigError`, including an unknown key and `version = 2`.
  - Palette: bad key, bad hex and unknown field each give the right code; a `#rrggbbaa` value and a table value load correctly.
  - `format_problem` for a positioned problem, a `line == 0` problem and a path outside the root.
  - `main(["build"])` in a directory with no project returns 2.
- `uv run sprite --help` lists all seven subcommands.
- `uv tree` (or `pyproject.toml`) shows Pillow as the only runtime dependency.

## Completion criteria

- [x] Package installs with `uv sync` and `uv run sprite --help` works.
- [x] `model.py` matches the dataclasses above.
- [x] `project.load` enforces every config and palette rule listed.
- [x] All seven subcommands and their flags are declared with stubs.
- [x] `make test` passes; `uv.lock` committed.
- [x] Index status and completion log updated.
