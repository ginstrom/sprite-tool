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
| 07 | [Godot export](07-godot-export.md) | `godot` target: sheet, `SpriteFrames` `.tres` per sprite, index JSON | 05 | done |
| 08 | [Preview](08-preview.md) | `sprite preview` for sprites, `--grid`, `--on`, contact sheet | 03, 04 | done |
| 09 | [`init`, `new` and `guide`](09-init-new-guide.md) | Project scaffolding, blank sprite scaffolding, agent reference text | 05 | done |
| 10 | [Import](10-import.md) | `sprite import` with `--scale` and `--snap` | 03, 04 | done |
| 11 | [Golden files, documentation and acceptance](11-golden-docs-acceptance.md) | Golden output, determinism and speed tests, README and AGENTS.md, manual acceptance | 06, 07, 08, 09, 10 | done |

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

### After the plan: review fixes, 2026-10-10

Changes made after a review of the finished tool. The design was revised to match (sections 4.1, 4.5, 4.6, 4.8). `make check`: 897 passed, then `ok: 4 sprites, 6 frames`; golden files unchanged.

- **Preview** draws a sprite that has only style problems (E106, E201, E202), printing them before the path, exit 0. Several ids give one stacked image. Files are named `<ids>.plain.png`, `<ids>.grid.png`, `<ids>.on-<tile-id>.png`; `sheet.png` is unchanged. An unknown id lists the known ones.
- **Checks.** An outline fault carried into a derived frame is reported once, in the frame it comes from. A sprite with every frame empty is W003 and is left out of the build, so `sprite new` no longer stops it. A file name or variant name that is not `[a-z0-9_]+` is E001. An id that would export to another sprite's `<id>__<frame>.png` is E003.
- **Project and paths.** With no project at or above the current directory, a single project up to three levels below is used. Problem paths are relative to the current directory, like the paths `new` and `preview` print.
- **Guide** now covers the anchor, display scale, the default frame, facing right, `rows` as a table, `preview --on`, the contact sheet and `import` (58 lines for the demo).
- **Not changed:** a target whose `out` is changed still leaves its old directory behind, because the tool keeps no record of past output directories. The README says to delete those files by hand.

### Plan complete, 2026-10-10

Every row in the task table is `done`. The overall completion criteria were run after step 11:

- `make check` passes from a clean clone (`git clone`, `uv sync`, `make check`): 867 passed, then `ok: 4 sprites, 6 frames`.
- A1 to A15 each have an automated test (listed under step 11). The in-engine halves of A6 and A7 are recorded under steps 06 and 11; both were run headless and neither was watched by a person.
- `uv run sprite build --project examples/demo` twice leaves `git status` clean.
- `uv tree --no-dev` shows `pillow v12.3.0` as the only runtime dependency; `uv.lock` is committed.

### Step 11, 2026-10-10, commits `b0c03e1`, `4beed9b`, `c026a5f`, `18cd702`, `b16e3cd`, and the commit that adds this entry

**Evidence**

- `make test`: 867 passed (855 before the step; 9 new in `tests/test_golden.py`, 1 each in `tests/test_build.py`, `tests/test_cli.py` and `tests/test_init_new_guide.py`). `make check` runs the tests and then `uv run sprite check --project examples/demo`, which prints `ok: 4 sprites, 6 frames`.
- `tests/golden/{frames,phaser,godot}/` holds 20 files (10 PNG, 10 text). `make golden` on an unchanged tree produces no diff.
- With a path, a date and the version appended to one golden `.tres` and a stray PNG added, four of the golden tests failed.
- **Q5: 200 sprites (200 frames, three targets) built in 0.096 s** in process on the author's laptop; the test bound is 5 s. The sprites are 200 copies of the demo goblin.
- Clean clone: `git clone`, `uv sync`, `make check` passed; `make golden` and a build there left `git status` clean.

**Acceptance criteria and their tests**

| | Test |
|---|---|
| A1 | `test_a1_init_then_build_in_an_empty_directory` |
| A2 | `test_a2_palette_change_recolours_that_key_and_nothing_else` |
| A3 | `test_a3_three_problems_with_positions_then_the_summary` |
| A4 | `test_a4_a_frame_derived_with_rows_renders_as_the_same_frame_written_in_full` (new, at the PNG level), `test_from_with_rows_equals_the_hand_written_grid` |
| A5 | `test_a5_red_variant_is_the_base_with_its_colours_swapped`, `test_a5_red_variant_frame_differs_from_the_base`, `test_a5_the_red_variant_has_its_own_resource_with_recoloured_frames` |
| A6 | structure: `tests/test_export_phaser.py`; in engine: step 06 below |
| A7 | `test_a7_godot_loads_each_resource_as_sprite_frames`; in the game project: below |
| A8 | `test_a8_two_copies_of_the_demo_build_to_identical_bytes`, `test_a8_a_second_build_in_place_changes_no_byte` |
| A9 | `test_a9_preview_writes_one_png_and_prints_only_its_path` |
| A10 | `test_a10_an_imported_png_renders_back_to_the_identical_image` |
| A11 | `test_a11_png_reports_size_mismatch_and_off_palette_pixels` |
| A12 | `test_a12_deleted_sprite_is_cleaned_up_and_other_files_are_left` |
| A13 | `test_a13_demo_guide_is_short_and_lists_the_palette_and_canvas_classes` |
| A14 | `test_a14_sixteen_wide_row_in_a_32x32_sprite_is_e103`, `test_a14_unit_and_tile_are_in_one_sheet_at_their_own_sizes`, and one in each atlas exporter's tests |
| A15 | `test_a15_on_writes_the_unit_on_the_tile`, `test_a15_unit_stands_on_the_tile_each_at_its_own_display_scale` |

**Manual acceptance**

1. **Phaser (A6).** The step 06 entry records the in-engine result: `pivot` is read and a frame's `duration` replaces the base frame time in Phaser 4.2.1. The README says no `setOrigin` call is needed.
2. **Godot (A7).** Run in a scratch copy of fantasy-tactics (Godot 4.7.2) with the demo's `godot` target writing to its `assets/sprites` and `res_path = "res://assets/sprites"`. Godot ran headless with its home directory in the scratch area. **Nobody opened the editor window or watched the animation**; that is still worth doing once on the first real export.
   - `godot --headless --editor --quit` imported the sheet and loaded the editor with no error. It added `atlas.png.import` and changed no generated file: `sprite build --check` afterwards printed `up to date: 4 sprites, 6 frames, 3 targets`.
   - A script loaded `warrior.tres`: a `SpriteFrames` with one animation, `idle`, 2 frames, speed 2.5, looping; frame 0 an `AtlasTexture` with region `(34, 1, 32, 32)` on `res://assets/sprites/atlas.png` (128 x 67). In an `AnimatedSprite2D`, `play("idle")` gave frame changes 399 to 407 ms apart, alternating 1 and 0.
   - **Saving from Godot does rewrite the file.** `ResourceSaver.save` of the loaded resource to another path dropped `load_steps=4` from the header, changed the external resource id from `"1"` to `"1_k7vgq"`, and wrote `"loop": 1` for `"loop": true`. Opening does not do this; saving would make `build --check` report the file as stale. The README says not to save generated `.tres` files from the editor.
   - `~/play/fantasy-tactics` was not touched (`git status` clean).
3. **Agent trial.** A fresh agent was given a copy of the demo, told to use only `sprite guide` and the tool's own output, and asked to add an `archer` unit with a two-frame `idle`. It ran `guide`, `--help`, `new archer --canvas unit --dir units`, `check`, `preview archer --grid` and `build`, drew the grid by hand, and passed `check` on the first attempt; `build` printed `built: 5 sprites, 8 frames, 3 targets`. It read no source, design or existing sprite file. The preview shows a recognisable archer with a blink as the second frame.
   - What it had to guess: where sprite files go (it read the directory listing), whether frame names mean anything, whether a replacement row must be full width, and that diagonals do not count for the outline rule, which makes any part 1 or 2 pixels wide all outline. **The guide now says each of these** (50 lines for the demo, longest 97 characters).
   - Noted and not changed: "default frame", `anchor` and `display scale` are not explained in the guide; `preview` without `--grid` or an id is not described; the guide does not list `init` or `import`.

**Choices the task file left open**

- **A second golden test compares a fresh build with `tests/golden/` file by file**, as well as the `build --check` test the task file asks for. `build --check` reads the manifest, so it would not notice a stray file in `tests/golden/`.
- **`make golden` deletes `tests/golden/` before copying**, so a file that is no longer generated does not stay.
- **The clean-output audit** checks text files for an absolute path, a date, a time, a run of nine or more digits and the package version, and PNGs for any chunk other than `IHDR`, `IDAT`, `IEND`.
- **`import --scale` help text** now reads `enlarge the PNG N times before importing (default: 1)`. The old text said "shrink it first", which is the opposite of what the option does (step 10's note).
- `sprite guide` still leaves out `import`; the README covers it.

**Notes**

- Golden PNG bytes depend on the Pillow minor version. `AGENTS.md` says a change to the pin means `make golden` in the same commit.
- The Q5 test prints its time; run `uv run pytest tests/test_golden.py -k q5 -s` to see it.

### Step 07, 2026-10-10, commit `1e0cab9` and the commit that adds this entry

**Evidence**

- `make test`: 855 passed (821 before the step; 34 new in `tests/test_export_godot.py`). `make check`: same.
- **The headless Godot test ran and passed** (Godot 4.7.2 at `/opt/homebrew/bin/godot`). It is `test_a7_godot_loads_each_resource_as_sprite_frames`: the demo is built into a temporary Godot project, `godot --headless --import` imports the sheet, and a script loads each `.tres`. Each is a `SpriteFrames`; the animations are `default` (goblin, ground_light; 1 frame, speed 1.0, loop) and `idle` (warrior, warrior_red; 2 frames, speed 2.5, loop); the first frame of each is an `AtlasTexture` with the atlas loaded and the region given in `atlas.json`; Godot prints no `ERROR`. It skips when `godot` is not on `PATH`.
- `uv run sprite build --project examples/demo` prints `built: 4 sprites, 6 frames, 3 targets` and exits 0; a second run leaves every file under `out/` with the same bytes; `--check` prints `up to date: 4 sprites, 6 frames, 3 targets`. `out/godot/` holds `atlas.png`, `atlas.json` and four `.tres` files. `git status` shows no new files.
- The byte-for-byte case is `test_two_frame_sprite_gives_the_resource_in_the_design_byte_for_byte`. The Godot part of A5 is `test_a5_the_red_variant_has_its_own_resource_with_recoloured_frames`; of A14, `test_a14_units_and_the_tile_share_one_sheet_at_their_own_sizes`.
- Every case in the task file's verification list has a test. Seven deliberate faults in `godot.py` (region offset, texture path, sub-resource type, speed, `load_steps`, animation order, the default's `loop`) each failed at least one test; the first four also failed the headless test.

**Names later steps need**

- `export.godot.export` is registered as `EXPORTERS["godot"]`. `godot.DEFAULT_ANIM` is `"default"`.
- `examples/demo/sprite-tool.toml` has three `[[export]]` blocks: `frames`, `phaser`, then `godot` to `out/godot` with `name = "atlas"`, `res_path = "res://sprites"` and the default padding of 1. `tests/test_demo.py` asserts this list.
- The demo's Godot sheet has the same bytes as its Phaser sheet (`test_the_sheet_is_the_one_the_phaser_target_packs`).
- `tests/test_export_godot.py` has `parse(tres)` (load steps, texture path, regions by sub-resource id, animations), `copy_demo(root, exports)` and `godot(project, home, *args)`, which step 11 can reuse for golden files or the speed test.

**Choices the task file left open**

- **`atlas.json` is written by `manifest.json_bytes`**, like every other generated JSON file, so each rectangle is spread over several lines. The task file's example shows them on one line; its rule (sorted keys, two-space indent, trailing newline) is what was followed.
- **Animations are ordered by name**, which is how Godot orders them when it saves a `SpriteFrames`. Frames within an animation keep their order, and a frame named twice is listed twice.
- **Every frame has a sub-resource**, in file order, whether or not an animation uses it. The index lists every frame too.
- **`speed` is Python's shortest float text for `1000 / ms`**: `2.5`, `1.0`, `3.3333333333333335` for 300 ms.
- **A `res_path` that ends in `/`** (`res://`) is joined to the sheet name without a second slash.
- **Strings are escaped** (backslash, double quote, newline, tab), because animation names are not restricted. Files are UTF-8.
- **Index values come from the canvas** (`anchor`, `size`, `display_scale`); frame rectangles come from the placement.
- **No sprites** gives a 64 x 2 sheet and `{}`, with no `.tres` files.

**Notes**

- **The headless test gives Godot a home directory under `tmp_path`** (`HOME` and `CFFIXED_USER_HOME`, and the `XDG_*` variables for Linux). Without it Godot creates `~/Library/Application Support/Godot/app_userdata/<project name>/` on macOS, which would break the rule that tests write only under `tmp_path`. One such folder, `sprite-tool A7`, was created while writing the test and has been removed.
- Godot writes `atlas.png.import` next to the sheet on first import. The manifest does not list it, so `sprite build` leaves it alone, as intended.
- An `ms` above about 10^7 would make `speed` print in exponent form (`1e-05`). Godot reads that, but it has no decimal point.
- The headless test adds about 1.4 s to `make test` (2.5 s in total). Step 11's speed test should not count it.
- A7's manual half (opening the export in the Godot editor and playing an animation) is still for step 11.

### Step 10, 2026-10-10, commits `6064243`, `94c086e`, and the commit that adds this entry

**Evidence**

- `make test`: 821 passed (762 before the step; 31 new in `tests/test_importer.py`, 29 in `tests/test_import.py`; 1 stub case for `import` removed from `tests/test_cli.py`). `make check`: same.
- A10 is `test_a10_an_imported_png_renders_back_to_the_identical_image`: the demo goblin is rendered, imported as `goblin_copy`, loaded and rendered again; the pixels are equal and stdout is exactly `goblin_copy.sprite.toml`.
- Every case in the task file's verification list has a test, at the command (`tests/test_import.py`) and, for mapping, placement, `--scale` and `--snap`, at the function (`tests/test_importer.py`).
- Five deliberate faults in `importer.py` (centre rounding, the alpha threshold, which key wins a shared colour, the row offset, the scale repeat) each failed at least one test.
- Manual check, on a copy of the demo: importing `out/frames/goblin.png` gave a grid identical to `units/goblin.sprite.toml`. A 16x16 placeholder in two off-palette colours with `--scale 2` printed ten E302 lines and a count and exited 1; with `--snap` it printed `#28283c -> k (#1a1c2c) x32`, `#c83c5a -> r (#b13e53) x48` and the path, and `sprite check` on the result printed `ok: 1 sprite, 1 frame`. A second import exited 2 with `error: ph.sprite.toml already exists`.
- `uv run sprite build --project examples/demo` still prints `built: 4 sprites, 6 frames, 2 targets`.

**Names later steps need**

- `importer.import_png(path, canvas, palette, *, scale=1, snap=False)` and `importer.to_rows(image, canvas, palette, path, *, scale=1, snap=False)`, each returning `Imported(rows, problems, snapped)`. `rows` is empty when there is a problem. `importer.sprite_text(canvas_name, rows)` is the file text.
- `check.off_palette_problems(path, pixels)` builds the E302 lines (ten, then a count) from `(x, y, colour)` tuples. It was the end of `check.check_png`, which now calls it; `check_png` behaves as before.
- `cli._not_implemented` is gone, since no subcommand is a stub any more.

**Choices the task file left open**

- **`--scale` repeats keys, not pixels.** Colours are matched on the PNG as given and each key is then repeated, so E302 coordinates are those of the original file whatever the scale. The scaled size is what must fit: `image is 32x32 at --scale 2, canvas 'tile' is 16x16`.
- **Placement is one rule.** The left edge is `anchor x - width // 2` and the top edge `anchor y - height`, each then moved to keep the image inside the canvas. An anchor of `[0, 0]` therefore gives top-left without a special case, and an anchor near an edge never pushes pixels off the canvas. With an odd width the extra column is to the right of the anchor.
- **E301 and E302 are reported together** when a PNG is both too large and off-palette, as `sprite check` does. With `--snap`, a too-large PNG is E301 only.
- **`--snap`.** Pixels that match exactly (alpha included) and alpha-0 pixels are left alone and not reported. Every other pixel is snapped: alpha below 128 becomes `.`, reported as `#b13e5364 -> . (transparent) x1`; otherwise the nearest key in RGB over every palette colour, the first in palette order on a tie. A source colour that is not opaque is printed as `#rrggbbaa`. Lines are sorted by the source colour's red, green, blue, alpha.
- **Refusals (exit 2)** are those of `new`: a bad id, an unknown class, an existing `<id>.sprite.toml` in the project root, and an id already used by a sprite or variant elsewhere in the project. When the id came from the file stem the message ends `(use --id <id>)`. They are checked before the PNG is read.
- **A PNG that is missing or cannot be read** is an E001 line and exit 1, as in `sprite check`, not exit 2.
- **A bad palette** prints the palette problems and exits 1 without reading the PNG (P5).
- **The printed path** is relative to the current directory, as for `new`. The file always goes to the project root; there is no `--dir`.

**Notes**

- `sprite guide` does not mention `import`. Its command list is the drawing loop (`new`, `check`, `preview`, `build`); step 11 can decide whether to add a line.
- With more than ten off-palette pixels the count line is printed before the pixel lines, because `cli.report` sorts problems with no position first. Step 03 recorded the same for `sprite check` on a PNG. Not changed here.
- The `--scale` help text is `the PNG is enlarged N times; shrink it first`, which reads as if `--scale` shrinks. It was written in step 01 and is not changed here.

### Step 08, 2026-10-10, commits `fbd8ce6`, `0570db6`, and the commit that adds this entry

**Evidence**

- `make test`: 762 passed (716 before the step; 48 new in `tests/test_preview.py`; 2 stub cases for `preview` removed from `tests/test_cli.py`). `make check`: same.
- A9 is `test_a9_preview_writes_one_png_and_prints_only_its_path`: stdout is exactly `.preview/goblin.png` and a newline, and the image is `32 * 6 + 2 * MARGIN` square.
- A15 is `test_a15_on_writes_the_unit_on_the_tile` (the command) and `test_a15_unit_stands_on_the_tile_each_at_its_own_display_scale` (the layout). `test_unit_anchor_is_at_the_bottom_centre_of_a_larger_tile` and `test_image_grows_to_show_a_unit_larger_than_the_tile` cover the anchor position where the demo's sizes would hide a mistake, because the demo's unit and tile are both 128 pixels square on screen.
- Every case in the task file's verification list has a test.
- Manual check, on a copy of the demo: `sprite preview warrior --grid --sheet`, `sprite preview warrior` and `sprite preview warrior --on ground_light` were run and the PNGs looked at. Frames, the red variant row, grid lines, the indices 0 to 28, the ids on the sheet and the warrior on the tile are all legible.
- `uv run sprite build --project examples/demo` still prints `built: 4 sprites, 6 frames, 2 targets`.

**Names later steps need**

- `preview.sprite_preview(project, sprite, variants, scale, grid=False)`, `preview.on_tile(project, sprite, tile, scale)` and `preview.contact_sheet(project, sprites)`, each returning an RGBA `PIL.Image`.
- Layout constants in `preview.py`: `MARGIN` 8 (border of every image), `GAP` 8 (between frames, rows and sheet cells), `GRID_MARGIN` 20, `GRID_LABEL_EVERY` 4, `ON_TILE_SCALE` 2, `SHEET_COLUMNS` 8, `LABEL_GAP` 2, and the font's `CHAR_WIDTH` 6 and `LINE_HEIGHT` 11.
- `cli.PREVIEW_DIR` is `".preview"`.
- `tests/test_preview.py` has the `demo` fixture (a copy of the demo as the current directory) and `break_sprite(root, name)`.

**Choices the task file left open**

- **Sizes without the grid.** Width is `2 * MARGIN + frames * canvas width * scale + (frames - 1) * GAP`; height is the same with rows (the sprite, then each variant).
- **The grid adds pixels instead of covering them.** Each art pixel is `scale` pixels plus a one-pixel line, so a gridded frame is `canvas * (scale + 1) + 1` and no art is hidden, even at `--scale 1`. Each frame has its own `GRID_MARGIN` on the left and top with the indices.
- **Label and line colours follow the background**: white text on a dark background, black on a light one, and grid lines half-way between.
- **Text uses `ImageFont.load_default_imagefont()`**, the bitmap font. `load_default()` returns a FreeType font when Pillow has FreeType.
- **`--on` writes `.preview/<id>.png`**, the same name as the plain preview. `--scale` is the common factor; `[preview].scale` is not used in this mode.
- **`--on` with no id** writes only the contact sheet. The tile id is still checked (unknown is exit 2).
- **`--scale` and `--grid` do not affect the contact sheet.**
- **Contact sheet layout.** Classes in config order, each starting a new row; at most `SHEET_COLUMNS` sprites per row. A cell is as wide as the sprite or the longest id in its class, whichever is greater, with the art and the id centred.
- **Checks.** With ids only, the problems considered are those in the files of the requested sprites and the `--on` tile; an error in another sprite does not stop the preview. With the contact sheet, every problem counts. A palette error always stops it (P5). Warnings are printed only alongside an error, so a successful run prints paths only.
- **An id whose file is too broken to give a sprite** is a check failure (exit 1, the file's problems), not an unknown id. A variant of such a file is an unknown id (exit 2), since nothing names it.
- **Order.** A repeated id is written once. Paths are printed in the order given, the sheet last. All images are made before any is written.
- **A preview that cannot be written** is `error: cannot write preview: <reason>`, exit 2.
- The preview background may have alpha; the image then keeps it.

**Notes**

- Grid indices overlap below about `--scale 3` for two-digit columns (a label is 12 pixels wide and labelled columns are `4 * (scale + 1)` apart, so they touch at scale 2).
- A canvas more than 999 pixels on a side would have labels wider than `GRID_MARGIN`.
- Old files in `.preview/` are never removed.

### Step 09, 2026-10-10, commits `397f8c5`, `672f910`, `1ca4c67`, and the commit that adds this entry

**Evidence**

- `make test`: 716 passed (664 before the step; 55 new in `tests/test_init_new_guide.py`; 3 stub cases for `init`, `guide` and `new` removed from `tests/test_cli.py`). `make check`: same.
- A1 is `test_a1_init_then_build_in_an_empty_directory`. Run by hand in an empty scratch directory as well: `sprite init` prints `created . (3 files)`, `sprite build` prints `built: 2 sprites, 4 frames, 1 target` and writes six PNGs under `out/`, and a second `sprite init` exits 2 with `error: sprite-tool.toml already exists`.
- A13 is `test_a13_demo_guide_is_short_and_lists_the_palette_and_canvas_classes`. `uv run sprite guide --project examples/demo` prints 47 lines, none longer than 100 characters.
- Templates ship in the package: `test_templates_ship_in_the_package` reads each through `importlib.resources`, and a wheel built by hand with `uv build --wheel` lists all four under `sprite_tool/templates/`. No test builds a wheel, because the build may need the network.
- `test_templates_match_the_demo` fails if `templates/palette.toml` or `templates/warrior.sprite.toml` differs from the demo's copy.
- Every case in the task file's verification list has a test.
- `uv run sprite build --project examples/demo` still prints `built: 4 sprites, 6 frames, 2 targets`, and `--check` prints `up to date`.

**Names later steps need**

- `guide.guide_text(project) -> str` and `guide.EXAMPLE`, the sprite file shown in the guide. `test_guide_example_is_a_valid_sprite_file_for_the_demo` runs `EXAMPLE` through `sprite check`, so a format change that breaks the example fails a test.
- `model.hex_colour(rgba)` gives `#rrggbb`, or `#rrggbbaa` when not opaque. It was `check._hex`; `check.py` and `guide.py` both use it now.
- In `cli.py`, for step 10 (`import`): `_SPRITE_ID_RE`, `_sprite_ids(project) -> dict[str, Path]` (every id in use, variants included, with its file), `_from_cwd(path, root)` (the path as printed by `new`) and `_unknown_canvas(name, project)`.
- `tests/test_init_new_guide.py` has the `empty` fixture (an empty current directory) and `project` (the same after `init`).
- A project from `init` has two sprites, `warrior` and `warrior_red`, four frames, and one `frames` target writing to `out`.

**Choices the task file left open**

- **`init` refuses if any of its three files exists**, not only `sprite-tool.toml`, so it never overwrites a palette or sprite. The message is `error: <path> already exists`, with the path as the user gave the directory.
- **The `.gitignore` from `init` holds only `.preview/`**, as specified. `out/` is not ignored, since a game normally commits exported art.
- **`new` prints the path relative to the current directory** when that directory is inside the project or contains the file, else absolute. This is the path to pass to `sprite check`.
- **`new --dir` creates the directory** if needed and must stay inside the project; otherwise exit 2.
- **A duplicate id in `new`** covers file stems anywhere in the project and variant ids (`warrior_red`). A file too broken to parse still holds its id.
- **`new` works with a bad palette.** It does not report palette problems.
- **`guide` with a bad palette** prints the palette problems and exits 1 without the guide (as P5 does for `check`).
- **Guide layout.** The palette legend is two colours per line, which keeps the demo guide at 47 lines. A colour with no name is listed as key and hex. The outline and grounded rules are always explained, even if no class uses them.
- The per-sprite `outline = false` and `grounded = false` are described in the canvas section, not in the example file.

**Notes**

- The guide lists `sprite preview <id> --grid`, which is a stub until step 08.
- The guide example uses the keys `k`, `w`, `b`, `B`, `r` and `R`. A project whose palette lacks them still gets this example; the legend below it is the project's own.
- If `init` fails part-way (for example a read-only directory), the files already written stay.

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
