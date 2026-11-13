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
events, in event-history order (CEH-05-003), except where a transient state
forces one next event the record does not take: the projection takes it,
moving the recorded event or implying one (CEH-05-009).  Every
other participant is reported with the reason it has none (CEH-05-007).

The sequence is the deliverable; nothing here scores it (CEH-05-008).  The
history's own holes (``missing_log_indices``, ``end_confirmed``) are the
caller's to judge, as for any measure built on the history.
"""

from __future__ import annotations

from pydantic import ValidationError

from vultron.core.states.cs import CS
from vultron.core.states.cs_invariants import (
    CSEvent,
    apply_cs_event,
    required_next_cs_events,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.measure.history import (
    CaseEvent,
    CaseEventHistory,
    EventScope,
    scope_of,
)
from vultron.measure.sequences.model import (
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
    members = _take_forced_ways_out(events, participant)
    try:
        return CaseStateSequence(participant=participant, events=members)
    except ValidationError as exc:
        return UnprojectableParticipant(
            participant=participant,
            reason=UnprojectableReason.NOT_A_VALID_PREFIX,
            detail="; ".join(_messages(exc)),
        )


def _take_forced_ways_out(
    events: list[CaseEvent], participant: str
) -> list[SequenceEvent]:
    """Take each transient state's one way out where the record does not.

    Replaying the recorded order, a state that ``required_next_cs_events``
    says forces one next event (``pX`` forces ``P``, ``vP`` forces ``V``,
    CSB-17-003) is followed by that event: the recorded one, moved up when the
    ledger records it later, or an implied one when it records it nowhere
    (CEH-05-009).  So ``P, X, V`` becomes ``P, V, X``, ``X, V, P`` becomes
    ``X, P, V``, and ``V, X, A`` becomes ``V, X, P, A``.  Every recorded event
    keeps its log index and clocks; an order that does not replay is left
    for the sequence model to refuse.
    """
    pending = [SequenceEvent(event=event) for event in events]
    placed: list[SequenceEvent] = []
    state = CS.vfdpxa
    while pending:
        member = _next_member(pending, placed, state, participant)
        placed.append(member)
        try:
            state = apply_cs_event(state, member.kind)
        except VultronValidationError, VultronInvalidStateTransitionError:
            return [*placed, *pending]
    return placed


def _next_member(
    pending: list[SequenceEvent],
    placed: list[SequenceEvent],
    state: CS,
    participant: str,
) -> SequenceEvent:
    """Take the member that comes after *state* off *pending*."""
    forced = required_next_cs_events(state)
    if len(forced) != 1 or pending[0].kind in forced:
        return pending.pop(0)
    (kind,) = forced
    for i, member in enumerate(pending):
        if member.kind is kind:
            return SequenceEvent(
                event=pending.pop(i).event, placement=Placement.MOVED
            )
    return SequenceEvent(
        event=_implied(kind, placed[-1].event, participant),
        placement=Placement.IMPLIED,
    )


def _implied(kind: CSEvent, cause: CaseEvent, participant: str) -> CaseEvent:
    """An event of *kind* on *cause*'s entry, with its clocks and gap labels.

    *participant* owns it when *kind* belongs to a participant.
    """
    fields = cause.model_dump(exclude={"scope"})
    fields["kind"] = kind
    fields["participant"] = (
        None if scope_of(kind) is EventScope.CASE else participant
    )
    return CaseEvent.model_validate(fields)


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
