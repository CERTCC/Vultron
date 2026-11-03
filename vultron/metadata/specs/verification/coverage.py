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
"""Per-item verification coverage checks and the summary lines ``spec-lint``
prints (MS-10-003, MS-10-005, MS-10-019).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from vultron.metadata.base import issue_number
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    SpecKind,
    StatementSpec,
)
from vultron.metadata.specs.verification.debt import (
    DebtReport,
    debt_by_kind,
    owes_verification,
    owns_kind,
)


def verification_problems(
    registry: SpecRegistry,
    owners: Mapping[SpecKind, frozenset[str]],
) -> list[str]:
    """Every per-requirement violation of MS-10-003 and MS-10-006..008.

    Each requirement is judged alone, so the result never depends on how many
    other requirements are verified.
    """
    problems: list[str] = []
    specs = registry.all_specs
    for spec_id in sorted(specs):
        spec = specs[spec_id]
        marker = spec.verification_debt
        kind = spec.kind.value
        owes = owes_verification(spec.priority, spec.verification)
        if owes and not marker:
            problems.append(
                f"{spec_id}: priority {spec.priority.value} has no "
                f"verification: field (MS-10-003); add a verification: "
                f"criterion"
            )
        elif marker and not owes:
            problems.append(_stale_marker_problem(spec_id, spec, marker))
        if not marker or owns_kind(owners, spec.kind, marker):
            continue
        kind_owners = owners.get(spec.kind)
        if kind_owners:
            problems.append(
                f"{spec_id}: verification_debt: '{marker}' does not own "
                f"kind={kind} (owners: {', '.join(sorted(kind_owners))}); a "
                f"relabel brings its verification: field with it (MS-10-008)"
            )
        else:
            problems.append(
                f"{spec_id}: kind={kind} has no verification backlog left, so "
                f"verification_debt: '{marker}' is not accepted (MS-10-026); "
                f"add a verification: criterion"
            )
    return problems


def _stale_marker_problem(
    spec_id: str, spec: StatementSpec, marker: str
) -> str:
    if spec.priority.is_must_tier:
        return (
            f"{spec_id}: has a verification: field and a stale "
            f"verification_debt: '{marker}' marker; delete the marker "
            f"(MS-10-006)"
        )
    return (
        f"{spec_id}: priority {spec.priority.value} is below the MUST tier, "
        f"so it owes no verification: field; delete its "
        f"verification_debt: '{marker}' marker (MS-10-006)"
    )


def idle_owners(
    reports: Mapping[SpecKind, DebtReport],
    owners: Mapping[SpecKind, frozenset[str]],
) -> list[str]:
    """Advisory lines for owner-table entries no marker names (MS-10-025).

    Advisory, not a hard error: two PRs that each verify some of an owner's
    last markers are green alone and would be red merged — the race the
    per-item rule exists to avoid (#3984). The PR that closes the owner issue
    fails until the entry is removed (:func:`closing_pr_problems`).
    """
    return [
        f"[WARN] verification_debt kind={kind.value}: no marker names owner "
        f"{owner}; remove it from VERIFICATION_DEBT_OWNERS (and the kind's "
        f"entry with its last owner) so the kind accepts no new debt "
        f"(MS-10-007)"
        for kind, kind_owners in owners.items()
        for owner in sorted(kind_owners, key=issue_number)
        if not reports[kind].by_owner.get(owner)
    ]


def summary_line(report: DebtReport, kind_owners: Iterable[str] = ()) -> str:
    """The one default-output line for a kind (MS-10-005)."""
    tally = report.by_owner
    owner_text = (
        ", ".join(
            f"{owner}: {tally.get(owner, 0)}"
            for owner in sorted(set(kind_owners) | set(tally))
        )
        or "no owner"
    )
    return (
        f"[INFO] verification_debt kind={report.kind.value}: "
        f"{report.count} MUST-tier requirement(s) with no verification: "
        f"field ({owner_text})"
    )


def listing_lines(report: DebtReport) -> list[str]:
    """The opt-in per-ID lines for one kind (MS-10-005)."""
    return [
        f"    {spec_id}  {marker}"
        for spec_id, marker in report.markers.items()
    ]


def check_verification_coverage(
    registry: SpecRegistry,
    owners: Mapping[SpecKind, frozenset[str]],
    list_unverified: bool = False,
) -> tuple[list[str], list[str]]:
    """The ``spec-lint`` check for unverified MUST-tier requirements.

    Returns ``(hard_errors, status_lines)``: every per-requirement violation
    from :func:`verification_problems`, one summary line for each kind that
    has an owner entry or a marker — with that kind's marked IDs beneath it
    when *list_unverified* is set — and a warning per idle owner.
    """
    lines: list[str] = []
    reports = debt_by_kind(registry)
    for kind, report in reports.items():
        kind_owners = owners.get(kind, frozenset())
        if not report.count and not kind_owners:
            continue
        lines.append(summary_line(report, kind_owners))
        if list_unverified:
            lines.extend(listing_lines(report))
    lines.extend(idle_owners(reports, owners))
    return verification_problems(registry, owners), lines
