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
| 01 | [Runs](01-runs.md) | `runs` in a frame table; `from` optional | none | pending |
| 02 | [Automatic outline](02-auto-outline.md) | `outline = "auto"` draws the outline; edge faults reported with their own wording | 01 | pending |
| 03 | [`build = false`](03-build-false.md) | A sprite that is checked and previewed and never exported | none | pending |
| 04 | [Adopt by id](04-adopt-by-id.md) | `build --adopt [id ...]`, `adopted` lines, new stop message | 03 | pending |
| 05 | [Export index, demo sprites and golden files](05-export-index-demo-golden.md) | `sprites.json` in `frames`, `canvas` and `bounds` in the `godot` index, two new demo sprites, regenerated golden files | 01, 02, 03 | pending |
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

Nothing yet.
