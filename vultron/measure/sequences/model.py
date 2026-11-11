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
history's event plus whether the model placed it: a vendor-awareness event
recorded after public awareness sits immediately after ``P`` (CEH-05-009,
CSB-17-003), keeping its recorded log index and clocks.  It refuses at construction anything the
case-state history validator would not replay as a prefix (CEH-05-002,
CEH-05-004), so a held sequence is always a valid, possibly incomplete,
prefix (CEH-05-005).

A participant with no sequence is an :class:`UnprojectableParticipant`, with
the reason (CEH-05-007).  :class:`CaseStateSequences` holds both, and holds no
case-wide sequence: several vendors are never combined into one (CEH-05-006).
Nothing here is a score (CEH-05-008).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.states.cs_invariants import CSEvent, replay_cs_history
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.measure.history import CaseEvent, CaseEventKind, EventScope
from vultron.primitives import NonEmptyString


class SequenceEvent(BaseModel):
    """One member of a projected sequence: a history event and where it sits.

    Fields:
        event: The event from the case event history, unchanged: its kind,
            log index, clocks and gap labels are the recorded ones.
        placed_at_public_awareness: ``True`` for a vendor-awareness event the
            ledger records after the case's public awareness with a later
            public-state event between them.  The model couples the two: once
            the public is aware the vendor counts as aware at once, because
            the vendor-unaware, public-aware state is transient (CSB-17-003).
            So the sequence places that ``V`` immediately after ``P``, out of
            log order (CEH-05-009).  ``False`` for an event in its recorded
            position.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event: CaseEvent
    placed_at_public_awareness: bool = False

    @property
    def kind(self) -> CaseEventKind:
        """The event's kind."""
        return self.event.kind

    @property
    def log_index(self) -> int:
        """The recorded log index of the event."""
        return self.event.log_index


class CaseStateSequence(BaseModel):
    """One vendor's case-state events, in replay order (CEH-05-001).

    Fields:
        participant: The vendor the sequence belongs to.
        events: The vendor's own ``V``, ``F`` and ``D`` events and the case's
            ``P``, ``X`` and ``A`` events, in event-history order, except a
            ``V`` recorded after public awareness, which sits immediately
            after ``P`` and says so (CEH-05-009).
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
        """The recorded log index of the vendor's vendor-awareness event."""
        return next(m.log_index for m in self.events if m.kind is CSEvent.V)

    @property
    def awareness_placed_at_public_awareness(self) -> bool:
        """Whether the vendor's awareness was placed at public awareness."""
        return any(m.placed_at_public_awareness for m in self.events)

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
        if CSEvent.V not in kinds:
            problems.append("the events include no vendor-awareness event")
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
        """Recorded events keep log order; a placed ``V`` follows ``P`` and
        precedes at least one event recorded no later than itself."""
        problems: list[str] = []
        recorded = [
            m.log_index
            for m in self.events
            if not m.placed_at_public_awareness
        ]
        if recorded != sorted(recorded):
            problems.append("the events are not in log order")
        placed = [
            i
            for i, m in enumerate(self.events)
            if m.placed_at_public_awareness
        ]
        for i in placed:
            member = self.events[i]
            previous = self.events[i - 1] if i > 0 else None
            following = (
                self.events[i + 1] if i + 1 < len(self.events) else None
            )
            if member.kind is not CSEvent.V:
                problems.append(
                    f"only a vendor-awareness event is placed at public"
                    f" awareness, not {member.kind}"
                )
            if previous is None or previous.kind is not CSEvent.P:
                problems.append(
                    "a placed vendor-awareness event must follow public"
                    " awareness"
                )
            if following is None or following.log_index > member.log_index:
                problems.append(
                    "a placed vendor-awareness event must come before an"
                    " event recorded no later than itself"
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
    #: do not replay as a case-state history prefix even after its
    #: awareness is placed at public awareness (CEH-05-004, CEH-05-009).
    #: An exploit recorded before public awareness with the vendor's
    #: awareness between them (``X, V, P``) still lands here.
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
