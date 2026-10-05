#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Per-kind ceilings on MUST-tier requirements with no ``verification:``.

MS-10-003 obliges every ``MUST`` and ``MUST_NOT`` requirement to carry a
``verification:`` field. The backlog is worked down per kind by the owning
issues named below; until a kind reaches zero, its live count is pinned here to
a ceiling equal to that count (MS-10-006), ``spec-lint`` prints the count and
ceiling as one line per kind (MS-10-005), and
``test/metadata/specs/test_must_verification_ratchet.py`` fails when they
differ in either direction.

The table is the single source both consumers read. It only shrinks: a
backfill lowers its kind's ceiling in the same change, and the change that
reaches zero deletes the entry, which turns that kind's check into a hard error
``lint_suppress`` cannot silence (MS-10-007).

Suppressed items count. ``lint_suppress: [must_without_verification]`` does not
remove a requirement from its kind's number, so a kind cannot reach zero by
suppression.

Runnable locally::

    spec-lint                    # one summary line per kind
    spec-lint --list-unverified  # plus the offending IDs

Requirements: specs/meta-specifications.yaml MS-10-005 through MS-10-008.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import LintWarningCode, SpecKind


@dataclass(frozen=True)
class VerificationCeiling:
    """The pinned count for one kind and the issues driving it to zero."""

    ceiling: int
    #: GitHub issue references (``#N``). Required while ``ceiling`` is non-zero
    #: (MS-10-006); the ratchet test fails on an owner-less entry.
    owners: tuple[str, ...] = ()


#: One entry per kind that still has unverified MUST-tier requirements.
#: Seeded at the measured count on 2026-09-30; lower an entry alongside the
#: backfill that lowers its count, and delete it at zero (MS-10-007). Never
#: raise one — MS-10-008 says a relabel brings its ``verification:`` with it.
VERIFICATION_CEILINGS: Mapping[SpecKind, VerificationCeiling] = (
    MappingProxyType(
        {
            SpecKind.PROTOCOL: VerificationCeiling(126, ("#3612",)),
            SpecKind.ARCHITECTURE: VerificationCeiling(68, ("#2569",)),
            SpecKind.PROCESS: VerificationCeiling(177, ("#2571",)),
            SpecKind.PROJECT: VerificationCeiling(
                992, ("#2573", "#2574", "#2575")
            ),
        }
    )
)


@dataclass
class UnverifiedReport:
    """MUST-tier requirements of one kind with no ``verification:`` field.

    Follows ``coverage.py``'s count-then-list convention: the count is the
    default output and the IDs appear only in the opt-in listing.
    """

    kind: SpecKind
    ids: list[str] = field(default_factory=list)
    #: The subset of ``ids`` carrying ``lint_suppress: [must_without_verification]``.
    #: They are counted regardless (MS-10-006); the listing marks them.
    suppressed: frozenset[str] = frozenset()

    @property
    def count(self) -> int:
        """Unverified MUST-tier requirements of this kind, suppressed included."""
        return len(self.ids)


def unverified_by_kind(
    registry: SpecRegistry,
) -> dict[SpecKind, UnverifiedReport]:
    """Count MUST-tier requirements with no ``verification:``, per kind.

    Every kind gets a report, so a caller can tell "zero" from "not counted".
    IDs are sorted for stable output.
    """
    reports = {kind: UnverifiedReport(kind) for kind in SpecKind}
    suppressed: dict[SpecKind, set[str]] = {kind: set() for kind in SpecKind}
    for spec_id, spec in registry.all_specs.items():
        if not spec.priority.is_must_tier or spec.verification:
            continue
        reports[spec.kind].ids.append(spec_id)
        if LintWarningCode.MUST_WITHOUT_VERIFICATION in (
            spec.lint_suppress or []
        ):
            suppressed[spec.kind].add(spec_id)
    for kind, report in reports.items():
        report.ids.sort()
        report.suppressed = frozenset(suppressed[kind])
    return reports


def ceiling_mismatches(
    reports: Mapping[SpecKind, UnverifiedReport],
    ceilings: Mapping[SpecKind, VerificationCeiling],
) -> list[str]:
    """Kinds whose live count differs from the pinned ceiling, either way.

    A count above the ceiling is a new unverified MUST-tier requirement (or a
    relabel without its ``verification:``, MS-10-008); a count below it is a
    backfill that did not lower the ceiling. A kind with unverified items and
    no entry is a mismatch too — MS-10-007 makes those hard errors, so the
    entry must be restored or the items verified.
    """
    problems: list[str] = []
    for kind in SpecKind:
        count = reports[kind].count if kind in reports else 0
        entry = ceilings.get(kind)
        if entry is None:
            if count:
                problems.append(
                    f"kind={kind.value}: {count} unverified MUST-tier "
                    f"requirement(s) but no ceiling entry — MS-10-007 makes "
                    f"each a hard error; add a verification: field to each, "
                    f"or restore the entry with an owner"
                )
            continue
        if count != entry.ceiling:
            direction = "above" if count > entry.ceiling else "below"
            problems.append(
                f"kind={kind.value}: live count {count} is {direction} the "
                f"ceiling {entry.ceiling}; set the ceiling to {count} "
                f"(MS-10-006 pins it to the live count in either direction)"
            )
    return problems


def ownerless_ceilings(
    ceilings: Mapping[SpecKind, VerificationCeiling],
) -> list[str]:
    """Non-zero ceilings that name no owning issue (MS-10-006)."""
    return [
        f"kind={kind.value}: ceiling {entry.ceiling} names no owning issue"
        for kind, entry in ceilings.items()
        if entry.ceiling and not entry.owners
    ]


def zero_ceilings(
    ceilings: Mapping[SpecKind, VerificationCeiling],
) -> list[str]:
    """Entries at zero, which MS-10-007 says must be deleted, not kept."""
    return [
        f"kind={kind.value}: ceiling is 0; delete the entry so the kind's "
        f"check becomes a hard error (MS-10-007)"
        for kind, entry in ceilings.items()
        if entry.ceiling == 0
    ]


def summary_line(report: UnverifiedReport, entry: VerificationCeiling) -> str:
    """The one default-output line for a kind with a ceiling (MS-10-005)."""
    owners = ", ".join(entry.owners) if entry.owners else "no owner"
    if report.count == entry.ceiling:
        tag, tail = "[INFO]", ""
    else:
        tag = "[WARN]"
        tail = (
            " — differs from the ceiling; "
            "test_must_verification_ratchet.py fails until the table matches"
        )
    return (
        f"{tag} must_without_verification kind={report.kind.value}: "
        f"{report.count} MUST-tier requirement(s) with no verification: field "
        f"(ceiling {entry.ceiling}; owner {owners}){tail}"
    )


def listing_lines(report: UnverifiedReport) -> list[str]:
    """The opt-in per-ID lines for one kind (MS-10-005)."""
    return [
        f"    {spec_id}"
        + (
            "  (lint_suppress, still counted)"
            if spec_id in report.suppressed
            else ""
        )
        for spec_id in report.ids
    ]


def check_verification_coverage(
    registry: SpecRegistry,
    ceilings: Mapping[SpecKind, VerificationCeiling],
    list_unverified: bool = False,
) -> tuple[list[str], list[str]]:
    """The ``spec-lint`` check for MUST-tier requirements with no
    ``verification:`` (MS-10-005, MS-10-007).

    Returns ``(hard_errors, status_lines)``.

    - A kind **with** a ceiling entry gets one summary line — its live count,
      suppressed items included, beside the pinned ceiling and owner — and,
      only when *list_unverified* is set, the offending IDs beneath it. The
      count is never a hard error here: the two-sided pin is the ratchet
      test's job (MS-10-006), so the line says when they disagree.
    - A kind **without** an entry has reached zero, and every unverified
      MUST-tier requirement of that kind is a hard error that
      ``lint_suppress: [must_without_verification]`` cannot silence
      (MS-10-007).
    """
    hard_errors: list[str] = []
    lines: list[str] = []
    for kind, report in unverified_by_kind(registry).items():
        entry = ceilings.get(kind)
        if entry is None:
            hard_errors.extend(
                f"{spec_id}: kind={kind.value} has no MS-10-006 ceiling, so a "
                f"MUST-tier requirement with no verification: field is a hard "
                f"error that lint_suppress cannot silence (MS-10-007); add a "
                f"verification: criterion"
                for spec_id in report.ids
            )
            continue
        lines.append(summary_line(report, entry))
        if list_unverified:
            lines.extend(listing_lines(report))
    return hard_errors, lines
