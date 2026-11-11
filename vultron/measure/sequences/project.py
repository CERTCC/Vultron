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
"""Project a case event history onto per-vendor case-state sequences (CEH-05).

The projection is keyed on the vendor-awareness event, never on a role
(CEH-05-001): a participant whose events include ``V`` gets one sequence
holding its own fix-path and deployment events and the case's public-state
events, in event-history order (CEH-05-003), except that a late
public-awareness event is placed right after exploit publication and a late
vendor-awareness event right after public awareness (CEH-05-009).  Every
other participant is reported with the reason it has none (CEH-05-007).

The sequence is the deliverable; nothing here scores it (CEH-05-008).  The
history's own holes (``missing_log_indices``, ``end_confirmed``) are the
caller's to judge, as for any measure built on the history.
"""

from __future__ import annotations

from pydantic import ValidationError

from vultron.core.states.cs_invariants import CSEvent
from vultron.measure.history import CaseEvent, CaseEventHistory, EventScope
from vultron.measure.sequences.model import (
    PLACEMENT_RULES,
    CaseStateSequence,
    CaseStateSequences,
    Placement,
    SequenceEvent,
    UnprojectableParticipant,
    UnprojectableReason,
)


def _is_case_state(event: CaseEvent) -> bool:
    return isinstance(event.kind, CSEvent)


def _participants(history: CaseEventHistory) -> list[str]:
    """Every participant of *history*, in first-event order."""
    return list(
        dict.fromkeys(
            event.participant
            for event in history.events
            if event.participant is not None
        )
    )


def _project_one(
    history: CaseEventHistory, participant: str
) -> CaseStateSequence | UnprojectableParticipant:
    """The sequence of *participant*, or the reason it has none."""
    own = [
        event
        for event in history.for_participant(participant)
        if _is_case_state(event)
    ]
    if not own:
        return UnprojectableParticipant(
            participant=participant,
            reason=UnprojectableReason.NO_CASE_STATE_EVENTS,
            detail="it has no fix-path or deployment event of its own",
        )
    if not any(event.kind is CSEvent.V for event in own):
        held = ", ".join(f"{e.kind} at log index {e.log_index}" for e in own)
        return UnprojectableParticipant(
            participant=participant,
            reason=UnprojectableReason.NO_VENDOR_AWARENESS,
            detail=(
                f"it holds {held} but no vendor-awareness event, and the"
                " case-state model has no state for a fix path that does not"
                " start with vendor awareness (CSB-15-004)"
            ),
        )
    events = [
        event
        for event in history.events
        if _is_case_state(event)
        and (
            event.participant == participant or event.scope is EventScope.CASE
        )
    ]
    try:
        return CaseStateSequence(
            participant=participant, events=_place_coupled_events(events)
        )
    except ValidationError as exc:
        return UnprojectableParticipant(
            participant=participant,
            reason=UnprojectableReason.NOT_A_VALID_PREFIX,
            detail="; ".join(_messages(exc)),
        )


def _place_coupled_events(events: list[CaseEvent]) -> list[SequenceEvent]:
    """Place each coupled event the ledger records late (CEH-05-009).

    The model couples exploit publication to public awareness and public
    awareness to vendor awareness, because ``pX`` and ``vP`` are transient
    (CSB-17-003).  A ``P`` recorded after ``X`` with another event between
    them is placed immediately after ``X``; then a ``V`` recorded after that
    ``P`` with another event between them is placed immediately after ``P``.
    The order composes: ``X, V, P`` becomes ``X, P, V``.  Every event keeps
    its recorded log index and clocks, and every other event stays where the
    history put it.
    """
    members = [SequenceEvent(event=event) for event in events]
    for placement, (kind, after) in PLACEMENT_RULES.items():
        members = _place(members, kind, after, placement)
    return members


def _place(
    members: list[SequenceEvent],
    kind: CSEvent,
    after: CSEvent,
    placement: Placement,
) -> list[SequenceEvent]:
    """Move *kind* to directly after *after* when something lies between."""
    kinds = [member.kind for member in members]
    if kind not in kinds or after not in kinds:
        return members
    anchor, found = kinds.index(after), kinds.index(kind)
    if found <= anchor + 1:
        return members
    moved = members.pop(found)
    members.insert(
        anchor + 1, SequenceEvent(event=moved.event, placement=placement)
    )
    return members


def _messages(exc: ValidationError) -> list[str]:
    """The validator's own words, without pydantic's ``Value error,``."""
    return [
        str(error["msg"]).removeprefix("Value error, ")
        for error in exc.errors()
    ]


def case_state_sequences(history: CaseEventHistory) -> CaseStateSequences:
    """Project *history* onto one case-state sequence per vendor (CEH-05).

    Args:
        history: One case's event history, from
            :func:`vultron.measure.history.case_event_history`.

    Returns:
        The sequence of every participant whose events include a
        vendor-awareness event and replay as a case-state history prefix,
        ordered by that event; every other participant of the history is in
        ``unprojectable`` with its reason.  No sequence is case-wide.
    """
    sequences: list[CaseStateSequence] = []
    unprojectable: list[UnprojectableParticipant] = []
    for participant in _participants(history):
        result = _project_one(history, participant)
        if isinstance(result, CaseStateSequence):
            sequences.append(result)
        else:
            unprojectable.append(result)
    sequences.sort(key=lambda sequence: sequence.awareness_index)
    return CaseStateSequences(
        case_id=history.case_id,
        sequences=sequences,
        unprojectable=unprojectable,
    )
