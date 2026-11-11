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
"""Per-vendor case-state sequences and the participants with none (CEH-05).

A :class:`CaseStateSequence` is one vendor's case-state events, in log order:
its own fix-path and deployment events combined with the case's public-state
events (CEH-05-001, CEH-05-003).  Each member is a :class:`SequenceEvent`, the
history's event plus its :class:`Placement`: where a transient state forces
one next event and the ledger records it later, it is moved there, and where
the ledger records it nowhere, it is implied there (CEH-05-009, CSB-17-003).
It refuses at construction anything the case-state history validator would
not replay as a prefix (CEH-05-002, CEH-05-004), so a held sequence is always
a valid, possibly incomplete, prefix (CEH-05-005).

A participant with no sequence is an :class:`UnprojectableParticipant`, with
the reason (CEH-05-007).  :class:`CaseStateSequences` holds both, and holds no
case-wide sequence: several vendors are never combined into one (CEH-05-006).
Nothing here is a score (CEH-05-008).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.states.cs import CS
from vultron.core.states.cs_invariants import (
    CSEvent,
    apply_cs_event,
    replay_cs_history,
    required_next_cs_events,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.measure.history import CaseEvent, CaseEventKind, EventScope
from vultron.primitives import NonEmptyString


class Placement(StrEnum):
    """Where a sequence member sits relative to what the ledger records.

    Two case states are transient and force one next event: ``pX`` (exploit
    public, public unaware) forces ``P``, and ``vP`` (public aware, vendor
    unaware) forces ``V`` (CSB-17-003, ``required_next_cs_events``).  When the
    recorded order does not take that way out, the projection does
    (CEH-05-009).
    """

    #: Recorded, and in the order the event history records it.
    RECORDED = "recorded"
    #: Recorded later; placed where the transient state before it forces it.
    MOVED = "moved"
    #: Recorded nowhere; forced by the transient state the previous member
    #: reached, and carrying that member's log index and clocks.
    IMPLIED = "implied"


class SequenceEvent(BaseModel):
    """One member of a projected sequence: a history event and where it sits.

    Fields:
        event: The event from the case event history, unchanged: its kind,
            log index, clocks and gap labels are the recorded ones.
            An ``IMPLIED`` member's event is not in the history: it is the
            forced kind with the previous member's other fields.
        placement: Whether the event is recorded in place, recorded later and
            moved, or implied (CEH-05-009).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event: CaseEvent
    placement: Placement = Placement.RECORDED

    @property
    def kind(self) -> CaseEventKind:
        """The event's kind."""
        return self.event.kind

    @property
    def log_index(self) -> int:
        """The recorded log index of the event."""
        return self.event.log_index

    @property
    def is_placed(self) -> bool:
        """Whether the event sits out of its recorded position."""
        return self.placement is not Placement.RECORDED


def _is_recorded_v(member: SequenceEvent) -> bool:
    """Whether *member* is a vendor-awareness event the ledger records.

    An implied ``V`` is forced by the model, never recorded, so it does not
    key a sequence (CEH-05-001).
    """
    return (
        member.kind is CSEvent.V and member.placement is not Placement.IMPLIED
    )


class CaseStateSequence(BaseModel):
    """One vendor's case-state events, in replay order (CEH-05-001).

    Fields:
        participant: The vendor the sequence belongs to.
        events: The vendor's own ``V``, ``F`` and ``D`` events and the case's
            ``P``, ``X`` and ``A`` events, in event-history order, except a
            ``P`` or ``V`` a transient state forces, which sits where it is
            forced and says so (CEH-05-009).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    participant: NonEmptyString
    events: list[SequenceEvent] = Field(min_length=1)

    @property
    def kinds(self) -> tuple[CSEvent, ...]:
        """The sequence as the case-state history validator reads it."""
        return tuple(CSEvent(member.kind) for member in self.events)

    @property
    def awareness_index(self) -> int:
        """The recorded log index of the vendor's vendor-awareness event.

        Only a recorded (or moved) ``V`` counts: an implied one borrows the
        log index of the event before it.
        """
        return next(m.log_index for m in self.events if _is_recorded_v(m))

    @property
    def placed(self) -> tuple[SequenceEvent, ...]:
        """The members moved or implied (CEH-05-009)."""
        return tuple(m for m in self.events if m.is_placed)

    @model_validator(mode="after")
    def _is_a_valid_prefix(self) -> CaseStateSequence:
        """Refuse a foreign event, a disorder, or a non-replaying compound.

        Every violation is named (EH-07-001).  The replay runs only when every
        member is a case-state event: over a foreign one it would report the
        foreign value again rather than an ordering problem.
        """
        problems: list[str] = []
        for member in self.events:
            event = member.event
            if not isinstance(event.kind, CSEvent):
                problems.append(f"{event.kind} is not a case-state event")
            elif (
                event.scope is EventScope.PARTICIPANT
                and event.participant != self.participant
            ):
                problems.append(
                    f"the {event.kind} event at log index {event.log_index}"
                    f" belongs to {event.participant}, not {self.participant}"
                )
        problems.extend(self._order_problems())
        kinds = [member.kind for member in self.events]
        if not any(_is_recorded_v(member) for member in self.events):
            problems.append(
                "the events include no vendor-awareness event the ledger"
                " records"
            )
        if all(isinstance(kind, CSEvent) for kind in kinds):
            try:
                replay_cs_history(kinds)
            except (
                VultronValidationError,
                VultronInvalidStateTransitionError,
            ) as exc:
                problems.append(
                    f"{''.join(kinds)} is not a valid case-state history"
                    f" prefix: {exc}"
                )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _order_problems(self) -> list[str]:
        """Recorded members keep log order, and each moved or implied member
        is the one event the state before it forces (CEH-05-009)."""
        problems: list[str] = []
        recorded = [m.log_index for m in self.events if not m.is_placed]
        if recorded != sorted(recorded):
            problems.append("the events are not in log order")
        state = CS.vfdpxa
        for i, member in enumerate(self.events):
            if not isinstance(member.kind, CSEvent):
                return problems
            if member.is_placed:
                problems.extend(self._placement_problems(i, state))
            try:
                state = apply_cs_event(state, member.kind)
            except (
                VultronValidationError,
                VultronInvalidStateTransitionError,
            ):
                return problems
        return problems

    def _placement_problems(self, i: int, state: CS) -> list[str]:
        """What is wrong with the moved or implied member at *i*."""
        member = self.events[i]
        label = f"{member.kind} {member.placement}"
        problems: list[str] = []
        if member.kind not in required_next_cs_events(state):
            problems.append(f"{label} is not forced by {state.name}")
        if member.placement is Placement.MOVED and not any(
            later.placement is not Placement.IMPLIED
            and later.log_index <= member.log_index
            for later in self.events[i + 1 :]
        ):
            problems.append(
                f"{label} must come before an event recorded no later than"
                " itself"
            )
        if member.placement is Placement.IMPLIED:
            previous = self.events[i - 1].event if i else None
            if (
                previous is None
                or member.log_index != previous.log_index
                or member.event.committed_at != previous.committed_at
                or member.event.claimed_at != previous.claimed_at
            ):
                problems.append(
                    f"{label} must carry the log index and clocks of the"
                    " event before it"
                )
        return problems


class UnprojectableReason(StrEnum):
    """Why a participant has no case-state sequence (CEH-05-007)."""

    #: The participant has no fix-path or deployment event of its own.
    NO_CASE_STATE_EVENTS = "no_case_state_events"
    #: The participant has a fix-path or deployment event but no
    #: vendor-awareness event, as a Deployer without the Vendor role does
    #: (CSB-15-004).  The case-state model has no state for it.
    NO_VENDOR_AWARENESS = "no_vendor_awareness"
    #: The participant's events combined with the case's public-state events
    #: do not replay as a case-state history prefix even after the coupled
    #: events are placed (CEH-05-004, CEH-05-009).  The placements make every
    #: order of one vendor's and the case's events replay, so only an entry a
    #: CASE_MANAGER would refuse reaches it, such as a fix deployed before it
    #: is ready.
    NOT_A_VALID_PREFIX = "not_a_valid_prefix"


class UnprojectableParticipant(BaseModel):
    """A participant the projection yields no sequence for (CEH-05-007).

    Its events stay in the event history, where a measure that needs no
    replayable sequence reads them.

    Fields:
        participant: The participant.
        reason: Why it has no sequence.
        detail: The reason in words, naming the events involved.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    participant: NonEmptyString
    reason: UnprojectableReason
    detail: NonEmptyString


class CaseStateSequences(BaseModel):
    """One case's per-vendor case-state sequences (CEH-05).

    There is deliberately no case-wide sequence: which vendor's events stand
    for the case is an open question (CEH-05-006, #5143).

    Fields:
        case_id: The case.
        sequences: One sequence per participant whose events include a
            vendor-awareness event that replays, in the order of those
            events.
        unprojectable: Every other participant of the history, in
            first-event order, with the reason it has no sequence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    sequences: list[CaseStateSequence] = Field(default_factory=list)
    unprojectable: list[UnprojectableParticipant] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_answer_per_participant(self) -> CaseStateSequences:
        """Refuse a participant answered twice, or sequences out of order."""
        problems: list[str] = []
        projected = [s.participant for s in self.sequences]
        reported = [u.participant for u in self.unprojectable]
        for label, names in (
            ("projected", projected),
            ("reported unprojectable", reported),
        ):
            twice = sorted({n for n in names if names.count(n) > 1})
            if twice:
                problems.append(f"{', '.join(twice)} {label} twice")
        both = sorted(set(projected) & set(reported))
        if both:
            problems.append(
                f"{', '.join(both)} both projected and reported unprojectable"
            )
        order = [s.awareness_index for s in self.sequences]
        if order != sorted(order):
            problems.append("the sequences are not in vendor-awareness order")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def for_participant(self, participant: str) -> CaseStateSequence | None:
        """The sequence of *participant*, or ``None`` when it has none."""
        for sequence in self.sequences:
            if sequence.participant == participant:
                return sequence
        return None
