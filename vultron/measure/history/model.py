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
"""The case event record and the case event history (CEH-03).

One :class:`CaseEvent` reports one CVD event: what happened, whom it belongs
to, which ledger entry recorded it, both clocks of that entry, and the data
gaps that bound what a measure built on it can claim.  The record refuses a
missing or misplaced field at construction (CEH-03-001).

The six case-state events (``V``, ``F``, ``D``, ``P``, ``X``, ``A``) are named
by :class:`~vultron.core.states.cs_invariants.CSEvent`, the vocabulary the
case-state history validator reads; :class:`EventKind` names every other
event, so no case-state event has a second name.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    computed_field,
    model_validator,
)

from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.states.rm import RM
from vultron.measure.ledger import Dimension, LedgerSource, UnusableRow
from vultron.primitives import NonEmptyString


class EventKind(StrEnum):
    """Every CVD event a case records that is not a case-state event.

    Together with :class:`CSEvent` this is the closed enumeration of event
    kinds (CEH-03-002); :data:`CaseEventKind` is the union.
    """

    #: A participant's report management enters ``RM.RECEIVED``.
    REPORT_RECEIVED = "report_received"
    #: ... enters ``RM.INVALID``.
    REPORT_INVALID = "report_invalid"
    #: ... enters ``RM.VALID``.
    REPORT_VALID = "report_valid"
    #: ... enters ``RM.DEFERRED``.
    REPORT_DEFERRED = "report_deferred"
    #: ... enters ``RM.ACCEPTED``.
    REPORT_ACCEPTED = "report_accepted"
    #: ... enters ``RM.CLOSED``.
    REPORT_CLOSED = "report_closed"
    #: A participant accepted its invitation to the case (CEH-04-010).
    JOINED = "joined"
    #: A participant agreed to one embargo register entry (CEH-04-008).
    CONSENT_AGREED = "consent_agreed"
    #: A participant declined one embargo register entry.
    CONSENT_DECLINED = "consent_declined"
    #: A participant's invitation to one embargo register entry timed out.
    CONSENT_TIMED_OUT = "consent_timed_out"
    #: An embargo register entry went into force on the case (CEH-04-005).
    EMBARGO_START = "embargo_start"
    #: The embargo in force ended (CEH-04-005, CEH-04-006).
    EMBARGO_EXIT = "embargo_exit"


#: The closed enumeration of event kinds (CEH-03-002).
CaseEventKind = EventKind | CSEvent

#: The report-management event each RM state entered yields (CEH-04-002).
#: ``RM.START`` is the state before any report, so entering it is no event.
RM_EVENT_KINDS: dict[RM, EventKind] = {
    RM.RECEIVED: EventKind.REPORT_RECEIVED,
    RM.INVALID: EventKind.REPORT_INVALID,
    RM.VALID: EventKind.REPORT_VALID,
    RM.DEFERRED: EventKind.REPORT_DEFERRED,
    RM.ACCEPTED: EventKind.REPORT_ACCEPTED,
    RM.CLOSED: EventKind.REPORT_CLOSED,
}

CONSENT_KINDS: frozenset[EventKind] = frozenset(
    {
        EventKind.CONSENT_AGREED,
        EventKind.CONSENT_DECLINED,
        EventKind.CONSENT_TIMED_OUT,
    }
)
EMBARGO_KINDS: frozenset[EventKind] = frozenset(
    {EventKind.EMBARGO_START, EventKind.EMBARGO_EXIT}
)

#: The kinds that belong to the case rather than to one participant: the
#: public state and the embargo (SDO-03-001, ADR-0122).
CASE_KINDS: frozenset[CaseEventKind] = frozenset(
    {CSEvent.P, CSEvent.X, CSEvent.A, *EMBARGO_KINDS}
)


class EventScope(StrEnum):
    """Whom an event belongs to (CEH-03-003, CEH-03-004)."""

    PARTICIPANT = "participant"
    CASE = "case"


def scope_of(kind: CaseEventKind) -> EventScope:
    """Return whether events of *kind* belong to the case or a participant."""
    return EventScope.CASE if kind in CASE_KINDS else EventScope.PARTICIPANT


class GapLabel(StrEnum):
    """A data gap that changes what an event's time means (CEH-03-010).

    ``docs/topics/measuring_cvd/what_a_case_records.md`` § "Data gaps"
    describes each one.
    """

    #: The creation sequence committed the status, so its stamp is the
    #: creation time, not the event's (CEH-03-011, CM-14-009, CM-14-012).
    SEATED_AT_CREATION = "seated_at_creation"
    #: The case's public state changed when the CASE_MANAGER adopted it, not
    #: when a participant first reported it (CEH-03-012).
    STAMPED_AT_ADOPTION = "stamped_at_adoption"
    #: A passing deadline caused the change, and the CASE_MANAGER made it
    #: when it next handled the case (CEH-03-013, EMB-13-003, CM-28-015).
    STAMPED_WHEN_NEXT_HANDLED = "stamped_when_next_handled"
    #: The event happened outside the protocol, and the delay before it was
    #: reported is not recorded (CEH-03-014).
    REPORTED_OUT_OF_BAND = "reported_out_of_band"


class CaseEvent(BaseModel):
    """One CVD event, derived from one case ledger entry (CEH-03).

    Fields:
        kind: What happened (CEH-03-002).
        participant: The actor the event belongs to; ``None`` exactly when
            the event belongs to the case (CEH-03-003, CEH-03-004).
        semantic_type: The semantic type of the entry that caused the event
            (CEH-03-009).
        log_index: The causing entry's log index (CEH-03-005).
        committed_at: The entry's commit stamp, from the CASE_MANAGER's
            clock (CEH-03-006, CLP-14-002).
        claimed_at: The time the entry's activity claims, from its sender's
            clock, or ``None`` when the activity states none.  Never a copy
            of the commit stamp (CEH-03-007, CEH-03-008).
        gaps: Every data gap that applies, in enumeration order
            (CEH-03-010).
        deadline: A deadline the ledger states that bounds the event's real
            time better than its stamp (CEH-03-015).
        embargo_id: The embargo register entry a consent answer answers, or
            the embargo that started or ended (CEH-04-009).  Required on
            those kinds and absent on every other.
        replaces_embargo_id: For an embargo start, the embargo that was in
            force until this one replaced it, as a revision does.
        exit_reason: For an embargo exit, whether the embargo reached its
            end time or ended early (CEH-04-006).  Required there and absent
            on every other kind.
        exit_cause: For an embargo exit, the structured cause the entry
            records, as recorded (CEH-04-007).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: CaseEventKind
    participant: NonEmptyString | None = None
    semantic_type: MessageSemantics
    log_index: int = Field(ge=0)
    committed_at: datetime
    claimed_at: datetime | None = None
    gaps: list[GapLabel] = Field(default_factory=list)
    deadline: datetime | None = None
    embargo_id: NonEmptyString | None = None
    replaces_embargo_id: NonEmptyString | None = None
    exit_reason: TerminationReason | None = None
    exit_cause: dict[str, JsonValue] | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def scope(self) -> EventScope:
        """Whether the event belongs to the case or to :attr:`participant`."""
        return scope_of(self.kind)

    @model_validator(mode="after")
    def _fields_match_kind(self) -> CaseEvent:
        """Refuse a field missing for, or foreign to, the event's kind."""
        problems = [
            *self._subject_problems(),
            *self._embargo_problems(),
        ]
        if len(set(self.gaps)) != len(self.gaps):
            problems.append("a gap label is listed twice")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _subject_problems(self) -> list[str]:
        """A participant event names its participant; a case event none."""
        if scope_of(self.kind) is EventScope.PARTICIPANT:
            if self.participant is None:
                return ["a participant event must name its participant"]
        elif self.participant is not None:
            return ["a case event must not name a participant"]
        return []

    def _embargo_problems(self) -> list[str]:
        """The embargo fields appear exactly on the kinds that carry them."""
        kind = self.kind
        problems: list[str] = []
        needs_embargo = kind in CONSENT_KINDS or kind in EMBARGO_KINDS
        if needs_embargo and self.embargo_id is None:
            problems.append(f"a {kind} event must name its embargo")
        if not needs_embargo and self.embargo_id is not None:
            problems.append(f"a {kind} event names no embargo")
        if kind is EventKind.EMBARGO_EXIT:
            if self.exit_reason is None:
                problems.append("an embargo exit must carry its reason")
        elif self.exit_reason is not None or self.exit_cause is not None:
            problems.append("only an embargo exit carries a reason or cause")
        if (
            kind is not EventKind.EMBARGO_START
            and self.replaces_embargo_id is not None
        ):
            problems.append("only an embargo start replaces an embargo")
        return problems


class ExcludedState(BaseModel):
    """A state an entry named behind the state already reached (CEH-04-016).

    No event is emitted for it (CEH-04-015); it is reported so a caller can
    judge the history, as a merge reports its holes.

    Fields:
        log_index: The entry naming the state.
        semantic_type: That entry's semantic type, as written.
        participant: The participant the state belongs to, or ``None`` for
            the case's public state.
        dimension: The state dimension.
        named: The state the entry named.
        reached: The state already reached, which the history keeps.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    log_index: int = Field(ge=0)
    semantic_type: NonEmptyString
    participant: NonEmptyString | None = None
    dimension: Dimension
    named: NonEmptyString
    reached: NonEmptyString


class UnreadableEntry(BaseModel):
    """A placed ledger entry the history could derive nothing from.

    Fields:
        log_index: The entry.
        reason: What it lacks: a commit stamp, a known semantic type, or a
            termination reason on an embargo exit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    log_index: int = Field(ge=0)
    reason: NonEmptyString


class CaseEventHistory(BaseModel):
    """One case's CVD events, in log-index order (CEH-04-011).

    Fields:
        case_id: The case.
        source: Whether the entries were one complete copy or a merge of
            replicas (CEH-02-004, CEH-02-005).
        end_confirmed: Whether the entries prove nothing follows the last
            one (``vultron.measure.ledger.ends``).
        missing_log_indices: Indices no copy supplied; a measure over a
            history with a hole is wrong, not imprecise (CEH-02-006).
        conflicting_log_indices: Indices at which the copies disagree.
        unusable_rows: Rows naming this case that could not be placed.
        events: The events, ordered by log index, and within one entry in
            the order the entry records them (CEH-04-011, CEH-04-012).
        excluded: Every state named behind the state already reached
            (CEH-04-016).
        unreadable_entries: Every entry that yielded nothing because it
            lacked a field the derivation needs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    source: LedgerSource
    end_confirmed: bool
    missing_log_indices: list[int] = Field(default_factory=list)
    conflicting_log_indices: list[int] = Field(default_factory=list)
    unusable_rows: list[UnusableRow] = Field(default_factory=list)
    events: list[CaseEvent] = Field(default_factory=list)
    excluded: list[ExcludedState] = Field(default_factory=list)
    unreadable_entries: list[UnreadableEntry] = Field(default_factory=list)

    def of_kind(self, *kinds: CaseEventKind) -> list[CaseEvent]:
        """The events of any of *kinds*, in history order."""
        return [event for event in self.events if event.kind in kinds]

    def for_participant(self, participant: str) -> list[CaseEvent]:
        """The events that belong to *participant*, in history order."""
        return [e for e in self.events if e.participant == participant]


class CaseEventHistories(BaseModel):
    """The event history of every case in the ledger files a caller named.

    Fields:
        histories: One :class:`CaseEventHistory` per case id, in case-id
            order (CEH-02-007).
        unusable_rows: Every row that could not be parsed or placed in a
            case (CEH-02-008).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    histories: dict[str, CaseEventHistory] = Field(default_factory=dict)
    unusable_rows: list[UnusableRow] = Field(default_factory=list)
