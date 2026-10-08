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

"""Embargo-ending notices to bound signatories the ledger no longer reaches.

A ``SIGNATORY`` that was removed (CM-31-001) or that left the case and is
skipped at RM ``CLOSED`` (CM-23-004) stays bound by the embargo, but no
ledger entry reaches it.  When the active embargo is terminated, or replaced
by a revision that ends no later (ADR-0093 containment), the CASE_MANAGER
sends each such participant a direct notice outside the ledger stream
(CM-31-009, ADR-0116):

==========================================  ==============================
Change                                      Notice
==========================================  ==============================
Termination, the case going public included  ``Remove(EmbargoEvent)`` (ET)
Revision ending no later than the embargo   ``Announce(EmbargoEvent)`` with
it replaces                                 the new terms
Revision ending later                       none
Termination on or after the agreed end      none: that is expiry
==========================================  ==============================

**The CASE_MANAGER side** is a linked pair of nodes that brackets the EM
write: :class:`CaptureActiveEmbargoNode` records the case's active embargo
before it, and :class:`SendEmbargoEndingNoticesNode` compares it with the
active embargo after it and sends what is owed.  One pair serves every path
that ends or replaces an embargo — the received ``Remove`` and
``Add(EmbargoEvent)``, the owner's received ``Accept`` of a revision, and the
trigger and P/X/A cascade terminations — so no path decides on its own what
"ended" or "shorter" means.  :func:`embargo_ending_notice_nodes` builds the
pair.  The notice is delivery, not a record: it is queued on the outbox and
never committed, and each recipient gets its own activity, so no notice
names another participant.

**The paused replica side** (CM-31-010): :class:`LedgerStreamPausedNode`
tells a replica whether the notice is its only channel, and
:class:`ApplyAnnouncedEmbargoRevisionNode` applies a shorter revision from
the CASE_MANAGER's ``Announce(EmbargoEvent)`` through ``EmbargoLifecycle``
(EMB-18-001).  A termination notice is a ``Remove(EmbargoEvent)``, which the
received teardown tree already applies through ``EmbargoLifecycle``.  The
sender check that admits only the CASE_MANAGER at a replica is the use
case's sender guard (ADR-0115, PCR-03-001).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.models._helpers import now_utc
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.participants.recipients import (
    embargo_ending_notice_recipients,
    ledger_stream_paused,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.services.embargo_ordering import (
    earliest_expiring_embargo_id,
    read_embargo_event,
)
from vultron.errors import VultronError


class EmbargoEndingKind(StrEnum):
    """Which notice an embargo change owes a bound, unreached signatory."""

    #: ``Remove(EmbargoEvent)`` naming the terminated embargo (ET).
    TERMINATED = "terminated"
    #: ``Announce(EmbargoEvent)`` naming the shorter revision now in force.
    SHORTENED = "shortened"


@dataclass(frozen=True)
class EmbargoEndingNotice:
    """The notice owed for one embargo change (CM-31-009).

    *ended_embargo_id* is the embargo whose signatories are owed it — the one
    terminated or replaced.  *notice_embargo_id* is the embargo the notice
    names: the terminated one, or the revision now in force.
    """

    kind: EmbargoEndingKind
    ended_embargo_id: str
    notice_embargo_id: str


def embargo_ending_notice(
    store: CasePersistence,
    *,
    before: str | None,
    after: str | None,
) -> EmbargoEndingNotice | None:
    """Decide the CM-31-009 notice a change of active embargo owes.

    *before* and *after* are the case's active embargo either side of one EM
    write.  ``None`` means no notice is owed: nothing was in force, nothing
    changed, the revision ends later than the embargo it replaces (its
    signatories never agreed to it), or the embargo was terminated on or
    after its agreed end (expiry, which every signatory already knows).
    A revision that ends at the same instant counts as no later: it is the
    EP-05-001 carry-over arm, so the bound participant is now bound by it.

    Raises:
        VultronNotFoundError: An embargo the case named is not in *store*.
        VultronNotAnEmbargoError: That record is not an ``EmbargoEvent``.
    """
    if before is None or before == after:
        return None
    if after is None:
        if read_embargo_event(store, before).end_time <= now_utc():
            return None
        return EmbargoEndingNotice(
            kind=EmbargoEndingKind.TERMINATED,
            ended_embargo_id=before,
            notice_embargo_id=before,
        )
    # A tie keeps the first id, so equal end times read as "no later".
    if earliest_expiring_embargo_id(store, [after, before]) != after:
        return None
    return EmbargoEndingNotice(
        kind=EmbargoEndingKind.SHORTENED,
        ended_embargo_id=before,
        notice_embargo_id=after,
    )


class ActiveEmbargoSnapshot:
    """The active embargo a case named before an EM write.

    Shared by one :class:`CaptureActiveEmbargoNode` and the
    :class:`SendEmbargoEndingNoticesNode` built with it, so neither reads a
    blackboard key a nested tree could overwrite.
    """

    def __init__(self) -> None:
        self.captured = False
        self.embargo_id: str | None = None


class CaptureActiveEmbargoNode(DataLayerActionWithPorts):
    """Record the case's active embargo ahead of an EM write.

    Read-only.  Fails like any Regime 1 read when the case is missing
    (ADR-0087).
    """

    def __init__(
        self,
        case_id: str,
        snapshot: ActiveEmbargoSnapshot,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._snapshot = snapshot

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        self._snapshot.embargo_id = case.active_embargo_id
        self._snapshot.captured = True
        self.feedback_message = (
            f"Case '{self.case_id}' active embargo before the EM write:"
            f" {self._snapshot.embargo_id!r}"
        )
        return Status.SUCCESS


class SendEmbargoEndingNoticesNode(_EmitSingleActivityBase):
    """Tell each bound signatory the ledger no longer reaches (CM-31-009).

    Runs after the EM write, as the CASE_MANAGER.  Compares the active
    embargo its :class:`CaptureActiveEmbargoNode` recorded with the one the
    case names now (:func:`embargo_ending_notice`) and, when a notice is
    owed, sends one activity per recipient from
    :func:`~vultron.core.participants.recipients.embargo_ending_notice_recipients`:
    ``Remove(EmbargoEvent)`` for a termination, ``Announce(EmbargoEvent)``
    for a shorter revision.  ``actor`` is the CASE_MANAGER; when the change
    was requested by another actor (the Case Owner), that actor is
    ``attributedTo`` (CM-24-001, CM-24-002).

    The notice is not committed to the ledger and carries nothing but the
    embargo.  No notice owed, or nobody to send it to, is ``SUCCESS`` with
    nothing sent.  A notice owed with no trigger-activity factory is a
    wiring fault and fails the node (BT-14-001); so does a capture node that
    never ran.  A factory or outbox error escapes to ``BTBridge``: the EM
    write is already done, so it is an internal fault, not a refusal.
    """

    def __init__(
        self,
        case_id: str,
        snapshot: ActiveEmbargoSnapshot,
        requested_by: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._snapshot = snapshot
        self._requested_by = requested_by

    def _attributed_to(self) -> str | None:
        if self._requested_by is None or self._requested_by == self.actor_id:
            return None
        return self._requested_by

    def _send(self, notice: EmbargoEndingNotice, recipient: str) -> str:
        assert self.trigger_activity_factory is not None
        actor = cast(str, self.actor_id)
        build = (
            self.trigger_activity_factory.terminate_embargo
            if notice.kind is EmbargoEndingKind.TERMINATED
            else self.trigger_activity_factory.announce_embargo
        )
        activity_id, blob = build(
            embargo_id=notice.notice_embargo_id,
            case_id=self.case_id,
            actor=actor,
            to=[recipient],
            attributed_to=self._attributed_to(),
        )
        self._emit_through_seam(activity_id, blob)
        return activity_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if not self._snapshot.captured:
            raise RuntimeError(
                f"{self.name}: no active-embargo snapshot for case"
                f" '{self.case_id}'; CaptureActiveEmbargoNode must run first"
            )
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        datalayer = cast(CasePersistence, self.datalayer)
        notice = embargo_ending_notice(
            datalayer,
            before=self._snapshot.embargo_id,
            after=case.active_embargo_id,
        )
        if notice is None:
            self.feedback_message = (
                f"No embargo-ending notice owed on case '{self.case_id}'"
            )
            return Status.SUCCESS
        recipients = embargo_ending_notice_recipients(
            case,
            datalayer,
            notice.ended_embargo_id,
            excluding={cast(str, self.actor_id)},
        )
        if not recipients:
            self.feedback_message = (
                f"Embargo '{notice.ended_embargo_id}' {notice.kind} on case"
                f" '{self.case_id}'; every bound signatory is reached by the"
                " ledger"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        if (f := self._require_factory()) is not None:
            self.logger.error(
                "%s: %s — %d embargo-ending notice(s) owed on case '%s'"
                " (CM-31-009)",
                self.name,
                self.feedback_message,
                len(recipients),
                self.case_id,
            )
            return f
        sent = [self._send(notice, recipient) for recipient in recipients]
        self.feedback_message = (
            f"Sent {len(sent)} embargo-ending notice(s) ({notice.kind},"
            f" embargo '{notice.notice_embargo_id}') on case"
            f" '{self.case_id}' to {recipients} (CM-31-009)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


def embargo_ending_notice_nodes(
    case_id: str, requested_by: str | None = None
) -> tuple[CaptureActiveEmbargoNode, SendEmbargoEndingNoticesNode]:
    """Return the linked capture and notice nodes for one EM write.

    Place the capture node before the write and the notice node after it,
    behind the CASE_MANAGER gate.  *requested_by* names the actor whose
    request the CASE_MANAGER is carrying out, for ``attributedTo``.
    """
    snapshot = ActiveEmbargoSnapshot()
    return (
        CaptureActiveEmbargoNode(case_id=case_id, snapshot=snapshot),
        SendEmbargoEndingNoticesNode(
            case_id=case_id, snapshot=snapshot, requested_by=requested_by
        ),
    )


class LedgerStreamPausedNode(DataLayerConditionWithPorts):
    """Condition: the executing actor's ledger stream on the case is paused.

    ``SUCCESS`` when the actor's own record in this replica says it is not
    active or is at RM ``CLOSED``
    (:func:`~vultron.core.participants.recipients.ledger_stream_paused`), so
    a direct embargo-ending notice from the CASE_MANAGER is its only channel
    (CM-31-010).  ``FAILURE`` otherwise, a case this store does not hold
    included: an active replica takes embargo changes from the ledger
    (RSH-08-003).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        datalayer = cast(CasePersistence, self.datalayer)
        # Regime 2 (ADR-0087): a store with no replica of the case is not a
        # paused participant of it, and that is not an anomaly.
        case = self._resolve_case_replica(self.case_id)
        if case is None:
            self.feedback_message = f"No replica of case '{self.case_id}'"
            return Status.FAILURE
        if ledger_stream_paused(case, datalayer, cast(str, self.actor_id)):
            self.feedback_message = (
                f"'{self.actor_id}' ledger stream on case '{self.case_id}'"
                " is paused"
            )
            return Status.SUCCESS
        self.feedback_message = (
            f"'{self.actor_id}' is reached by the ledger of case"
            f" '{self.case_id}'"
        )
        return Status.FAILURE


class ApplyAnnouncedEmbargoRevisionNode(DataLayerActionWithPorts):
    """Apply a shorter revision a paused replica was told of (CM-31-010).

    The CASE_MANAGER's ``Announce(EmbargoEvent)`` notice names the revision
    now in force.  When it ends no later than the replica's active embargo,
    the node stores the announced ``EmbargoEvent`` (when carried inline and
    not yet held, EMB-18-003) and activates it through
    ``EmbargoLifecycle.activate_embargo`` in ``OBSERVED`` mode (EMB-18-001),
    which carries the replica's signatories over as the CASE_MANAGER did
    (EP-05-001).

    Nothing is written, and the node succeeds, when the replica has no
    embargo in force, already has the announced one, or the announced one
    ends later: none of those is a shortening this replica is bound by.
    ``applied`` says whether the revision was applied.  An announced embargo
    that belongs to another case, or that cannot be read, fails the node.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        embargo: EmbargoEvent | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self._embargo = embargo
        self.applied = False

    def _hold_announced_embargo(self, datalayer: CasePersistence) -> None:
        """Store the inline embargo if absent; refuse one from another case."""
        if self._embargo is None:
            return
        if self._embargo.context != self.case_id:
            raise VultronError(
                f"Announced embargo '{self.embargo_id}' belongs to"
                f" '{self._embargo.context}', not case '{self.case_id}'"
            )
        if datalayer.read(self.embargo_id) is None:
            datalayer.save(self._embargo)

    def update(self) -> Status:
        self.applied = False
        if (f := self._require_datalayer()) is not None:
            return f
        datalayer = cast(CasePersistence, self.datalayer)
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        current = case.active_embargo_id
        if current is None or current == self.embargo_id:
            self.feedback_message = (
                f"Case '{self.case_id}' has {current!r} in force — the"
                f" announced embargo '{self.embargo_id}' changes nothing"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        try:
            self._hold_announced_embargo(datalayer)
            notice = embargo_ending_notice(
                datalayer, before=current, after=self.embargo_id
            )
            if notice is None:
                self.feedback_message = (
                    f"Announced embargo '{self.embargo_id}' ends later than"
                    f" '{current}' on case '{self.case_id}' — not a"
                    " shortening, ignored (CM-31-009)"
                )
                self.logger.warning("%s: %s", self.name, self.feedback_message)
                return Status.SUCCESS
            result = EmbargoLifecycle(persistence=datalayer).activate_embargo(
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=self.actor_id,
                transition_mode=TransitionMode.OBSERVED,
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.applied = True
        self.feedback_message = (
            f"Applied shorter revision '{self.embargo_id}' (replacing"
            f" '{current}') on case '{self.case_id}' from the CASE_MANAGER's"
            " notice (CM-31-010)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        if result.em_after != result.em_before:
            log_em_transition(
                self.logger,
                self.actor_id or "<unknown>",
                self.case_id,
                result.em_before,
                result.em_after,
            )
        return Status.SUCCESS


__all__ = [
    "ActiveEmbargoSnapshot",
    "ApplyAnnouncedEmbargoRevisionNode",
    "CaptureActiveEmbargoNode",
    "EmbargoEndingKind",
    "EmbargoEndingNotice",
    "LedgerStreamPausedNode",
    "SendEmbargoEndingNoticesNode",
    "embargo_ending_notice",
    "embargo_ending_notice_nodes",
]
