"""ADR lifecycle epochs and the checks built on them (ADR-0120).

Requirements: specs/meta-specifications.yaml MS-14-007 through MS-14-010 and
MS-14-012.

An ADR's ``status`` tracks how settled the decision is. Two timers measured
from the last *material* edit (``updated``) and one event decide its epoch:

- epoch 1, ``proposed``: until day 14, or until the first test-verified
  dependent, whichever comes first
- epoch 2, ``accepted-provisional``: from then until day 28
- epoch 3, ``accepted``: day 28 on

A test-verified dependent is a spec requirement that cites the ADR in ``adr:``
and whose ``verification:`` names a ``test/`` file that exists, counted in the
tree being checked (the pull request's head, or ``main`` for the scheduled
report). A material edit restarts the timers but not the dependency. ``updated``
is a date, so the boundaries are counted in whole days.

The computed epoch is a floor: a status ahead of it stands, and a status only
moves forward (MS-14-012). A human may hold a status off its epoch with
``status_override: <reason>``. Retired and rejected ADRs have no epoch.

The clock alone never fails a merge-blocking check: nothing in the repository
changes when an ADR crosses an epoch boundary, so a check that reads today's
date would turn ``main`` red with no commit to blame. Two checks live here:

- :func:`check_change` compares the working tree with a base commit. It
  refuses the edits the epochs forbid (:func:`edit_faults`): a material edit
  (``updated`` moved, or a new ADR) that leaves ``status`` off its epoch on
  that date, a promotion ahead of the epoch without a new
  ``status_override:``, and a changed decision section of an epoch-3 ADR
  without an Amendment. It also refuses a change that gives a ``proposed`` ADR
  its first test-verified dependent without flipping it to
  ``accepted-provisional`` (:func:`first_dependent_faults`), whether or not
  the change touches the ADR. It runs as the ``adr-lifecycle-check``
  pre-commit hook and a pull-request job.
- :func:`epoch_drift` lists every ADR whose ``status`` is behind today's
  epoch. It only reports, through the scheduled ``adr-status-drift`` workflow.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Protocol, TypeAlias

import frontmatter
from pydantic import BaseModel, ConfigDict, ValidationError

from vultron.metadata.adr.loader import adr_number, load_adr_registry
from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.base import NonEmptyStr
from vultron.metadata.file_loading import (
    load_yaml,
    loads_frontmatter,
    loads_yaml,
    validate,
)
from vultron.metadata.specs.schema import AdrIdStr, AdrStatus

#: Whole days of age at which epoch 2 and epoch 3 begin.
EPOCH_2_START_DAYS = 14
EPOCH_3_START_DAYS = 28

#: Decision sections an epoch-3 ADR may change only through an Amendment.
_PROTECTED_SECTIONS = ("Decision Outcome", "Considered Options")

#: Files under docs/adr/ that are not decision records.
_NON_ADR_FILES = {"index.md", "README.md"}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_AMENDMENT_TITLE_RE = re.compile(
    r"(?=.*\bAmendment\b)(?=.*\d{4}-\d{2}-\d{2})", re.IGNORECASE
)
_FENCE_RE = re.compile(r"^(```|~~~)")


class AdrEpoch(IntEnum):
    """The three lifecycle epochs of ADR-0120."""

    PROPOSED = 1
    PROVISIONAL = 2
    SETTLED = 3


EPOCH_STATUS: dict[AdrEpoch, AdrStatus] = {
    AdrEpoch.PROPOSED: AdrStatus.PROPOSED,
    AdrEpoch.PROVISIONAL: AdrStatus.ACCEPTED_PROVISIONAL,
    AdrEpoch.SETTLED: AdrStatus.ACCEPTED,
}

_EPOCH_OF_STATUS: dict[AdrStatus, AdrEpoch] = {
    v: k for k, v in EPOCH_STATUS.items()
}


#: An ADR number (``"0120"``) mapped to the spec IDs that cite it in ``adr:``
#: and whose ``verification:`` names a test file that exists.
DependentMap: TypeAlias = Mapping[str, list[str]]

_SPEC_FILE_RE = re.compile(r"specs/[^/]+\.yaml")


def today_utc() -> _dt.date:
    """Return today in UTC, the one clock the epochs are counted on."""
    return _dt.datetime.now(tz=_dt.UTC).date()


def epoch_for(
    updated: _dt.date, today: _dt.date, *, tested: bool = False
) -> AdrEpoch:
    """Return the epoch of an ADR last materially edited on ``updated``.

    ``tested`` says the ADR has a test-verified dependent, which ends epoch 1
    whatever the date (MS-14-007).
    """
    age = (today - updated).days
    if age >= EPOCH_3_START_DAYS:
        return AdrEpoch.SETTLED
    if tested or age >= EPOCH_2_START_DAYS:
        return AdrEpoch.PROVISIONAL
    return AdrEpoch.PROPOSED


def _effective_epoch(
    fm: AdrFrontmatter, today: _dt.date, *, tested: bool
) -> AdrEpoch:
    """Return the epoch an ADR is in for the edit tiers.

    The computed epoch is a floor, so a status already ahead of it stands
    (MS-14-012): this is the later of the two. A ``status_override`` is a
    human holding the status where it is, so the epoch its status names wins.
    """
    computed = epoch_for(fm.updated, today, tested=tested)
    named = _EPOCH_OF_STATUS.get(fm.status, computed)
    return named if fm.status_override else max(computed, named)


def _epoch_claim(
    name: str,
    fm: AdrFrontmatter,
    epoch: AdrEpoch,
    today: _dt.date,
    tested: bool,
) -> str:
    dependent = " and a test-verified dependent" if tested else ""
    return (
        f"{name}: status is '{fm.status.value}' but updated {fm.updated}"
        f"{dependent} put it in epoch {int(epoch)} "
        f"('{EPOCH_STATUS[epoch].value}') on {today}"
    )


def status_epoch_fault(
    name: str, fm: AdrFrontmatter, today: _dt.date, *, tested: bool = False
) -> str | None:
    """Describe a ``status`` that is not its epoch's, or return None.

    The rule for a material edit, which owns the status on its date
    (MS-14-007). Only ``proposed``, ``accepted-provisional`` and ``accepted``
    have an epoch. A ``status_override`` reason lets the disagreement stand.
    """
    if fm.status not in _EPOCH_OF_STATUS or fm.status_override:
        return None
    epoch = epoch_for(fm.updated, today, tested=tested)
    if fm.status is EPOCH_STATUS[epoch]:
        return None
    return (
        f"{_epoch_claim(name, fm, epoch, today, tested)} (MS-14-007); change "
        f"the status, or record a human's reason in 'status_override:'"
    )


def status_behind_fault(
    name: str, fm: AdrFrontmatter, today: _dt.date, *, tested: bool = False
) -> str | None:
    """Describe a ``status`` behind its epoch, or return None.

    The rule for the scheduled report. A status ahead of its epoch stands
    (MS-14-012), and a ``status_override`` reason holds one behind it.
    """
    status_epoch = _EPOCH_OF_STATUS.get(fm.status)
    if status_epoch is None or fm.status_override:
        return None
    epoch = epoch_for(fm.updated, today, tested=tested)
    if status_epoch >= epoch:
        return None
    return (
        f"{_epoch_claim(name, fm, epoch, today, tested)} (MS-14-007); flip "
        f"the status, or record a human's reason in 'status_override:'"
    )


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


def _parse_sections(body: str) -> list[tuple[int, str, str]]:
    """Return ``(level, title, own text)`` for each heading, in order.

    Headings inside fenced code blocks are ignored. A section's own text ends
    at the next heading of any level.
    """
    sections: list[tuple[int, str, list[str]]] = []
    in_fence = False
    for line in body.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        match = None if in_fence else _HEADING_RE.match(line)
        if match:
            sections.append((len(match.group(1)), match.group(2) or "", []))
        elif sections:
            sections[-1][2].append(line)
    return [(lvl, title, "\n".join(lines)) for lvl, title, lines in sections]


def _is_amendment_title(title: str) -> bool:
    return bool(_AMENDMENT_TITLE_RE.search(title))


def _protected_text(body: str) -> dict[str, str]:
    """Map each protected section name to its full text.

    A heading belongs to a protected section when its title starts with the
    section name, ignoring case ("Considered Options (request side)" counts).
    The text runs through nested subsections, except dated Amendment blocks,
    which are how the section is allowed to change.
    """
    out: dict[str, list[str]] = {}
    sections = _parse_sections(body)
    for idx, (level, title, text) in enumerate(sections):
        name = next(
            (
                n
                for n in _PROTECTED_SECTIONS
                if title.lower().startswith(n.lower())
            ),
            None,
        )
        if name is None:
            continue
        parts = out.setdefault(name, [])
        parts.append(f"{title}\n{text}")
        skip_below: int | None = None
        for sub_level, sub_title, sub_text in sections[idx + 1 :]:
            if sub_level <= level:
                break
            if skip_below is not None and sub_level > skip_below:
                continue
            skip_below = None
            if _is_amendment_title(sub_title):
                skip_below = sub_level
                continue
            parts.append(f"{sub_title}\n{sub_text}")
    return {k: "\n".join(v).strip() for k, v in out.items()}


def _amendment_count(body: str) -> int:
    """Count dated Amendment headings outside fenced code blocks."""
    return sum(
        1
        for _, title, _ in _parse_sections(body)
        if _is_amendment_title(title)
    )


def _parse_adr(text: str) -> tuple[frontmatter.Post, AdrFrontmatter | None]:
    """Return an ADR text's post and its frontmatter, or None for the latter
    when it fails its schema, which is left to the loader to report."""
    post = loads_frontmatter(text)
    try:
        return post, AdrFrontmatter.model_validate(post.metadata)
    except ValidationError:
        return post, None


def _override_is_new(
    old_fm: AdrFrontmatter | None, new_fm: AdrFrontmatter
) -> bool:
    """Say whether the change adds or changes ``status_override:``.

    An override already on the base was written for some earlier reason, so
    it does not cover a new status decision (MS-14-012).
    """
    old = old_fm.status_override if old_fm else None
    return bool(new_fm.status_override) and new_fm.status_override != old


def _status_move_faults(
    name: str,
    old_fm: AdrFrontmatter,
    new_fm: AdrFrontmatter,
    today: _dt.date,
    *,
    tested: bool,
) -> list[str]:
    """Refuse a status change that is not forward to its epoch (MS-14-012).

    A move back, or a promotion ahead of the epoch, needs a
    ``status_override:`` that this edit adds or changes: an override already
    on the base was written for some earlier reason.
    """
    old_epoch = _EPOCH_OF_STATUS.get(old_fm.status)
    new_epoch = _EPOCH_OF_STATUS.get(new_fm.status)
    if old_epoch is None or new_epoch is None or old_epoch is new_epoch:
        return []
    if _override_is_new(old_fm, new_fm):
        return []
    remedy = (
        "add or change 'status_override:' with a human's reason; an "
        "override already on the base does not count (MS-14-012)"
    )
    if new_epoch < old_epoch:
        return [
            f"{name}: status moved back from '{old_fm.status.value}' to "
            f"'{new_fm.status.value}'; a status only moves forward, so keep "
            f"it, or {remedy}"
        ]
    epoch = epoch_for(new_fm.updated, today, tested=tested)
    if new_epoch > epoch:
        return [
            f"{name}: status moved to '{new_fm.status.value}', ahead of "
            f"epoch {int(epoch)} ('{EPOCH_STATUS[epoch].value}') on {today}; "
            f"{remedy}"
        ]
    return []


def edit_faults(
    name: str,
    old_text: str | None,
    new_text: str,
    today: _dt.date,
    *,
    tested_on_base: bool = False,
    tested_on_head: bool = False,
) -> list[str]:
    """Return the lifecycle faults in an edit of one ADR (MS-14-007).

    ``old_text`` is ``None`` for a new ADR. ``tested_on_base`` and
    ``tested_on_head`` say whether the ADR has a test-verified dependent
    before and after the change.

    - A material edit (``updated`` moved, or a new ADR) must leave ``status``
      on the epoch for that date, counting the dependents after the change,
      unless a ``status_override`` says why. An edit that leaves ``updated``
      alone is not held to this: drift on an untouched ADR is the scheduled
      report's.
    - A status change must move forward, and not ahead of the epoch, unless
      the edit adds or changes a ``status_override`` (MS-14-012).
    - Bumping ``updated`` on an ADR that was past epoch 1 needs a
      ``status_override`` (MS-14-009).
    - Changing Decision Outcome or Considered Options of an epoch-3 ADR needs a
      new dated Amendment block (MS-14-009).

    The epoch an ADR "was" in is the later of its computed epoch and the one
    its status names, since a status ahead of the clock stands.
    """
    new, new_fm = _parse_adr(new_text)
    if new_fm is None:
        return []
    if old_text is None:
        fault = status_epoch_fault(name, new_fm, today, tested=tested_on_head)
        return [fault] if fault else []
    old, old_fm = _parse_adr(old_text)
    if old_fm is None:
        return []

    faults: list[str] = []
    if new_fm.updated != old_fm.updated:
        epoch_fault = status_epoch_fault(
            name, new_fm, today, tested=tested_on_head
        )
        if epoch_fault:
            faults.append(epoch_fault)
    faults.extend(
        _status_move_faults(name, old_fm, new_fm, today, tested=tested_on_head)
    )
    old_epoch = _effective_epoch(old_fm, today, tested=tested_on_base)

    if (
        new_fm.updated > old_fm.updated
        and old_epoch > AdrEpoch.PROPOSED
        and not new_fm.status_override
    ):
        faults.append(
            f"{name}: 'updated' moved {old_fm.updated} -> {new_fm.updated} "
            f"on an ADR in epoch {int(old_epoch)}; supersede it or amend it, "
            f"or record a human's reason in 'status_override:' (MS-14-009)"
        )

    if old_fm.status in _EPOCH_OF_STATUS and old_epoch is AdrEpoch.SETTLED:
        old_sections = _protected_text(old.content)
        new_sections = _protected_text(new.content)
        changed = [
            title
            for title in _PROTECTED_SECTIONS
            if old_sections.get(title) != new_sections.get(title)
        ]
        if changed and _amendment_count(new.content) <= _amendment_count(
            old.content
        ):
            faults.append(
                f"{name}: {' and '.join(changed)} changed on an epoch-3 ADR "
                f"without a new dated Amendment block (a heading naming "
                f"'Amendment' and a YYYY-MM-DD date); amend it or supersede "
                f"it with a new ADR (MS-14-009)"
            )
    return faults


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

    With ``tracked``, a test file counts only if git tracks it, so a stray
    untracked file cannot change a local check's answer from CI's.
    """
    files = (
        (path, load_yaml(path, root=root))
        for path in sorted((root / "specs").glob("*.yaml"))
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
    specs = (
        (
            Path(f"{ref}:{f}"),
            loads_yaml(_text_at(ref, Path(f)) or "", Path(f"{ref}:{f}")),
        )
        for f in sorted(files)
        if _SPEC_FILE_RE.fullmatch(f)
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


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    )


def verify_base(base: str) -> None:
    """Raise ``ValueError`` unless ``base`` names a commit.

    Without this, a mistyped ref reads as "every ADR is new" and the gate
    passes everything.
    """
    res = _git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if res.returncode != 0:
        raise ValueError(f"--base {base!r} is not a commit in this repository")


def _text_at(base: str, path: Path) -> str | None:
    """Return the text of ``path`` at ``base``, or None if absent there."""
    res = _git("show", f"{base}:{path.as_posix()}")
    return res.stdout if res.returncode == 0 else None


def _rename_sources(base: str) -> dict[Path, Path]:
    """Map each renamed path to the path it had at ``base``."""
    res = _git("diff", "-M", "--name-status", "--diff-filter=R", base)
    out: dict[Path, Path] = {}
    for line in res.stdout.splitlines():
        _, old, new = line.split("\t")
        out[Path(new)] = Path(old)
    return out


def edited_adrs(
    paths: Iterable[Path], base: str
) -> list[tuple[Path, str | None, str]]:
    """Pair each edited ADR's text at ``base`` with its working-tree text.

    Returns ``(path, old_text, new_text)`` for every path that is a decision
    record present in the working tree; ``index.md``, ``README.md``, files
    starting with ``_`` and deleted paths are skipped. A renamed path is
    paired with the text of the path it had at ``base``, and a path with no
    text at ``base`` (a new ADR) gets ``None``. Raises ``ValueError`` if
    ``base`` is not a commit.

    Shared by every check that judges an edit rather than the corpus, so each
    one reads the merge base the same way.
    """
    verify_base(base)
    renames = _rename_sources(base)
    out: list[tuple[Path, str | None, str]] = []
    for path in paths:
        if path.name in _NON_ADR_FILES or path.name.startswith("_"):
            continue
        if not path.is_file():
            continue
        old_text = _text_at(base, renames.get(path, path))
        out.append((path, old_text, path.read_text(encoding="utf-8")))
    return out


def check_paths(
    paths: Iterable[Path],
    base: str,
    today: _dt.date,
    dependents: Dependents,
) -> list[str]:
    """Check each ADR path's working-tree text against its text at ``base``.

    A renamed path is compared with the path it had at ``base``. A path with
    no text at ``base`` is a new ADR, held to the epoch rule. Raises
    ``ValueError`` if ``base`` is not a commit.
    """
    faults: list[str] = []
    for path, old_text, new_text in edited_adrs(paths, base):
        number = adr_number(path)
        faults.extend(
            edit_faults(
                path.name,
                old_text,
                new_text,
                today,
                tested_on_base=number in dependents.base,
                tested_on_head=number in dependents.head,
            )
        )
    return faults


def first_dependent_faults(
    base: str, root: Path, dependents: Dependents
) -> list[str]:
    """Refuse a change that gives a ``proposed`` ADR its first dependent.

    The change that creates an ADR's first test-verified dependent, by a new
    requirement, a new ``adr:`` or verification, or a new test file, must set
    the ADR to ``accepted-provisional`` (MS-14-010), whether or not it
    touches the ADR. Only a ``status_override:`` the change adds or changes
    can hold it back; one already on the base was written for another reason.
    A new ADR is held to its epoch by :func:`edit_faults` instead.
    """
    renames = _rename_sources(base)
    faults: list[str] = []
    for rel, fm in sorted(load_adr_registry(root).items()):
        number = adr_number(Path(rel))
        deps = dependents.head.get(number or "")
        if not deps or number in dependents.base:
            continue
        if fm.status is not AdrStatus.PROPOSED:
            continue
        old_text = _text_at(base, renames.get(Path(rel), Path(rel)))
        if old_text is None:
            continue
        if _override_is_new(_parse_adr(old_text)[1], fm):
            continue
        faults.append(
            f"{Path(rel).name}: is 'proposed' and this change gives it its "
            f"first test-verified dependent ({', '.join(sorted(deps))}); set "
            f"its status to 'accepted-provisional' in the same change, or add "
            f"a human's reason in 'status_override:' (MS-14-010)"
        )
    return faults


def check_change(
    paths: Iterable[Path], base: str, today: _dt.date, root: Path
) -> list[str]:
    """Return the lifecycle faults in the change from ``base`` to the tree.

    ``paths`` are the ADRs the change edits; the dependency rule
    (MS-14-010) covers every ADR. Raises ``ValueError`` if ``base`` is not a
    commit.
    """
    verify_base(base)
    dependents = Dependents(
        base=dependents_at(base),
        head=tree_dependents(root, tracked=_git_files("--")),
    )
    return check_paths(paths, base, today, dependents) + (
        first_dependent_faults(base, root, dependents)
    )


def main(argv: list[str] | None = None) -> None:
    """CLI: ``adr-lifecycle-check [--base REF] [paths...] | --report-drift``."""
    parser = argparse.ArgumentParser(
        prog="adr-lifecycle-check",
        description="Refuse ADR edits the lifecycle epochs forbid (MS-14-007).",
    )
    parser.add_argument("--base", default="HEAD", help="ref to diff against")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument(
        "--report-drift",
        action="store_true",
        help=(
            "instead of checking an edit, list every ADR whose status is "
            "behind today's epoch; run by the scheduled adr-status-drift "
            "workflow, which reports and never fails"
        ),
    )
    args = parser.parse_args(argv)
    if args.report_drift:
        drift = epoch_drift(Path.cwd(), today_utc())
        for fault in drift:
            print(f"[ERROR] {fault}", file=sys.stderr)
        sys.exit(1 if drift else 0)
    try:
        faults = check_change(args.paths, args.base, today_utc(), Path.cwd())
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
    for fault in faults:
        print(f"[ERROR] {fault}", file=sys.stderr)
    sys.exit(1 if faults else 0)


if __name__ == "__main__":
    main()
