# sprite-tool 0.3 implementation plan: fixes from the Yomi session

- **Source design:** [docs/designs/feedback-fixes.md](../../designs/feedback-fixes.md), dated 2026-10-10. The file was untracked when this plan was written; the repository was at commit `61fa765` (release 0.2.0).
- **Amends:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), the base design. Requirement and criterion ids continue its numbering.
- **Plan written:** 2026-10-10
- **Repository state when planned:** 0.2.0, `make test` gives 900 passed, `sprite guide` prints 58 lines for the demo. The earlier plan in [../sprite-tool/](../sprite-tool/index.md) is complete and is not changed by this one.

## Purpose and scope

Release 0.3.0, in which an agent can draw a unit as a short list of pixel runs
with no outline, see it at game size, and have the game read scale, anchor and
bounds from a generated file. Seven requirements, R13 to R19:

- `outline = "auto"` on a sprite (R13) and `runs` in a frame (R14).
- A `sprites.json` index in the `frames` target, and two more keys in the `godot` index (R15).
- `build --adopt <id>...` (R16) and `build = false` on a sprite (R17).
- More facts in `sprite guide` (R18) and game-size frames in `sprite preview` (R19).

Out of scope (design non-goals): a `sprite outline` command, a canvas-wide
auto-outline switch, an `exclude` list in the config, a column ruler in
`sprite new`, sprite data in the Phaser atlas files, and any change to the
Yomi repository.

## Shared constraints

Every task file repeats these.

- **Stack.** Python 3.11 or later. One runtime dependency, Pillow, pinned to `>=12.3,<12.4`. `argparse` for the CLI. `pytest` is the only dev dependency. Add nothing.
- **Tests.** `make test` runs `uv run pytest`; `make check` runs the tests and then `sprite check` on `examples/demo`, and must pass before every commit. No test may need a display or the network. Tests write only under pytest's `tmp_path`; they never write into `examples/demo/` or `tests/golden/`.
- **Output.** Success prints one summary line. Each problem is one line on stdout. No colour, banners or progress output. Exit codes: `0` success, `1` check failures, `2` usage or config error (`error: <message>` on stderr). Exceptions: `init` prints a second line, and after this plan `build --adopt` prints one `adopted` line per file before the summary.
- **Determinism.** The same inputs give byte-identical PNG, JSON and `.tres` files. Iterate in sorted order; write no timestamps, absolute paths or tool version into generated files. Previews are exempt.
- **Safe writes.** Export files are only created, overwritten or deleted through `manifest.py`.
- **Compatibility.** Every 0.2.0 project loads and builds unchanged, apart from the new index file in a `frames` target. `version = 1` in the config stays.
- **Golden files.** `tests/golden/` changes only in step 05, by `make golden`, with the diff read before committing.

## Tasks

| Step | Task | Outcome | Depends on | Status |
|---|---|---|---|---|
| 01 | [Runs](01-runs.md) | `runs` in a frame table; `from` optional | none | done |
| 02 | [Automatic outline](02-auto-outline.md) | `outline = "auto"` draws the outline; edge faults reported with their own wording | 01 | done |
| 03 | [`build = false`](03-build-false.md) | A sprite that is checked and previewed and never exported | none | done |
| 04 | [Adopt by id](04-adopt-by-id.md) | `build --adopt [id ...]`, `adopted` lines, new stop message | 03 | done |
| 05 | [Export index, demo sprites and golden files](05-export-index-demo-golden.md) | `sprites.json` in `frames`, `canvas` and `bounds` in the `godot` index, two new demo sprites, regenerated golden files | 01, 02, 03 | done |
| 06 | [Preview at game size](06-preview-game-size.md) | Game-size frames beside the enlarged ones; `--scale display` | none | pending |
| 07 | [Guide and template](07-guide-template.md) | Guide states key rules, exports, removed keys, runs, auto outline, `build = false` | 01, 02, 03, 04, 05 | pending |
| 08 | [Documentation, version 0.3.0 and acceptance](08-docs-release-acceptance.md) | Base design, README and AGENTS.md brought in line; version set; manual acceptance run | 01 to 07 | pending |

## Execution order

1. **01**, then **02**, then **03**. Step 03 does not need 01 or 02, but all three edit `_Parser.parse` in `src/sprite_tool/spritefile.py` and the dataclasses in `model.py`, so run them in this order unless you are ready to merge.
2. **04** and **05**, in either order. Both edit `cli._build`; 04 changes the ownership check and output, 05 changes nothing there beyond what 03 did, so a merge is small.
3. **07**.
4. **08** last.

**06** depends on nothing and may run at any point before 08, or in parallel
with 01 to 05. It edits `cli._preview` and the `preview` arguments in
`cli.build_parser`; no other step touches those.

**Integration checkpoints.**

- After 03: `make check` passes and `git status` shows no change under `tests/golden/` or `examples/demo/`.
- After 05: `make check` passes against the regenerated golden files, and `uv run sprite build --project examples/demo` run twice leaves `git status` clean.
- After 08: `make check` passes from a clean clone and `uv run sprite --version` prints `sprite 0.3.0`.

## Requirement mapping

| Requirement | Steps |
|---|---|
| R13 automatic outline | 02, 05 (demo sprite under the golden test) |
| R14 runs | 01, 05 (demo sprite) |
| R15 sprite data in exports | 05 |
| R16 adopt by id | 04 |
| R17 `build = false` | 03, 05 (demo sprite) |
| R18 guide | 07 |
| R19 preview at game size | 06 |
| Q1 deterministic output | 05 |
| Q2 one summary line, with the `adopted` exception | 04, 08 (AGENTS.md) |
| Q3 thin; auto-outline leaves the non-goals | 02, 08 (base design) |
| Compatibility | 01, 03, 05 (existing tests keep passing) |

| Acceptance criterion | Steps |
|---|---|
| A16 auto sprite equals its hand-outlined twin | 02 |
| A17 edge pixel is E201 at its line and column | 02 |
| A18 runs-only frame equals a full grid | 01 |
| A19 derived frame differs in exactly the run's pixels | 01 |
| A20 run past the edge, unknown key | 01 |
| A21 `sprites.json` contents | 05 |
| A22 `build --check` after a `display_scale` edit | 05 |
| A23 `--adopt warrior` stops; `--adopt warrior goblin` builds | 04 |
| A24 `--adopt nosuch` exits 2 | 04 |
| A25 `build = false` | 03 |
| A26 guide facts, under 80 lines | 07 |
| A27 preview widths | 06 |
| Manual acceptance (design section 7) | 08 |

## Decisions made while planning

The design leaves these points open. None blocks work; each has a default
that the task files use. Change the default here and in the named step if you
disagree.

| ID | Point | Default used in this plan | Steps |
|---|---|---|---|
| P1 | **When to run `make golden`.** The design says once. `AGENTS.md` says golden files are committed with the change that caused them, and `make check` must pass at every commit. | Everything that changes generated output (the index, the godot keys, the frames manifest key, the two demo sprites) is in step 05. Steps 01 to 04 do not touch `examples/demo/`. | 05 |
| P2 | **New dataclass fields.** `Canvas.outline_key`, `Sprite.auto_outline` and `Sprite.build` are added to dataclasses that many tests construct directly. | They are the last fields and have defaults (`None`, `False`, `True`). | 02, 03 |
| P3 | **A bad `outline` value.** The design gives the E001 for `"auto"` on a class with no rule, and nothing for other bad values or for what the sprite is afterwards. | Any value other than `true`, `false` or `"auto"` is E001 `outline must be true, false or "auto"`. After either E001 the sprite is parsed as `outline = true` without auto. | 02 |
| P4 | **E201 wording for an auto sprite.** The design gives the text after the frame name. | Keep the existing prefix: `frame 'main': 'b' is on the canvas edge; ...`, and `frame 'main' row r, col c: ...` for a frame with no line per row. | 02 |
| P5 | **A17 and runs.** A17 wants the fault "at its own line and column"; section 4.2 says a runs frame has no line per row. | A17 is tested on a frame written as a grid. A runs frame reports the same fault at the frame's line with `row r, col c` in the message. | 02 |
| P6 | **Stop message for one file.** The design gives only the plural form. | One file: `<path> already exists and was not written by sprite-tool (...)`. More: `<path> and N more already exist and were not written by sprite-tool (...)`. | 04 |
| P7 | **`--check --adopt nosuch`.** The design says `--check` ignores `--adopt`. | Ignored entirely: ids are not validated under `--check`. | 04 |
| P8 | **When adopt ids are validated.** | After the check failures are reported (a failing project exits 1 first) and before anything is planned or written. Variant ids such as `warrior_red` are valid ids. | 04 |
| P9 | **A sprite named like a shared file.** By the naming rule, a sprite with id `atlas` makes `--adopt atlas` take `atlas.png` and `atlas.json`. | Follow the rule as written. No special case. | 04 |
| P10 | **Bounds of an empty grid.** A build never exports one (blank sprites are left out, an empty frame is E106), but the function is public. | `bounds` returns `[0, 0, 0, 0]`, and `union` skips boxes of zero width. | 05 |
| P11 | **`--scale display --grid --on <tile>`.** `--on` ignores `--grid` today. | `--scale display` with `--grid` is exit 2 whether or not `--on` is given. | 06 |
| P12 | **Tagging the release.** The design's outcome is a 0.3.0 release; a release is a pushed tag. | Step 08 sets the version and commits. `git tag` and `git push` are left to the author. | 08 |

## Overall completion criteria

- `make check` passes from a clean clone with `uv` installed.
- Every acceptance criterion A16 to A27 has an automated test.
- `uv run sprite build --project examples/demo` run twice leaves `git status` clean.
- `pyproject.toml` still lists Pillow as the only runtime dependency, and its version is `0.3.0`.
- The manual acceptance run in step 08 is recorded below.
- Every row in the task table is `done`, with evidence recorded below.

## Blockers and open questions

No blockers. The design's two non-blocking questions need no work here:

1. Writing the same index for the Phaser target. Left out; no game uses that target yet.
2. `sprite new --runs`. To be decided after the manual acceptance run in step 08 shows which form an agent reaches for; record what you saw there.

## For implementers

After working on a task, update its row in the task table (`in progress`,
`done` or `blocked`) and add an entry under **Completion log** with the date,
the commit, and the evidence (the test command and its result), or the
blocker. If you depart from a default in **Decisions made while planning**,
record it there.

## Completion log

### Step 01: Runs (2026-10-10, commit `610d7af`)

- **Evidence.** `uv run pytest tests/test_spritefile.py`: 177 passed. `make check`: 957 passed (900 before the step), then `ok: 4 sprites, 6 frames`. `git status` shows no change under `examples/demo/` or `tests/golden/`.
- **Criteria.** A18 and A19 are tested on the parsed grid in `tests/test_spritefile.py` and on the rendered PNGs in `tests/test_build.py`. A20 is `test_a20_bad_run_is_one_line_at_its_row_and_drops_the_frame`, each case in the inline and the table form.
- **Wording chosen where the task file gave none.**
  - A row whose value is not a list of pairs: E001 `frame 'x' row 1: runs must be a list of [column, "pixels"] pairs`.
  - An empty pixel string: E001 `frame 'x' row 1: run at col 1 has no pixels`.
  - `runs` that is not a table: E001 at the `runs` key.
  - A negative column is the same E103 as a run past the right edge (`run at col -1 is 1 wide, ...`).
  - `from` of the wrong type now reads `from must be a frame name`; a frame of the wrong type reads `must be a grid string or a table with from, rows or runs`.
- **Choices later steps may meet.**
  - The `N more unknown palette keys` line goes to the line of `rows` when the table has `rows`, otherwise to the line of `runs`.
  - `Frame.line` of a table frame is the line of `rows` if it has one, else the frame's own header, else its `[frames.<name>.runs]` header.
  - `rows` without `from` is accepted as well (the frame starts transparent), as the task's "`from` is optional" implies.
  - An empty run list (`9 = []`) is accepted and writes nothing.
- **No deviation** from the task file.

### Step 02: Automatic outline (2026-10-10, commit `3953d33`)

- **Evidence.** `uv run pytest tests/test_spritefile.py tests/test_check.py tests/test_project.py`: 349 passed. `make check`: 992 passed (957 before the step), then `ok: 4 sprites, 6 frames`. `git status` shows no change under `examples/demo/` or `tests/golden/`. A scratch project with one auto-outlined runs sprite: `sprite check` and `sprite build` exit 0 and the PNG holds the outline; with an interior pixel in column 0, `check` prints the one E201 line and exits 1.
- **Criteria.** A16 is `test_a16_auto_outlined_sprite_passes_and_renders_as_its_hand_outlined_twin` and A17 is `test_a17_interior_pixel_on_the_canvas_edge_of_an_auto_sprite_is_e201_at_that_pixel`, both in `tests/test_check.py`.
- **One existing test changed.** `test_load_valid_project` in `tests/test_project.py` compares whole `Canvas` values, so its expected `unit` canvas now has `outline_key="k"`. The task file expected no existing test to change; this one follows from the new field and nothing else did.
- **Choices later steps may meet.**
  - The outline pass is in `_Parser.parse`, on the tuple of resolved frames, not inside `_Parser._frames`. The effect is the one the task file asks for: every frame is resolved on interiors first.
  - `outline = "auto"` on a class with `outline = []` is read as `outline = true` after its E001 (plan decision P3), so `Sprite.outline` is true there and `check` would report every edge pixel against the empty list. On a class with no rule `Sprite.outline` is false.
  - A grid frame of an auto sprite stays `literal` with its line, so its E201 is at the pixel's own line and column.
  - The edge wording is used for every E201 of an auto sprite that is not a variant, including a derived frame that `shift` moved onto the edge (`frame 'lean' row 2, col 0: ...`).
  - Step 07: the old E001 text `outline must be true or false` is now `outline must be true, false or "auto"`.
- **No other deviation** from the task file.

### Step 03: `build = false` (2026-10-10, commit `770e1f2`)

- **Evidence.** `uv run pytest tests/test_build.py tests/test_spritefile.py`: 244 passed. `make check`: 1004 passed (992 before the step), then `ok: 4 sprites, 6 frames`. `git status` shows no change under `examples/demo/` or `tests/golden/` (the integration checkpoint after 03).
- **Criteria.** A25 is the `test_a25_*` tests: nine in `tests/test_build.py`, on a copy of the demo with `scout` (the goblin's file plus a `pale` variant) added by `add_scout`, and two in `tests/test_spritefile.py` for the field. Each clause of the task's verification list has one; `build --check` reporting the stale files before the rebuild has its own as well.
- **Choices later steps may meet.**
  - `build = "no"` is reported and the sprite is then read as `build = true`, which is what `_flag` does for `outline` and `grounded`.
  - The filter in `cli._build` is one list comprehension with the blank-sprite filter: `sprite.build and not check.is_blank(sprite)`. Step 04 validates adopt ids against the list it leaves.
  - `ALL_TARGETS` in `tests/test_build.py` configures the three target types in one project; step 05 can use it.
- **No deviation** from the task file. `check.py`, `preview.py` and the exporters are unchanged.

### Step 04: Adopt by id (2026-10-10, commits `8421d52`, `fc7a2bf`)

- **Evidence.** `uv run pytest tests/test_manifest.py tests/test_build.py`: 104 passed. `make check`: 1035 passed (1004 before the step), then `ok: 4 sprites, 6 frames`. `git status` shows no change under `examples/demo/` or `tests/golden/`. `uv run sprite build --help` shows `--adopt [id ...]` with the new help text.
- **Criteria.** A23 is the two `test_a23_*` tests and A24 is `test_a24_adopting_an_unknown_id_exits_2_and_writes_nothing`, in `tests/test_build.py`. Each other clause of the task's verification list has a test beside them; the naming rule and both forms of the stop message are in `tests/test_manifest.py` under "adopting by sprite id".
- **Existing tests changed.** `test_an_unowned_file_blocks_the_build` now asserts the whole new stop message, `test_adopt_takes_ownership_of_existing_files` expects its `adopted` line, and `test_parsed_arguments` in `tests/test_cli.py` expects `args.adopt` to be `None` without the flag. The older tests in `tests/test_manifest.py` assert only parts of the message that did not change, so they needed no edit.
- **Choices later steps may meet.**
  - `manifest.check_ownership(plans, adopt_ids=None)`: `None` and an empty set both adopt nothing. The bare flag is `args.adopt == []` in `cli._build`, which skips the call, as before.
  - `manifest.belongs_to` looks at the last part of the path, so a file in a subdirectory of the output directory follows the same rule.
  - The path in the stop message is still the directory joined to the name, as it was at 0.2.0 (absolute when `out` resolves to an absolute path). Only the `adopted` lines go through `cli._from_cwd`.
  - An unknown id is reported even when no file needs adopting, and with no sprites in the build the list reads `(sprites: none)`, as in `cli._preview`.
  - Giving an id twice is accepted.
  - Steps 07 and 08: the README still describes only the bare `--adopt` (command table and the safe-writes section), `AGENTS.md` still has the old output rule, and the guide does not mention `--adopt` at all.
- **No deviation** from the task file.

### Step 05: Export index, demo sprites and golden files (2026-10-11, commits `faacf42`, `648de2a`)

- **Evidence.** `make check`: 1063 passed (1035 before the step), then `ok: 6 sprites, 8 frames`. `uv run sprite build --project examples/demo` twice prints `built: 5 sprites, 7 frames, 3 targets` each time and `git status` shows nothing new (the integration checkpoint after 05). The headless Godot test ran, not skipped.
- **Golden files.** `make golden` run once. 23 files (20 before): 12 text, 11 PNG. New: `frames/slime.png`, `frames/sprites.json`, `godot/slime.tres`. Changed, as the task file expected: the frames manifest (key `frames:sprites`, two more files), the godot manifest (`slime.tres`), `godot/atlas.json` (`canvas`, `bounds`, the `slime` entry, moved rectangles), the regions in three `.tres` files, `phaser/atlas.json` and both sheets. Nothing for `sample_slime`.
- **Criteria.** A21 is the two `test_a21_*` tests and A22 is `test_a22_build_check_flags_the_index_after_a_display_scale_edit`, in `tests/test_build.py` under "the index". The pure functions are in `tests/test_export_index.py`; the entry's shape is in `tests/test_export_frames.py` and `tests/test_export_godot.py`; `name` on a frames target is in `tests/test_project.py`. One A21 test compares every frame's `bounds` with the bounding box of the exported PNG.
- **Demo sprites.** `units/slime.sprite.toml` is 14 rows of runs with `outline = "auto"`. `units/sample_slime.sprite.toml` is the same slime as a full grid with the outline written in, with `build = false`; `tests/test_demo.py` holds the two to the same rows. If the slime's art changes, `sample_slime` must be rewritten to match.
- **Existing tests changed**, all for the demo's new contents or the new file: the `built:` and `up to date:` lines (`5 sprites, 7 frames`), `ok: 6 sprites, 8 frames`, the id lists in unknown-id messages, `DEMO_FILES`, the manifest key `frames:sprites`, E401 counts in `tests/test_build.py` (the index is one more file), the golden counts, the contact sheet tests in `tests/test_preview.py` (five unit cells as wide as `sample_slime`), and `"name on frames"` in `tests/test_project.py`, which was an error case and is now two (not a string, empty). The demo fixtures in `tests/test_export_godot.py` and `tests/test_export_phaser.py` now drop sprites with `build = false`, as `cli._build` does.
- **Choices later steps may meet.**
  - A frames target with no sprites still writes `<name>.json`, holding `{}`, as the godot target does.
  - `project.DEFAULT_INDEX_NAME` is `"sprites"`. `ExportTarget.name` is never `None` for a target loaded from a config; `manifest.target_key` still handles `None` for targets built by hand in tests.
  - When a sprite leaves the build, `sprites.json` is rewritten and `build --check` reports it as `stale` beside the sprite's `no longer generated` files.
  - Step 06: the demo's contact sheet now has five units (`goblin`, `sample_slime`, `slime`, `warrior`, `warrior_red`); `UNIT_IDS` in `tests/test_preview.py` lists them.
  - Step 07: the demo's lines are `ok: 6 sprites, 8 frames` and `built: 5 sprites, 7 frames, 3 targets`. The docstring of `manifest.target_key` already says `frames:sprites`.
  - Step 08: `export/index.py` (`bounds`, `union`, `sprite_entry`) is not yet in the layout in `AGENTS.md`.
- **No deviation** from the task file.
