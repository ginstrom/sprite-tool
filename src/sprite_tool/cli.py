"""Argument parsing, command dispatch and exit codes for the `sprite` command."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from . import project as project_module
from .model import Problem, Project
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
            raise ConfigError(
                f"no {CONFIG_NAME} found in {Path.cwd()} or any parent directory (use --project <dir>)"
            )
    return project_module.load(root)


def _not_implemented(args: argparse.Namespace) -> int:
    print("error: not implemented", file=sys.stderr)
    return EXIT_USAGE


# One handler per subcommand. Each takes the parsed arguments and returns the exit code.
HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "init": _not_implemented,
    "guide": _not_implemented,
    "new": _not_implemented,
    "check": _not_implemented,
    "preview": _not_implemented,
    "build": _not_implemented,
    "import": _not_implemented,
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
    preview.add_argument("ids", nargs="*", metavar="id", help="sprite ids to preview (default: contact sheet)")
    preview.add_argument("--scale", type=_positive_int, metavar="N", help="upscale factor")
    preview.add_argument("--grid", action="store_true", help="draw a pixel grid")
    preview.add_argument("--on", metavar="<tile-id>", help="draw the sprite on top of this tile sprite")
    preview.add_argument("--sheet", action="store_true", help="write the contact sheet")

    build = commands.add_parser("build", parents=[in_project], help="check everything, then write every export target")
    build.add_argument("--check", action="store_true", help="write nothing; exit 1 if generated files are missing or stale")
    build.add_argument("--adopt", action="store_true", help="take ownership of existing files in the export directories")

    import_ = commands.add_parser("import", parents=[in_project], help="write a sprite file from a PNG")
    import_.add_argument("png", help="PNG file to import")
    import_.add_argument("--canvas", required=True, metavar="<class>", help="canvas class of the sprite")
    import_.add_argument("--id", metavar="<id>", help="sprite id (default: the PNG file stem)")
    import_.add_argument("--scale", type=_positive_int, metavar="N", help="the PNG is enlarged N times; shrink it first")
    import_.add_argument("--snap", action="store_true", help="snap each pixel to the nearest palette colour")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return HANDLERS[args.command](args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
