# Step 02: Automatic outline

- **Plan:** [index.md](index.md)
- **Design:** [feedback-fixes.md](../../designs/feedback-fixes.md), sections 4.1, 5.1, 5.2 and 5.3
- **Requirement:** R13. **Criteria:** A16, A17.

## Objective

A sprite file can say `outline = "auto"`. Its source then holds the interior
only, and the tool adds the one-pixel outline.

```toml
canvas = "unit"
outline = "auto"
```

## Dependencies

- **Step 01 (runs).** It makes `from` optional in a frame table and adds `runs`, applied in the order `rows`, `runs`, `shift`, `flip`. This step's outline pass runs after all four. If step 01 is not done, this step can still be built and tested with grid and `rows` frames, but the edits land in the same functions (`_Parser._frames`, `_Parser._resolve`), so do 01 first.

Existing code this step changes (all inspected at 0.2.0):
`src/sprite_tool/model.py`, `src/sprite_tool/project.py` (`_load_canvas`),
`src/sprite_tool/spritefile.py`, `src/sprite_tool/check.py`
(`_outline_problems`).

## Constraints

- Python 3.11 or later; Pillow is the only runtime dependency and `pytest` the only dev dependency. Add nothing.
- Tests need no display or network and write only under `tmp_path`, never into `examples/demo/` or `tests/golden/`.
- Each problem is one output line. Bad art never raises.
- Every 0.2.0 project loads and checks exactly as before. `outline = true` and `outline = false` keep their meaning.
- Do not change `examples/demo/` or `tests/golden/` in this step.
- Auto-outline is the only drawing helper. Lines, fills and shading stay out.

## Behaviour to implement

`outline` at the top of a sprite file takes `true` (default), `false`, or
`"auto"`. With `"auto"`:

- The outline key is the **first** key in the canvas class's `outline` list in `sprite-tool.toml`. A class with no `outline` rule, or an empty list, makes this E001 at the `outline` line: `outline = "auto" needs an outline rule on canvas class 'tile'`.
- Every transparent pixel that has a drawn pixel directly above, below, left or right of it becomes the outline key. It is one pass over the frame as written: new outline pixels do not grow further outlines. Diagonals do not count, so corners come out rounded.
- A transparent hole inside the shape is outlined too. A one-pixel hole fills completely.
- It runs once per frame, on the final interior: after `rows`, `runs`, `shift` and `flip`, and before variant swaps. A derived frame therefore edits its parent's interior, never its parent's outline.
- The outline rule is then checked as usual. The only fault an auto sprite can have is an interior pixel on the canvas edge, where there is no room for the outline. It is E201 at that pixel, with the message `'b' is on the canvas edge; with outline = "auto" keep the interior 1 pixel inside` after the usual frame prefix (plan decision P4): `frame 'main': 'b' is on ...` for a grid frame, `frame 'main' row 5, col 0: 'b' is on ...` for a frame with no line per row.
- With `grounded`, the interior stops one row above the bottom and the outline supplies the bottom row. No code is needed for this; it follows from the pass.
- Variants are unchanged: a swap that recolours the outline key to one not in the class's list is still E201 for the variant, with the existing wording.

Plan decision P3: any `outline` value other than `true`, `false` or `"auto"`
is E001 `outline must be true, false or "auto"`. After either E001 the sprite
is parsed as `outline = true` without auto, so the rest of the file is still
checked.

## Implementation guidance

**Model (`model.py`).**

- `Canvas.outline_key: str | None = None`: the first key of the config's `outline` list; `None` with no rule or an empty list. `Canvas.outline` stays a `frozenset`, which is why the order has to be kept separately. Set it in `project._load_canvas`.
- `Sprite.auto_outline: bool = False`. Variants inherit it, since `spritefile._variant` uses `dataclasses.replace`.
- Both are last in their dataclass and have defaults (plan decision P2), so the many tests and `tests/conftest.py` helpers that build `Canvas` and `Sprite` directly keep working.

**Parsing (`spritefile.py`).**

- `_Parser.parse` reads `outline` with `self._flag(data, "outline")`, which accepts only a bool. Replace that with a helper returning `(applies, auto)`.
- `add_outline(rows, key)`: a pure function from a tuple of row strings to a tuple of row strings. It is the only new drawing code.
- **Where the pass goes.** `_Parser._frames` resolves every frame, derived ones through `_resolve`, on interior rows as today. Only after all frames are resolved, for an auto sprite, replace each resolved frame's `rows` with `add_outline(rows, canvas.outline_key)`. Doing it earlier would let a derived frame inherit its parent's outline.
- Invariant to keep: after parsing, `Frame.rows` is the final grid that is checked, rendered and exported. Nothing downstream knows about auto outlines except the wording below.

**Checks (`check.py`).**

- `_outline_problems` uses the canvas-edge wording when `sprite.auto_outline` is set and `sprite.variant_of is None`. It currently builds `{key!r} touches transparency, expected outline key {expected}`.
- No other change. `_outline_faults` already treats the canvas edge as transparent, and `_inherited_faults` already moves a parent's fault with `shift` and `flip`, so an edge fault carried into a derived frame is reported once, in the frame it comes from.

Not in this step: the guide's Rules line and the template comment (step 07),
a demo sprite with `outline = "auto"` (step 05), the base design's non-goal
wording (step 08).

## Verification

Tests go in `tests/test_spritefile.py` (parsing, `add_outline`),
`tests/test_check.py` (E201 wording) and `tests/test_project.py`
(`outline_key`), next to the tests they extend.

- `add_outline` on small grids: a plain shape; a shape with a hole; a one-pixel hole, which fills; a shape touching the edge, which gets no outline on that side and does not raise.
- `Canvas.outline_key` for `outline = ["k"]`, for `outline = ["o", "k"]` (it is `"o"`), for `outline = []` and for no rule.
- **A16.** An interior-only sprite with `outline = "auto"` on a class with `outline = ["k"]` passes `check`, and its rendered PNG bytes (`render.render` then `render.png_bytes`) equal those of the same sprite with the outline written by hand.
- **A17.** In such a sprite, written as a grid, an interior pixel in column 0 is E201 at its own line and column 1, and the message names the canvas edge.
- The same fault in a runs frame is one E201 with `row r, col 0` in the message (needs step 01).
- E001 on a class with no rule and on a class with an empty list, at the `outline` line. E001 for `outline = "foo"` and `outline = 3`.
- A derived frame of an auto sprite (`from` plus `rows`, and `from` plus `shift`) equals the outline of the edited interior, not an edit of the parent's outlined grid.
- A variant whose swap recolours `k` to a key outside the class's list is still E201 with the existing variant wording.
- `outline = true` and `outline = false` behave as before; the existing tests cover this and must pass unchanged.

Commands: `uv run pytest tests/test_spritefile.py tests/test_check.py tests/test_project.py`,
then `make check`. Expected: all pass, and `make check` ends with
`ok: 4 sprites, 6 frames`.

## Completion criteria

- [ ] A16 and A17 each have a passing test.
- [ ] Every earlier test still passes.
- [ ] `git status` shows no change under `examples/demo/` or `tests/golden/`.
- [ ] `make check` passes.
- [ ] The step's row in [index.md](index.md) is `done`, with a completion log entry (date, commit, test result).

**Handed to later steps:** `Canvas.outline_key`, `Sprite.auto_outline`, and
sprite files that may say `outline = "auto"` (steps 05 and 07 rely on them).
