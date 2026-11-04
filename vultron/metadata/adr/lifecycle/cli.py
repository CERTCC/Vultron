"""Check a branch's ADR edits against the lifecycle, and the ``adr-lifecycle-check`` CLI."""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from collections.abc import Iterable
from pathlib import Path

from vultron.metadata.adr.lifecycle.dependents import (
    Dependents,
    _git_files,
    dependents_at,
    epoch_drift,
    tree_dependents,
)
from vultron.metadata.adr.lifecycle.edits import (
    _override_is_new,
    _parse_adr,
    edit_faults,
)
from vultron.metadata.adr.lifecycle.epochs import status_epoch_fault, today_utc
from vultron.metadata.adr.lifecycle.git_reads import (
    _rename_sources,
    _text_at,
    edited_adrs,
    verify_base,
)
from vultron.metadata.adr.loader import adr_number, load_adr_registry
from vultron.metadata.specs.schema import AdrStatus


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
    base: str, root: Path, today: _dt.date, dependents: Dependents
) -> list[str]:
    """Refuse a change that gives a ``proposed`` ADR its first dependent.

    The change that creates an ADR's first test-verified dependent, by a new
    requirement, a new ``adr:`` or verification, or a new test file, must set
    the ADR to ``accepted-provisional`` (MS-14-010), whether or not it
    touches the ADR. Only a ``status_override:`` the change adds or changes
    can hold it back; one already on the base was written for another reason.
    A new ADR, or a material edit that :func:`edit_faults` already refuses
    for a status off its epoch, is reported there instead, once.
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
        old_fm = _parse_adr(old_text)[1]
        if _override_is_new(old_fm, fm):
            continue
        if (
            old_fm is not None
            and fm.updated != old_fm.updated
            and status_epoch_fault(Path(rel).name, fm, today, tested=True)
        ):
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
        first_dependent_faults(base, root, today, dependents)
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
