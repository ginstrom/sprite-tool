# Step 07: Godot export

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.7 (`godot`), 5.6, 5.7

## Objective

Add the `godot` export target: a packed sheet, one text `SpriteFrames`
resource per sprite, and a JSON index carrying anchors and display scale.

## Requirements and context

- **R7 (part), R8.** The Godot 4 atlas target, using the shared deterministic packer.
- **Q1.** Byte-identical output: sub-resource ids come from sprite id and frame name, never random; no `uid`s, timestamps or absolute paths.
- **A5 (part).** A `red` variant appears as `<name>_red.tres`.
- **A7.** The export loads in Godot 4.7 as a `SpriteFrames` resource with the expected animation names and frame counts.
- **A14 (part).** A 32x32 unit and a 16x16 tile appear in one atlas at their own sizes.
- Every target exports all sprites, including variants. Frames are full canvas size.
- The tool does not write `.import` files or `uid`s. Godot creates those on first import, and they belong to the game repository.

### Files, for `name = "atlas"` and `res_path = "res://assets/sprites"`

**`atlas.png`**: the packed sheet.

**`<id>.tres`**: one per sprite, format 3 text resource, in exactly this shape:

```
[gd_resource type="SpriteFrames" load_steps=4 format=3]

[ext_resource type="Texture2D" path="res://assets/sprites/atlas.png" id="1"]

[sub_resource type="AtlasTexture" id="warrior_idle_0"]
atlas = ExtResource("1")
region = Rect2(1, 1, 32, 32)

[sub_resource type="AtlasTexture" id="warrior_idle_1"]
atlas = ExtResource("1")
region = Rect2(34, 1, 32, 32)

[resource]
animations = [{
"frames": [{
"duration": 1.0,
"texture": SubResource("warrior_idle_0")
}, {
"duration": 1.0,
"texture": SubResource("warrior_idle_1")
}],
"loop": true,
"name": &"idle",
"speed": 2.5
}]
```

- `load_steps` is the number of sub-resources plus two.
- The `ext_resource` path is `<res_path>/<name>.png`.
- One `AtlasTexture` sub-resource per frame, id `<sprite id>_<frame name>`, in file frame order.
- Each sprite animation becomes an animation with the same name, `speed = 1000 / ms`, and `loop` as declared. Format `speed` deterministically with a decimal point (`2.5`, `1.0`).
- A sprite with no animations gets one animation named `default` holding all its frames at `speed` `1.0`, with `loop` `true` (plan decision P11).
- Line endings are `\n`; end the file with one newline.

**`atlas.json`**: a plain index, because `SpriteFrames` cannot carry an anchor.

```json
{
  "warrior": {
    "anchor": [16, 32],
    "display_scale": 2,
    "frames": {"idle_0": [1, 1, 32, 32], "idle_1": [34, 1, 32, 32]},
    "size": [32, 32]
  }
}
```

Sorted keys, two-space indent, trailing newline.

## Dependencies and prerequisites

- **Step 01** provides `model.py`: `Sprite(id, source, canvas, frames, anims, outline, grounded, variant_of)`, `Canvas(name, width, height, anchor, display_scale, ...)`, `Anim(name, frames, ms, loop)`, `Placement(sprite_id, frame, x, y, w, h)`, `ExportTarget(type, out, name, res_path, padding)`. Config loading already accepts `type = "godot"` and requires `res_path`.
- **Step 04** provides `export.atlas.compose_sheet(sprites, images, padding) -> tuple[bytes, tuple[int, int], list[Placement]]`.
- **Step 05** provides the exporter contract `export(sprites, images, target) -> dict[str, bytes]` (relative path to content, no disk access), the registry `EXPORTERS` in `src/sprite_tool/export/__init__.py`, a deterministic JSON helper (see step 05's completion log for its name), and a working `sprite build`.
- **Environment:** `godot` 4.7.2 was on `PATH` (`/opt/homebrew/bin/godot`) when this plan was written, so the headless test should run on the author's machine. It must skip cleanly where `godot` is absent.

## Scope and implementation guidance

- `src/sprite_tool/export/godot.py` (proposed): the exporter.
- `src/sprite_tool/export/__init__.py` (exists): register `"godot"`. Step 06 adds a line here too.
- `examples/demo/sprite-tool.toml` (exists): add `[[export]]` with `type = "godot"`, `out = "out/godot"`, `name = "atlas"`, `res_path = "res://sprites"`. Step 06 also appends a block.
- If an existing test asserts the demo's target count in the `built:` line, update it.
- A target sharing a directory with `frames` (as in the design's example config) must not collide: this target writes `<name>.png`, `<name>.json` and `<id>.tres`, while `frames` writes `<id>.png`. A sprite whose id equals `name` would collide on the PNG; the step 05 conflict check reports that, and no extra handling is needed here.

### Exclusions

No `.import` files, no `uid`s, no GDScript for the games.

## Verification

`make test` (`uv run pytest`). Tests build a copy of `examples/demo/` under
`tmp_path`; no network or display. Proposed `tests/test_export_godot.py`:

- A two-frame fixture at known placements produces text equal to the example above, byte for byte.
- For each demo sprite, parse the `.tres` text: `load_steps` is correct; each `region` cut from `atlas.png` equals the rendered frame; animation names, frame counts, `speed` and `loop` match the sprite.
- `goblin.tres` (no animations) has one `default` animation with its frame.
- `warrior_red.tres` exists (A5).
- `atlas.json` has anchor, size, display scale and frame rectangles for every sprite; the unit is 32x32 and the tile 16x16 in one sheet (A14).
- Calling the exporter twice gives identical bytes.
- **Headless load (A7)**, skipped when `shutil.which("godot")` is `None`:
  1. Create a temporary Godot project in `tmp_path` (a minimal `project.godot`) and build the demo into it so that `res_path` matches the output location.
  2. Run `godot --headless --path <project> --import` so the sheet is imported.
  3. Run a small GDScript with `godot --headless --path <project> --script <file>` that loads each `.tres`, asserts it is a `SpriteFrames`, prints animation names and frame counts, and quits with a non-zero code on failure.
  4. Assert the printed names and counts.
  Use a subprocess timeout so a hung editor cannot stall the suite.

## Completion criteria

- [ ] `godot` exporter registered and producing the files as specified.
- [ ] Demo project builds with the `godot` target.
- [ ] Text-level tests pass; the headless Godot test passes on a machine with Godot 4.7 and skips elsewhere.
- [ ] `make test` passes.
- [ ] Index status and completion log updated, stating whether the headless test ran or skipped.
