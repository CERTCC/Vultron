"""ADR lifecycle epochs and the checks built on them (ADR-0120).

Requirements: specs/meta-specifications.yaml MS-14-007, MS-14-008.

An ADR's ``status`` tracks how settled the decision is, and that is a function
of time since the last *material* edit (``updated``):

- epoch 1, under 72 hours: ``proposed``
- epoch 2, 72 hours to day 10: ``accepted-provisional``
- epoch 3, day 10 on: ``accepted``

``updated`` is a date, so the boundaries are counted in whole days (3 and 10).
A human may override the computed status with ``status_override: <reason>``.
Retired and rejected ADRs have no epoch.

Two checks live here:

- :func:`status_epoch_fault` compares ``status`` with the epoch (run by
  ``spec-lint``).
- :func:`edit_faults` compares an ADR's text before and after an edit and
  refuses the edits the epochs forbid (run by the ``adr-lifecycle-check``
  pre-commit hook).

:func:`hardened_adrs` reports the early-promotion signal: an ADR still in epoch
1 or 2 that a spec requirement depends on and verifies with a test.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from enum import IntEnum
from pathlib import Path
from typing import Protocol

import frontmatter
from pydantic import ValidationError

from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.specs.schema import AdrStatus

#: Whole days of age at which epoch 2 and epoch 3 begin (72 hours, day 10).
EPOCH_2_START_DAYS = 3
EPOCH_3_START_DAYS = 10

#: Decision sections an epoch-3 ADR may change only through an Amendment.
_PROTECTED_SECTIONS = ("Decision Outcome", "Considered Options")

#: Files under docs/adr/ that are not decision records.
_NON_ADR_FILES = {"index.md", "README.md"}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_AMENDMENT_RE = re.compile(
    r"^#{1,6}\s+(?=.*\bAmendment\b)(?=.*\d{4}-\d{2}-\d{2})",
    re.IGNORECASE | re.MULTILINE,
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


def today_utc() -> _dt.date:
    """Return today in UTC, the one clock the epochs are counted on."""
    return _dt.datetime.now(tz=_dt.UTC).date()


def epoch_for(updated: _dt.date, today: _dt.date) -> AdrEpoch:
    """Return the epoch of an ADR last materially edited on ``updated``."""
    age = (today - updated).days
    if age < EPOCH_2_START_DAYS:
        return AdrEpoch.PROPOSED
    if age < EPOCH_3_START_DAYS:
        return AdrEpoch.PROVISIONAL
    return AdrEpoch.SETTLED


def status_epoch_fault(
    name: str, fm: AdrFrontmatter, today: _dt.date
) -> str | None:
    """Describe a ``status`` that disagrees with the epoch, or return None.

    Only ``proposed``, ``accepted-provisional`` and ``accepted`` have an epoch.
    A ``status_override`` reason lets the disagreement stand (MS-14-007).
    """
    if fm.status not in _EPOCH_OF_STATUS or fm.status_override:
        return None
    epoch = epoch_for(fm.updated, today)
    expected = EPOCH_STATUS[epoch]
    if fm.status is expected:
        return None
    return (
        f"{name}: status is '{fm.status.value}' but updated {fm.updated} "
        f"puts it in epoch {int(epoch)} ('{expected.value}') on {today} "
        f"(MS-14-007); change the status, or record a human's reason in "
        f"'status_override:'"
    )


def _split_sections(body: str) -> dict[str, str]:
    """Map each heading title to its text, up to the next heading of any level.

    Headings inside fenced code blocks are ignored. Nested subsections (an
    Amendment, say) are separate entries, so a section's text excludes them.
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None
    in_fence = False
    for line in body.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        match = None if in_fence else _HEADING_RE.match(line)
        if match:
            title = match.group(2) or ""
            current = title
            sections.setdefault(title, [])
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _amendment_count(body: str) -> int:
    return len(_AMENDMENT_RE.findall(body))


def edit_faults(
    name: str, old_text: str, new_text: str, today: _dt.date
) -> list[str]:
    """Return the lifecycle faults in an edit of one ADR (MS-14-007).

    - Bumping ``updated`` on an ADR that was past epoch 1 needs a
      ``status_override``.
    - Changing Decision Outcome or Considered Options of an epoch-3 ADR needs a
      new dated Amendment block.

    Frontmatter that fails its schema is left to the loader to report.
    """
    old = frontmatter.loads(old_text)
    new = frontmatter.loads(new_text)
    try:
        old_fm = AdrFrontmatter.model_validate(old.metadata)
        new_fm = AdrFrontmatter.model_validate(new.metadata)
    except ValidationError:
        return []

    faults: list[str] = []
    old_epoch = epoch_for(old_fm.updated, today)

    if (
        new_fm.updated > old_fm.updated
        and old_epoch > AdrEpoch.PROPOSED
        and not new_fm.status_override
    ):
        faults.append(
            f"{name}: 'updated' moved {old_fm.updated} -> {new_fm.updated} "
            f"on an ADR in epoch {int(old_epoch)}; supersede it or amend it, "
            f"or record a human's reason in 'status_override:' (MS-14-007)"
        )

    if old_fm.status is AdrStatus.ACCEPTED and old_epoch is AdrEpoch.SETTLED:
        old_sections = _split_sections(old.content)
        new_sections = _split_sections(new.content)
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
                f"it with a new ADR (MS-14-007)"
            )
    return faults


class _SpecLike(Protocol):
    """The two spec fields :func:`verified_dependents` reads."""

    @property
    def adr(self) -> list[str] | None: ...

    @property
    def verification(self) -> str | None: ...


_TEST_PATH_RE = re.compile(r"`(test/[A-Za-z0-9_./-]+\.py)")


def verified_dependents(
    specs: Mapping[str, _SpecLike], root: Path
) -> dict[str, list[str]]:
    """Map an ADR number to the spec IDs that depend on it and are tested.

    A spec depends on an ADR when it lists it in ``adr:``. It is tested when
    its ``verification:`` names a ``test/`` file that exists under ``root``.
    """
    out: dict[str, list[str]] = {}
    for spec_id, spec in specs.items():
        if not spec.adr or not spec.verification:
            continue
        if not any(
            (root / m).is_file()
            for m in _TEST_PATH_RE.findall(spec.verification)
        ):
            continue
        for adr_id in spec.adr:
            out.setdefault(adr_id.split("-", 1)[1], []).append(spec_id)
    return out


def hardened_adrs(
    registry: dict[str, AdrFrontmatter],
    verified_dependents: dict[str, list[str]],
    today: _dt.date,
) -> dict[str, list[str]]:
    """Return ADRs a human could promote early, with their dependent specs.

    ``verified_dependents`` maps an ADR number (``"0120"``) to the spec IDs
    that cite it in ``adr:`` and carry a test-backed ``verification:``. An ADR
    in epoch 1 or 2 with such a dependent is reported (MS-14-007).
    """
    out: dict[str, list[str]] = {}
    for rel_path, fm in registry.items():
        number = Path(rel_path).name.split("-", 1)[0]
        deps = verified_dependents.get(number)
        if (
            deps
            and fm.status in _EPOCH_OF_STATUS
            and epoch_for(fm.updated, today) < AdrEpoch.SETTLED
        ):
            out[rel_path] = deps
    return out


def _text_at(base: str, path: Path) -> str | None:
    res = subprocess.run(
        ["git", "show", f"{base}:{path.as_posix()}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return res.stdout if res.returncode == 0 else None


def check_paths(
    paths: Iterable[Path], base: str, today: _dt.date
) -> list[str]:
    """Check each ADR path's working-tree text against its text at ``base``.

    A path with no text at ``base`` is a new ADR and is unconstrained.
    """
    faults: list[str] = []
    for path in paths:
        if path.name in _NON_ADR_FILES or path.name.startswith("_"):
            continue
        if not path.is_file():
            continue
        old_text = _text_at(base, path)
        if old_text is None:
            continue
        faults.extend(
            edit_faults(
                path.name, old_text, path.read_text(encoding="utf-8"), today
            )
        )
    return faults


def main(argv: list[str] | None = None) -> None:
    """CLI: ``uv run adr-lifecycle-check [--base REF] [paths...]``."""
    parser = argparse.ArgumentParser(
        prog="adr-lifecycle-check",
        description="Refuse ADR edits the lifecycle epochs forbid (MS-14-007).",
    )
    parser.add_argument("--base", default="HEAD", help="ref to diff against")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)
    faults = check_paths(args.paths, args.base, today_utc())
    for fault in faults:
        print(f"[ERROR] {fault}", file=sys.stderr)
    sys.exit(1 if faults else 0)


if __name__ == "__main__":
    main()
