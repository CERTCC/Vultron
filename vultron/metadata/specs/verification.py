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
"""Per-requirement ``verification_debt`` markers on unverified MUST-tier items.

MS-10-003 obliges every ``MUST`` and ``MUST_NOT`` requirement to carry a
``verification:`` field. Until the backlog is worked down, each requirement
that still lacks one carries ``verification_debt: '#N'`` instead, naming the
issue that owns verifying it (MS-10-006). The rule is checked one requirement
at a time, so there is no committed count for two concurrent PRs to race on
(#3984): two PRs conflict only when they edit the same requirement.

Per requirement, ``spec-lint`` fails when:

- a MUST-tier item has neither ``verification:`` nor a marker;
- an item has both (the marker is stale — delete it);
- a marker sits on an item below the MUST tier;
- a marker names an issue that does not own the item's kind in
  :data:`VERIFICATION_DEBT_OWNERS`. That covers a relabel that kept the old
  kind's marker (MS-10-008) and a marker on a kind whose backlog is finished
  and whose entry is gone (MS-10-007).

The owner table holds issue references only, never counts, so nothing in it
moves when a requirement is verified. ``spec-lint`` prints one summary line
per kind computed from the markers (MS-10-005), and
``spec-lint --check-debt-owners`` (CI only — it needs the GitHub API) fails
when any marker or table entry names a closed issue.

Runnable locally::

    spec-lint                      # one summary line per kind
    spec-lint --list-unverified    # plus the marked IDs
    spec-lint --check-debt-owners  # plus the open-owner check (needs gh)

Requirements: specs/meta-specifications.yaml MS-10-003, MS-10-005 through
MS-10-008.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    RFC2119Priority,
    SpecKind,
    StatementSpec,
)

#: The issues that own each kind's verification backlog. A marker must name an
#: owner of its item's kind. Remove an owner once no marker names it (spec-lint
#: warns; the CI open-owner check fails once the issue closes), and the kind's
#: entry with its last owner; from then on any marker of that kind is a hard
#: error (MS-10-007). Never add an owner to admit new debt — the growth guard
#: (#4200) rejects a PR that adds a marker.
VERIFICATION_DEBT_OWNERS: Mapping[SpecKind, frozenset[str]] = MappingProxyType(
    {
        SpecKind.PROTOCOL: frozenset({"#3612"}),
        SpecKind.ARCHITECTURE: frozenset({"#2569"}),
        SpecKind.PROCESS: frozenset({"#2571"}),
        SpecKind.PROJECT: frozenset({"#2573", "#2574", "#2575"}),
    }
)


def issue_number(ref: str) -> int:
    """The number in an ``#N`` issue reference."""
    return int(ref.removeprefix("#"))


def owes_verification(
    priority: RFC2119Priority, verification: str | None
) -> bool:
    """A MUST-tier requirement with no ``verification:`` field (MS-10-003)."""
    return priority.is_must_tier and not verification


def owns_kind(
    owners: Mapping[SpecKind, frozenset[str]], kind: SpecKind, marker: str
) -> bool:
    """Whether *marker* names an owner of *kind* (MS-10-006..008)."""
    return marker in owners.get(kind, frozenset())


@dataclass
class DebtReport:
    """The MUST-tier requirements of one kind that carry a marker.

    Follows ``coverage.py``'s count-then-list convention: the count is the
    default output and the IDs appear only in the opt-in listing.
    """

    kind: SpecKind
    #: ``spec_id -> marker``, in ID order.
    markers: dict[str, str] = field(default_factory=dict)

    @property
    def count(self) -> int:
        """Marked requirements of this kind."""
        return len(self.markers)

    @property
    def by_owner(self) -> Counter[str]:
        """How many of this kind's markers name each issue."""
        return Counter(self.markers.values())


def debt_by_kind(registry: SpecRegistry) -> dict[SpecKind, DebtReport]:
    """Group every ``verification_debt`` marker by its item's kind.

    Every kind gets a report, so a caller can tell "zero" from "not counted".
    """
    reports = {kind: DebtReport(kind) for kind in SpecKind}
    for spec_id in sorted(registry.all_specs):
        spec = registry.all_specs[spec_id]
        if spec.verification_debt:
            reports[spec.kind].markers[spec_id] = spec.verification_debt
    return reports


def verification_problems(
    registry: SpecRegistry,
    owners: Mapping[SpecKind, frozenset[str]],
) -> list[str]:
    """Every per-requirement violation of MS-10-003 and MS-10-006..008.

    Each requirement is judged alone, so the result never depends on how many
    other requirements are verified.
    """
    problems: list[str] = []
    for spec_id in sorted(registry.all_specs):
        spec = registry.all_specs[spec_id]
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
                f"verification_debt: '{marker}' is not accepted (MS-10-007); "
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
    """Advisory lines for owner-table entries no marker names (MS-10-007).

    Advisory, not a hard error: two PRs that each verify some of an owner's
    last markers are green alone and would be red merged — the race the
    per-item rule exists to avoid (#3984). The CI open-owner check fails on the
    entry once its issue closes, which forces the removal.
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


def debt_owner_refs(
    registry: SpecRegistry,
    owners: Mapping[SpecKind, frozenset[str]],
) -> set[str]:
    """Every issue a marker or an owner-table entry names."""
    refs = {ref for kind_owners in owners.values() for ref in kind_owners}
    refs.update(
        spec.verification_debt
        for spec in registry.all_specs.values()
        if spec.verification_debt
    )
    return refs


def gh_issue_state(ref: str) -> str:
    """The GitHub state (``OPEN``/``CLOSED``) of issue *ref* (``#N``).

    Uses the ``gh`` CLI against the current repository, so it needs ``gh`` on
    ``PATH`` and a token (``GH_TOKEN`` in CI). Raises
    :class:`subprocess.CalledProcessError` or :class:`FileNotFoundError` when
    the lookup cannot be made.
    """
    result = subprocess.run(
        ["gh", "issue", "view", str(issue_number(ref)), "--json", "state"],
        capture_output=True,
        text=True,
        check=True,
    )
    return str(json.loads(result.stdout)["state"])


def closed_debt_owners(
    refs: Iterable[str],
    issue_state: Callable[[str], str] | None = None,
) -> list[str]:
    """Hard errors for every ref whose issue is closed or cannot be read.

    A lookup failure is an error, not a pass: a check that cannot see the
    issue has not shown it is open. *issue_state* defaults to
    :func:`gh_issue_state`.
    """
    if issue_state is None:
        issue_state = gh_issue_state
    errors: list[str] = []
    for ref in sorted(refs, key=issue_number):
        try:
            state = issue_state(ref)
        except (
            OSError,
            subprocess.CalledProcessError,
            KeyError,
            ValueError,
        ) as exc:
            errors.append(
                f"verification_debt owner {ref}: could not read its state "
                f"({exc}); the open-owner check needs gh and a token"
            )
            continue
        if state.upper() != "OPEN":
            errors.append(
                f"verification_debt owner {ref} is {state.upper()}: an "
                f"unverified requirement must name an open owning issue "
                f"(MS-10-006); verify the items that cite it, or re-point "
                f"them and the owner table at the issue that took the work over"
            )
    return errors
