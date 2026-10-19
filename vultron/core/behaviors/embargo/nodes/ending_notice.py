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

A signatory that was removed (CM-31-001) or that left the case and is
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

**The paused replica side** (CM-31-010) is in
:mod:`~vultron.core.behaviors.embargo.nodes.ending_notice_replica`.
"""

from enum import StrEnum
from typing import cast

from py_trees.common import Status
from pydantic import BaseModel, ConfigDict

from vultron.core.behaviors.delegated_authorship import delegated_authorship
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    _EmitSingleActivityBase,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.participants.recipients import (
    embargo_ending_notice_recipients,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_ordering import (
    earliest_expiring_embargo_id,
    read_embargo_event,
)
from vultron.errors import BtNodePreconditionError


class EmbargoEndingKind(StrEnum):
    """Which notice an embargo change owes a bound, unreached signatory."""

    #: ``Remove(EmbargoEvent)`` naming the terminated embargo (ET).
    TERMINATED = "terminated"
    #: ``Announce(EmbargoEvent)`` naming the shorter revision now in force.
    SHORTENED = "shortened"


class EmbargoEndingNotice(BaseModel):
    """The notice owed for one embargo change (CM-31-009).

    *ended_embargo_id* is the embargo whose signatories are owed it — the one
    terminated or replaced.  *notice_embargo_id* is the embargo the notice
    names: the terminated one, or the revision now in force.
    """

    model_config = ConfigDict(frozen=True)

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
    embargo; a termination notice adds the what and the why the register
    records (EMB-13-005).  No notice owed, or nobody to send it to, is ``SUCCESS`` with
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

    def _send(
        self,
        notice: EmbargoEndingNotice,
        recipient: str,
        termination: EmbargoTermination | None,
    ) -> str:
        assert self.trigger_activity_factory is not None
        actor = cast(str, self.actor_id)
        requested = self._requested_by
        authorship = (
            delegated_authorship(
                doing_actor_id=actor, requesting_actor_id=requested
            )
            if requested is not None and requested != actor
            else None
        )
        factory = self.trigger_activity_factory
        if notice.kind is not EmbargoEndingKind.TERMINATED:
            activity_id, blob = factory.announce_embargo(
                embargo_id=notice.notice_embargo_id,
                case_id=self.case_id,
                actor=actor,
                to=[recipient],
                attributed_to=authorship.attributed_to if authorship else None,
            )
        elif termination is None:
            raise BtNodePreconditionError(
                f"{self.name}: case '{self.case_id}' records no termination"
            )
        else:
            # The notice carries the what and the why the register records
            # (ADR-0122, EMB-13-005).
            activity_id, blob = factory.terminate_embargo(
                embargo_id=notice.notice_embargo_id,
                case_id=self.case_id,
                actor=actor,
                reason=termination.reason,
                cause=termination.cause,
                to=[recipient],
                attributed_to=authorship.attributed_to if authorship else None,
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
        before = self._snapshot.embargo_id
        # One capture serves one notice: a re-tick must capture again.
        self._snapshot.captured = False
        notice = embargo_ending_notice(
            datalayer, before=before, after=case.active_embargo_id
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
        sent = [
            self._send(notice, recipient, case.embargo_termination)
            for recipient in recipients
        ]
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


__all__ = [
    "ActiveEmbargoSnapshot",
    "CaptureActiveEmbargoNode",
    "EmbargoEndingKind",
    "EmbargoEndingNotice",
    "SendEmbargoEndingNoticesNode",
    "embargo_ending_notice",
    "embargo_ending_notice_nodes",
]
