"""Find and load `sprite-tool.toml` and `palette.toml`.

This is the only module that reads the config and palette files. Anything wrong
with the config raises `ConfigError`; palette problems are returned as
`Problem`s so they are reported like check failures.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from .model import Canvas, Color, ExportTarget, PreviewConfig, Problem, Project

CONFIG_NAME = "sprite-tool.toml"
EXPORT_TYPES = ("frames", "phaser", "godot")
ATLAS_TYPES = ("phaser", "godot")

DEFAULT_PALETTE = "palette.toml"
DEFAULT_PREVIEW_SCALE = 6
DEFAULT_PREVIEW_BACKGROUND = "#3a3a3a"
DEFAULT_ATLAS_NAME = "atlas"
DEFAULT_PADDING = 1

_HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
_TOML_POSITION_RE = re.compile(r"at line (\d+), column (\d+)")
_FORBIDDEN_KEY_CHARS = frozenset(".\"'\\")


class ConfigError(Exception):
    """A problem in `sprite-tool.toml`, or a missing palette file."""


def find_project(start: Path) -> Path | None:
    """Return the first directory at or above `start` holding `sprite-tool.toml`."""
    start = start.resolve()
    for directory in (start, *start.parents):
        if (directory / CONFIG_NAME).is_file():
            return directory
    return None


def load(root: Path) -> tuple[Project, list[Problem]]:
    """Load the project in `root`.

    Raises `ConfigError` for the config; returns palette problems. When the
    palette has problems the project still holds the valid colours.
    """
    root = root.resolve()
    config_path = root / CONFIG_NAME
    try:
        text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"no {CONFIG_NAME} in {root}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot read {config_path}: {exc}") from None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{CONFIG_NAME}: invalid TOML: {exc}") from None

    _reject_unknown(data, ("version", "palette", "canvas", "preview", "export"), "")
    if "version" not in data:
        raise ConfigError(f"{CONFIG_NAME}: version is required (version = 1)")
    if not _is_int(data["version"]) or data["version"] != 1:
        raise ConfigError(f"{CONFIG_NAME}: unsupported version {data['version']!r}; this tool reads version 1")

    palette_name = data.get("palette", DEFAULT_PALETTE)
    if not isinstance(palette_name, str) or not palette_name:
        raise ConfigError(f"{CONFIG_NAME}: palette must be a path string")
    palette_path = (root / palette_name).resolve()

    canvases = _load_canvases(data.get("canvas"))
    preview = _load_preview(data.get("preview", {}))
    exports = _load_exports(data.get("export", []), root)

    palette, problems = _load_palette(palette_path)
    if not problems:
        for canvas in canvases.values():
            for key in sorted(canvas.outline or ()):
                if key not in palette:
                    raise ConfigError(
                        f"{CONFIG_NAME}: canvas.{canvas.name}.outline key {key!r} is not in the palette"
                    )

    project = Project(
        root=root,
        palette_path=palette_path,
        palette=palette,
        canvases=canvases,
        preview=preview,
        exports=exports,
    )
    return project, problems


# --- config -----------------------------------------------------------------


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _reject_unknown(table: dict[str, Any], allowed: tuple[str, ...], where: str) -> None:
    for key in table:
        if key not in allowed:
            raise ConfigError(f"{CONFIG_NAME}: unknown key {where + key!r}")


def _int_at_least(table: dict[str, Any], key: str, minimum: int, default: int, where: str) -> int:
    value = table.get(key, default)
    if not _is_int(value) or value < minimum:
        raise ConfigError(f"{CONFIG_NAME}: {where}{key} must be an integer of {minimum} or more")
    return value


def _int_pair(table: dict[str, Any], key: str, where: str) -> tuple[int, int]:
    if key not in table:
        raise ConfigError(f"{CONFIG_NAME}: {where}{key} is required")
    value = table[key]
    if not isinstance(value, list) or len(value) != 2 or not all(_is_int(item) for item in value):
        raise ConfigError(f"{CONFIG_NAME}: {where}{key} must be a list of two integers")
    return value[0], value[1]


def _parse_hex(value: Any) -> tuple[int, int, int, int] | None:
    """Parse `#rrggbb` or `#rrggbbaa`; None when `value` is not one of those."""
    if not isinstance(value, str) or not _HEX_RE.fullmatch(value):
        return None
    digits = value[1:] if len(value) == 9 else value[1:] + "ff"
    return tuple(int(digits[i : i + 2], 16) for i in range(0, 8, 2))  # type: ignore[return-value]


def _load_canvases(raw: Any) -> dict[str, Canvas]:
    if raw is None:
        raise ConfigError(f"{CONFIG_NAME}: at least one [canvas.<name>] table is required")
    if not isinstance(raw, dict):
        raise ConfigError(f"{CONFIG_NAME}: canvas must be a table of [canvas.<name>] tables")
    if not raw:
        raise ConfigError(f"{CONFIG_NAME}: at least one [canvas.<name>] table is required")
    return {name: _load_canvas(name, table) for name, table in raw.items()}


def _load_canvas(name: str, table: Any) -> Canvas:
    where = f"canvas.{name}."
    if not isinstance(table, dict):
        raise ConfigError(f"{CONFIG_NAME}: canvas.{name} must be a table")
    _reject_unknown(table, ("size", "anchor", "display_scale", "outline", "grounded"), where)

    width, height = _int_pair(table, "size", where)
    if width < 1 or height < 1:
        raise ConfigError(f"{CONFIG_NAME}: {where}size must be two positive integers")
    anchor = _int_pair(table, "anchor", where)
    if not (0 <= anchor[0] <= width and 0 <= anchor[1] <= height):
        raise ConfigError(f"{CONFIG_NAME}: {where}anchor must be within 0..{width} and 0..{height}")

    outline = table.get("outline")
    if outline is not None:
        if not isinstance(outline, list) or not all(isinstance(key, str) for key in outline):
            raise ConfigError(f"{CONFIG_NAME}: {where}outline must be a list of palette keys")
        outline = frozenset(outline)

    grounded = table.get("grounded", False)
    if not isinstance(grounded, bool):
        raise ConfigError(f"{CONFIG_NAME}: {where}grounded must be true or false")

    return Canvas(
        name=name,
        width=width,
        height=height,
        anchor=anchor,
        display_scale=_int_at_least(table, "display_scale", 1, 1, where),
        outline=outline,
        grounded=grounded,
    )


def _load_preview(table: Any) -> PreviewConfig:
    if not isinstance(table, dict):
        raise ConfigError(f"{CONFIG_NAME}: preview must be a table")
    _reject_unknown(table, ("scale", "background"), "preview.")
    background = _parse_hex(table.get("background", DEFAULT_PREVIEW_BACKGROUND))
    if background is None:
        raise ConfigError(f"{CONFIG_NAME}: preview.background must be a hex colour (#rrggbb or #rrggbbaa)")
    return PreviewConfig(
        scale=_int_at_least(table, "scale", 1, DEFAULT_PREVIEW_SCALE, "preview."),
        background=background,
    )


def _load_exports(raw: Any, root: Path) -> tuple[ExportTarget, ...]:
    if not isinstance(raw, list) or not all(isinstance(table, dict) for table in raw):
        raise ConfigError(f"{CONFIG_NAME}: export must be an array of [[export]] tables")
    return tuple(_load_export(index, table, root) for index, table in enumerate(raw, start=1))


def _load_export(index: int, table: dict[str, Any], root: Path) -> ExportTarget:
    where = f"export {index}: "
    _reject_unknown(table, ("type", "out", "name", "res_path", "padding"), where)

    kind = table.get("type")
    if kind not in EXPORT_TYPES:
        expected = ", ".join(EXPORT_TYPES)
        if kind is None:
            raise ConfigError(f"{CONFIG_NAME}: {where}type is required (one of {expected})")
        raise ConfigError(f"{CONFIG_NAME}: {where}unknown type {kind!r} (expected one of {expected})")

    allowed = {"frames": (), "phaser": ("name", "padding"), "godot": ("name", "res_path", "padding")}[kind]
    for key in ("name", "res_path", "padding"):
        if key in table and key not in allowed:
            raise ConfigError(f"{CONFIG_NAME}: {where}{key} is not used by type {kind!r}")

    out = table.get("out")
    if not isinstance(out, str) or not out:
        raise ConfigError(f"{CONFIG_NAME}: {where}out is required and must be a path string")

    name = None
    padding = 0
    if kind in ATLAS_TYPES:
        name = table.get("name", DEFAULT_ATLAS_NAME)
        if not isinstance(name, str) or not name:
            raise ConfigError(f"{CONFIG_NAME}: {where}name must be a non-empty string")
        padding = _int_at_least(table, "padding", 0, DEFAULT_PADDING, where)

    res_path = None
    if kind == "godot":
        res_path = table.get("res_path")
        if not isinstance(res_path, str) or not res_path:
            raise ConfigError(f"{CONFIG_NAME}: {where}res_path is required for type 'godot'")

    return ExportTarget(type=kind, out=(root / out).resolve(), name=name, res_path=res_path, padding=padding)


# --- palette ----------------------------------------------------------------


def _load_palette(path: Path) -> tuple[dict[str, Color], list[Problem]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"palette file not found: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot read palette file {path}: {exc}") from None

    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        match = _TOML_POSITION_RE.search(str(exc))
        line, col = (int(match[1]), int(match[2])) if match else (0, 0)
        return {}, [Problem(path, line, col, "E001", f"invalid TOML: {exc}")]

    lines = _key_lines(text)
    palette: dict[str, Color] = {}
    problems: list[Problem] = []

    def report(key_path: tuple[str, ...], code: str, message: str) -> None:
        line = lines.get(key_path, 0)
        problems.append(Problem(path, line, 1 if line else 0, code, message))

    for key in data:
        if key != "colors":
            report((key,), "E001", f"unknown field {key!r}; a palette holds only a [colors] table")

    colors = data.get("colors")
    if colors is None:
        report((), "E001", "missing [colors] table")
    elif not isinstance(colors, dict):
        report(("colors",), "E001", "colors must be a table")
    else:
        for key, value in colors.items():
            where = ("colors", key)
            if not _is_palette_key(key):
                report(where, "E002", f"bad palette key {key!r}: {_KEY_RULE}")
                continue
            hex_value, name = value, None
            if isinstance(value, dict):
                unknown = [field for field in value if field not in ("hex", "name")]
                if unknown:
                    report(where, "E001", f"unknown field {unknown[0]!r} in palette colour {key!r}")
                    continue
                hex_value, name = value.get("hex"), value.get("name")
                if name is not None and not isinstance(name, str):
                    report(where, "E002", f"name of palette colour {key!r} must be a string")
                    continue
            rgba = _parse_hex(hex_value)
            if rgba is None:
                report(where, "E002", f"bad colour for palette key {key!r}: expected #rrggbb or #rrggbbaa")
                continue
            palette[key] = Color(key=key, rgba=rgba, name=name)

    problems.sort(key=lambda problem: problem.line)
    return palette, problems


_KEY_RULE = "a key is one printable ASCII character other than . \" ' \\ or whitespace"


def _is_palette_key(key: str) -> bool:
    return len(key) == 1 and "!" <= key <= "~" and key not in _FORBIDDEN_KEY_CHARS


def _key_lines(text: str) -> dict[tuple[str, ...], int]:
    """Map `(table..., key)` to the 1-based line that defines it.

    Works line by line, so it finds table headers and single-line `key = value`
    entries. Anything else (multi-line values, dotted keys) is left out and its
    problems are reported with line 0.
    """
    found: dict[tuple[str, ...], int] = {}
    table: tuple[str, ...] = ()
    for number, raw in enumerate(text.splitlines(), start=1):
        try:
            parsed = tomllib.loads(raw)
        except tomllib.TOMLDecodeError:
            continue
        if len(parsed) != 1:
            continue
        key, value = next(iter(parsed.items()))
        if raw.lstrip().startswith("["):
            table = (key,) if value == {} else ()
            found.setdefault((key,), number)
        else:
            found.setdefault((*table, key), number)
    return found
