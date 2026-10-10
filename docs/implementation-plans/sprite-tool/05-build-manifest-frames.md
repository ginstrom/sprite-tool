# Step 05: Build pipeline, manifest and `frames` target

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.5, 4.7, 5.4, 5.6

## Objective

Make `sprite build` work end to end with the loose-PNG target: check, render,
export, and write through a manifest that keeps the tool from touching files
it does not own. Include `--check` and `--adopt`.

## Requirements and context

- **R7 (part).** `build` renders every sprite and writes each configured export target. This step delivers the `frames` target and the mechanism the other two plug into.
- **R5.** Variants are exported as ordinary sprites.
- **Q1.** Byte-identical output for the same inputs.
- **Q4.** The tool only creates, overwrites or deletes files it generated itself, tracked by a manifest per output directory.
- **A2.** Changing one palette colour and rebuilding changes the pixels of every sprite using that key and nothing else.
- **A5 (part).** A sprite with a `red` variant produces `<name>_red` in the `frames` target with swapped colours.
- **A12.** After a sprite is deleted, `build` removes its generated files and leaves unrelated files in the output directory alone.
- `build` never writes partial output: if `check` fails, no file is touched.

### Command

`sprite build [--check] [--adopt] [--project <dir>]`

1. Run all checks. On any error: print the problems and summary, exit 1, write nothing.
2. Render every frame and call each configured exporter.
3. Validate ownership for every output directory before writing anything (below).
4. Write, clean up, rewrite manifests.
5. Print `built: 12 sprites, 31 frames, 3 targets`. Variants count as sprites. Zero targets is valid.

`--check` writes nothing. For each generated file that is missing or whose
bytes differ, and for each file in the manifest that would now be deleted,
print `<path>: E401 <missing|stale|no longer generated>` and exit 1 with the
usual summary line. Otherwise print
`up to date: N sprites, M frames, T targets` (plan decision P9).

### `frames` target

- `<id>.png`: the default (first) frame. Always written.
- `<id>__<frame>.png`: every frame, written only when the sprite has more than one frame.
- Frames are full canvas size.

### Exporter contract

Each exporter is a function
`export(sprites: Sequence[Sprite], images: dict[tuple[str, str], Image], target: ExportTarget) -> dict[str, bytes]`
mapping a path relative to `target.out` to file content. Exporters never touch
the disk. This is the one extension point.

### Manifest

- File: `.sprite-tool-manifest.json` in each output directory, listing the files the tool wrote there, by target. Proposed shape: `{"targets": {"<key>": ["a.png", ...]}, "version": 1}` with key `frames` for the loose target and `<type>:<name>` for atlas targets. Sorted keys, two-space indent, `\n` line endings, trailing newline.
- Files in the old manifest that are not produced this time are deleted.
- Before writing a file that exists and is not in the manifest, stop with exit 2 and name the file. `--adopt` takes ownership of such files and overwrites them.
- Two targets may share an output directory if they produce no file in common. A common file is a config error (exit 2) naming both targets and the file.
- Only write files whose bytes changed.
- Do all ownership and conflict checks for all directories first, so a failure leaves every directory untouched.
- Create output directories as needed. Never delete anything not listed in the manifest.

## Dependencies and prerequisites

- **Step 01** provides `model.py` (`Sprite`, `Frame`, `Problem`, `ExportTarget(type, out: Path absolute, name, res_path, padding)`, `Project` with `exports` and `palette`, `format_problem`) and `cli.py` with a stub `build` handler whose parser already has `--check` and `--adopt`.
- **Step 03** provides `cli.load_checked(args) -> tuple[Project, list[Sprite], list[Problem]]` (project, all sprites with variants expanded, sorted problems) and `cli.report(problems, root) -> int` (prints problems and the failure summary, returns the error count). It also created `examples/demo/` with sprites `warrior` (frames `idle_0`, `idle_1`, animation `idle`, variant `red`), `goblin` and `ground_light`, and no `[[export]]` blocks.
- **Step 04** provides `render.render_all(sprites, palette) -> dict[tuple[str, str], Image]`, `render.png_bytes(image) -> bytes`, and an empty `src/sprite_tool/export/__init__.py`.

## Scope and implementation guidance

Paths are proposed unless noted as existing.

- `src/sprite_tool/export/frames.py`: the `frames` exporter. Encode with `render.png_bytes`.
- `src/sprite_tool/export/__init__.py` (exists, empty): add `EXPORTERS: dict[str, Callable]` with `"frames"`. A target type with no registered exporter is a config error (exit 2) saying the target is not available. Steps 06 and 07 add `"phaser"` and `"godot"`.
- `src/sprite_tool/manifest.py`: read and write the manifest, the ownership check, the shared-directory conflict check, apply (write changed, delete stale), and compare (for `--check`). Provide a JSON helper with the deterministic settings above that steps 06 and 07 reuse for their JSON output; name it `manifest.json_bytes(obj) -> bytes` or place it in a small shared module and note the name in the completion log.
- `src/sprite_tool/cli.py` (exists): replace the `build` stub.
- `examples/demo/sprite-tool.toml` (exists): add `[[export]]` with `type = "frames"`, `out = "out/frames"`. `examples/demo/.gitignore` already ignores `out/` (plan decision P12).

### Exclusions

No atlas targets. No golden files (step 11).

## Verification

`make test` (`uv run pytest`). Each test copies `examples/demo/` to `tmp_path`
and builds there; no test writes into the repository. No network or display.
Proposed `tests/test_build.py` and `tests/test_manifest.py`:

- Build the demo copy: exit 0, summary line as specified, files `warrior.png`, `warrior__idle_0.png`, `warrior__idle_1.png`, `warrior_red.png`, `warrior_red__idle_0.png`, `warrior_red__idle_1.png`, `goblin.png`, `ground_light.png` and the manifest; no `goblin__*.png`.
- PNG sizes: 32x32 for units, 16x16 for the tile.
- **A5:** `warrior_red.png` equals `warrior.png` with the two swapped colours exchanged pixel for pixel.
- **A2:** change one palette colour, rebuild; every pixel that used that key has the new colour and all other pixels in all files are unchanged.
- A failing check leaves the output directory byte-for-byte unchanged and exits 1.
- **A12:** delete a sprite file and rebuild; its PNGs are gone and a hand-placed `notes.txt` in the output directory is untouched.
- A pre-existing unowned `goblin.png` blocks the build with exit 2, names the file, and nothing is written; with `--adopt` the build succeeds and the file is in the manifest.
- Two targets producing the same file in one directory exit 2; two targets with disjoint files in one directory succeed.
- `--check`: clean after a build; reports E401 and exits 1 after editing a sprite, after deleting an output file, and after deleting a sprite; writes nothing in any case.
- A second build rewrites no file (compare modification times or stub the writer).
- A project with zero `[[export]]` blocks prints `built: ..., 0 targets`.

Manual check: `uv run sprite build --project examples/demo` exits 0, and
`git status` shows no new tracked or untracked files.

## Completion criteria

- [ ] `sprite build`, `--check` and `--adopt` behave as specified.
- [ ] Exporter registry and contract in place; `frames` exporter registered.
- [ ] Manifest rules enforced, with tests for A12, the unowned-file block, `--adopt` and the shared-directory conflict.
- [ ] A2 and the `frames` part of A5 have tests.
- [ ] `make test` passes.
- [ ] Index status and completion log updated, including the name of the JSON helper.
