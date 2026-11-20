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


"""The scoreboard's standing: the case's public state as badges, one row
per participant with its tally of desiderata, and the holes that keep the
ledger from a standing.

An event the source cannot observe reads as unknown (CRD-02-005).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping, Sequence

from vultron.core.states.cs import (
    AttackObservation,
    ExploitPublication,
    PublicAwareness,
)
from vultron.core.states.cs_invariants import CSEvent
from vultron.measure.history import PxaName
from vultron.measure.scoring import UnscoredScope
from vultron.measure.standing import (
    DesideratumStanding,
    DesideratumStatus,
    ParticipantStanding,
    StandingGap,
)
from vultron.shadow.dashboard.case_state import (
    PXA_NOTATION,
    unknown_events,
    vfd_badge,
)
from vultron.shadow.dashboard.view.desiderata import DESIDERATUM_BADGES
from vultron.shadow.dashboard.view.labels import (
    EVENT_LABELS,
    RM_BADGES,
    Row,
    actor_label,
)

#: The statuses a tally counts only when a desideratum has one: a source
#: that observes every event, and a vendor its walk reads, show no empty
#: count for them.
_COUNTED_WHEN_SEEN = frozenset(
    {DesideratumStatus.UNKNOWN, DesideratumStatus.UNSCORED}
)


def public_badges(
    pxa: PxaName, unobservable: Collection[CSEvent] = ()
) -> tuple[str, str, str]:
    """The case's public state as three badges: public, exploit, attacks.

    An event the source cannot observe, and the reading does not show as
    happened, reads as unknown (CRD-02-005).
    """
    state = pxa.value
    known = (
        "📢 Public aware"
        if state.public_awareness is PublicAwareness.PUBLIC_AWARE
        else "🤫 Not public",
        "💥 Exploit public"
        if state.exploit_publication is ExploitPublication.EXPLOIT_PUBLIC
        else "🛡️ No public exploit",
        "🎯 Attacks observed"
        if state.attack_observation is AttackObservation.ATTACKS_OBSERVED
        else "🛡️ No attacks observed",
    )
    unknown = unknown_events(pxa.name, PXA_NOTATION, unobservable)
    public, exploit, attacks = (
        f"❔ {EVENT_LABELS[event]} unknown" if event in unknown else badge
        for event, badge in zip(PXA_NOTATION, known, strict=True)
    )
    return public, exploit, attacks


def _tally(desiderata: Sequence[DesideratumStanding]) -> str:
    """Each status's count; unknown or unscored only when a desideratum is
    (:data:`_COUNTED_WHEN_SEEN`)."""
    counts = Counter(d.status for d in desiderata)
    return "  ".join(
        f"{DESIDERATUM_BADGES[status].split()[0]} {counts[status]}"
        for status in DesideratumStatus
        if counts[status] or status not in _COUNTED_WHEN_SEEN
    )


def _not_scored_because(participant: ParticipantStanding) -> str:
    """Why the participant, or part of its scope, has no score; empty when
    all of it is scored.

    A participant with no case-state sequence says why it has none.  A
    vendor whose walk cannot go on from its case keeps its original
    desiderata's statuses, so the reason names the part left unscored.
    """
    if participant.unscored is not None:
        return participant.unscored.detail
    if isinstance(participant.extended, UnscoredScope):
        return (
            "report-handling and embargo desiderata:"
            f" {participant.extended.reason}"
        )
    return ""


def participant_rows(
    participants: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> list[Row]:
    """One row per participant: roles, report state, fix path, tally."""
    rows: list[Row] = []
    for p in participants:
        rows.append(
            {
                "Participant": actor_label(p.participant, names),
                "Roles": ", ".join(p.roles) or "—",
                "Joined": "✔️ joined" if p.joined else "✉️ invited",
                "Report": RM_BADGES[p.rm],
                "Fix path": vfd_badge(p.case_state, p.case.unobservable)
                if p.case_state is not None
                else "—",
                "Desiderata": _tally(p.desiderata) if p.desiderata else "—",
                "Not scored because": _not_scored_because(p),
                "Actor": p.participant,
            }
        )
    return rows


def gap_lines(gap: StandingGap) -> list[str]:
    """Each hole that keeps the ledger from a standing, in words."""
    lines = []
    if gap.missing_log_indices:
        lines.append(f"Missing log indices: {gap.missing_log_indices}")
    if gap.conflicting_log_indices:
        lines.append(f"Conflicting log indices: {gap.conflicting_log_indices}")
    lines.extend(row.describe() for row in gap.unusable_rows)
    lines.extend(
        f"Unreadable entry at log index {entry.log_index}: {entry.reason}"
        for entry in gap.unreadable_entries
    )
    if gap.register_problem is not None:
        # Already worded as an embargo register problem (derive_em).
        lines.append(gap.register_problem)
    return lines


__all__ = [
    "gap_lines",
    "participant_rows",
    "public_badges",
]
