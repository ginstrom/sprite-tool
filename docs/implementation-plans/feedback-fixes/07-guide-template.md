# Step 07: Guide and template

- **Plan:** [index.md](index.md)
- **Design:** [feedback-fixes.md](../../designs/feedback-fixes.md), sections 4.6 and 5.7
- **Requirement:** R18. **Criterion:** A26 (replaces the base design's A13).

## Objective

`sprite guide` states the palette key rules and limit, what each configured
export target writes and where, and what removing a palette key does, and it
documents runs, `outline = "auto"` and `build = false`.

## Dependencies

The guide must describe what the tool does, so these come first. What each
provides, stated here so this file stands alone:

- **Step 01 (runs).** A frame table accepts `runs`: a zero-based row index mapped to a list of `[column, "pixels"]` pairs, replacing exactly those pixels; `.` erases. Operations apply in the order `rows`, `runs`, `shift`, `flip`. `from` is optional; a table without it starts transparent, and a whole frame is written as a `[frames.<name>.runs]` table, one row per line.
- **Step 02 (auto outline).** `outline = "auto"` at the top of a sprite file: draw the interior only, one pixel inside the canvas edge; the tool draws the outline with the first key of the class's `outline` list.
- **Step 03.** `build = false` at the top of a sprite file: checked and previewed, never exported.
- **Step 04.** The command form `sprite build --adopt [<id>...]`.
- **Step 05.** A `frames` target writes `<name>.json` (`name` defaults to `sprites`) with size, anchor, scale and bounds, and `ExportTarget.name` is `"sprites"` for a frames target with no name.

Existing code (inspected at 0.2.0): `src/sprite_tool/guide.py` has `EXAMPLE`
(a complete sprite file on a 6x4 canvas), `_FORMAT`, `_RULES`, `_COMMANDS`,
and `guide_text(project)` joining the sections SPRITE FILE, PALETTE, CANVAS
CLASSES and COMMANDS. It prints 58 lines for the demo. The existing facts it
will now state: a palette key is one printable ASCII character other than
`.` `"` `'` `\` (`project._is_palette_key`), which allows 90; a sprite using
a removed key gets E104 per use and `build` writes nothing;
`preview --grid` labels every fourth row and column
(`preview.GRID_LABEL_EVERY`).

## Constraints

- Python 3.11 or later; Pillow is the only runtime dependency and `pytest` the only dev dependency. Add nothing.
- Tests need no display or network and write only under `tmp_path`.
- The guide is plain ASCII, no line longer than 100 characters, no trailing spaces, one trailing newline (existing tests hold all four).
- The demo's guide stays under 80 lines. Every line costs the reader tokens; add facts, not prose.
- The guide's example must stay a valid sprite file: `test_guide_example_is_a_valid_sprite_file_for_the_demo` in `tests/test_init_new_guide.py` writes it into a project and checks it.
- Do not change `tests/golden/`. The guide is not a generated export file.

## Changes

New or changed text, in the guide's existing sections:

- **Palette.** `A key is one printable ASCII character except . " ' \ and space, so a palette holds up to 90 colours.` and `Removing or renaming a key breaks every sprite that uses it: check reports each use as E104 and build writes nothing until they are fixed.`
- **Sprite file example.** One `runs` line in the derived frame, and the order comment renumbered: `rows`, `runs`, `shift`, `flip`. The comment on `from` says "required" today; it is now optional.
- **Format notes.** The table form of `runs` for a whole frame; `build = false`.
- **Rules.** `outline = "auto"`: draw the interior only, one pixel inside the canvas edge.
- **Exports**, a new section generated from the config, one entry per target:

  ```
  EXPORTS  sprite build writes these; do not edit them by hand
  frames  ../public/assets/sprites  <id>.png (the default frame), <id>__<frame>.png when a sprite
                                    has several frames, sprites.json (size, anchor, scale, bounds)
  ```

  The directory is shown relative to the project root, with forward slashes. The index file name comes from the target's `name`. A `phaser` target writes `<name>.png`, `<name>.json` and `<name>.anims.json`; a `godot` target writes `<name>.png`, `<name>.json` (the index) and one `<id>.tres` per sprite. Print the target's real name in place of `<name>`. A project with no targets prints `EXPORTS  none configured`.
- **Commands.** `preview --grid` gains "labels every 4th row and column"; `build --adopt [<id>...]` is listed.

Also:

- `src/sprite_tool/templates/sprite-tool.toml`: the comment on `outline = ["k"]` says the first key is the one `outline = "auto"` draws with.
- `tests/test_init_new_guide.py`: `test_a13_demo_guide_is_short_and_lists_the_palette_and_canvas_classes` asserts `len(lines) < 60`; the limit becomes 80.

## Implementation guidance

- Add `_exports(project)` to `guide.py` and a section for it in `guide_text`. `project.exports` holds `ExportTarget(type, out, name, res_path, padding)` with `out` absolute; `os.path.relpath(target.out, project.root)` gives the shown directory.
- The demo has three targets, so its Exports section is the long case. Count the lines after each addition: `uv run sprite guide --project examples/demo | wc -l`.
- `AGENTS.md` says of `guide.py`: update it when the sprite file format or a command changes. That is this step.

Not in this step: README, `AGENTS.md` and the base design (step 08).

## Verification

In `tests/test_init_new_guide.py`:

- **A26.** `sprite guide` for the demo names the forbidden key characters, the limit of 90, each export directory with its file pattern, and E104 for a removed key, in under 80 lines.
- Presence of each fact under **Changes**: the `runs` line and the renumbered order in the example, the table form, `build = false`, `outline = "auto"`, the `--grid` labels, `build --adopt [<id>...]`.
- The Exports section for zero targets (`EXPORTS  none configured`), one target and three; a frames target with `name = "units"` prints `units.json`; a directory outside the project prints with `../`.
- The example is still a valid sprite file (the existing test), and its `runs` line changes the frame it is in.
- A project made by `sprite init` loads, and its config comment mentions `auto`.
- The existing format tests (ASCII, 100 columns, no trailing spaces) pass.

Commands: `uv run pytest tests/test_init_new_guide.py`, then `make check`.
Read the output once as its reader would:
`uv run sprite guide --project examples/demo`.

## Completion criteria

- [ ] A26 has a passing test; the demo's guide is under 80 lines.
- [ ] Each fact under **Changes** is asserted by a test.
- [ ] `git status` shows no change under `tests/golden/`.
- [ ] `make check` passes.
- [ ] The step's row in [index.md](index.md) is `done`, with a completion log entry (date, commit, test result, and the demo guide's line count).

**Handed to later steps:** the guide's line count and final wording (step 08
runs the manual acceptance with only the guide as reference).
