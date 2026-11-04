"""The verified specs that depend on each ADR, in the tree and at a revision."""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeAlias

from pydantic import BaseModel, ConfigDict

from vultron.metadata.adr.lifecycle.epochs import status_behind_fault
from vultron.metadata.adr.lifecycle.git_reads import _git, _texts_at
from vultron.metadata.adr.loader import adr_number, load_adr_registry
from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.base import NonEmptyStr
from vultron.metadata.file_loading import (
    load_yaml,
    loads_yaml,
    validate,
)
from vultron.metadata.specs.schema import AdrIdStr, AdrStatus

#: An ADR number (``"0120"``) mapped to the spec IDs that cite it in ``adr:``
#: and whose ``verification:`` names a test file that exists.
DependentMap: TypeAlias = Mapping[str, list[str]]


_SPEC_FILE_RE = re.compile(r"specs/[^/]+\.yaml")


def epoch_drift(repo_root: Path, today: _dt.date) -> list[str]:
    """Describe every ADR whose ``status`` is behind today's epoch.

    Reads the whole ADR registry and spec corpus under ``repo_root``. The
    result is a report, never a gate (MS-14-007): see the module docstring.
    """
    tested = tree_dependents(repo_root)
    faults = (
        status_behind_fault(
            Path(rel).name, fm, today, tested=adr_number(Path(rel)) in tested
        )
        for rel, fm in load_adr_registry(repo_root).items()
    )
    return [f for f in faults if f]


class _SpecLike(Protocol):
    """The two spec fields :func:`verified_dependents` reads."""

    @property
    def adr(self) -> list[str] | None: ...

    @property
    def verification(self) -> str | None: ...


class _SpecFields(BaseModel):
    """The two fields of a requirement :func:`verified_dependents` reads."""

    model_config = ConfigDict(extra="ignore")

    id: NonEmptyStr
    adr: list[AdrIdStr] | None = None
    verification: str | None = None


class _SpecGroupFields(BaseModel):
    model_config = ConfigDict(extra="ignore")

    specs: list[_SpecFields] = []


class _SpecFileFields(BaseModel):
    """A spec file narrowed to what the dependency rule reads.

    Validated on these fields alone, so a change that edits the rest of the
    spec schema cannot stop the base side of that change from being read.
    """

    model_config = ConfigDict(extra="ignore")

    groups: list[_SpecGroupFields] = []


_TEST_PATH_RE = re.compile(r"`(test/[A-Za-z0-9_./-]+\.py)")


def verified_dependents(
    specs: Mapping[str, _SpecLike], exists: Callable[[str], bool]
) -> dict[str, list[str]]:
    """Map an ADR number to the spec IDs that depend on it and are tested.

    A spec depends on an ADR when it lists it in ``adr:``. It is tested when
    its ``verification:`` names a ``test/`` file for which ``exists`` (given
    the repository-relative path) is true.
    """
    out: dict[str, list[str]] = {}
    for spec_id, spec in specs.items():
        if not spec.adr or not spec.verification:
            continue
        if not any(
            exists(m) for m in _TEST_PATH_RE.findall(spec.verification)
        ):
            continue
        for adr_id in spec.adr:
            out.setdefault(adr_id.split("-", 1)[1], []).append(spec_id)
    return out


def _spec_fields(
    files: Iterable[tuple[Path, object]],
) -> dict[str, _SpecFields]:
    """Index each requirement's ``adr:`` and ``verification:`` by ID.

    ``files`` pairs the path each file is shown as with its parsed YAML.
    Raises ``MetadataLoadError`` naming the file that fails.
    """
    out: dict[str, _SpecFields] = {}
    for path, data in files:
        spec_file = validate(_SpecFileFields, data, path=path)
        for group in spec_file.groups:
            out.update((spec.id, spec) for spec in group.specs)
    return out


def _git_files(ref: str) -> set[str]:
    """Return every path tracked in commit ``ref`` (``"--"``: the index)."""
    if ref == "--":
        res = _git("ls-files", "--full-name")
    else:
        res = _git("ls-tree", "-r", "--full-tree", "--name-only", ref)
    return set(res.stdout.splitlines())


def tree_dependents(
    root: Path, *, tracked: set[str] | None = None
) -> dict[str, list[str]]:
    """Return the test-verified dependents in the working tree at ``root``.

    With ``tracked``, a spec or test file counts only if git tracks it, so a
    stray untracked file cannot change a local check's answer from CI's.
    """
    files = (
        (path, load_yaml(path, root=root))
        for path in sorted((root / "specs").glob("*.yaml"))
        if tracked is None or path.relative_to(root).as_posix() in tracked
    )
    return verified_dependents(
        _spec_fields(files),
        lambda rel: (
            (root / rel).is_file() and (tracked is None or rel in tracked)
        ),
    )


def dependents_at(ref: str) -> dict[str, list[str]]:
    """Return the test-verified dependents in the tree of commit ``ref``."""
    files = _git_files(ref)
    texts = _texts_at(
        ref, sorted(f for f in files if _SPEC_FILE_RE.fullmatch(f))
    )
    specs = (
        (Path(f"{ref}:{f}"), loads_yaml(text, Path(f"{ref}:{f}")))
        for f, text in texts.items()
    )
    return verified_dependents(_spec_fields(specs), files.__contains__)


@dataclass(frozen=True)
class Dependents:
    """The test-verified dependents on each side of a change."""

    base: DependentMap
    head: DependentMap


def unflipped_adrs(
    registry: Mapping[str, AdrFrontmatter], dependents: DependentMap
) -> dict[str, list[str]]:
    """Return each ``proposed`` ADR that has test-verified dependents.

    Maps the ADR's path to its dependents. An ADR held by a
    ``status_override`` is left out. Each one should already be
    ``accepted-provisional`` (MS-14-010).
    """
    out: dict[str, list[str]] = {}
    for rel_path, fm in registry.items():
        deps = dependents.get(adr_number(Path(rel_path)) or "")
        if deps and fm.status is AdrStatus.PROPOSED and not fm.status_override:
            out[rel_path] = deps
    return out
