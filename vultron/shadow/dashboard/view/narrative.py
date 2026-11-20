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


"""The case narrative: one row per ledger entry, each with its state
changes in words, and a case-state flag the source cannot observe shown as
unknown (CRD-02-005).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from vultron.core.models._helpers import format_timestamp
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.history import (
    NarrativeLine,
    StateChange,
    StateMachine,
)
from vultron.measure.ledger import MISSING_SLOT
from vultron.shadow.dashboard.view.labels import (
    EM_BADGES,
    RM_BADGES,
    Row,
    actor_label,
)

#: The case-state event each letter of a ``vfd`` or ``pxa`` spelling
#: stands for, by its lower-case letter.
_CS_LETTERS: Mapping[str, CSEvent] = {
    event.value.lower(): event for event in CSEvent
}

#: What the page shows for a case-state flag its source cannot observe.
UNKNOWN_FLAG = "?"


def cs_spelling(state: str, unobservable: frozenset[CSEvent]) -> str:
    """A ``vfd`` or ``pxa`` spelling, each flag the source cannot observe
    shown as ``?``.

    A lower-case letter says its event has not happened, which a source
    that never records the event cannot say (CRD-02-005).
    """
    return "".join(
        UNKNOWN_FLAG
        if letter.islower() and _CS_LETTERS.get(letter) in unobservable
        else letter
        for letter in state
    )


def _state_label(
    machine: StateMachine, state: str, unobservable: frozenset[CSEvent]
) -> str:
    if machine is StateMachine.RM:
        return RM_BADGES[RM[state]]
    if machine is StateMachine.EM:
        return EM_BADGES[EM[state]]
    return cs_spelling(state, unobservable)


def change_text(
    change: StateChange,
    names: Mapping[str, str],
    unobservable: frozenset[CSEvent] = frozenset(),
) -> str:
    """One state change in words: ``Vendor RM: 📥 Received → ☑️ Valid``.

    The participant reads by its display name, never a bare URI or UUID
    (DRPT-03-009).
    """
    who = (
        f"{actor_label(change.participant, names)} "
        if change.participant is not None
        else ""
    )
    before, after = (
        _state_label(change.machine, state, unobservable)
        for state in (change.before, change.after)
    )
    return f"{who}{change.machine}: {before} → {after}"


def narrative_rows(
    lines: Sequence[NarrativeLine],
    names: Mapping[str, str],
    unobservable: frozenset[CSEvent] = frozenset(),
) -> list[Row]:
    """One row per line of the case narrative, in log-index order.

    The time is the one the entry's activity claims; the commit stamp shows
    only where it differs, each in its own column, so neither stands in for
    the other (CEH-03-008).  The ``#`` column is the entry's log index.
    A line that could not read its entry in full says why, in a notes column
    the table has only when some line needs it.
    """
    noted = any(line.notes for line in lines)
    rows: list[Row] = []
    for line in lines:
        row: Row = {
            "#": line.log_index,
            "Time": format_timestamp(line.claimed_at)
            if line.claimed_at is not None
            else MISSING_SLOT,
            "Committed": format_timestamp(line.committed_at)
            if line.committed_at is not None and line.commit_differs
            else "",
            "Actor": line.actor or MISSING_SLOT,
            "Activity": line.phrase,
            "Object": line.object or MISSING_SLOT,
            "State changes": "; ".join(
                change_text(change, names, unobservable)
                for change in line.changes
            ),
        }
        if noted:
            row["Notes"] = "; ".join(line.notes)
        rows.append(row)
    return rows


__all__ = [
    "UNKNOWN_FLAG",
    "change_text",
    "cs_spelling",
    "narrative_rows",
]
