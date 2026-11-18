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

"""A case narrative: who did what, when, and which states each entry changed.

:func:`case_narrative` reads one line per ledger entry, in log-index order,
from the ledger alone; nothing in it is written by hand.  A line names the
time the entry's activity claims and the entry's commit stamp, each in its
own field (CEH-03-007, CEH-03-008); the acting actor and the object by
their friendly display names (CEH-01-006, DRPT-03-009); the registry phrase
of the entry's semantic type (CEH-01-007, DRPT-03-002); and every state
change the entry caused.

The state changes come from the walk the event history takes
(:func:`~vultron.measure.history.derive_case_steps`): the states reached
after an entry are compared with those reached before it, so a line shows
exactly what the history reads the entry as changing.  That covers each
participant's report management (RM) and its vendor fix path and deployment
(VFD), the case's EM state, derived from its embargo register (ADR-0122),
and the case's public state (PXA).

Each line carries its entry's log index, so a reader can point at one line
and read the case as it stood there.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.models._helpers import timestamp_serializer
from vultron.core.states.em import EM
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.history.derive import derive_case_steps
from vultron.measure.history.reached import ReachedParticipant, ReachedState
from vultron.measure.history.render import entry_labels
from vultron.measure.history.snapshot import parse_time
from vultron.measure.ledger import (
    CaseLedger,
    actor_uri,
    first_present,
    label_names,
    payload_of,
)
from vultron.primitives import NonEmptyString


class StateMachine(StrEnum):
    """A state machine whose changes a narrative line lists."""

    #: A participant's report management.
    RM = "RM"
    #: The case's embargo management, derived from its embargo register.
    EM = "EM"
    #: A participant's vendor fix path and fix deployment.
    VFD = "VFD"
    #: The case's public state.
    PXA = "PXA"


#: The machines one participant has; the others belong to the case.
PARTICIPANT_MACHINES: frozenset[StateMachine] = frozenset(
    {StateMachine.RM, StateMachine.VFD}
)


class StateChange(BaseModel):
    """One state an entry moved a machine out of, and the one it moved to.

    Fields:
        machine: The state machine.
        participant: The participant the state belongs to, for RM and VFD;
            ``None`` for the case's EM and PXA.
        before: The state reached before the entry, by name: an RM or EM
            member's name, or a ``vfd`` or ``pxa`` spelling.
        after: The state reached after it, named the same way.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    machine: StateMachine
    participant: NonEmptyString | None = None
    before: NonEmptyString
    after: NonEmptyString

    @model_validator(mode="after")
    def _a_change_names_its_owner(self) -> StateChange:
        problems: list[str] = []
        if self.machine in PARTICIPANT_MACHINES:
            if self.participant is None:
                problems.append(
                    f"an {self.machine} change names a participant"
                )
        elif self.participant is not None:
            problems.append(f"an {self.machine} change belongs to the case")
        if self.before == self.after:
            problems.append(f"{self.before} to itself is no change")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class NarrativeLine(BaseModel):
    """One ledger entry of a case narrative.

    Fields:
        log_index: The entry's log index.
        committed_at: The entry's commit stamp, from the CASE_MANAGER's
            clock; ``None`` when the entry holds none.
        claimed_at: The time the entry's activity claims, from its sender's
            clock; ``None`` when it states none.  Never a copy of the commit
            stamp (CEH-03-008).
        semantic_type: The entry's semantic type, as recorded.
        actor_id: The acting actor's id, as recorded.
        actor: The acting actor's display name.
        object: The object's display name, with its destination when the
            entry names one (``object → destination``).
        phrase: The registry phrase of the semantic type, its slots filled
            with the actor's and the object's names (DRPT-03-004).
        changes: Every state change the entry caused: RM, then EM, then
            VFD, then PXA, participants in the order the walk first met
            them.
        notes: What keeps the line from reading the entry in full: each
            part of it the walk could not read, and an embargo register
            the entry left with no EM state.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    log_index: int = Field(ge=0)
    committed_at: datetime | None = None
    claimed_at: datetime | None = None
    semantic_type: NonEmptyString | None = None
    actor_id: NonEmptyString | None = None
    actor: NonEmptyString | None = None
    object: NonEmptyString | None = None
    phrase: NonEmptyString
    changes: tuple[StateChange, ...] = ()
    notes: tuple[NonEmptyString, ...] = ()

    #: Every time serializes in the one fixed form (CS-13-007, ADR-0167).
    _serialize_times = timestamp_serializer("committed_at", "claimed_at")

    @property
    def commit_differs(self) -> bool:
        """Whether the commit stamp says something the claimed time does not:
        the entry has one, and it is not the claimed time."""
        return self.committed_at is not None and (
            self.committed_at != self.claimed_at
        )


def _em(reached: ReachedState) -> tuple[EM | None, str | None]:
    """The case's EM state, or why its register gives none."""
    try:
        return reached.em(), None
    except VultronInvalidStateTransitionError as exc:
        return None, str(exc)


def _participant_changes(
    before: ReachedState, after: ReachedState
) -> tuple[list[StateChange], list[StateChange]]:
    """Each participant's RM changes and VFD changes from *before* to *after*."""
    rm: list[StateChange] = []
    vfd: list[StateChange] = []
    for now in after.participants:
        was = before.for_participant(now.participant) or ReachedParticipant(
            participant=now.participant
        )
        if was.rm is not now.rm:
            rm.append(
                StateChange(
                    machine=StateMachine.RM,
                    participant=now.participant,
                    before=was.rm.name,
                    after=now.rm.name,
                )
            )
        was_vfd, now_vfd = f"{was.vf}{was.d}", f"{now.vf}{now.d}"
        if was_vfd != now_vfd:
            vfd.append(
                StateChange(
                    machine=StateMachine.VFD,
                    participant=now.participant,
                    before=was_vfd,
                    after=now_vfd,
                )
            )
    return rm, vfd


def _changes(
    before: ReachedState,
    after: ReachedState,
    em_before: EM | None,
    em_after: EM | None,
) -> tuple[StateChange, ...]:
    """Every state change from *before* to *after*, in line order."""
    rm, vfd = _participant_changes(before, after)
    em: list[StateChange] = []
    if (
        em_before is not None
        and em_after is not None
        and em_before != em_after
    ):
        em.append(
            StateChange(
                machine=StateMachine.EM,
                before=em_before.name,
                after=em_after.name,
            )
        )
    pxa: list[StateChange] = []
    if before.pxa is not after.pxa:
        pxa.append(
            StateChange(
                machine=StateMachine.PXA,
                before=before.pxa.name,
                after=after.pxa.name,
            )
        )
    return (*rm, *em, *vfd, *pxa)


def _line(
    entry: Mapping[str, Any],
    log_index: int,
    names: Mapping[str, str],
    case_id: str,
    changes: tuple[StateChange, ...],
    notes: tuple[str, ...],
) -> NarrativeLine:
    """The line of *entry*, with the *changes* it caused and its *notes*."""
    payload = payload_of(entry)
    raw_type = first_present(entry, "semanticType", "semantic_type")
    semantic_type = (
        raw_type if isinstance(raw_type, str) and raw_type else None
    )
    labels = entry_labels(entry, names, case_id)
    return NarrativeLine(
        log_index=log_index,
        committed_at=parse_time(
            first_present(entry, "published", "receivedAt", "received_at")
        ),
        claimed_at=parse_time(payload.get("published")),
        semantic_type=semantic_type,
        actor_id=actor_uri(payload.get("actor")),
        actor=labels.actor,
        object=labels.object_cell,
        phrase=labels.phrase(semantic_type or ""),
        changes=changes,
        notes=notes,
    )


def case_narrative(ledger: CaseLedger) -> tuple[NarrativeLine, ...]:
    """One line per row of *ledger*, in log-index order.

    Each line's state changes compare the states the event history's walk
    has reached after the entry with those it had reached before it
    (:func:`~vultron.measure.history.derive_case_steps`).  An entry the walk
    cannot read keeps its line, which says why it changed nothing.  When an
    entry leaves the embargo register with no EM state, its line says why,
    and the next EM change is read from the last EM state the register gave.
    """
    names = label_names({ledger.case_id: ledger.entries})
    history, steps = derive_case_steps(ledger)
    unreadable: dict[int, list[str]] = {}
    for item in history.unreadable_entries:
        unreadable.setdefault(item.log_index, []).append(item.reason)
    lines: list[NarrativeLine] = []
    before = ReachedState()
    em_before, problem_before = _em(before)
    for placed, after in zip(ledger.rows, steps, strict=True):
        em_after, problem = _em(after)
        notes = list(dict.fromkeys(unreadable.get(placed.log_index, ())))
        if problem is not None and problem != problem_before:
            notes.append(f"Embargo register: {problem}")
        lines.append(
            _line(
                placed.data,
                placed.log_index,
                names,
                ledger.case_id,
                _changes(before, after, em_before, em_after),
                tuple(notes),
            )
        )
        before, problem_before = after, problem
        if em_after is not None:
            em_before = em_after
    return tuple(lines)


__all__ = [
    "PARTICIPANT_MACHINES",
    "NarrativeLine",
    "StateChange",
    "StateMachine",
    "case_narrative",
]
