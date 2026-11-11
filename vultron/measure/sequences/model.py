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
events (CEH-05-001, CEH-05-003).  It refuses at construction anything the
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

from vultron.core.states.cs_invariants import (
    CSEvent,
    is_valid_cs_history_prefix,
)
from vultron.measure.history import CaseEvent, EventScope
from vultron.primitives import NonEmptyString


class CaseStateSequence(BaseModel):
    """One vendor's case-state events, in log order (CEH-05-001).

    Fields:
        participant: The vendor the sequence belongs to.
        events: The vendor's own ``V``, ``F`` and ``D`` events and the case's
            ``P``, ``X`` and ``A`` events, in event-history order.  Each keeps
            its log index, clocks and gap labels.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    participant: NonEmptyString
    events: list[CaseEvent] = Field(min_length=1)

    @property
    def kinds(self) -> tuple[CSEvent, ...]:
        """The sequence as the case-state history validator reads it."""
        return tuple(CSEvent(event.kind) for event in self.events)

    @model_validator(mode="after")
    def _is_a_valid_prefix(self) -> CaseStateSequence:
        """Refuse a foreign event, a disorder, or a non-replaying compound."""
        problems: list[str] = []
        for event in self.events:
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
        indices = [event.log_index for event in self.events]
        if indices != sorted(indices):
            problems.append("the events are not in log order")
        if problems:
            raise ValueError("; ".join(problems))
        if CSEvent.V not in self.kinds:
            problems.append("the events include no vendor-awareness event")
        elif not is_valid_cs_history_prefix(self.kinds):
            problems.append(
                f"{''.join(self.kinds)} is not a valid case-state history"
                " prefix"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self


class UnprojectableReason(StrEnum):
    """Why a participant has no case-state sequence (CEH-05-007)."""

    #: The participant has no fix-path or deployment event of its own.
    NO_CASE_STATE_EVENTS = "no_case_state_events"
    #: The participant has a fix-path or deployment event but no
    #: vendor-awareness event, as a Deployer without the Vendor role does
    #: (CSB-15-004).  The case-state model has no state for it.
    NO_VENDOR_AWARENESS = "no_vendor_awareness"
    #: The participant's events combined with the case's public-state events
    #: do not replay as a case-state history prefix (CEH-05-004).
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
            vendor-awareness event, in the order of those events.
        unprojectable: Every other participant of the history, in
            first-event order, with the reason it has no sequence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    sequences: list[CaseStateSequence] = Field(default_factory=list)
    unprojectable: list[UnprojectableParticipant] = Field(default_factory=list)

    def for_participant(self, participant: str) -> CaseStateSequence | None:
        """The sequence of *participant*, or ``None`` when it has none."""
        for sequence in self.sequences:
            if sequence.participant == participant:
                return sequence
        return None
