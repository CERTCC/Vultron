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
"""Derive a case's CVD event history from its ledger (CEH-04).

The entries are walked in log-index order, tracking each participant's
report-management, vendor-fix-path and deployment state and the case's public
state.  Those events come from **state comparison** (CEH-04-001): a status the
history has not seen is compared with the state already reached, and yields
an event for each state it moves forward, nothing for a state already reached
(CEH-04-013), and an exclusion for a state behind it (CEH-04-015,
CEH-04-016).  A status is identified by its ``id``, so a snapshot that carries
a participant's whole status list re-reports nothing it already recorded.

Joining, embargo start and exit, and consent answers move no status
dimension, so they come from the entry's **semantic type and carried object**
(CEH-04-005, CEH-04-010).  ``notes/case-event-history.md`` gives the reasoning.

An inert participant — one the CASE_MANAGER seated when it sent a stub Invite
(CM-11-006) — has not joined, so its seated state is not yet a case event.
Its events wait for the entry recording its acceptance and take that entry
(CEH-04-010); an invitee that refuses or never answers yields no participant
event, only its consent answer.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.cs import CS_pxa
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM, RMDeclaration, classify_rm_declaration
from vultron.measure.history.model import (
    RM_EVENT_KINDS,
    CaseEvent,
    CaseEventHistories,
    CaseEventHistory,
    CaseEventKind,
    EventKind,
    ExcludedState,
    GapLabel,
    UnreadableEntry,
)
from vultron.measure.history.reached import ReachedParticipant, ReachedState
from vultron.measure.history.register import RebuiltRegister
from vultron.measure.history.snapshot import (
    ParticipantRecord,
    member_of,
    parse_time,
    roles_of,
    snapshot_records,
)
from vultron.measure.ledger import (
    CaseLedger,
    Dimension,
    actor_uri,
    case_manager_ids,
    dimension_state,
    first_present,
    log_index_of,
    payload_of,
    read_case_ledgers,
)

logger = logging.getLogger(__name__)

#: The consent answer each answered row state records (CEH-04-008).
_CONSENT_EVENT_KINDS: dict[EmbargoConsentState, EventKind] = {
    EmbargoConsentState.AGREED: EventKind.CONSENT_AGREED,
    EmbargoConsentState.DECLINED: EventKind.CONSENT_DECLINED,
    EmbargoConsentState.TIMED_OUT: EventKind.CONSENT_TIMED_OUT,
}

#: The flags a fix-path or public-state value spells, one letter each, with
#: the case-state event that raises each flag, in the order they are raised.
_VF_FLAGS: tuple[tuple[str, CSEvent], ...] = (
    ("v", CSEvent.V),
    ("f", CSEvent.F),
)
_D_FLAGS: tuple[tuple[str, CSEvent], ...] = (("d", CSEvent.D),)
_PXA_FLAGS: tuple[tuple[str, CSEvent], ...] = (
    ("p", CSEvent.P),
    ("x", CSEvent.X),
    ("a", CSEvent.A),
)

_VENDOR = "VENDOR"
_DEPLOYER = "DEPLOYER"


def _flags(
    value: str, letters: tuple[tuple[str, CSEvent], ...]
) -> tuple[bool, ...] | None:
    """Read a ``vf``/``d``/``pxa`` spelling as raised flags, or ``None``.

    Each letter is lower-case when its flag is down and upper-case when it is
    up, in the fixed order of *letters*.
    """
    if len(value) != len(letters):
        return None
    flags: list[bool] = []
    for char, (letter, _) in zip(value, letters, strict=True):
        if char == letter:
            flags.append(False)
        elif char == letter.upper():
            flags.append(True)
        else:
            return None
    return tuple(flags)


@dataclass
class _Entry:
    """The fields every event derived from one entry shares."""

    log_index: int
    semantic_type: MessageSemantics
    committed_at: datetime
    claimed_at: datetime | None
    creation: bool
    actor: str | None
    payload: dict[str, Any]

    def event(
        self,
        kind: CaseEventKind,
        *,
        participant: str | None = None,
        gaps: Iterable[GapLabel] = (),
        deadline: datetime | None = None,
        embargo_id: str | None = None,
        replaces_embargo_id: str | None = None,
        exit_reason: TerminationReason | None = None,
        exit_cause: dict[str, JsonValue] | None = None,
    ) -> CaseEvent:
        """Build the event of *kind* this entry records."""
        labels = set(gaps)
        if self.creation:
            labels.add(GapLabel.SEATED_AT_CREATION)
        return CaseEvent(
            kind=kind,
            participant=participant,
            semantic_type=self.semantic_type,
            log_index=self.log_index,
            committed_at=self.committed_at,
            claimed_at=self.claimed_at,
            gaps=[label for label in GapLabel if label in labels],
            deadline=deadline,
            embargo_id=embargo_id,
            replaces_embargo_id=replaces_embargo_id,
            exit_reason=exit_reason,
            exit_cause=exit_cause,
        )


@dataclass
class _Participant:
    """What the history has reached for one participant."""

    actor: str
    rm: RM = RM.START
    vf: tuple[bool, ...] = (False, False)
    d: tuple[bool, ...] = (False,)
    roles: set[str] = field(default_factory=set)
    joined: bool = True
    #: Events recorded while inert, emitted when the participant joins.
    held: list[CaseEventKind] = field(default_factory=list)


@dataclass
class _Deriver:
    """Walks one case's entries in log-index order, emitting its events."""

    case_managers: set[str]
    events: list[CaseEvent] = field(default_factory=list)
    excluded: list[ExcludedState] = field(default_factory=list)
    unreadable: list[UnreadableEntry] = field(default_factory=list)
    participants: dict[str, _Participant] = field(default_factory=dict)
    seen_statuses: set[str] = field(default_factory=set)
    seen_case_statuses: set[str] = field(default_factory=set)
    pxa: tuple[bool, ...] = (False, False, False)
    consent: dict[tuple[str, str], EmbargoConsentState] = field(
        default_factory=dict
    )
    rsvp_deadlines: dict[tuple[str, str], datetime] = field(
        default_factory=dict
    )
    end_times: dict[str, datetime] = field(default_factory=dict)
    active_embargo: str | None = None
    started: set[str] = field(default_factory=set)
    exited: set[str] = field(default_factory=set)
    #: Each embargo register entry's status as the ledger's steps leave it.
    register: RebuiltRegister = field(default_factory=RebuiltRegister)

    # -- one entry -----------------------------------------------------

    def read(
        self, entry: Mapping[str, Any], log_index: int, creation: bool
    ) -> None:
        """Derive the events of the entry at *log_index*."""
        context = self._context(entry, log_index, creation)
        if context is None:
            return
        self._acts(context)
        records = snapshot_records(context.payload)
        for _ in range(records.nameless_participants):
            self._unreadable(
                context.log_index, "a participant record names no actor"
            )
        for record in records.participants:
            self._participant_record(context, record)
        for status in records.loose_statuses:
            actor = actor_uri(
                first_present(status, "attributedTo", "attributed_to")
            )
            if actor is None:
                self._unreadable(
                    context.log_index,
                    "a participant status names no participant",
                )
                continue
            self._status(context, self._tracker(actor), status)
        for case_status in records.case_statuses:
            self._case_status(context, case_status)
        for row in records.consents:
            self._consent_row(context, row, None)
        for register_entry in records.register_entries:
            self._register_entry(context, register_entry)

    def _context(
        self, entry: Mapping[str, Any], log_index: int, creation: bool
    ) -> _Entry | None:
        """Read the shared fields of *entry*, or report it unreadable."""
        raw_type = first_present(entry, "semanticType", "semantic_type")
        semantic_type = member_of(MessageSemantics, raw_type)
        if semantic_type is None:
            self._unreadable(log_index, f"unknown semantic type {raw_type!r}")
            return None
        committed_at = parse_time(
            first_present(entry, "published", "receivedAt", "received_at")
        )
        if committed_at is None:
            self._unreadable(log_index, "no commit stamp")
            return None
        payload = payload_of(entry)
        return _Entry(
            log_index=log_index,
            semantic_type=semantic_type,
            committed_at=committed_at,
            claimed_at=parse_time(payload.get("published")),
            creation=creation,
            actor=actor_uri(payload.get("actor")),
            payload=payload,
        )

    def _unreadable(self, log_index: int, reason: str) -> None:
        logger.warning("Ledger entry %d: unreadable: %s", log_index, reason)
        self.unreadable.append(
            UnreadableEntry(log_index=log_index, reason=reason)
        )

    # -- acts keyed on the semantic type (CEH-04-005, CEH-04-010) ------

    def _acts(self, context: _Entry) -> None:
        """Apply the act the entry's semantic type names, when it has one."""
        handler = _ACT_HANDLERS.get(context.semantic_type)
        if handler is not None:
            obj = context.payload.get("object")
            handler(self, context, obj)

    def _on_embargo_terms(self, context: _Entry, obj: object) -> None:
        """A created embargo: keep its end time."""
        self._remember_end_time(obj)

    def _on_proposal(self, context: _Entry, obj: object) -> None:
        """A proposed embargo: keep its end time; a new one is ``PROPOSED``.

        The CASE_MANAGER fans one proposal out as an Invite to each
        participant, so only the first Invite of an embargo opens its entry.
        """
        self._remember_end_time(obj)
        embargo_id = actor_uri(obj)
        if embargo_id is not None:
            self.register.propose(embargo_id)

    def _on_proposal_rejected(self, context: _Entry, obj: object) -> None:
        """The Case Owner's ``Reject(EmbargoEvent)`` of a proposal."""
        embargo_id = actor_uri(obj)
        if embargo_id is not None:
            self.register.reject(embargo_id)

    def _on_invite_undone(self, context: _Entry, invite: object) -> None:
        """The CASE_MANAGER's ``Undo(Invite(EmbargoEvent))``: an abandoned
        proposal is cancelled (EMB-16-001)."""
        embargo_id = _invitee(invite)
        if embargo_id is not None:
            self.register.cancel(embargo_id)

    def _on_activation(self, context: _Entry, obj: object) -> None:
        self._remember_end_time(obj)
        embargo_id = actor_uri(obj)
        if embargo_id is not None:
            self._activate(context, embargo_id)

    def _on_termination(self, context: _Entry, obj: object) -> None:
        self._exit(context, obj)

    def _on_stub_accept(self, context: _Entry, invite: object) -> None:
        invitee = _invitee(invite) or context.actor
        if invitee is not None:
            self._join(context, invitee, invite)

    def _on_stub_reject(self, context: _Entry, invite: object) -> None:
        """A refused stub Invite declines the embargo in force (CM-11-007)."""
        invitee = _invitee(invite) or context.actor
        embargo_id = self._embargo_of_stub(invite)
        if invitee is not None and embargo_id is not None:
            self._answer(
                context, invitee, embargo_id, EmbargoConsentState.DECLINED
            )

    def _on_embargo_reply(self, context: _Entry, invite: object) -> None:
        """A participant's ``Accept`` or ``Reject`` of an embargo Invite."""
        embargo_id = _invitee(invite)
        if context.actor is None or embargo_id is None:
            self._unreadable(
                context.log_index,
                "an embargo reply names no embargo or sender",
            )
            return
        state = (
            EmbargoConsentState.AGREED
            if context.semantic_type
            is MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE
            else EmbargoConsentState.DECLINED
        )
        self._answer(context, context.actor, embargo_id, state)

    def _embargo_of_stub(self, invite: object) -> str | None:
        """The embargo in force when a stub Invite is answered (CM-11-001).

        The history's own record of the register wins, since the embargo the
        Invite named may have ended before the answer; the Invite's
        ``activeEmbargo`` is read only when the history has seen no embargo
        start or end, as in a merge missing the genesis entry.
        """
        if self.started or self.exited:
            return self.active_embargo
        if isinstance(invite, dict):
            target = invite.get("target")
            if isinstance(target, dict):
                return actor_uri(
                    first_present(target, "activeEmbargo", "active_embargo")
                )
        return None

    def _join(self, context: _Entry, invitee: str, invite: object) -> None:
        """An accepted stub Invite: the invitee joins (CEH-04-010, CM-11-001).

        The joining event comes first, then every event held while the
        invitee was inert, then the consent to the embargo in force that
        joining implies unless the invitee had declined it.
        """
        tracker = self._tracker(invitee)
        self.events.append(
            context.event(EventKind.JOINED, participant=invitee)
        )
        self._release(context, tracker)
        embargo_id = self._embargo_of_stub(invite)
        if embargo_id is not None:
            self._agree_unless_declined(context, invitee, embargo_id)

    def _release(self, context: _Entry, tracker: _Participant) -> None:
        """Mark *tracker* joined and emit its held events at *context*."""
        tracker.joined = True
        held, tracker.held = tracker.held, []
        for kind in held:
            self.events.append(context.event(kind, participant=tracker.actor))

    # -- embargo start and exit ----------------------------------------

    def _remember_end_time(self, embargo: object) -> None:
        if not isinstance(embargo, dict):
            return
        embargo_id = actor_uri(embargo)
        end_time = parse_time(first_present(embargo, "endTime", "end_time"))
        if embargo_id is not None and end_time is not None:
            self.end_times[embargo_id] = end_time

    def _start(self, context: _Entry, embargo_id: str) -> None:
        """An embargo register entry goes into force, once (CEH-04-005)."""
        if embargo_id in self.started:
            return
        self.started.add(embargo_id)
        replaced = self.active_embargo
        self.register.activate(embargo_id)
        self.events.append(
            context.event(
                EventKind.EMBARGO_START,
                embargo_id=embargo_id,
                replaces_embargo_id=replaced
                if replaced != embargo_id
                else None,
            )
        )
        self.active_embargo = embargo_id

    def _activate(self, context: _Entry, embargo_id: str) -> None:
        """The Case Owner's activation of a proposal, and its consent effect.

        Activation is the owner's decision, so the owner's row becomes
        ``AGREED``; and when the new embargo replaces one that ends no
        earlier, every signatory of the replaced embargo agrees to the new
        one by containment (CM-10-001, EP-05-001).
        """
        replaced = self.active_embargo
        self._start(context, embargo_id)
        if context.actor is not None:
            self._agree_unless_declined(context, context.actor, embargo_id)
        if replaced is None or replaced == embargo_id:
            return
        old_end = self.end_times.get(replaced)
        new_end = self.end_times.get(embargo_id)
        if old_end is None or new_end is None or new_end > old_end:
            return
        signatories = [
            participant
            for (participant, answered), state in self.consent.items()
            if answered == replaced and state is EmbargoConsentState.AGREED
        ]
        for participant in signatories:
            self._agree_unless_declined(context, participant, embargo_id)

    def _agree_unless_declined(
        self, context: _Entry, participant: str, embargo_id: str
    ) -> None:
        """Record an implied ``AGREED``, which never overrides a refusal."""
        if (
            self.consent.get((participant, embargo_id))
            is not EmbargoConsentState.DECLINED
        ):
            self._answer(
                context, participant, embargo_id, EmbargoConsentState.AGREED
            )

    def _exit(self, context: _Entry, embargo: object) -> None:
        """A termination ``Remove(EmbargoEvent)`` (CEH-04-006, CEH-04-007).

        The reason is the ``content`` (EMB-13-004) and the cause the
        ``terminationCause``, carried as recorded.  An exit at the end time
        carries the end time as its bounding deadline (CEH-03-015), and,
        when the CASE_MANAGER committed it, the stamped-when-next-handled
        label (CEH-03-013), whichever path reached it: the ledger records the
        lazy check and an outside request alike.
        """
        self._remember_end_time(embargo)
        embargo_id = actor_uri(embargo) or self.active_embargo
        if embargo_id is None:
            self._unreadable(
                context.log_index, "embargo exit names no embargo"
            )
            return
        if embargo_id in self.exited:
            return
        reason = member_of(TerminationReason, context.payload.get("content"))
        if reason is None:
            self._unreadable(
                context.log_index, "embargo exit carries no termination reason"
            )
            return
        self.exited.add(embargo_id)
        self.register.terminate(embargo_id)
        cause = first_present(
            context.payload, "terminationCause", "termination_cause"
        )
        at_end_time = reason is TerminationReason.END_TIME_REACHED
        lazy = at_end_time and context.actor in self.case_managers
        self.events.append(
            context.event(
                EventKind.EMBARGO_EXIT,
                embargo_id=embargo_id,
                exit_reason=reason,
                exit_cause=cause if isinstance(cause, dict) else None,
                deadline=self.end_times.get(embargo_id)
                if at_end_time
                else None,
                gaps=[GapLabel.STAMPED_WHEN_NEXT_HANDLED] if lazy else [],
            )
        )
        if self.active_embargo == embargo_id:
            self.active_embargo = None

    def _register_entry(
        self, context: _Entry, register_entry: Mapping[str, Any]
    ) -> None:
        """A carried case's register: an ``ACTIVE`` entry is in force, and
        any other status is carried unless it is behind the one held
        (:meth:`.RebuiltRegister.carry`)."""
        embargo = register_entry.get("embargo")
        self._remember_end_time(embargo)
        embargo_id = actor_uri(embargo)
        status = member_of(EmbargoRegisterStatus, register_entry.get("status"))
        if embargo_id is None:
            return
        if status is EmbargoRegisterStatus.ACTIVE:
            self._start(context, embargo_id)
        elif status is not None:
            self.register.carry(embargo_id, status)

    # -- consent answers (CEH-04-008, CEH-04-009) ----------------------

    def _consent_row(
        self, context: _Entry, row: Mapping[str, Any], actor: str | None
    ) -> None:
        """A carried consent row: record its deadline, and any new answer."""
        participant = actor or actor_uri(
            first_present(row, "attributedTo", "attributed_to")
        )
        embargo_id = actor_uri(first_present(row, "embargoId", "embargo_id"))
        state = member_of(EmbargoConsentState, row.get("state"))
        if state is None or participant is None or embargo_id is None:
            self._unreadable(
                context.log_index,
                "a consent row lacks its participant, embargo or a known state",
            )
            return
        deadline = parse_time(
            first_present(row, "rsvpDeadline", "rsvp_deadline")
        )
        if deadline is not None:
            self.rsvp_deadlines[(participant, embargo_id)] = deadline
        self._answer(context, participant, embargo_id, state)

    def _answer(
        self,
        context: _Entry,
        participant: str,
        embargo_id: str,
        state: EmbargoConsentState,
    ) -> None:
        """Record *state* on a consent row, emitting it when it is a new answer.

        A timed-out invitation is the CASE_MANAGER's sweep when it next
        handled the case (CM-28-015), and carries the RSVP deadline recorded
        on the earlier ``INVITED`` row (CEH-03-013, CEH-03-015).
        """
        key = (participant, embargo_id)
        previous = self.consent.get(key)
        self.consent[key] = state
        kind = _CONSENT_EVENT_KINDS.get(state)
        if kind is None or previous is state:
            return
        timed_out = state is EmbargoConsentState.TIMED_OUT
        self.events.append(
            context.event(
                kind,
                participant=participant,
                embargo_id=embargo_id,
                deadline=self.rsvp_deadlines.get(key) if timed_out else None,
                gaps=[GapLabel.STAMPED_WHEN_NEXT_HANDLED] if timed_out else [],
            )
        )

    # -- state comparison (CEH-04-001 to CEH-04-004) -------------------

    def _tracker(self, actor: str) -> _Participant:
        tracker = self.participants.get(actor)
        if tracker is None:
            tracker = self.participants[actor] = _Participant(actor=actor)
        return tracker

    def _participant_record(
        self, context: _Entry, record: ParticipantRecord
    ) -> None:
        """One participant record: its joined flag, roles, statuses, rows."""
        known = record.actor in self.participants
        tracker = self._tracker(record.actor)
        tracker.roles |= record.roles
        if not known and record.joined is False:
            tracker.joined = False
        elif not tracker.joined and record.joined is True:
            # Joined with no acceptance entry in the input (a merge hole):
            # its held state is a case state from here, with no joining event.
            self._release(context, tracker)
        for status in record.statuses:
            self._status(context, tracker, status)
        for row in record.consents:
            self._consent_row(context, row, record.actor)

    def _emit(
        self, context: _Entry, tracker: _Participant, kind: CaseEventKind
    ) -> None:
        if tracker.joined:
            self.events.append(context.event(kind, participant=tracker.actor))
        else:
            tracker.held.append(kind)

    def _exclude(
        self,
        context: _Entry,
        participant: str | None,
        dimension: Dimension,
        named: str,
        reached: str,
    ) -> None:
        logger.info(
            "Ledger entry %d names %s %s behind %s for %s; no event",
            context.log_index,
            dimension.value,
            named,
            reached,
            participant or "the case",
        )
        self.excluded.append(
            ExcludedState(
                log_index=context.log_index,
                semantic_type=context.semantic_type.value,
                participant=participant,
                dimension=dimension,
                named=named,
                reached=reached,
            )
        )

    def _status(
        self, context: _Entry, tracker: _Participant, status: Mapping[str, Any]
    ) -> None:
        """One participant status the history may not have seen."""
        status_id = actor_uri(status)
        if status_id is not None:
            if status_id in self.seen_statuses:
                return
            self.seen_statuses.add(status_id)
        tracker.roles |= roles_of(first_present(status, "cvdRole", "cvd_role"))
        self._rm(context, tracker, status)
        vf = dimension_state([dict(status)], Dimension.VF)
        if vf is not None and (_VENDOR in tracker.roles or not tracker.roles):
            tracker.vf = self._flag_change(
                context, tracker, Dimension.VF, vf, tracker.vf, _VF_FLAGS
            )
        d = dimension_state([dict(status)], Dimension.D)
        if d is not None and (_DEPLOYER in tracker.roles or not tracker.roles):
            tracker.d = self._flag_change(
                context, tracker, Dimension.D, d, tracker.d, _D_FLAGS
            )

    def _rm(
        self, context: _Entry, tracker: _Participant, status: Mapping[str, Any]
    ) -> None:
        raw = dimension_state([dict(status)], Dimension.RM)
        declared = member_of(RM, raw)
        if declared is None:
            self._unreadable(
                context.log_index,
                f"a participant status has no known RM state ({raw!r})",
            )
            return
        verdict = classify_rm_declaration(tracker.rm, declared)
        if verdict is RMDeclaration.CONFIRMATION:
            return
        if verdict is RMDeclaration.REGRESSION:
            self._exclude(
                context, tracker.actor, Dimension.RM, declared, tracker.rm
            )
            return
        tracker.rm = declared
        self._emit(context, tracker, RM_EVENT_KINDS[declared])

    def _flag_change(
        self,
        context: _Entry,
        tracker: _Participant | None,
        dimension: Dimension,
        raw: str,
        reached: tuple[bool, ...],
        letters: tuple[tuple[str, CSEvent], ...],
    ) -> tuple[bool, ...]:
        """Compare a flag spelling with *reached*; return the state kept.

        Each newly raised flag yields its case-state event, in letter order;
        a lowered flag is a state behind the one reached, so the whole value
        is excluded and *reached* kept (CEH-04-015).
        """
        named = _flags(raw, letters)
        if dimension is Dimension.VF and named == (False, True):
            named = None  # a fix ready with no vendor aware has no spelling
        if named is None:
            self._unreadable(
                context.log_index,
                f"unreadable {dimension.value} state {raw!r}",
            )
            return reached
        if any(
            was and not now for was, now in zip(reached, named, strict=True)
        ):
            spelled = "".join(
                letter.upper() if up else letter
                for (letter, _), up in zip(letters, reached, strict=True)
            )
            self._exclude(
                context,
                tracker.actor if tracker else None,
                dimension,
                raw,
                spelled,
            )
            return reached
        for (_, event), was, now in zip(letters, reached, named, strict=True):
            if now and not was:
                if tracker is None:
                    self.events.append(self._case_event(context, event))
                else:
                    self._emit(context, tracker, event)
        return named

    def _case_event(self, context: _Entry, event: CSEvent) -> CaseEvent:
        """A public-state event: adopted, and out of band for X and A."""
        gaps = [GapLabel.STAMPED_AT_ADOPTION]
        if event in (CSEvent.X, CSEvent.A):
            gaps.append(GapLabel.REPORTED_OUT_OF_BAND)
        return context.event(event, gaps=gaps)

    def _case_status(
        self, context: _Entry, case_status: Mapping[str, Any]
    ) -> None:
        """One case status: the case's own public state (CEH-03-012)."""
        status_id = actor_uri(case_status)
        if status_id is not None:
            if status_id in self.seen_case_statuses:
                return
            self.seen_case_statuses.add(status_id)
        pxa = dimension_state([dict(case_status)], Dimension.PXA)
        if pxa is not None:
            self.pxa = self._flag_change(
                context, None, Dimension.PXA, pxa, self.pxa, _PXA_FLAGS
            )


def _pxa_of(flags: tuple[bool, ...]) -> CS_pxa:
    """The public state the raised *flags* spell, one per ``p``, ``x``, ``a``."""
    return CS_pxa[
        "".join(
            letter.upper() if up else letter
            for (letter, _), up in zip(_PXA_FLAGS, flags, strict=True)
        )
    ]


def _reached(deriver: _Deriver) -> ReachedState:
    """What *deriver* has reached once it has read every entry."""
    return ReachedState(
        participants=[
            ReachedParticipant(
                participant=tracker.actor,
                rm=tracker.rm,
                roles=tuple(sorted(tracker.roles)),
                joined=tracker.joined,
            )
            for tracker in deriver.participants.values()
        ],
        pxa=_pxa_of(deriver.pxa),
        embargo_register=dict(deriver.register.statuses),
    )


def _invitee(invite: object) -> str | None:
    """The id of what an ``Invite`` invites: an actor, or an embargo."""
    return (
        actor_uri(invite.get("object")) if isinstance(invite, dict) else None
    )


_Handler = Callable[[_Deriver, _Entry, object], None]

#: The acts each semantic type names (CEH-04-005, CEH-04-010).
_ACT_HANDLERS: dict[MessageSemantics, _Handler] = {
    MessageSemantics.CREATE_EMBARGO_EVENT: _Deriver._on_embargo_terms,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: _Deriver._on_proposal,
    MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE: _Deriver._on_proposal_rejected,
    MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE: _Deriver._on_invite_undone,
    MessageSemantics.ACTIVATE_EMBARGO_ON_CASE: _Deriver._on_activation,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: _Deriver._on_termination,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: _Deriver._on_stub_accept,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: _Deriver._on_stub_reject,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: _Deriver._on_embargo_reply,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: _Deriver._on_embargo_reply,
}


def _creation_end(
    entries: list[dict[str, Any]], case_managers: set[str]
) -> int:
    """The log index of the first entry after the creation sequence.

    The creation sequence is the genesis entry and the CASE_MANAGER's own
    entries that follow it without a break: the steps of case initialization
    (CM-14-001) commit before any other actor's activity is ledgered.
    """
    end = 1
    for entry in entries:
        index = log_index_of(entry)
        if index is None or index < end:
            continue
        actor = actor_uri(payload_of(entry).get("actor"))
        if index != end or actor not in case_managers:
            break
        end += 1
    return end


def case_event_history(ledger: CaseLedger) -> CaseEventHistory:
    """Derive one case's CVD event history from its ledger (CEH-01-003).

    Args:
        ledger: The case's entries from the source a measure should trust,
            as :func:`vultron.measure.ledger.read_case_ledgers` selects it.

    Returns:
        The events in log-index order, with every excluded state and
        unreadable entry, and the ledger's holes, conflicts and end carried
        over so a caller can refuse a history it cannot trust.
    """
    history, _ = derive_case(ledger)
    return history


def derive_case(ledger: CaseLedger) -> tuple[CaseEventHistory, ReachedState]:
    """Derive one case's event history and the states its ledger reached.

    One walk yields both, so the reached states are exactly those the
    history's events lead to (:mod:`~vultron.measure.history.reached`).
    """
    entries = ledger.entries
    managers = case_manager_ids(entries)
    creation_end = _creation_end(entries, managers)
    deriver = _Deriver(case_managers=managers)
    for placed in ledger.rows:
        deriver.read(
            placed.data,
            placed.log_index,
            creation=placed.log_index < creation_end,
        )
    history = CaseEventHistory(
        case_id=ledger.case_id,
        source=ledger.source,
        end_confirmed=ledger.end_confirmed,
        missing_log_indices=ledger.missing_log_indices,
        conflicting_log_indices=ledger.conflicting_log_indices,
        unusable_rows=ledger.unusable_rows,
        events=deriver.events,
        excluded=deriver.excluded,
        unreadable_entries=deriver.unreadable,
    )
    return history, _reached(deriver)


def read_case_event_histories(paths: Iterable[Path]) -> CaseEventHistories:
    """Read the ledger files the caller names and derive each case's history.

    The layer globs for nothing: *paths* is the whole input (CEH-02-003,
    CEH-02-010).

    Raises:
        LedgerReadError: When a named file cannot be read at all.
    """
    read = read_case_ledgers(paths)
    return CaseEventHistories(
        histories={
            case_id: case_event_history(ledger)
            for case_id, ledger in read.cases.items()
        },
        unusable_rows=read.unusable_rows,
    )
