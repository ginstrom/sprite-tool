# sprite-tool implementation plan

- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md) at commit `4b72dd4`
- **Plan written:** 2026-10-10
- **Repository state when planned:** design, `README.md`, `LICENSE` (MIT) and `.gitignore` only. No code, no tests, no `pyproject.toml`.

## Purpose and scope

Build `sprite-tool`, a Python command-line tool (`sprite`) that turns text sprite
definitions into pixel art for Godot 4 and Phaser games. This plan covers the
whole design: seven commands (`init`, `guide`, `new`, `check`, `preview`,
`build`, `import`), three export targets (`frames`, `phaser`, `godot`), the
example project in `examples/demo/`, golden files and documentation.

Out of scope (design non-goals): drawing helpers, GUI, watch mode, frame
trimming, tilemap export, rotation or advanced packing, other engines, and any
change to the two game repositories.

## Shared constraints

Every task file repeats the ones that apply to it.

- **Stack.** Python 3.11 or later. One runtime dependency, Pillow, pinned to `>=12.3,<12.4`. `argparse` for the CLI. `pytest` is the only dev dependency. Nothing else may be added (Q3).
- **Tests.** `make test` runs `uv run pytest`. No test may need a display or the network. Tests write only under pytest's `tmp_path`; they never write into `examples/demo/` or `tests/golden/`.
- **Output.** Success prints one summary line. Each problem is one line on stdout. No colour, banners or progress output (Q2). Exit codes: `0` success, `1` check failures, `2` usage or config error (message on stderr).
- **Determinism.** Same inputs give byte-identical PNG, JSON and `.tres` files. Sorted iteration everywhere; no timestamps, absolute paths or tool version in generated files (Q1). Previews are exempt.
- **Safe writes.** Export files are only created, overwritten or deleted through the manifest (Q4).

## Tasks

| Step | Task | Outcome | Depends on | Status |
|---|---|---|---|---|
| 01 | [Scaffold, model and project loading](01-scaffold-model-project.md) | Installable package, `sprite` CLI skeleton with all subcommands declared, data model, config and palette loading | none | done |
| 02 | [Sprite file parser](02-sprite-file-parser.md) | `*.sprite.toml` parsed into sprites with derived frames, variants and source positions | 01 | done |
| 03 | [Checks, `check` command and demo project](03-checks-and-demo.md) | Style and PNG checks, working `sprite check`, `examples/demo/` sources | 02 | done |
| 04 | [Render, pack and sheet composition](04-render-pack-sheet.md) | Deterministic frame rendering, PNG encoding, shelf packer, atlas sheet helper | 01 | done |
| 05 | [Build pipeline, manifest and `frames` target](05-build-manifest-frames.md) | Working `sprite build` with `--check` and `--adopt`, safe writes, loose PNG export | 03, 04 | done |
| 06 | [Phaser export](06-phaser-export.md) | `phaser` target: sheet, JSON Hash atlas, animation JSON | 05 | done |
| 07 | [Godot export](07-godot-export.md) | `godot` target: sheet, `SpriteFrames` `.tres` per sprite, index JSON | 05 | pending |
| 08 | [Preview](08-preview.md) | `sprite preview` for sprites, `--grid`, `--on`, contact sheet | 03, 04 | pending |
| 09 | [`init`, `new` and `guide`](09-init-new-guide.md) | Project scaffolding, blank sprite scaffolding, agent reference text | 05 | pending |
| 10 | [Import](10-import.md) | `sprite import` with `--scale` and `--snap` | 03, 04 | pending |
| 11 | [Golden files, documentation and acceptance](11-golden-docs-acceptance.md) | Golden output, determinism and speed tests, README and AGENTS.md, manual acceptance | 06, 07, 08, 09, 10 | pending |

## Execution order

The immediate use is Phaser (author, 2026-10-10), so the order reaches a usable
Phaser export first. Godot stays in scope and follows.

**Phaser milestone**

1. **01**
2. **02** and **04** can run in parallel (no shared files beyond what 01 created).
3. **03** (needs 02).
4. **05** (needs 03 and 04).
5. **06**, including its in-engine Phaser check. The tool is usable in yomi from here, with a hand-written config.
6. **09** (`init`, `new`, `guide`) and **08** (preview), which complete the agent drawing loop.

**After the milestone**

7. **10** (import), then **07** (Godot).
8. **11** last.

Steps 06 to 10 are independent of each other and may run in parallel if
capacity allows; 08 and 10 need only 03 and 04.

**Coordination for parallel work.** Step 01 declares every subcommand and flag in
`cli.py` with a stub handler, so later steps only replace their own handler.
Steps 06 and 07 each add one line to the exporter registry in
`src/sprite_tool/export/__init__.py` and one `[[export]]` block to
`examples/demo/sprite-tool.toml`; expect a trivial merge there.

**Integration checkpoints.**

- After 05: `uv run sprite build --project examples/demo` exits 0 and writes loose PNGs.
- After 06 (Phaser milestone): the same command also writes the Phaser atlas, and the atlas has been loaded and played in a scratch copy of yomi.
- After 07: the same command writes all three targets, and running it twice changes nothing.
- After 11: `make check` passes from a clean clone.

## Requirement mapping

| Requirement | Steps |
|---|---|
| R1 palette file | 01, 03 (W001) |
| R2 canvas classes, mixed sizes | 01, 02, 05, 11 (A14) |
| R3 sprite text files | 02 |
| R4 derived frames | 02 |
| R5 palette-swap variants | 02, 03, 05 |
| R6 `check` for sprite files and PNGs | 02, 03 |
| R7 `build` and export targets | 05, 06, 07 |
| R8 deterministic packing with padding | 04 |
| R9 previews and contact sheet | 08 |
| R10 `new` and `import` | 09, 10 |
| R11 `guide` | 09 |
| R12 `init` | 09 |
| Q1 deterministic output | 04, 05, 06, 07, 11 |
| Q2 token-friendly output | 01, 03, and every command step |
| Q3 thin | 01 |
| Q4 safe writes | 05 |
| Q5 200 sprites in under 2 s | 11 |

| Acceptance criterion | Steps |
|---|---|
| A1 init then build | 09 |
| A2 palette change re-renders | 05 |
| A3 three problems with positions | 03 |
| A4 derived frame equals full grid | 02 |
| A5 `red` variant in every target | 05, 06, 07 |
| A6 Phaser export loads | 06 (structure and manual) |
| A7 Godot export loads | 07 (headless), 11 (manual) |
| A8 two builds byte-identical | 11 |
| A9 `preview warrior` | 08 |
| A10 import round trip | 10 |
| A11 PNG check | 03 |
| A12 deleted sprite cleaned up | 05 |
| A13 guide under 60 lines | 09 |
| A14 mixed sizes in one atlas, E103 | 03, 06, 07, 11 |
| A15 `preview --on` | 08 |

## Decisions made while planning

The design leaves these points open or inconsistent. None blocks work; each has
a default that the task files use. Change the default here and in the named
step if you disagree.

| ID | Point | Default used in this plan | Steps |
|---|---|---|---|
| P1 | **A3 against section 5.4.** A3 asks for three problems from one grid (row too long, unknown key, missing outline pixel). Section 5.4 says a frame that fails to resolve is dropped from later checks, so the outline check never sees that grid. | Follow 5.4. The A3 fixture is one sprite file: the long row and the unknown key are in one grid, the missing outline pixel is in a second frame. | 02, 03 |
| P2 | **`init` file count.** The command writes four files (config, palette, sprite, `.gitignore`) but its output is given as `(3 files)`. | Print `created <dir> (3 files)`; `.gitignore` is not counted. | 09 |
| P3 | **`init` directory and export.** A1 runs `init` then `build` in one empty directory, so `init` must default to `.` and the template must have an export that stays inside it. | `dir` defaults to `.`; the template has one `frames` export with `out = "out"`. | 09 |
| P4 | **Where `padding` is set.** The design gives a default of 1 but no config key. | Optional integer `padding` on `phaser` and `godot` export tables. | 01, 04 |
| P5 | **Exit code for a bad palette.** E002 is a check code (exit 1), but config errors exit 2. | A bad `sprite-tool.toml` exits 2. A bad `palette.toml` prints E001/E002 lines and exits 1, and sprites are not checked in that run. | 01, 03 |
| P6 | **Data model gaps.** Section 5.3 has no `display_scale`, no source position on frames, and no link from a variant to its base sprite, all of which other sections need. | Add `Canvas.display_scale`, `Frame.line`, `Frame.literal`, `Sprite.variant_of`, and `Project`, `ExportTarget`, `PreviewConfig` dataclasses. | 01 |
| P7 | **Checks on variants.** Running every check on each variant repeats the same problem once per variant. | Variant sprites get only E003 and E201. | 03 |
| P8 | **Packer order.** The packer is given no frame index, but must order by frame order in the file. | Callers pass frames in file order; the packer sorts stably by height then sprite id. | 04 |
| P9 | **Lines without a position.** No format is given for problems that have no line (E401, a missing file). | `path: CODE message`. `build --check` prints `up to date: N sprites, M frames, T targets` on success. | 01, 05 |
| P10 | **Phaser per-frame `duration`.** Older Phaser 3 releases add it to the base frame time instead of replacing it. The design also asks to confirm that `pivot` is read. | Write what the design specifies. **Confirmed in Phaser 4.2.1 in step 06:** `pivot` sets the origin, and a frame's `duration` replaces the base frame time. The exporter needed no change. | 06 |
| P11 | **Godot `default` animation.** `loop` is not specified for sprites with no animations. | `loop` is `true`. | 07 |
| P12 | **Golden file layout.** | Demo targets write to `examples/demo/out/{frames,phaser,godot}` (gitignored). Golden copies live in `tests/golden/{frames,phaser,godot}` and are regenerated with `make golden`. | 05, 11 |

## Overall completion criteria

- `make check` passes from a clean clone with `uv` installed.
- Every acceptance criterion A1 to A15 has an automated test, apart from the in-engine halves of A6 (recorded in step 06) and A7 (recorded in step 11).
- `uv run sprite build --project examples/demo` run twice leaves `git status` clean.
- `pyproject.toml` lists Pillow as the only runtime dependency and `uv.lock` is committed.
- Every row in the task table is `done`, with evidence recorded below.

## Blockers and open questions

No blockers. The design's two non-blocking questions (larger unit classes, pixel
density) are art decisions and need no work here.

## For implementers

After working on a task, update its row in the task table (`in progress`,
`done` or `blocked`) and add a line under **Completion log** with the date, the
commit, and the evidence (the test command and its result), or the blocker.
If you depart from a default in **Decisions made while planning**, record it
there.

## Completion log

### Step 06, 2026-10-10, commit `027319c` and the commit that adds this entry

**Evidence**

- `make test`: 664 passed (642 before the step; 22 new in `tests/test_export_phaser.py`). `make check`: same.
- `uv run sprite build --project examples/demo` prints `built: 4 sprites, 6 frames, 2 targets` and exits 0, twice; `--check` then prints `up to date: 4 sprites, 6 frames, 2 targets`. `out/phaser/` holds `atlas.png`, `atlas.json` and `atlas.anims.json`. `git status` shows no new files.
- The Phaser part of A5 is `test_frame_keys_cover_every_sprite_and_frame_including_the_variant` and `test_a5_red_variant_frame_differs_from_the_base`; the Phaser part of A14 is `test_a14_units_and_the_tile_share_one_sheet_at_their_own_sizes`.
- Every case in the task file's verification list has a test. `test_build_writes_the_phaser_target` runs the target through `sprite build` with a custom `name` and `padding`.

**In-engine check (A6, decision P10)**

Run in a scratch copy of yomi (Phaser 4.2.1, WebGL, `pixelArt: true`), served by Vite in the `yomi-dev` container and opened in headless Chrome 154. A scratch scene called `this.load.atlas` and `this.load.animation` on the demo's export, added sprites with no `setOrigin` call, and recorded each `ANIMATION_UPDATE`. Values were read back from the page and a screenshot was taken. Nobody watched it in a browser window; the first build into yomi is the time to do that.

- **Loads.** All six frames and both animations were present. No console errors.
- **Pivot is read.** Units had origin `(0.5, 1)` and the tile `(0, 0)` without `setOrigin`; a 32x32 unit at scale 4 placed at `(120, 200)` had bounds `x 56..184, y 72..200`. No `setOrigin` fallback is needed.
- **Timing is right.** 14 frame changes per animation over 6 s were 399 to 401 ms apart, alternating `idle_0` and `idle_1`. In Phaser 4.2.1 a frame's `duration` replaces the base frame time (`Animation.getNextTick`: `currentFrame.duration || msPerFrame`). The animation's own `frameRate` stays at Phaser's default of 24 and is not used.
- **Art.** In the screenshot the warrior, goblin and tile are drawn correctly with hard pixel edges and no bleed from neighbouring frames, and `warrior_red` has red in place of blue.
- The exporter was not changed after the check. `~/play/yomi` was not touched.

**Names later steps need**

- `export.phaser.export` is registered as `EXPORTERS["phaser"]`. Step 07 adds its import and entry next to it.
- `examples/demo/sprite-tool.toml` has two `[[export]]` blocks: `frames` to `out/frames`, then `phaser` to `out/phaser` with `name = "atlas"` and the default padding of 1. `tests/test_demo.py` asserts this list, so step 07 must add its target there.
- The demo's Phaser sheet is 128 x 67.

**Choices the task file left open**

- **`pivot` values are always written as decimals** (`0.0`, `1.0`), because they come from a division.
- **The exporter sorts sprites by id itself**, so its output does not depend on the order it is given.
- **Frame entries are sized from the placement** (the rendered image), as `compose_sheet` does, not from the canvas.
- **No sprites** gives a 64 x 2 sheet, `"frames": {}` and `"anims": []`.
- An animation that names the same frame twice lists it twice.

**Notes**

- A sprite id or frame name containing `/` would make frame keys ambiguous. Ids are file stems, so only a frame or animation name could do it. Not handled here.
- For the scratch run, `node_modules` was mounted read-only, so Vite needed `--configLoader native` and a `cacheDir` outside `node_modules`. This matters only for repeating the check.

### Step 05, 2026-10-10, commits `fa4f3c5`, `74061d9`, and the commit that adds this entry

**Evidence**

- `make test`: 642 passed (578 before the step; 32 new in `tests/test_manifest.py`, 5 in `tests/test_export_frames.py`, 28 in `tests/test_build.py`; 1 stub case for `build` removed from `tests/test_cli.py`). `make check`: same.
- `uv run sprite build --project examples/demo` prints `built: 4 sprites, 6 frames, 1 target` and exits 0, twice; `--check` then prints `up to date: 4 sprites, 6 frames, 1 target`. `git status` shows no new files (`out/` is ignored).
- A2 is `test_a2_palette_change_recolours_that_key_and_nothing_else`; the `frames` part of A5 is `test_a5_red_variant_is_the_base_with_its_colours_swapped`; A12 is `test_a12_deleted_sprite_is_cleaned_up_and_other_files_are_left`.
- The unowned-file block, `--adopt`, the shared-directory conflict and "a second build rewrites no file" each have a test in `tests/test_build.py` and in `tests/test_manifest.py`. "A failing check writes nothing" is tested in `tests/test_build.py`.

**Names later steps need**

- **The JSON helper is `manifest.json_bytes(obj) -> bytes`**: sorted keys, two-space indent, `\n` line endings, trailing newline, ASCII only (non-ASCII characters are written as `\uXXXX` escapes).
- `export.EXPORTERS: dict[str, Exporter]` in `src/sprite_tool/export/__init__.py`, holding `"frames"`. Steps 06 and 07 add an import and one entry each. The exporter signature is the one in the task file; `images` is typed as a `Mapping`.
- `manifest.MANIFEST_NAME` is `".sprite-tool-manifest.json"`. `manifest.target_key(target)` gives `frames` or `<type>:<name>`.
- `manifest.plan(outputs) -> list[Plan]` takes `[(target, files)]`, groups by output directory and reads the manifests on disk. `manifest.check_ownership(plans)`, `manifest.apply(plans)` and `manifest.compare(plans) -> list[Problem]` do the rest. `cli._build` is the only caller.
- `examples/demo/sprite-tool.toml` has one `[[export]]` block, `frames` to `out/frames`.
- `tests/test_build.py` has the `demo` fixture (a copy of `examples/demo/` under `tmp_path`, without `out/`), `set_exports(root, text)` to replace the config's `[[export]]` blocks, and `tree(root)`. Steps 06 and 07 can import or copy them.

**Choices the task file left open**

- **An existing file that is not in the manifest blocks the build even when its bytes already match**, so ownership is never taken without `--adopt`. The message names the first such file and counts the rest: `error: <path> and 2 more already exists and was not written by sprite-tool (use --adopt to overwrite)`.
- **The manifest is one of the generated files.** It is rewritten only when its bytes change, and `build --check` reports it as `missing` or `stale` like any other file. So `--check` after a sprite is deleted prints two lines: the manifest `stale` and the PNG `no longer generated`.
- **`build --check` does no ownership check** and ignores `--adopt`. An unowned file with different bytes is `stale`. The shared-directory conflict and a damaged manifest are still exit 2.
- **`build --check` prints warnings and E401 lines together**, with one summary line counting both.
- **A manifest that cannot be trusted is exit 2**: invalid JSON, a version other than 1, or an entry that is not a plain relative path inside the directory (absolute, containing `..` or a backslash, or the manifest itself). Listed files get deleted, so such an entry is refused instead of followed.
- **A target type with no exporter** is `error: export target type 'phaser' is not available in this version`, raised before any check output.
- **Write order** in each directory: delete stale files, write the manifest, write the other files. If a write fails part-way, the files already written are owned and the next build finishes the job.
- **A target that is removed from the config** has its files deleted on the next build only if another target still writes to the same directory. A directory that no target uses any more is never read.
- Files are written in place, not through a temporary file.

**Notes**

- Directories left empty after cleanup are not removed. No current target writes into subdirectories.
- `frames` file names can collide if one sprite is called `a__b` and another, `a`, has a frame `b`. The later file wins without a message. Not handled here; a check in `check.py` would be the place.

### Step 03, 2026-10-10, commits `e1e4eae`, `9874710`, `52a0ec9`, and the commit that adds this entry

**Evidence**

- `make test`: 578 passed (510 before the step; 37 new in `tests/test_check.py`, 28 in `tests/test_check_command.py`, 3 in `tests/test_demo.py`, 2 in `tests/test_model.py`; 2 stub cases for `check` removed from `tests/test_cli.py`). `make check`: same.
- `uv run sprite check --project examples/demo` prints `ok: 4 sprites, 6 frames` and exits 0.
- A3 is `test_a3_three_problems_with_positions_then_the_summary`: exit 1, three lines at `6:3` (E104), `6:6` (E103) and `13:5` (E201), then `3 errors, 0 warnings in 1 file`.
- A11 is `test_a11_png_reports_size_mismatch_and_off_palette_pixels`; the E103 part of A14 is `test_a14_sixteen_wide_row_in_a_32x32_sprite_is_e103`.
- Every code in the step's table has a test asserting code, line and column.

**Names later steps need**

- `check.run(project, sprites)` and `check.check_png(project, path, canvas)`, as in the task file. `check.run` returns problems unsorted.
- `check.is_palette_colour(project, rgba) -> bool` is the palette match used for PNG pixels (alpha 0, or exactly a palette colour). Step 10 can reuse it.
- `cli.load_checked(args, extra=()) -> (project, sprites, problems)`. `extra` is a list of sprite files to load in addition to those found in the project. With a bad palette it returns no sprites and only the palette problems.
- `cli.report(problems, root) -> int` sorts before printing, so callers may add problems to the list from `load_checked`.
- `cli.count(number, noun)` gives `1 sprite` or `2 sprites`; the `ok:` line uses it.
- `Problem` has a new field `pixel: bool = False`. When true, `col` is x and `line` is y (zero-based) and `format_problem` prints `path:x,y:`.
- `examples/demo/` has no `[[export]]` blocks. Its sprite ids are `goblin`, `ground_light`, `warrior`, `warrior_red`. `warrior` has frames `idle_0` (grid) and `idle_1` (derived, row 9 replaced) and animation `idle`; `goblin` and `ground_light` each have one frame, `main`.

**Choices the task file left open**

- **Summary counts are singular for one**: `ok: 1 sprite, 1 frame`, `1 error, 0 warnings in 1 file`. The failure summary always gives the warning count. "Files" counts every file with a printed problem, warnings included.
- **Given paths.** A path must end in `.sprite.toml` or `.png`, else exit 2. A sprite file that does not exist is an E001 line (exit 1). The `ok:` line counts only the sprites from the given files. `W001` is at `palette.toml`, so it is not printed when paths are given; palette errors always are.
- **PNG paths.** An unknown `--canvas` exits 2. A PNG that cannot be read is E001. Clean PNGs add a count to the summary: `ok: 0 sprites, 0 frames, 1 image`. A PNG with the wrong size still has its pixels checked.
- **Positions.** E106 and W002 are at the frame's line, column 1. E202 is at the bottom row of a grid frame, column 1. E003, E301 and W001 have no line. W002 is one line per sprite, at the first unused frame, listing them all.
- **Count lines.** The E201 count line is at the frame's line, column 1, and the E302 count line has no position, so after sorting a count line can come before the pixel lines it follows on from.
- **E106 excludes E202.** A fully transparent frame is reported as E106 only.
- **Variants (P7).** A variant's E201 lines leave out any pixel that already fails in the base sprite, so a base fault is reported once. The message starts `variant 'warrior_red' frame 'idle_0'`.
- **Derived frames** report E201 as `frame 'idle_1' row 2, col 4`, zero-based, at the frame's line.

**Notes**

- The demo art was drawn with a throwaway script (not committed) that fills shapes and then outlines them with `k`. The committed sprite files are the source of truth.
- W002 can appear for a frame whose only animation was dropped for an error. It comes with that error, so it does not change the exit code.

### Step 04, 2026-10-10, commits `c3c0d17`, `ed9ed22`, and the commit that adds this entry

**Evidence**

- `make test`: 510 passed (243 before the step; 6 new in `tests/test_render.py`, 252 in `tests/test_pack.py`, 9 in `tests/test_atlas.py`). `make check`: same.
- Packer properties run over 40 seeded inputs each (mixed sizes, padding 0, 1, 2 or 4): every item placed once, inside the sheet, `padding` from the edge and from each other, width a power of two of at least 64 and the smallest that qualifies, height no greater than width, same result when the sprites are shuffled. Removing the padding from the packer's x step fails 33 of these tests.
- The worked example is `test_worked_example`: `(1, 1)` and `(34, 1)` on a 128 x 34 sheet.
- `test_png_bytes_writes_no_metadata_chunks`: the PNG holds only `IHDR`, `IDAT`, `IEND`, even when the image carries `dpi`, an ICC profile and a comment in `image.info`.

**Names later steps need**

- `render.render`, `render.render_all`, `render.png_bytes`, `pack.pack` and `export.atlas.compose_sheet`, with the signatures in the task file. `render.TRANSPARENT` is `(0, 0, 0, 0)`; `render.COMPRESS_LEVEL` is 6.
- `src/sprite_tool/export/__init__.py` is empty.
- `tests/conftest.py` has `make_frame(name, *rows)`, `make_sprite(sprite_id, *frames)` (canvas sized from the first frame, no style rules) and `pixels(image)`, for tests that build sprites without a file.

**Choices the task file left open**

- **A frame fits a shelf when `x + w + padding <= sheet_w`.** A frame wider than `sheet_w - 2 * padding` widens the sheet.
- **Empty input** gives `(64, max(1, 2 * padding), [])`, so the sheet is at least one pixel high and always a valid image. `compose_sheet([], {}, 1)` is a transparent 64 x 2 PNG.
- **Negative padding** raises `ValueError` in `pack`. `project.py` already refuses it in config.
- **`png_bytes` accepts any image mode** and converts to RGBA. It drops `image.info`, so an image opened from a file can be passed in safely.
- **`compose_sheet` takes each frame's size from its image**, not from the canvas. Frames are pasted without a mask, so semi-transparent pixels are copied, not blended.
- **Placements are in packing order** (height descending, sprite id, frame order), not input order.

**Notes**

- Pillow 12.3 deprecates `Image.getdata` (removal in Pillow 14); tests use `get_flattened_data`.

### Step 02, 2026-10-10, commits `70102ca`, `8309e87`, `d19b22c`

**Evidence**

- `make test`: 243 passed (127 before the step, 116 new in `tests/test_spritefile.py`). `make check`: same.
- Every code in the step's table (E001, E101, E102, E103, E104, E105, E107) has a test asserting line and column, including the worked example `units/warrior.sprite.toml:9:14: E104 unknown palette key 'x'`.
- A4 at the grid level: `test_from_with_rows_equals_the_hand_written_grid`.
- `test_bad_input_is_reported_and_never_raises` runs 20 malformed files through `load_all`.

**Names later steps need**

- `spritefile.discover(root) -> list[Path]` and `spritefile.load_all(project, paths=None) -> tuple[list[Sprite], list[Problem]]`, as in the task file. `spritefile.SUFFIX` is `".sprite.toml"` and `spritefile.TRANSPARENT` is `"."`.
- Sprites come back sorted by id. Problems come back in file order and, within a file, in the order found; they are not sorted by line (step 03 sorts).
- `Problem.path` and `Sprite.source` are the paths as passed in. `discover` returns absolute paths because `Project.root` is absolute.
- Every problem from this module has line 1 or more and column 1 or more, except an unreadable file, which is E001 at line 0.

**Choices the task file left open**

- **A file with no resolved frame gives no sprite** (and no variants), so `Sprite.frames[0]` always exists. Such a file always has at least one problem. A file with no `[frames]` table, or an empty one, is E001.
- **Message text.** E104 in a located grid is exactly `unknown palette key 'x'`, as in the design. Every other frame problem names the frame, and the row where relevant (`frame 'idle_0' row 3: 17 wide, expected 16`). E104 in a `rows` override or an unlocated grid adds ` in frame 'idle_1' row 5`. The E104 count line is `N more unknown palette keys in frame 'idle_0'`, at the frame's opening line, column 1.
- **One E103 per row.** A row with trailing whitespace gets only the trailing-whitespace E103, even if its width is also wrong. Its other characters are still checked for E104.
- **Positions.** Problems outside a grid (unknown fields, `from`, `shift`, animations, variants) are at the line of the key concerned, else the line of its table header, else line 1; column 1. Frames written as inline tables or with dotted keys are not located: an inline table is reported at its own line, a dotted key at line 1.
- **Cycles.** A `from` cycle is one E105, at the `from` line of the cycle's first frame in file order, with the loop in the message (`a -> b -> a`). Frames that lead into a cycle are dropped without a problem.
- **Derived frames.** A missing `from`, a non-integer `shift`, a non-boolean `flip` and an unknown field are E001 and drop the frame. A `rows` index must be a decimal integer from 0 to height minus 1.
- **Animations.** `frames` must be a non-empty list of strings. An animation with any E001 or E105 is left out. Animation and variant names are not restricted.
- **Variants.** `.` is not a palette key, so it is E107 as a swap source or target. An empty `swap` table is allowed.

### Step 01, 2026-10-10, commit `68cec6f`

**Evidence**

- `make test`: 127 passed (Python 3.11.10, Pillow 12.3.0, pytest 9.1.1). `make check`: same.
- `uv run sprite --help` lists `init`, `guide`, `new`, `check`, `preview`, `build`, `import`.
- `uv run sprite build` outside a project and `uv run sprite` with no subcommand both exit 2.
- `uv tree --no-dev` shows `pillow v12.3.0` as the only runtime dependency. `uv.lock` is committed.

**Names later steps need**

- `cli.HANDLERS` maps each subcommand name to `handler(args) -> int`. A step replaces its own entry; every entry is currently the `not implemented` stub.
- `cli.load_project(args) -> tuple[Project, list[Problem]]` is the project-loading helper. It raises `ConfigError` (including "no project found"), which `main` prints as `error: <message>` on stderr and turns into exit 2, so handlers do not catch it.
- `cli.build_parser()` returns the parser. Argument names: `init`: `dir` (default `"."`); `new`: `id`, `canvas`, `dir`; `check`: `paths`, `canvas`; `preview`: `ids`, `scale`, `grid`, `on`, `sheet`; `build`: `check`, `adopt`; `import`: `png`, `canvas`, `id`, `scale`, `snap`. `project` is `None` when not given. `--scale` is `None` when not given and is refused below 1.
- `cli.EXIT_OK`, `EXIT_CHECK_FAILED`, `EXIT_USAGE` are 0, 1, 2.
- `project.CONFIG_NAME` is `"sprite-tool.toml"`. `project.EXPORT_TYPES` and `ATLAS_TYPES` list the target types.
- `tests/conftest.py` has `write_project(root, config, palette)`, the `project_dir` fixture and the `VALID_CONFIG`, `MINIMAL_CONFIG`, `VALID_PALETTE` strings.

**Choices the task file left open**

- `Project.root`, `palette_path` and `ExportTarget.out` are resolved absolute paths (`Path.resolve()`), so `out = "../assets"` has no `..` left in it.
- A `frames` target has `name = None`, `res_path = None`, `padding = 0`. A key the target type does not use (`name` or `padding` on `frames`, `res_path` on `frames` or `phaser`) is a `ConfigError`, in line with "unknown keys are an error".
- `[canvas.<name>].outline` keys are checked against the palette only when the palette loaded without problems. Otherwise a bad palette entry would surface as a config error (exit 2) and hide the E002 line that P5 says to print (exit 1).
- Palette problems carry column 1 when the line is known. Lines are found for table headers and single-line `key = value` entries; a multi-line value or dotted key gives line 0. A palette with no `[colors]` table is E001 at line 0.
- A palette colour table with a non-string `name`, or without `hex`, is E002; an unknown field in it is E001. In each case that colour is left out of `Project.palette`.
- Added `src/sprite_tool/__main__.py` so `python -m sprite_tool` works; a test uses it to check the real process exit code.

**Left for later steps**

- `README.md` still says "design only" (step 11 rewrites it).
