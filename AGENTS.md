# Working on sprite-tool

`sprite-tool` is a Python command-line tool (`sprite`) that turns text sprite
definitions into pixel art for Godot 4 and Phaser. The design is in
[docs/designs/sprite-tool.md](docs/designs/sprite-tool.md) and the
implementation plan in
[docs/implementation-plans/sprite-tool/index.md](docs/implementation-plans/sprite-tool/index.md).

## Commands

Everything runs through `uv`.

- `uv sync` installs the package and the dev dependencies into `.venv/`.
- `make test` runs `uv run pytest`.
- `make check` runs every check required before a commit (currently the tests).
- `uv run pytest tests/test_project.py -k palette` runs a subset.
- `uv run sprite --help` runs the tool from the checkout.

## Constraints

- **Stack.** Python 3.11 or later. One runtime dependency, Pillow, pinned to
  `>=12.3,<12.4`. `argparse` for the CLI. `pytest` is the only dev dependency.
  Do not add anything else. Commit `uv.lock` when dependencies change.
- **Tests.** No test may need a display or the network. Tests write only under
  pytest's `tmp_path`; they never write into `examples/demo/` or
  `tests/golden/`.
- **Output.** Success prints one summary line. Each problem is one line on
  stdout. No colour, banners or progress output. Exit codes: `0` success, `1`
  check failures, `2` usage or config error (message on stderr as
  `error: <message>`).
- **Determinism.** The same inputs give byte-identical PNG, JSON and `.tres`
  files. Iterate in sorted order; write no timestamps, absolute paths or tool
  version into generated files. Previews are exempt.
- **Safe writes.** Export files are only created, overwritten or deleted
  through the manifest.

## Layout

- `src/sprite_tool/model.py`: frozen dataclasses shared by all modules, and
  `format_problem`.
- `src/sprite_tool/project.py`: the only module that reads `sprite-tool.toml`
  and `palette.toml`. Config problems raise `ConfigError` (exit 2); palette
  problems are returned as `Problem`s (exit 1).
- `src/sprite_tool/cli.py`: argument parsing and dispatch. Each subcommand has
  one entry in `HANDLERS`; a handler takes the parsed arguments and returns
  the exit code. Handlers call `load_project(args)` to resolve and load the
  project, or `load_checked(args)` to load and check every sprite as well.
  `report(problems, root)` prints problems and the failure summary.
- `src/sprite_tool/spritefile.py`: parses `*.sprite.toml` into sprites, and
  reports what it cannot parse.
- `src/sprite_tool/check.py`: checks on resolved sprites (`run`) and on PNG
  files (`check_png`).
- `src/sprite_tool/render.py`: frames to RGBA images. `png_bytes` is the only
  place PNGs are encoded for export.
- `src/sprite_tool/pack.py`: the shelf packer. Works on sizes only.
- `src/sprite_tool/export/atlas.py`: `compose_sheet`, the one sheet layout
  shared by the atlas targets.
- `src/sprite_tool/export/__init__.py`: `EXPORTERS`, one exporter per target
  type. An exporter returns `{relative path: bytes}` and never touches the
  disk. `export/frames.py` is the loose-PNG target; `export/phaser.py` is the
  Phaser atlas target (sheet, JSON Hash atlas, animation JSON).
- `src/sprite_tool/manifest.py`: the only code that creates, overwrites or
  deletes export files (`plan`, `check_ownership`, `apply`, `compare`), and
  `json_bytes`, the one JSON encoder for generated files.
- `tests/conftest.py`: `write_project` and the `project_dir` fixture for
  building a project under `tmp_path`; `make_frame`, `make_sprite` and
  `pixels` for tests that build sprites directly.
- `examples/demo/`: a small complete project, used by tests as a fixture.
  Tests copy it to `tmp_path` before changing or building it.
