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

"""What the dashboard shows, as plain rows: the scoreboard's words and icons.

Every function here reads a :class:`~vultron.shadow.analysis.CaseAnalysis`
and returns strings and rows, with no Streamlit call, so what an analyst
reads is tested without a browser.  :mod:`~vultron.shadow.dashboard.page`
lays the rows out.

A state reads as an icon and a short label, so the page reads at a glance
(ADR-0192).  The moves keep the standing record's order and each vendor's
own change: no column combines the vendors' numbers into one score
(SHD-03-002).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from vultron.core.models.case_reading import CaseReading
from vultron.core.states.cs import (
    AttackObservation,
    ExploitPublication,
    PublicAwareness,
)
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.history import PxaName
from vultron.measure.ledger import friendly_actor_name
from vultron.measure.standing import (
    DesideratumStanding,
    DesideratumStatus,
    ParticipantStanding,
    ScoredMove,
    StandingGap,
)

#: A row of a table the page shows, column name to cell text.
Row = dict[str, str]

#: Each case-state event's name, as the CS model pages spell it.
EVENT_LABELS: Mapping[CSEvent, str] = {
    CSEvent.V: "Vendor Awareness",
    CSEvent.F: "Fix Ready",
    CSEvent.D: "Fix Deployed",
    CSEvent.P: "Public Awareness",
    CSEvent.X: "Exploit Public",
    CSEvent.A: "Attacks Observed",
}

#: A desideratum's status as an icon and a word.
DESIDERATUM_BADGES: Mapping[DesideratumStatus, str] = {
    DesideratumStatus.MET: "✅ met",
    DesideratumStatus.BROKEN: "❌ broken",
    DesideratumStatus.OPEN: "⏳ open",
}

#: A report-management state as an icon and a word.
RM_BADGES: Mapping[RM, str] = {
    RM.START: "⚪ Start",
    RM.RECEIVED: "📥 Received",
    RM.INVALID: "🚫 Invalid",
    RM.VALID: "☑️ Valid",
    RM.DEFERRED: "⏸️ Deferred",
    RM.ACCEPTED: "▶️ Accepted",
    RM.CLOSED: "⏹️ Closed",
}

#: The case's embargo-management state as an icon and a word.
EM_BADGES: Mapping[EM, str] = {
    EM.NONE: "➖ No embargo",
    EM.PROPOSED: "📨 Embargo proposed",
    EM.ACTIVE: "🔒 Embargo active",
    EM.REVISE: "✏️ Revision proposed",
    EM.EXITED: "🔓 Embargo exited",
}

#: What an untranslated or unobservable fact means for the scores.
NOT_TRANSLATED_NOTE = (
    "The case reader could not translate these facts, so the states and"
    " scores above do not count them."
)
UNOBSERVABLE_NOTE = (
    "The source never records these facts, so the page reads each one as"
    " unknown, not as false."
)


def desideratum_label(desideratum: DesideratumStanding) -> str:
    """The desideratum in words: ``Fix Ready before Public Awareness``."""
    return (
        f"{EVENT_LABELS[desideratum.before]} before"
        f" {EVENT_LABELS[desideratum.after]}"
    )


def desideratum_code(desideratum: DesideratumStanding) -> str:
    """The desideratum in event letters: ``F ≺ P``."""
    return f"{desideratum.before.value} ≺ {desideratum.after.value}"


def public_badges(pxa: PxaName) -> tuple[str, str, str]:
    """The case's public state as three badges: public, exploit, attacks."""
    state = pxa.value
    return (
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


def _tally(desiderata: Sequence[DesideratumStanding]) -> str:
    counts = Counter(d.status for d in desiderata)
    return "  ".join(
        f"{DESIDERATUM_BADGES[status].split()[0]} {counts[status]}"
        for status in DesideratumStatus
    )


def participant_rows(
    participants: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> list[Row]:
    """One row per participant: roles, report state, case state, tally."""
    rows = []
    for p in participants:
        rows.append(
            {
                "Participant": friendly_actor_name(p.participant, names),
                "Roles": ", ".join(p.roles) or "—",
                "Joined": "✔️ joined" if p.joined else "✉️ invited",
                "Report": RM_BADGES[p.rm],
                "Case state": p.case_state.name
                if p.case_state is not None
                else "—",
                "Desiderata": _tally(p.desiderata) if p.desiderata else "—",
                "Not scored because": p.unscored.detail
                if p.unscored is not None
                else "",
                "Actor": p.participant,
            }
        )
    return rows


def desiderata_rows(
    participants: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> list[Row]:
    """One row per desideratum, one status column per scored vendor."""
    scored = [p for p in participants if p.desiderata]
    if not scored:
        return []
    rows: list[Row] = []
    for position, desideratum in enumerate(scored[0].desiderata):
        row: Row = {
            "Desideratum": desideratum_label(desideratum),
            "Events": desideratum_code(desideratum),
        }
        for p in scored:
            row[friendly_actor_name(p.participant, names)] = (
                DESIDERATUM_BADGES[p.desiderata[position].status]
            )
        rows.append(row)
    return rows


def _move_label(move: ScoredMove) -> tuple[str, str]:
    machine, _, trigger = move.move.name.partition(".")
    return machine.upper(), trigger.replace("_", " ").capitalize()


def move_effect(move: ScoredMove, names: Mapping[str, str]) -> str:
    """Each vendor's change from *move*, never one combined number.

    A vendor's part reads as how many desiderata the move makes likelier
    (▲) and unlikelier (▼) to be met than leaving the case to chance.
    """
    if move.advice:
        return "advice: changes no state"
    if move.unscored is not None:
        return f"not scored: {move.unscored}"
    changes = move.changes or ()
    vendors: dict[str, tuple[int, int]] = {}
    for change in changes:
        up, down = vendors.get(change.vendor, (0, 0))
        vendors[change.vendor] = (
            up + (change.change > 0),
            down + (change.change < 0),
        )
    parts = [
        f"{friendly_actor_name(vendor, names)}: ▲{up} ▼{down}"
        if up or down
        else f"{friendly_actor_name(vendor, names)}: no change"
        for vendor, (up, down) in vendors.items()
    ]
    return "; ".join(parts) or "no change"


def move_rows(
    moves: Sequence[ScoredMove], names: Mapping[str, str]
) -> list[Row]:
    """One row per allowed move, in the standing record's order."""
    rows = []
    for move in moves:
        machine, label = _move_label(move)
        rows.append(
            {
                "Who": friendly_actor_name(move.move.participant, names),
                "Machine": machine,
                "Move": label,
                "From → to": (
                    f"{move.move.source.name} → {move.move.destination.name}"
                ),
                "Effect by vendor": move_effect(move, names),
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
        lines.append(f"Embargo register: {gap.register_problem}")
    return lines


def untranslated_rows(reading: CaseReading) -> list[Row]:
    """One row per fact the case reader could not translate (SHD-01-004)."""
    return [
        {
            "Source record": fact.source_record,
            "Fact": fact.fact,
            "Why": fact.reason.value.replace("_", " "),
        }
        for fact in reading.untranslated
    ]


def inference_rows(reading: CaseReading) -> list[Row]:
    """One row per state or time the source implied (CRD-02-002)."""
    return [
        {
            "Entry": inference.entry_id,
            "Rule": inference.rule_id,
            "Caveat": inference.caveat,
        }
        for inference in reading.inferences
    ]


def unobservable_rows(reading: CaseReading) -> list[Row]:
    """One row per fact the source never records (CRD-02-005)."""
    return [
        {"Fact": fact.fact, "Why": fact.why} for fact in reading.unobservable
    ]


__all__ = [
    "DESIDERATUM_BADGES",
    "EM_BADGES",
    "EVENT_LABELS",
    "NOT_TRANSLATED_NOTE",
    "RM_BADGES",
    "UNOBSERVABLE_NOTE",
    "Row",
    "desiderata_rows",
    "desideratum_code",
    "desideratum_label",
    "gap_lines",
    "inference_rows",
    "move_effect",
    "move_rows",
    "participant_rows",
    "public_badges",
    "unobservable_rows",
    "untranslated_rows",
]
