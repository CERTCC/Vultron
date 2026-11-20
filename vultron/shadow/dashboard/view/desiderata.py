#!/usr/bin/env python

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


"""The Desiderata table: one row per desideratum of a vendor's scope, one
status column per scored vendor, each status as an icon and a word.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from vultron.measure.baselines import EventKind
from vultron.measure.standing import (
    DesideratumStanding,
    DesideratumStatus,
    ParticipantStanding,
)
from vultron.shadow.dashboard.view.labels import (
    EVENT_LABELS,
    Row,
    actor_label,
)

#: Each event a desideratum can order, by name: the six case-state events
#: as :data:`EVENT_LABELS` spells them, the report and embargo events as
#: ``_case_events.md`` and ``process_model_desiderata.md`` name them where
#: they do, and the rest as :class:`~vultron.measure.baselines.EventKind`
#: describes them.  Every kind has a name, so a desideratum added to the
#: catalog reads in words with no change here.
DESIDERATUM_EVENT_LABELS: Mapping[EventKind, str] = {
    **{EventKind(e.value): label for e, label in EVENT_LABELS.items()},
    EventKind.INVALIDATED: "Report Invalidation",
    EventKind.VALIDATED: "Report Validation",
    EventKind.DEFERRED: "Report Deferral",
    EventKind.ACCEPTED: "Report Acceptance",
    EventKind.CLOSED: "Report Closure",
    EventKind.EMBARGO_PROPOSED: "Embargo Proposal",
    EventKind.EMBARGO_REJECTED: "Embargo Rejection",
    EventKind.EMBARGO_CANCELLED: "Embargo Proposal Cancelled",
    EventKind.EMBARGO_START: "Embargo Start",
    EventKind.REVISION_PROPOSED: "Embargo Revision Proposal",
    EventKind.REVISION_SETTLED: "Embargo Revision Settled",
    EventKind.EXIT: "Embargo Exit",
    EventKind.EXIT_OWN_TERMS: "Embargo Exit on Its Own Terms",
    EventKind.EXIT_THREAT: "Embargo Exit on a Threat Signal",
    EventKind.EXIT_OTHER: "Other Early Embargo Exit",
}

#: A desideratum's status as an icon and a word.
DESIDERATUM_BADGES: Mapping[DesideratumStatus, str] = {
    DesideratumStatus.MET: "✅ met",
    DesideratumStatus.BROKEN: "❌ broken",
    DesideratumStatus.OPEN: "⏳ open",
    DesideratumStatus.UNKNOWN: "❔ unknown",
    DesideratumStatus.UNSCORED: "▫️ not scored",
}


#: Why the Desiderata table has no row for ``V_i ≺ F_j``, which the
#: desiderata page lists.  The page's other multi-party desideratum,
#: ``F_i ≺ P``, is each vendor's ``F ≺ P`` row, so it needs no note.
DESIDERATA_NOTE = (
    "The table leaves out V_i ≺ F_j (every vendor aware before any fix is"
    " ready): move advice does not use it (ADR-0200)."
)


def desideratum_label(desideratum: DesideratumStanding) -> str:
    """The desideratum in words: ``Fix Ready before Public Awareness``."""
    return (
        f"{DESIDERATUM_EVENT_LABELS[desideratum.before]} before"
        f" {DESIDERATUM_EVENT_LABELS[desideratum.after]}"
    )


def desideratum_code(desideratum: DesideratumStanding) -> str:
    """The desideratum in event letters: ``F ≺ P``."""
    return f"{desideratum.before.value} ≺ {desideratum.after.value}"


def _vendor_columns(
    scored: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> list[str]:
    """One column name per scored vendor, never one another's or a fixed one.

    A vendor's short label names its column.  A label two vendors share, or
    that a fixed column already uses, takes the vendor's actor id as well,
    so no vendor's column overwrites another's.
    """
    labels = [actor_label(p.participant, names) for p in scored]
    taken = Counter(labels) + Counter(_DESIDERATA_COLUMNS)
    return [
        label if taken[label] == 1 else f"{label} ({p.participant})"
        for label, p in zip(labels, scored, strict=True)
    ]


#: The desiderata table's own columns, before one column per vendor.
_DESIDERATA_COLUMNS = ("Desideratum", "Events")


def desiderata_rows(
    participants: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> list[Row]:
    """One row per desideratum of a vendor's scope, one status column per
    scored vendor.

    The rows are the desiderata move advice sums, in catalog order, each
    group of equivalent ones once under its first
    (:func:`~vultron.measure.baselines.scope_desiderata`), so a desideratum
    added to that list gets a row with no change here.
    """
    scored = [p for p in participants if p.desiderata]
    if not scored:
        return []
    columns = _vendor_columns(scored, names)
    rows: list[Row] = []
    for position, desideratum in enumerate(scored[0].desiderata):
        row: Row = dict(
            zip(
                _DESIDERATA_COLUMNS,
                (
                    desideratum_label(desideratum),
                    desideratum_code(desideratum),
                ),
                strict=True,
            )
        )
        for column, p in zip(columns, scored, strict=True):
            row[column] = DESIDERATUM_BADGES[p.desiderata[position].status]
        rows.append(row)
    return rows


__all__ = [
    "DESIDERATA_NOTE",
    "DESIDERATUM_BADGES",
    "DESIDERATUM_EVENT_LABELS",
    "desiderata_rows",
    "desideratum_code",
    "desideratum_label",
]
