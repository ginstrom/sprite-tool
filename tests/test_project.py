import pytest

from conftest import MINIMAL_CONFIG, VALID_CONFIG, VALID_PALETTE, write_project
from sprite_tool.model import Canvas, Color, ExportTarget, PreviewConfig
from sprite_tool.project import ConfigError, find_project, load

# --- find_project ---------------------------------------------------------


def test_find_project_walks_up_two_directories(project_dir):
    nested = project_dir / "units" / "heroes"
    nested.mkdir(parents=True)
    assert find_project(nested) == project_dir


def test_find_project_in_the_start_directory(project_dir):
    assert find_project(project_dir) == project_dir


def test_find_project_returns_none_without_a_config(tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_project(nested) is None


# --- valid config ---------------------------------------------------------


def test_load_valid_project(project_dir):
    project, problems = load(project_dir)

    assert problems == []
    assert project.root == project_dir
    assert project.palette_path == project_dir / "palette.toml"
    assert project.canvases == {
        "unit": Canvas(
            name="unit",
            width=32,
            height=32,
            anchor=(16, 32),
            display_scale=2,
            outline=frozenset({"k"}),
            grounded=True,
            outline_key="k",
        ),
        "tile": Canvas(
            name="tile",
            width=16,
            height=16,
            anchor=(0, 0),
            display_scale=4,
            outline=None,
            grounded=False,
        ),
    }
    assert list(project.canvases) == ["unit", "tile"]
    assert project.preview == PreviewConfig(scale=6, background=(0x3A, 0x3A, 0x3A, 255))
    game = project_dir.parent
    assert project.exports == (
        ExportTarget(type="frames", out=game / "assets" / "frames", name=None, res_path=None, padding=0),
        ExportTarget(
            type="phaser", out=game / "public" / "assets" / "sprites", name="atlas", res_path=None, padding=1
        ),
        ExportTarget(
            type="godot",
            out=project_dir / "out" / "godot",
            name="sheet",
            res_path="res://assets/sprites",
            padding=2,
        ),
    )
    assert all(target.out.is_absolute() for target in project.exports)


def test_load_applies_defaults(tmp_path):
    root = write_project(tmp_path, MINIMAL_CONFIG)
    project, problems = load(root)

    assert problems == []
    assert project.palette_path == root / "palette.toml"
    assert project.canvases["unit"].display_scale == 1
    assert project.canvases["unit"].outline is None
    assert project.canvases["unit"].grounded is False
    assert project.preview == PreviewConfig(scale=6, background=(0x3A, 0x3A, 0x3A, 255))
    assert project.exports == ()


OUTLINE_KEY_CASES = {
    "one key": ('outline = ["k"]', "k"),
    "first of several, not the first in sorted order": ('outline = ["o", "k"]', "o"),
    "empty list": ("outline = []", None),
    "no rule": ("", None),
}


@pytest.mark.parametrize("line, expected", OUTLINE_KEY_CASES.values(), ids=OUTLINE_KEY_CASES.keys())
def test_outline_key_is_the_first_key_of_the_outline_list(tmp_path, line, expected):
    palette = '[colors]\nk = "#000000"\no = "#111111"\n'
    project, problems = load(write_project(tmp_path, MINIMAL_CONFIG + line + "\n", palette))

    assert problems == []
    assert project.canvases["unit"].outline_key == expected


def test_atlas_name_defaults_to_atlas(tmp_path):
    config = MINIMAL_CONFIG + '\n[[export]]\ntype = "phaser"\nout = "out"\n'
    project, _ = load(write_project(tmp_path, config))
    assert project.exports[0].name == "atlas"


def test_load_resolves_a_relative_root(project_dir, monkeypatch):
    monkeypatch.chdir(project_dir.parent)
    project, _ = load(project_dir.relative_to(project_dir.parent))
    assert project.root == project_dir
    assert all(target.out.is_absolute() for target in project.exports)


def test_palette_path_is_relative_to_the_config(tmp_path):
    config = MINIMAL_CONFIG.replace("version = 1", 'version = 1\npalette = "art/colours.toml"')
    root = write_project(tmp_path, config, palette=None)
    (root / "art").mkdir()
    (root / "art" / "colours.toml").write_text(VALID_PALETTE, encoding="utf-8")

    project, problems = load(root)

    assert problems == []
    assert project.palette_path == root / "art" / "colours.toml"
    assert list(project.palette) == ["k", "w", "g"]


# --- config errors --------------------------------------------------------


def replaced(old: str, new: str) -> str:
    assert old in VALID_CONFIG
    return VALID_CONFIG.replace(old, new, 1)


BAD_CONFIGS = {
    "invalid toml": ("version = ", "invalid TOML"),
    "version missing": (replaced("version = 1\n", ""), "version"),
    "version 2": (replaced("version = 1", "version = 2"), "version"),
    "version as string": (replaced("version = 1", 'version = "1"'), "version"),
    "version as bool": (replaced("version = 1", "version = true"), "version"),
    "palette not a string": (replaced('palette = "palette.toml"', "palette = 3"), "palette"),
    "unknown top-level key": (replaced("version = 1", "version = 1\npalete = 'p.toml'"), "palete"),
    "no canvas": ("version = 1\n", "canvas"),
    "canvas not a table": ("version = 1\ncanvas = 3\n", "canvas"),
    "canvas class not a table": ("version = 1\n[canvas]\nunit = 3\n", "canvas.unit"),
    "size missing": (replaced("size = [32, 32]\n", ""), "size"),
    "size with one value": (replaced("size = [32, 32]", "size = [32]"), "size"),
    "size zero": (replaced("size = [32, 32]", "size = [0, 32]"), "size"),
    "size negative": (replaced("size = [32, 32]", "size = [32, -1]"), "size"),
    "size not integers": (replaced("size = [32, 32]", "size = [32.0, 32]"), "size"),
    "size not a list": (replaced("size = [32, 32]", "size = 32"), "size"),
    "anchor missing": (replaced("anchor = [16, 32]\n", ""), "anchor"),
    "anchor x past width": (replaced("anchor = [16, 32]", "anchor = [33, 32]"), "anchor"),
    "anchor y past height": (replaced("anchor = [16, 32]", "anchor = [16, 33]"), "anchor"),
    "anchor negative": (replaced("anchor = [16, 32]", "anchor = [-1, 32]"), "anchor"),
    "anchor not integers": (replaced("anchor = [16, 32]", 'anchor = ["a", 32]'), "anchor"),
    "display_scale zero": (replaced("display_scale = 2", "display_scale = 0"), "display_scale"),
    "display_scale not an integer": (replaced("display_scale = 2", "display_scale = 1.5"), "display_scale"),
    "outline not a list": (replaced('outline = ["k"]', 'outline = "k"'), "outline"),
    "outline entry not a string": (replaced('outline = ["k"]', "outline = [1]"), "outline"),
    "outline key not in palette": (replaced('outline = ["k"]', 'outline = ["k", "z"]'), "'z'"),
    "grounded not a boolean": (replaced("grounded = true", "grounded = 1"), "grounded"),
    "unknown canvas key": (replaced("grounded = true", "grounded = true\nanchro = [0, 0]"), "anchro"),
    "preview not a table": (replaced("[preview]\nscale = 6\nbackground = \"#3a3a3a\"", "preview = 6"), "preview"),
    "preview scale zero": (replaced("scale = 6", "scale = 0"), "scale"),
    "preview scale not an integer": (replaced("scale = 6", 'scale = "6"'), "scale"),
    "preview background bad hex": (replaced('"#3a3a3a"', '"3a3a3a"'), "background"),
    "preview background not a string": (replaced('"#3a3a3a"', "5"), "background"),
    "unknown preview key": (replaced("scale = 6", "scale = 6\ngrid = true"), "grid"),
    "export not an array of tables": ("version = 1\nexport = 3\n" + MINIMAL_CONFIG[len("version = 1\n") :], "export"),
    "export type missing": (replaced('type = "frames"\n', ""), "type"),
    "export type unknown": (replaced('type = "frames"', 'type = "unity"'), "unity"),
    "export out missing": (replaced('out = "../assets/frames"\n', ""), "out"),
    "export out not a string": (replaced('out = "../assets/frames"', "out = 1"), "out"),
    "export out empty": (replaced('out = "../assets/frames"', 'out = ""'), "out"),
    "export name not a string": (replaced('name = "atlas"', "name = 1"), "name"),
    "export name empty": (replaced('name = "atlas"', 'name = ""'), "name"),
    "name on frames": (replaced('out = "../assets/frames"', 'out = "../assets/frames"\nname = "x"'), "name"),
    "padding on frames": (replaced('out = "../assets/frames"', 'out = "../assets/frames"\npadding = 1'), "padding"),
    "res_path missing for godot": (replaced('res_path = "res://assets/sprites"\n', ""), "res_path"),
    "res_path not a string": (replaced('res_path = "res://assets/sprites"', "res_path = 1"), "res_path"),
    "res_path on phaser": (replaced('name = "atlas"', 'name = "atlas"\nres_path = "res://x"'), "res_path"),
    "padding negative": (replaced("padding = 2", "padding = -1"), "padding"),
    "padding not an integer": (replaced("padding = 2", "padding = true"), "padding"),
    "unknown export key": (replaced("padding = 2", "padding = 2\ntrim = true"), "trim"),
}


@pytest.mark.parametrize("config, mentions", BAD_CONFIGS.values(), ids=BAD_CONFIGS.keys())
def test_bad_config_raises_config_error(tmp_path, config, mentions):
    root = write_project(tmp_path, config)
    with pytest.raises(ConfigError) as excinfo:
        load(root)
    assert mentions in str(excinfo.value)


def test_missing_config_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="sprite-tool.toml"):
        load(tmp_path)


def test_missing_palette_raises_config_error(tmp_path):
    root = write_project(tmp_path, palette=None)
    with pytest.raises(ConfigError, match="palette.toml"):
        load(root)


def test_colliding_export_directories_are_not_checked_here(tmp_path):
    config = MINIMAL_CONFIG + '\n[[export]]\ntype = "frames"\nout = "out"\n' * 2
    project, _ = load(write_project(tmp_path, config))
    assert len(project.exports) == 2


# --- palette --------------------------------------------------------------


def load_palette(tmp_path, palette: str):
    return load(write_project(tmp_path, MINIMAL_CONFIG, palette))


def test_palette_values(project_dir):
    project, problems = load(project_dir)

    assert problems == []
    assert project.palette == {
        "k": Color(key="k", rgba=(0x1A, 0x1C, 0x2C, 255), name="outline"),
        "w": Color(key="w", rgba=(0xF4, 0xF4, 0xF4, 255), name=None),
        "g": Color(key="g", rgba=(0, 255, 0, 0x80), name=None),
    }
    assert list(project.palette) == ["k", "w", "g"]


def test_palette_table_without_name_and_uppercase_hex(tmp_path):
    project, problems = load_palette(tmp_path, '[colors]\nK = { hex = "#AABBCC" }\n')
    assert problems == []
    assert project.palette["K"] == Color(key="K", rgba=(0xAA, 0xBB, 0xCC, 255), name=None)


@pytest.mark.parametrize(
    "key_text",
    ["ab", '"."', '" "', "'\"'", '"\'"', "'\\'", '"é"', '""', '"\\t"'],
    ids=["two chars", "dot", "space", "double quote", "single quote", "backslash", "non-ascii", "empty", "tab"],
)
def test_palette_bad_key_is_e002(tmp_path, key_text):
    palette = f'[colors]\nk = "#000000"\n{key_text} = "#ffffff"\n'
    project, problems = load_palette(tmp_path, palette)

    assert [(p.code, p.line, p.path) for p in problems] == [("E002", 3, project.palette_path)]
    assert list(project.palette) == ["k"]


@pytest.mark.parametrize(
    "value",
    ['"1a1c2c"', '"#1a1c2"', '"#1a1c2c0"', '"#gggggg"', '"#1a1c2c00ff"', "5", "true", '["#000000"]'],
)
def test_palette_bad_hex_is_e002(tmp_path, value):
    palette = f'[colors]\nk = "#000000"\n\nw = {value}\n'
    project, problems = load_palette(tmp_path, palette)

    assert [(p.code, p.line) for p in problems] == [("E002", 4)]
    assert "'w'" in problems[0].message
    assert list(project.palette) == ["k"]


@pytest.mark.parametrize(
    "value",
    ['{ hex = "#12345" }', "{ hex = 5 }", '{ name = "skin" }', '{ hex = "#123456", name = 3 }'],
    ids=["bad hex", "hex not a string", "hex missing", "name not a string"],
)
def test_palette_bad_table_value_is_e002(tmp_path, value):
    project, problems = load_palette(tmp_path, f"[colors]\ns = {value}\n")
    assert [(p.code, p.line) for p in problems] == [("E002", 2)]
    assert project.palette == {}


def test_palette_unknown_field_in_colour_table_is_e001(tmp_path):
    palette = '[colors]\nk = "#000000"\ns = { hex = "#e8b796", nmae = "skin" }\n'
    project, problems = load_palette(tmp_path, palette)

    assert [(p.code, p.line) for p in problems] == [("E001", 3)]
    assert "nmae" in problems[0].message
    assert list(project.palette) == ["k"]


def test_palette_unknown_top_level_field_is_e001(tmp_path):
    palette = 'title = "mine"\n\n[colors]\nk = "#000000"\n\n[extra]\na = 1\n'
    project, problems = load_palette(tmp_path, palette)

    assert [(p.code, p.line) for p in problems] == [("E001", 1), ("E001", 6)]
    assert list(project.palette) == ["k"]


def test_palette_invalid_toml_is_e001_with_position(tmp_path):
    project, problems = load_palette(tmp_path, '[colors]\nk = "#000000"\nw = \n')

    assert [(p.code, p.line) for p in problems] == [("E001", 3)]
    assert problems[0].col >= 1
    assert project.palette == {}


def test_palette_without_colors_table_is_e001(tmp_path):
    _, problems = load_palette(tmp_path, "")
    assert [(p.code, p.line) for p in problems] == [("E001", 0)]


def test_palette_colors_not_a_table_is_e001(tmp_path):
    _, problems = load_palette(tmp_path, "colors = 3\n")
    assert [(p.code, p.line) for p in problems] == [("E001", 1)]


def test_palette_problems_are_reported_together_in_file_order(tmp_path):
    palette = '[colors]\nab = "#000000"\nk = "#111111"\nw = "nope"\n'
    project, problems = load_palette(tmp_path, palette)

    assert [(p.code, p.line) for p in problems] == [("E002", 2), ("E002", 4)]
    assert list(project.palette) == ["k"]


def test_duplicate_colours_are_not_reported_here(tmp_path):
    project, problems = load_palette(tmp_path, '[colors]\na = "#000000"\nb = "#000000"\n')
    assert problems == []
    assert list(project.palette) == ["a", "b"]


def test_outline_keys_are_not_checked_when_the_palette_has_problems(tmp_path):
    # The palette problem is the thing to report (exit 1), not a config error (exit 2).
    root = write_project(tmp_path, VALID_CONFIG, '[colors]\nk = "nope"\n')
    project, problems = load(root)
    assert [p.code for p in problems] == ["E002"]
    assert project.canvases["unit"].outline == frozenset({"k"})
