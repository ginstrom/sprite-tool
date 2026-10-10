"""The manifest of generated files in each output directory, and the only
code that creates, overwrites or deletes export files."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from sprite_tool.model import ExportTarget, Problem
from sprite_tool.project import ConfigError

MANIFEST_NAME = ".sprite-tool-manifest.json"
VERSION = 1


def json_bytes(obj: Any) -> bytes:
    """Deterministic JSON for generated files: sorted keys, two-space indent,
    `\\n` line endings, trailing newline."""
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode("utf-8")


def target_key(target: ExportTarget) -> str:
    """The name of a target in the manifest and in messages: `frames`, `phaser:atlas`."""
    return target.type if target.name is None else f"{target.type}:{target.name}"


@dataclass(frozen=True)
class Plan:
    """What one output directory should hold after a build.

    files: every generated file, the manifest included, by path relative to
    `directory`.
    owned: the files the manifest on disk lists.
    """

    directory: Path
    files: Mapping[str, bytes]
    owned: frozenset[str]

    @property
    def stale(self) -> list[str]:
        """Owned files that are no longer generated."""
        return sorted(self.owned - self.files.keys())

    @property
    def unowned(self) -> list[str]:
        """Generated files that exist on disk and are not in the manifest."""
        return [
            name
            for name in sorted(self.files)
            if name != MANIFEST_NAME and name not in self.owned and (self.directory / name).exists()
        ]


def plan(outputs: Sequence[tuple[ExportTarget, Mapping[str, bytes]]]) -> list[Plan]:
    """Group exporter output by directory and read each directory's manifest.

    Reads the disk but changes nothing. Raises `ConfigError` when two targets
    produce the same file in one directory, or a manifest cannot be trusted.
    """
    by_directory: dict[Path, dict[str, dict[str, bytes]]] = {}
    for target, files in outputs:
        targets = by_directory.setdefault(target.out, {})
        key = target_key(target)
        for other, taken in targets.items():
            shared = sorted(files.keys() & taken.keys())
            if shared:
                raise ConfigError(
                    f"export targets {other!r} and {key!r} both write {shared[0]} in {target.out}"
                )
        targets.setdefault(key, {}).update(files)

    plans = []
    for directory in sorted(by_directory):
        targets = by_directory[directory]
        files = {name: content for produced in targets.values() for name, content in produced.items()}
        files[MANIFEST_NAME] = json_bytes(
            {"targets": {key: sorted(produced) for key, produced in targets.items()}, "version": VERSION}
        )
        plans.append(Plan(directory=directory, files=files, owned=_read_owned(directory)))
    return plans


def belongs_to(name: str, ids: frozenset[str]) -> bool:
    """Whether a generated file is one of these sprites' own: `warrior.png`,
    `warrior__idle_0.png` and `warrior.tres` for `warrior`. A variant's files
    (`warrior_red.png`) belong to the variant's id, and a shared file
    (`atlas.png`) to no sprite."""
    file_name = PurePosixPath(name).name
    return file_name.split(".", 1)[0] in ids or file_name.split("__", 1)[0] in ids


def check_ownership(plans: Sequence[Plan], adopt_ids: frozenset[str] | None = None) -> None:
    """Raise `ConfigError` if a build would overwrite a file the tool did not
    write, other than the files of the sprites in `adopt_ids`."""
    ids = adopt_ids or frozenset()
    for item in plans:
        kept = [name for name in item.unowned if not belongs_to(name, ids)]
        if kept:
            found = f" and {len(kept) - 1} more already exist and were" if len(kept) > 1 else " already exists and was"
            raise ConfigError(
                f"{item.directory / kept[0]}{found} not written by sprite-tool"
                " (use --adopt <id>... for those sprites, or --adopt for all)"
            )


def apply(plans: Sequence[Plan]) -> None:
    """Delete what is no longer generated and write what changed."""
    for item in plans:
        for name in item.stale:
            (item.directory / name).unlink(missing_ok=True)
        # The manifest goes first: if a later write fails, the files that were
        # written are already owned and the next build can finish the job.
        for name in [MANIFEST_NAME, *sorted(item.files.keys() - {MANIFEST_NAME})]:
            path = item.directory / name
            if not _holds(path, item.files[name]):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(item.files[name])


def compare(plans: Sequence[Plan]) -> list[Problem]:
    """One E401 for each file a build would write or delete. Changes nothing."""
    problems = []
    for item in plans:
        states = {name: "no longer generated" for name in item.stale if (item.directory / name).exists()}
        for name, content in item.files.items():
            path = item.directory / name
            if not path.is_file():
                states[name] = "missing"
            elif not _holds(path, content):
                states[name] = "stale"
        problems += [
            Problem(path=item.directory / name, line=0, col=0, code="E401", message=state)
            for name, state in sorted(states.items())
        ]
    return problems


def _holds(path: Path, content: bytes) -> bool:
    return path.is_file() and path.read_bytes() == content


def _read_owned(directory: Path) -> frozenset[str]:
    """The files listed in the directory's manifest; none if it has no manifest."""
    path = directory / MANIFEST_NAME
    if not path.exists():
        return frozenset()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"{path}: cannot read manifest ({exc})") from None
    if not isinstance(data, dict) or data.get("version") != VERSION:
        raise ConfigError(f"{path}: not a version {VERSION} manifest")
    targets = data.get("targets")
    if not isinstance(targets, dict) or not all(isinstance(names, list) for names in targets.values()):
        raise ConfigError(f"{path}: targets must map each target to a list of files")
    owned = {name for names in targets.values() for name in names}
    for name in owned:
        # Listed files get deleted, so a path that could leave the directory is refused.
        if not _is_safe(name):
            raise ConfigError(f"{path}: {name!r} is not a file inside this directory")
    return frozenset(owned)


def _is_safe(name: object) -> bool:
    if not isinstance(name, str) or not name or name == MANIFEST_NAME:
        return False
    parts = PurePosixPath(name).parts
    return not PurePosixPath(name).is_absolute() and ".." not in parts and "\\" not in name
