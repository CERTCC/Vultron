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
"""The ``verification_debt`` owner table, the markers and the debt snapshot the
growth guard compares (MS-10-006, MS-10-016).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from vultron.metadata.specs.growth_guard import GrowthCheck, compare_with_base
from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import (
    RFC2119Priority,
    SpecKind,
    StatementSpec,
)

#: The issues that own each kind's verification backlog. A marker must name an
#: owner of its item's kind. Remove an owner once no marker names it (spec-lint
#: warns; the PR that closes the owner issue fails until it is removed), and
#: the kind's entry with its last owner; from then on any marker of that kind is a hard
#: error (MS-10-026). Never add an owner to admit new debt — the growth guard
#: (``test/architecture/test_verification_debt_guard.py``, MS-10-016) rejects
#: a PR that adds a marker.
VERIFICATION_DEBT_OWNERS: Mapping[SpecKind, frozenset[str]] = MappingProxyType(
    {
        SpecKind.PROTOCOL: frozenset({"#3612"}),
        SpecKind.ARCHITECTURE: frozenset({"#2569"}),
        SpecKind.PROCESS: frozenset({"#2571"}),
        SpecKind.PROJECT: frozenset({"#2573", "#2574", "#2575"}),
    }
)


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


def marked_specs(
    registry: SpecRegistry,
) -> Iterator[tuple[str, StatementSpec, str]]:
    """Each ``(spec_id, spec, marker)`` that carries a marker, in ID order."""
    specs = registry.all_specs
    for spec_id in sorted(specs):
        spec = specs[spec_id]
        if spec.verification_debt:
            yield spec_id, spec, spec.verification_debt


def debt_by_kind(registry: SpecRegistry) -> dict[SpecKind, DebtReport]:
    """Group every ``verification_debt`` marker by its item's kind.

    Every kind gets a report, so a caller can tell "zero" from "not counted".
    """
    reports = {kind: DebtReport(kind) for kind in SpecKind}
    for spec_id, spec, marker in marked_specs(registry):
        reports[spec.kind].markers[spec_id] = marker
    return reports


@dataclass(frozen=True)
class DebtSnapshot:
    """What the MS-10-016 guard reads from one tree.

    Attributes:
        ids: Every requirement ID in the tree.
        markers: Each marked requirement's ID mapped to its marker.
        links: Each requirement's ID mapped to the IDs its own
            ``relationships:`` name.
    """

    ids: frozenset[str]
    markers: Mapping[str, str]
    links: Mapping[str, frozenset[str]]


def _debt_item(spec_id: str, marker: str) -> str:
    return f"{spec_id} verification_debt: '{marker}'"


def debt_snapshot(repo_root: Path) -> DebtSnapshot:
    """The :class:`DebtSnapshot` of ``specs/`` under *repo_root*."""
    registry = load_registry(repo_root / "specs")
    specs = registry.all_specs
    return DebtSnapshot(
        ids=frozenset(specs),
        markers={
            spec_id: marker
            for spec_id, _spec, marker in marked_specs(registry)
        },
        links={
            spec_id: frozenset(r.spec_id for r in spec.relationships or ())
            for spec_id, spec in specs.items()
        },
    )


def added_debt(base: DebtSnapshot, head: DebtSnapshot) -> frozenset[str]:
    """Markers *head* has that *base* lacked, less those split off (MS-10-016).

    A requirement split into several IDs keeps its debt: a new ID whose own
    ``relationships:`` name a requirement that carried the same marker at the
    base, or that is itself such a split child, is not new debt. An ID the base
    already had is never a split child, so a marker it gains is still added.
    A child of a requirement with no marker at the base is not exempt either:
    that parent had no debt to pass on, so the split gives the child a
    ``verification:`` check rather than a marker.
    """
    added = {
        spec_id: marker
        for spec_id, marker in head.markers.items()
        if base.markers.get(spec_id) != marker
    }
    split: set[str] = set()
    grew = True
    while grew:
        grew = False
        for spec_id, marker in added.items():
            if spec_id in split or spec_id in base.ids:
                continue
            if any(
                base.markers.get(parent) == marker
                or (parent in split and head.markers.get(parent) == marker)
                for parent in head.links.get(spec_id, frozenset())
            ):
                split.add(spec_id)
                grew = True
    return frozenset(
        _debt_item(spec_id, marker)
        for spec_id, marker in added.items()
        if spec_id not in split
    )


def debt_added_since_base(
    repo_root: Path,
    *,
    base_ref: str | None = None,
    require_base: bool | None = None,
) -> GrowthCheck:
    """The MS-10-016 guard: :func:`added_debt` against the merge base.

    Arguments, skipping and errors are as
    :func:`~vultron.metadata.specs.growth_guard.added_since_base` documents.
    """
    seen = compare_with_base(
        debt_snapshot,
        repo_root=repo_root,
        paths=("specs",),
        base_ref=base_ref,
        require_base=require_base,
    )
    head_total = len(seen.head_value.markers)
    if seen.base_value is None:
        return GrowthCheck(None, frozenset(), head_total, skipped=seen.skipped)
    return GrowthCheck(
        seen.base, added_debt(seen.base_value, seen.head_value), head_total
    )
