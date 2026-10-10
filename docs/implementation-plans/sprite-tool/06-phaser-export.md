# Step 06: Phaser export

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.7 (`phaser`), 5.6, 8 (assumptions)

## Objective

Add the `phaser` export target: a packed sheet, a Phaser "JSON Hash" atlas and
a Phaser animation JSON file.

## Requirements and context

- **R7 (part), R8.** The Phaser atlas target, using the shared deterministic packer.
- **Q1.** Byte-identical output for the same inputs: sorted keys, two-space indent, `\n` line endings, trailing newline; no version or timestamp.
- **A5 (part).** A `red` variant appears as sprite `<name>_red` in this target.
- **A6.** The export loads with `this.load.atlas` and `this.load.animation` in Phaser 4. This step tests structure automatically and runs the in-engine check by hand (below), because Phaser is the immediate use.
- **A14 (part).** A 32x32 unit and a 16x16 tile appear in one atlas at their own sizes.
- Every target exports all sprites, including variants. Frames are full canvas size, never trimmed or rotated.

### Files, for `name = "atlas"`

**`atlas.png`**: the packed sheet.

**`atlas.json`**: frame key is `<id>/<frame>`.

```json
{
  "frames": {
    "warrior/idle_0": {
      "frame": {"h": 32, "w": 32, "x": 1, "y": 1},
      "pivot": {"x": 0.5, "y": 1.0},
      "rotated": false,
      "sourceSize": {"h": 32, "w": 32},
      "spriteSourceSize": {"h": 32, "w": 32, "x": 0, "y": 0},
      "trimmed": false
    }
  },
  "meta": {
    "app": "sprite-tool",
    "image": "atlas.png",
    "scale": "1",
    "size": {"h": 34, "w": 128}
  }
}
```

`pivot` is the canvas anchor divided by the canvas size (`[16, 32]` on 32x32
gives `0.5, 1.0`).

**`atlas.anims.json`**: one entry per sprite animation, key `<id>/<anim>`.

```json
{
  "anims": [
    {
      "frames": [
        {"duration": 400, "frame": "warrior/idle_0", "key": "atlas"},
        {"duration": 400, "frame": "warrior/idle_1", "key": "atlas"}
      ],
      "key": "warrior/idle",
      "repeat": -1
    }
  ]
}
```

`key` inside a frame entry is the atlas name. `repeat` is `-1` for looping
animations and `0` otherwise. Order the entries by animation key. A project
with no animations still writes the file with an empty list.

### Points to confirm in the engine (plan decision P10)

- The design assumes Phaser reads `pivot` from JSON Hash frames. If it does not, the fallback is to document `setOrigin` from the anchor.
- In some Phaser 3 releases a frame's `duration` is added to the animation's base frame time instead of replacing it. Write what is specified here first, then confirm playback speed in Phaser 4 and change the exporter if needed.

## Dependencies and prerequisites

- **Step 01** provides `model.py`: `Sprite(id, source, canvas, frames, anims, outline, grounded, variant_of)`, `Canvas(name, width, height, anchor, display_scale, ...)`, `Anim(name, frames, ms, loop)`, `Placement(sprite_id, frame, x, y, w, h)`, `ExportTarget(type, out, name, res_path, padding)`. Config loading already accepts `type = "phaser"` with `name` (default `atlas`) and `padding` (default 1).
- **Step 04** provides `export.atlas.compose_sheet(sprites, images, padding) -> tuple[bytes, tuple[int, int], list[Placement]]` returning the sheet PNG bytes, its size and the placements.
- **Step 05** provides the exporter contract `export(sprites, images, target) -> dict[str, bytes]` (relative path to content, no disk access), the registry `EXPORTERS` in `src/sprite_tool/export/__init__.py`, a deterministic JSON helper (see step 05's completion log for its name), and a working `sprite build`. `examples/demo/sprite-tool.toml` has a `frames` export to `out/frames`.

## Scope and implementation guidance

- `src/sprite_tool/export/phaser.py` (proposed): the exporter.
- `src/sprite_tool/export/__init__.py` (exists): register `"phaser"`. Step 07 adds a line here too; expect a trivial merge if both run in parallel.
- `examples/demo/sprite-tool.toml` (exists): add `[[export]]` with `type = "phaser"`, `out = "out/phaser"`, `name = "atlas"`. Step 07 also appends a block.
- If an existing test asserts the demo's target count in the `built:` line, update it.

### Exclusions

No changes committed to either game repository; the in-engine check uses a scratch copy.

## Verification

`make test` (`uv run pytest`). Tests build a copy of `examples/demo/` under
`tmp_path`; no network or display. Proposed `tests/test_export_phaser.py`:

- `atlas.json` has exactly the fields above for each frame; `meta.size` equals the PNG's size; no extra `meta` fields.
- Frame keys cover every sprite and frame, including `warrior_red/idle_0` (A5).
- Cutting each `frame` rectangle from `atlas.png` gives an image equal to the rendered frame.
- `pivot` is `0.5, 1.0` for units and `0, 0` for the tile.
- **A14:** unit frames are 32x32 and the tile frame is 16x16 in the same sheet.
- `atlas.anims.json`: `warrior/idle` and `warrior_red/idle` exist with two frames of 400 ms and `repeat` `-1`; a fixture animation with `loop = false` gives `repeat` `0`; every `frame` value is a key in `atlas.json`.
- Calling the exporter twice gives identical bytes for all three files.
- A custom `name` and `padding = 0` are honoured.

### In-engine check (A6)

The sibling repository `~/play/yomi` uses Phaser 4, TypeScript and Vite, with
Node running in a Podman container. It loads `assets/sprites/<kind>.png` in
`src/scenes/BattleScene.ts`, draws with origin `(0.5, 1)` and sets
`pixelArt: true` in `src/main.ts`. Work in a scratch copy only.

1. Copy `examples/demo/` and point its `phaser` target at the scratch copy's `public/assets/sprites`. Build.
2. In a scratch scene, call `this.load.atlas("atlas", "assets/sprites/atlas.png", "assets/sprites/atlas.json")` and `this.load.animation("anims", "assets/sprites/atlas.anims.json")`, add a sprite with frame `warrior/idle_0`, and play `warrior/idle`.
3. Confirm: the art is correct and crisp; each frame shows for 400 ms; the sprite's origin is bottom-centre without calling `setOrigin` (that is, `pivot` is read); `warrior_red/idle` plays with swapped colours.
4. If timing or pivot is wrong, fix `export/phaser.py` and its tests, or document `setOrigin` as the fallback, and record what changed in the index (decision P10).

## Completion criteria

- [ ] `phaser` exporter registered and producing the three files as specified.
- [ ] Demo project builds with the `phaser` target.
- [ ] Structure tests pass, including the A5 and A14 cases.
- [ ] In-engine check done in a scratch copy of yomi; result for art, timing and pivot recorded in the index completion log.
- [ ] `make test` passes.
- [ ] Index status and completion log updated.
