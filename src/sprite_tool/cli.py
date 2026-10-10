"""Argument parsing, command dispatch and exit codes for the `sprite` command."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from importlib import resources
from pathlib import Path

from . import __version__, check, importer, manifest, render, spritefile
from . import preview as preview_module
from . import guide as guide_module
from . import project as project_module
from .export import EXPORTERS
from .model import Problem, Project, Sprite, format_problem
from .project import CONFIG_NAME, ConfigError

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_USAGE = 2


def load_project(args: argparse.Namespace) -> tuple[Project, list[Problem]]:
    """Resolve and load the project for a command.

    Uses `--project <dir>` when given, otherwise walks up from the current
    directory. Raises `ConfigError`, which `main` reports as exit 2.
    """
    if args.project is not None:
        root = Path(args.project)
    else:
        root = project_module.find_project(Path.cwd())
        if root is None:
            # Not inside a project: the usual case is the game repository's
            # root, with the project in a directory below it.
            below = project_module.find_below(Path.cwd())
            if len(below) > 1:
                found = ", ".join(_from_cwd(path, path) for path in below)
                raise ConfigError(f"more than one project below {Path.cwd()}: {found} (use --project <dir>)")
            if not below:
                raise ConfigError(
                    f"no {CONFIG_NAME} found in {Path.cwd()}, any parent directory or below it (use --project <dir>)"
                )
            root = below[0]
    return project_module.load(root)


def load_checked(
    args: argparse.Namespace, extra: Sequence[Path] = ()
) -> tuple[Project, list[Sprite], list[Problem]]:
    """Load the project and every sprite file in it, and run the checks.

    Returns the sprites, variants included, and every problem in output
    order. `extra` names sprite files to load as well as the ones found. When
    the palette has problems, no sprite is loaded and only those problems are
    returned.
    """
    project, problems = load_project(args)
    sprites: list[Sprite] = []
    if not problems:
        paths = sorted({*spritefile.discover(project.root), *extra})
        sprites, problems = spritefile.load_all(project, paths)
        problems += check.run(project, sprites)
    return project, sprites, sorted(problems, key=_output_order)


def report(problems: Iterable[Problem], root: Path) -> int:
    """Print one line per problem, then the summary line if any is an error.

    Returns the number of errors. With warnings only it prints no summary, so
    the caller can print its own success line.
    """
    problems = sorted(problems, key=_output_order)
    for problem in problems:
        print(format_problem(problem, root, Path.cwd()))
    errors = sum(1 for problem in problems if _is_error(problem))
    if errors:
        warnings = len(problems) - errors
        files = len({problem.path for problem in problems})
        print(f"{count(errors, 'error')}, {count(warnings, 'warning')} in {count(files, 'file')}")
    return errors


def count(number: int, noun: str) -> str:
    """`1 sprite`, `2 sprites`."""
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _output_order(problem: Problem) -> tuple[Path, int, int, str]:
    return problem.path, problem.line, problem.col, problem.code


def _is_error(problem: Problem) -> bool:
    return problem.code.startswith("E")


def _usage_error(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return EXIT_USAGE


# Template name to the path `init` writes it to. The last is not counted in the summary line.
_INIT_FILES = {
    "sprite-tool.toml": CONFIG_NAME,
    "palette.toml": "palette.toml",
    "warrior.sprite.toml": "units/warrior" + spritefile.SUFFIX,
    "gitignore": ".gitignore",
}


def _init(args: argparse.Namespace) -> int:
    root = Path(args.dir)
    targets = {template: root / name for template, name in _INIT_FILES.items()}
    ignore = targets.pop("gitignore")
    for path in targets.values():
        if path.exists():
            return _usage_error(f"{path.as_posix()} already exists")

    templates = resources.files(__package__) / "templates"
    try:
        for template, path in targets.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((templates / template).read_bytes())
        if not ignore.exists():
            ignore.write_bytes((templates / "gitignore").read_bytes())
    except OSError as exc:
        return _usage_error(f"cannot write project: {exc}")
    print(f"created {root.as_posix()} ({count(len(targets), 'file')})")
    # Nothing else tells an agent working in the game repository that the tool is there.
    print(f"for agents, add to AGENTS.md: {agent_note(root)}")
    return EXIT_OK


REPOSITORY = "https://github.com/ginstrom/sprite-tool"


def agent_note(root: Path) -> str:
    """The lines that tell an agent in the game repository how to get the tool and start drawing."""
    project = "" if root == Path(".") else f" --project {root.as_posix()}"
    tag = "" if __version__ == "unknown" else f"@v{__version__}"
    return (
        f"Sprites are made with sprite-tool (`uv tool install git+{REPOSITORY}{tag}`). "
        f"Run `sprite guide{project}` before drawing or changing one."
    )


def _guide(args: argparse.Namespace) -> int:
    project, problems = load_project(args)
    if report(problems, project.root):
        return EXIT_CHECK_FAILED
    print(guide_module.guide_text(project), end="")
    return EXIT_OK


_SPRITE_ID_RE = spritefile.ID_RE


def _new(args: argparse.Namespace) -> int:
    project, _ = load_project(args)
    if not _SPRITE_ID_RE.fullmatch(args.id):
        return _usage_error(f"sprite id {args.id!r} must match {_SPRITE_ID_RE.pattern}")
    canvas = project.canvases.get(args.canvas)
    if canvas is None:
        return _unknown_canvas(args.canvas, project)
    directory = (project.root / (args.dir or "")).resolve()
    if not directory.is_relative_to(project.root):
        return _usage_error(f"--dir {args.dir} is outside the project")
    path = directory / (args.id + spritefile.SUFFIX)
    if path.exists():
        return _usage_error(f"{_from_cwd(path, project.root)} already exists")
    user = _sprite_ids(project).get(args.id)
    if user is not None:
        used_by = user.relative_to(project.root).as_posix()
        return _usage_error(f"sprite id {args.id!r} is already used by {used_by}")

    grid = (spritefile.TRANSPARENT * canvas.width + "\n") * canvas.height
    text = f'canvas = "{canvas.name}"\n\n[frames]\nmain = """\n{grid}"""\n'
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        return _usage_error(f"cannot write sprite file: {exc}")
    print(_from_cwd(path, project.root))
    return EXIT_OK


def _sprite_ids(project: Project) -> dict[str, Path]:
    """Every sprite id in use, variants included, with the file that defines it."""
    paths = spritefile.discover(project.root)
    # File stems first, so that a file too broken to give a sprite still holds its id.
    ids = {path.name.removesuffix(spritefile.SUFFIX): path for path in paths}
    for sprite in spritefile.load_all(project, paths)[0]:
        ids.setdefault(sprite.id, sprite.source)
    return ids


def _from_cwd(path: Path, root: Path) -> str:
    """`path` as the user would type it: relative to the current directory when
    that is inside the project or holds the path, else absolute."""
    cwd = Path.cwd()
    if path.is_relative_to(cwd) or cwd.is_relative_to(root):
        return Path(os.path.relpath(path, cwd)).as_posix()
    return str(path)


def _unknown_canvas(name: str, project: Project) -> int:
    expected = ", ".join(project.canvases)
    return _usage_error(f"unknown canvas class {name!r} (expected one of {expected})")


def _check(args: argparse.Namespace) -> int:
    given = [Path(path) for path in args.paths]
    images = [path for path in given if path.suffix.lower() == ".png"]
    # Resolved, to match the paths that `spritefile.discover` returns.
    chosen = {path.resolve() for path in given if path.name.endswith(spritefile.SUFFIX)}
    for path in given:
        if path not in images and path.resolve() not in chosen:
            return _usage_error(f"{path}: not a {spritefile.SUFFIX} or .png file")
    if images and args.canvas is None:
        return _usage_error("--canvas <class> is required to check a PNG")

    project, sprites, problems = load_checked(args, sorted(chosen))
    palette_failed = any(problem.path == project.palette_path and _is_error(problem) for problem in problems)
    if images and not palette_failed:
        canvas = project.canvases.get(args.canvas)
        if canvas is None:
            return _unknown_canvas(args.canvas, project)
        for path in images:
            problems += check.check_png(project, path, canvas)
    if given and not palette_failed:
        shown = chosen | set(images)
        problems = [problem for problem in problems if problem.path in shown]
        sprites = [sprite for sprite in sprites if sprite.source in chosen]

    if report(problems, project.root):
        return EXIT_CHECK_FAILED
    frames = sum(len(sprite.frames) for sprite in sprites)
    summary = f"ok: {count(len(sprites), 'sprite')}, {count(frames, 'frame')}"
    if images:
        summary += f", {count(len(images), 'image')}"
    print(summary)
    return EXIT_OK


def _build(args: argparse.Namespace) -> int:
    project, sprites, problems = load_checked(args)
    for target in project.exports:
        if target.type not in EXPORTERS:
            raise ConfigError(f"export target type {target.type!r} is not available in this version")
    if any(_is_error(problem) for problem in problems):
        report(problems, project.root)
        return EXIT_CHECK_FAILED

    # A sprite that is still blank has its warning and is not exported; nor is
    # one that says `build = false`.
    sprites = [sprite for sprite in sprites if sprite.build and not check.is_blank(sprite)]
    # `--adopt` alone takes every file; with ids, only the files of those sprites.
    adopt_ids = None if args.check or not args.adopt else frozenset(args.adopt)
    if adopt_ids:
        built = sorted(sprite.id for sprite in sprites)
        for name in args.adopt:
            if name not in built:
                return _usage_error(f"unknown sprite id {name!r} (sprites: {', '.join(built) or 'none'})")
    # Nothing is written until every directory has passed its checks.
    images = render.render_all(sprites, project.palette)
    plans = manifest.plan(
        [(target, EXPORTERS[target.type](sprites, images, target)) for target in project.exports]
    )
    if args.check:
        problems += manifest.compare(plans)
    elif args.adopt != []:
        manifest.check_ownership(plans, adopt_ids)

    if report(problems, project.root):
        return EXIT_CHECK_FAILED
    if not args.check:
        # Read before the build makes them owned. Any that passed the check is adopted.
        adopted = [item.directory / name for item in plans for name in item.unowned]
        manifest.apply(plans)
        for path in adopted:
            print(f"adopted {_from_cwd(path, project.root)}")
    frames = sum(len(sprite.frames) for sprite in sprites)
    totals = f"{count(len(sprites), 'sprite')}, {count(frames, 'frame')}, {count(len(project.exports), 'target')}"
    print(f"{'up to date' if args.check else 'built'}: {totals}")
    return EXIT_OK


PREVIEW_DIR = ".preview"
# Problems that leave a frame drawable. A preview is still written with these,
# because seeing the sprite is how they get fixed.
_STYLE_CODES = frozenset({"E106", "E201", "E202"})
_MAX_PREVIEW_STEM = 100


def _preview(args: argparse.Namespace) -> int:
    project, sprites, problems = load_checked(args)
    if any(problem.path == project.palette_path and _is_error(problem) for problem in problems):
        report(problems, project.root)
        return EXIT_CHECK_FAILED

    by_id = {sprite.id: sprite for sprite in sprites}
    # A file too broken to give a sprite is still a known id: its problems are reported.
    files = {path.name.removesuffix(spritefile.SUFFIX): path for path in spritefile.discover(project.root)}
    ids = list(dict.fromkeys(args.ids))
    involved = set()
    for name in [*ids, *([args.on] if args.on else [])]:
        if name in by_id:
            involved.add(by_id[name].source)
        elif name in files:
            involved.add(files[name])
        else:
            known = ", ".join(sorted(by_id)) or "none"
            return _usage_error(f"unknown sprite id {name!r} (sprites: {known})")
    sheet = args.sheet or not ids
    if not sheet:
        problems = [problem for problem in problems if problem.path in involved]
    errors = [problem for problem in problems if _is_error(problem)]
    if errors:
        # Warnings are printed only alongside an error, so a clean run prints paths only.
        report(problems, project.root)
        if any(problem.code not in _STYLE_CODES for problem in errors):
            return EXIT_CHECK_FAILED

    images = {}
    if ids:
        if args.on:
            kind = f"on-{args.on}"
            scale = args.scale or preview_module.ON_TILE_SCALE
            parts = [preview_module.on_tile(project, by_id[name], by_id[args.on], scale) for name in ids]
        else:
            kind = "grid" if args.grid else "plain"
            scale = args.scale or project.preview.scale
            parts = [
                preview_module.sprite_preview(
                    project, by_id[name], [other for other in sprites if other.variant_of == name], scale, args.grid
                )
                for name in ids
            ]
        stem = "+".join(ids)
        if len(stem) > _MAX_PREVIEW_STEM:
            stem = f"{ids[0]}+{len(ids) - 1}more"
        images[f"{stem}.{kind}"] = preview_module.stack(project, parts)
    if sheet:
        images["sheet"] = preview_module.contact_sheet(project, sprites)

    directory = project.root / PREVIEW_DIR
    try:
        directory.mkdir(exist_ok=True)
        for name, image in images.items():
            image.save(directory / f"{name}.png")
    except OSError as exc:
        return _usage_error(f"cannot write preview: {exc}")
    for name in images:
        print(_from_cwd(directory / f"{name}.png", project.root))
    return EXIT_OK


def _import(args: argparse.Namespace) -> int:
    project, problems = load_project(args)
    png = Path(args.png)
    sprite_id = png.stem if args.id is None else args.id
    if not _SPRITE_ID_RE.fullmatch(sprite_id):
        hint = " (use --id <id>)" if args.id is None else ""
        return _usage_error(f"sprite id {sprite_id!r} must match {_SPRITE_ID_RE.pattern}{hint}")
    canvas = project.canvases.get(args.canvas)
    if canvas is None:
        return _unknown_canvas(args.canvas, project)
    path = project.root / (sprite_id + spritefile.SUFFIX)
    if path.exists():
        return _usage_error(f"{_from_cwd(path, project.root)} already exists")
    user = _sprite_ids(project).get(sprite_id)
    if user is not None:
        used_by = user.relative_to(project.root).as_posix()
        return _usage_error(f"sprite id {sprite_id!r} is already used by {used_by}")

    if report(problems, project.root):
        return EXIT_CHECK_FAILED
    result = importer.import_png(png, canvas, project.palette, scale=args.scale or 1, snap=args.snap)
    if report(result.problems, project.root):
        return EXIT_CHECK_FAILED
    try:
        path.write_text(importer.sprite_text(canvas.name, result.rows), encoding="utf-8")
    except OSError as exc:
        return _usage_error(f"cannot write sprite file: {exc}")
    for line in result.snapped:
        print(line)
    print(_from_cwd(path, project.root))
    return EXIT_OK


# One handler per subcommand. Each takes the parsed arguments and returns the exit code.
HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "init": _init,
    "guide": _guide,
    "new": _new,
    "check": _check,
    "preview": _preview,
    "build": _build,
    "import": _import,
}


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite",
        description="Turn text sprite definitions into pixel art for Godot 4 and Phaser.",
    )
    parser.add_argument("--version", action="version", version=f"sprite {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    in_project = argparse.ArgumentParser(add_help=False)
    in_project.add_argument(
        "--project",
        metavar="<dir>",
        help=f"project directory (default: nearest {CONFIG_NAME} at or above the current directory)",
    )

    init = commands.add_parser("init", help="write a starter project")
    init.add_argument("dir", nargs="?", default=".", help="directory to create the project in (default: .)")

    commands.add_parser("guide", parents=[in_project], help="print the format reference, palette and canvas classes")

    new = commands.add_parser("new", parents=[in_project], help="write a blank sprite file")
    new.add_argument("id", help="sprite id (the file stem)")
    new.add_argument("--canvas", required=True, metavar="<class>", help="canvas class of the sprite")
    new.add_argument("--dir", metavar="<subdir>", help="subdirectory of the project to write into")

    check = commands.add_parser("check", parents=[in_project], help="check sprite files and PNGs")
    check.add_argument("paths", nargs="*", help="sprite files or PNGs to check (default: every sprite file)")
    check.add_argument("--canvas", metavar="<class>", help="canvas class for PNG paths")

    preview = commands.add_parser("preview", parents=[in_project], help="write preview PNGs")
    preview.add_argument(
        "ids",
        nargs="*",
        metavar="id",
        help="sprite ids to draw, one under another in a single image (default: the contact sheet)",
    )
    preview.add_argument("--scale", type=_positive_int, metavar="N", help="upscale factor")
    preview.add_argument("--grid", action="store_true", help="draw a pixel grid; writes <ids>.grid.png, not <ids>.plain.png")
    preview.add_argument("--on", metavar="<tile-id>", help="draw each sprite standing on this tile; writes <ids>.on-<tile-id>.png")
    preview.add_argument("--sheet", action="store_true", help="also write the contact sheet, sheet.png")

    build = commands.add_parser("build", parents=[in_project], help="check everything, then write every export target")
    build.add_argument("--check", action="store_true", help="write nothing; exit 1 if generated files are missing or stale")
    build.add_argument(
        "--adopt",
        nargs="*",
        metavar="id",
        help="overwrite existing files the tool did not write: all of them, or only those of the given sprite ids",
    )

    import_ = commands.add_parser("import", parents=[in_project], help="write a sprite file from a PNG")
    import_.add_argument("png", help="PNG file to import")
    import_.add_argument("--canvas", required=True, metavar="<class>", help="canvas class of the sprite")
    import_.add_argument("--id", metavar="<id>", help="sprite id (default: the PNG file stem)")
    import_.add_argument("--scale", type=_positive_int, metavar="N", help="enlarge the PNG N times before importing (default: 1)")
    import_.add_argument("--snap", action="store_true", help="snap each pixel to the nearest palette colour")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return HANDLERS[args.command](args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
