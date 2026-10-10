# Step 08: Documentation, version 0.3.0 and acceptance

- **Plan:** [index.md](index.md)
- **Design:** [feedback-fixes.md](../../designs/feedback-fixes.md), sections 6 and 7
- **Covers:** the consequences list in section 6, quality constraints Q2 and Q3 as documented rules, and the manual acceptance in section 7.

## Objective

The base design, `README.md` and `AGENTS.md` describe 0.3.0, the version is
`0.3.0`, and one unit has been redrawn in a scratch copy of Yomi using only
`sprite guide`.

## Dependencies

Steps 01 to 07, all done. What they changed, so this file stands alone:

| Step | What now exists |
|---|---|
| 01 | `runs` in a frame table (`{ 9 = [[13, "ddsskh"]] }`, or a `[frames.<name>.runs]` table); `from` optional; order `rows`, `runs`, `shift`, `flip`; E103 and E104 wording for runs. |
| 02 | `outline = "auto"`; `Canvas.outline_key`, `Sprite.auto_outline`; E201 canvas-edge wording; E001 on a class with no outline rule. |
| 03 | `build = false`; `Sprite.build`. |
| 04 | `build --adopt [id ...]`; `adopted <path>` lines before the summary; the new stop message; `manifest.belongs_to`. |
| 05 | `<name>.json` in a `frames` target (`name` defaults to `sprites`); `canvas` and `bounds` in the godot index; `src/sprite_tool/export/index.py`; manifest key `frames:sprites`; two more demo sprites; regenerated golden files. |
| 06 | Game-size frames in `sprite preview <id>`; `--scale display`; `--scale display --grid` is exit 2. |
| 07 | The guide's new facts and Exports section; limit of 80 lines for the demo. |

Read each step's completion log entry in [index.md](index.md) first, for
anything that departed from the plan, and document what was built.

## Constraints

- Python 3.11 or later; Pillow is the only runtime dependency and `pytest` the only dev dependency. `uv lock` after the version change must alter nothing but the project's own version.
- `make check` passes before the commit.
- Do not change `tests/golden/`. No generated file holds the tool version, so the version change must not move the golden test.
- Nothing in the Yomi repository (`~/play/yomi`) is changed. The acceptance run works on a copy outside it.
- Do not tag or push. `git tag -a v0.3.0` and the push are the author's (plan decision P12).

## Documentation changes

**Base design, `docs/designs/sprite-tool.md`.** Bring these sections in line
with the amending design, which wins where they disagree:

- 2: the non-goal "drawing helpers (lines, fills, shading, auto-outline)" loses auto-outline; A9 (preview) and A13 (guide under 60 lines, now 80, criterion A26).
- 4.3: `name` on a `frames` target.
- 4.4: frame tables (`runs`, optional `from`, the order), `outline` values, `build`.
- 4.5: `build --adopt [id ...]`, the `adopted` lines, `build = false`; `preview` rows and `--scale display`.
- 4.6: E103, E104 and E201 wording.
- 4.7: the frames index and the two new godot index keys.
- 4.8 and 5.3: preview and the data model (`Canvas.outline_key`, `Sprite.auto_outline`, `Sprite.build`).

Add a line near its top saying it was amended by `feedback-fixes.md`.

**`README.md`** (inspected at 0.2.0):

- The command table: `sprite build [--check] [--adopt [<id>...]]`, and `--scale N|display` on `preview`.
- The section "Safe writes: the manifest and `--adopt`": adopting by id, the `adopted` lines, and that shared files (`atlas.png`, `sprites.json`) need the bare flag.
- The sprite file format wherever it is described: `runs`, `outline = "auto"`, `build = false`.
- The export targets: `sprites.json` and what a game reads from it (canvas class, size, anchor, display scale, file names, bounds).
- An upgrade note for games on 0.2.0: `build --check` fails until they rebuild, because of the new index file; a hand-made `sprites.json` in a frames directory needs one bare `--adopt`.
- `0.2.0` appears on six lines (the install commands, the `sprite --version` comment and the CI line); all become `0.3.0`.

**`AGENTS.md`:**

- The Output rule: `build --adopt` adds one line per adopted file before the summary, next to the exception for `init`.
- The Layout: `src/sprite_tool/export/index.py` (bounds and the entry both indexes share), `manifest.belongs_to`, and that the `frames` target also writes an index.
- A pointer to the amending design and this plan beside the existing two links.

## Version

Following the Releases section of `AGENTS.md`:

1. `version = "0.3.0"` in `pyproject.toml`.
2. `uv lock`.
3. The README tag, as above.
4. `make check`, then commit.

Stop there.

## Manual acceptance

From the design, section 7: in a scratch copy of Yomi's `art/`, redraw one
unit as runs with `outline = "auto"`, using only `sprite guide`. It should
reach a clean `build` without a generator script, and the preview should show
the unit at 3x beside the 6x view.

1. Copy `~/play/yomi/art` to a scratch directory outside both repositories. Point any export `out` that leaves the copy at a directory inside the scratch area, so the run cannot write into Yomi.
2. Work from `uv run sprite guide --project <copy>` alone, as an agent in the game repository would. Do not read this repository's source or designs while drawing.
3. Pick one unit in `<copy>/units/`. Rewrite it as `[frames.<name>.runs]` with `outline = "auto"`.
4. `sprite check`, `sprite preview <id>`, `sprite build` until clean. Open the preview.
5. Record in the completion log: the unit, whether a script was needed, how many check rounds it took, anything the guide did not say that you had to guess, and whether you reached for the grid form or the runs form first. The last answers design question 2 (`sprite new --runs`).

If the guide left something to guess, fix the guide (keeping the demo under
80 lines and its tests passing) and say so in the log.

## Verification

- `make check` passes.
- `uv run sprite --version` prints `sprite 0.3.0`.
- `git diff --stat` shows nothing under `tests/golden/`, and `uv.lock` differs only in the project's version.
- `grep -n "0\.2\.0" README.md` finds nothing, or only the upgrade note.
- Every relative link in the changed Markdown files resolves.
- Each item in the design's section 6 list "Base design sections to update" is done or noted in the log as needing no change.
- From a clean clone (`git clone`, `uv sync`, `make check`): passes.

## Completion criteria

- [ ] Base design, README and `AGENTS.md` updated as listed.
- [ ] Version `0.3.0` in `pyproject.toml` and `uv.lock`; README install commands at `@v0.3.0`.
- [ ] Manual acceptance run recorded in the completion log, with what was observed.
- [ ] `make check` passes from a clean clone.
- [ ] Every row in the task table in [index.md](index.md) is `done`, with a "Plan complete" entry in the completion log restating the overall completion criteria and their results.
- [ ] The author has been told the tag and push remain: `git tag -a v0.3.0`, then push the branch and the tag.
