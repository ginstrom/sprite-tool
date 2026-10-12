# Working on sprite-tool

`sprite-tool` is a Python command-line tool (`sprite`) that turns text sprite
definitions into pixel art for Godot 4 and Phaser. The design is in
[docs/designs/sprite-tool.md](docs/designs/sprite-tool.md) and the
implementation plan in
[docs/implementation-plans/sprite-tool/index.md](docs/implementation-plans/sprite-tool/index.md).
Release 0.3 amended both:
[docs/designs/feedback-fixes.md](docs/designs/feedback-fixes.md) is its design
and
[docs/implementation-plans/feedback-fixes/index.md](docs/implementation-plans/feedback-fixes/index.md)
its plan. Release 0.4 amended the design again:
[docs/designs/text-view-and-runs-discovery.md](docs/designs/text-view-and-runs-discovery.md)
(`sprite show`, `new --runs`, and where the guide and help say to use runs).

## Commands

Everything runs through `uv`.

- `uv sync` installs the package and the dev dependencies into `.venv/`.
- `make test` runs `uv run pytest`.
- `make check` runs every check required before a commit: the tests, then
  `sprite check` on `examples/demo`.
- `make golden` rebuilds the demo and replaces `tests/golden/` with its output
  (see Golden files).
- `uv run pytest tests/test_project.py -k palette` runs a subset.
- `uv run sprite --help` runs the tool from the checkout.

## Constraints

- **Stack.** Python 3.11 or later. One runtime dependency, Pillow, pinned to
  `>=12.3,<12.4`. `argparse` for the CLI. `pytest` is the only dev dependency.
  Do not add anything else. Commit `uv.lock` when dependencies change.
- **Tests.** No test may need a display or the network. Tests write only under
  pytest's `tmp_path`; they never write into `examples/demo/` or
  `tests/golden/`.
- **Output.** Success prints one summary line. Two commands add to it:
  `init` prints a second line, the note for agents (`cli.agent_note`), and
  `build --adopt` prints one `adopted <path>` line per file it took over,
  before the summary. `guide` and `show` print their product and no summary:
  on success `show` prints the grid blocks and nothing else. Each problem is one line on
  stdout. No colour, banners or progress output. Exit codes: `0` success, `1`
  check failures, `2` usage or config error (message on stderr as
  `error: <message>`).
- **Determinism.** The same inputs give byte-identical PNG, JSON and `.tres`
  files. Iterate in sorted order; write no timestamps, absolute paths or tool
  version into generated files. Previews are exempt.
- **Safe writes.** Export files are only created, overwritten or deleted
  through the manifest.

## Releases

The version is `version` in `pyproject.toml`; `sprite --version` and the note
`sprite init` prints read it from the installed package. Games install by tag,
so a release is a tag:

1. Set the new version in `pyproject.toml`, run `uv lock`, and change the tag
   in the README's install commands.
2. `make check`, commit, then `git tag -a v<version>` and push the branch and
   the tag.

## Golden files

`tests/golden/{frames,phaser,godot}/` is the committed output of
`sprite build` on `examples/demo`, manifests included. `tests/test_golden.py`
fails when a fresh build of the demo differs from it by a byte.

- When that test fails and the change to the output was not intended, fix the
  code. Do not regenerate.
- When the change is intended (new demo art, an exporter change), run
  `make golden`, read `git diff tests/golden`, and commit it with the change
  that caused it.
- PNG bytes depend on the Pillow version, which is why the pin is to one minor
  release. Changing the pin means running `make golden` and committing the
  result in the same commit.
- `examples/demo/out/` is where the demo builds to. It is ignored by git and
  is not what the tests compare against.

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
  `_load_drawable` is what `preview` and `show` share: which ids are known,
  and which problems stop a sprite from being drawn.
- `src/sprite_tool/guide.py`: `guide_text`, the reference that `sprite guide`
  prints. Update it when the sprite file format or a command changes.
- `src/sprite_tool/templates/`: the files `sprite init` writes. The palette
  and the warrior sprite are copies of the demo's; a test fails if they differ.
- `src/sprite_tool/spritefile.py`: parses `*.sprite.toml` into sprites, and
  reports what it cannot parse.
- `src/sprite_tool/check.py`: checks on resolved sprites (`run`) and on PNG
  files (`check_png`).
- `src/sprite_tool/render.py`: frames to RGBA images. `png_bytes` is the only
  place PNGs are encoded for export.
- `src/sprite_tool/pack.py`: the shelf packer. Works on sizes only.
- `src/sprite_tool/export/atlas.py`: `compose_sheet`, the one sheet layout
  shared by the atlas targets.
- `src/sprite_tool/export/index.py`: `bounds` and `union`, the box of a
  frame's drawn pixels, and `sprite_entry`, the keys the `frames` and `godot`
  indexes share. Bounds come from the text rows, not from images.
- `src/sprite_tool/export/__init__.py`: `EXPORTERS`, one exporter per target
  type. An exporter returns `{relative path: bytes}` and never touches the
  disk. `export/frames.py` is the loose-PNG target, which also writes the
  index `<name>.json` (`sprites.json` by default); `export/phaser.py` is the
  Phaser atlas target (sheet, JSON Hash atlas, animation JSON);
  `export/godot.py` is the Godot target (sheet, a `SpriteFrames` `.tres` per
  sprite, JSON index). `tests/test_export_godot.py` loads the export in
  headless Godot when `godot` is on `PATH`, and skips that test otherwise.
- `src/sprite_tool/preview.py`: the images `sprite preview` writes
  (`sprite_preview`, `on_tile`, `contact_sheet`, and `stack` for several
  sprites in one image). Layout sizes are named
  constants, which the tests use. Previews are written straight to
  `.preview/`, not through the manifest.
- `src/sprite_tool/textview.py`: `frame_text`, the block `sprite show` prints
  for one frame. It prints `Frame.rows` unchanged and imports no image code.
- `src/sprite_tool/importer.py`: `import_png` and `to_rows`, a PNG to the grid
  of a sprite file for `sprite import`, and `sprite_text`, the file it writes.
- `src/sprite_tool/manifest.py`: the only code that creates, overwrites or
  deletes export files (`plan`, `check_ownership`, `apply`, `compare`),
  `belongs_to`, the rule for which files `build --adopt <id>` takes, and
  `json_bytes`, the one JSON encoder for generated files.
- `tests/conftest.py`: `write_project` and the `project_dir` fixture for
  building a project under `tmp_path`; `make_frame`, `make_sprite` and
  `pixels` for tests that build sprites directly.
- `examples/demo/`: a small complete project, used by tests as a fixture.
  Tests copy it to `tmp_path` before changing or building it.
- `tests/test_golden.py`: the golden comparison, the two-build determinism
  test, the audit that generated files hold no path, timestamp or version, and
  the 200-sprite speed test.
