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

"""The CASE_MANAGER's own act, built by a factory and committed from its blob.

Every change the CASE_MANAGER makes to the case file, and every decision it
takes from local policy or the clock, is committed as its own entry
(CLP-07-013).  The entry's ``payloadSnapshot`` is the activity the
trigger-activity factory builds and seals, verbatim (VM-08-003): never a
snapshot dict assembled in core, which would record an activity nobody sent.

:class:`_CommitCaseManagerActivityBase` is the one frame for that: build the
activity as the executing actor, queue it when it has an audience, and
commit the sealed blob.  A sent activity is committed after it is queued,
because a ledger entry records a completed act (ADR-0119).  An act every
replica learns from the entry alone is addressed to nobody and only
committed, as soon as it is decided; the ledger fan-out is its delivery.  The embargo decisions (``embargo/nodes/manager_commit.py``), the
case closure (``case/nodes/leave/fully_closed.py``) and the late-Accept
acknowledgement (``embargo/nodes/late_accept.py``) all subclass it.

Like the relay node, it catches nothing: a missing factory, a failed factory
call or a failed commit is not a protocol refusal, so the exception escapes to
``BTBridge`` and the handler raises (BT-14-001, ARCH-15-001).
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    TRIGGER_FACTORY_UNAVAILABLE,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.recipients import case_content_recipients
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronWiringError


class _CommitCaseManagerActivityBase(_EmitSingleActivityBase):
    """Build → (queue) → commit one activity the CASE_MANAGER decides on.

    Subclasses supply :meth:`_build`.  With ``notify_participants`` the
    activity is addressed to every case-content recipient except the
    executing actor, queued when that audience is not empty, and committed
    once queued (ADR-0119); otherwise it is addressed to nobody and only
    committed.  A queued activity whose commit fails is withdrawn from the
    outbox before the failure is raised (:meth:`_withdraw_unrecorded`).

    The queue write goes through the shared emit seam
    (:meth:`_EmitSingleActivityBase._emit_through_seam`, OX-14-001); unlike
    that base's ``update()``, this one catches nothing (see the module
    docstring).
    """

    #: Whether the commit refuses a gapped local ledger prefix
    #: (SYNC-10-001/002); see :func:`~vultron.core.behaviors.sync.commit_tree
    #: .create_commit_log_entry_tree`.
    _CHECK_LEDGER_FRESHNESS: bool = True

    def __init__(
        self,
        case_id: str,
        event_type: str,
        notify_participants: bool = False,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._event_type = event_type
        self._notify_participants = notify_participants
        #: The ids of the activities the last :meth:`update` committed.
        self.committed_activity_ids: list[str] = []

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        """Return ``(activity_id, sealed_blob)`` for an activity sent *to*."""
        raise NotImplementedError

    def _audience_case(self, case: VulnerabilityCase) -> VulnerabilityCase:
        """The case whose recipients the activity is addressed to.

        The stored *case* by default.  An act committed before it is applied
        (ADR-0124) returns the case as the act leaves it, so the audience is
        the one the act's own effect admits.
        """
        return case

    def _ledger_object_id(self, activity_id: str) -> str:
        """The entry's ``log_object_id``: the activity itself, by default."""
        return activity_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if self.trigger_activity_factory is None:
            # A composition fault, not a refusal: a FAILURE here can be read
            # by an enclosing Selector as a guard that did not pass (the
            # owner-close arm, CM-23-002), so it raises (ARCH-15-001).
            raise VultronWiringError(
                f"{self.name}: {TRIGGER_FACTORY_UNAVAILABLE} to build the"
                f" '{self._event_type}' activity of case '{self._case_id}'"
            )
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            # Regime 1 (ADR-0087).  A FAILURE, unlike the missing factory
            # above: every arm that composes this node has already read the
            # case (the owner-close arm through its Case Owner guard), so a
            # case missing here cannot pass for a guard that did not pass.
            return failure
        actor_id = cast(str, self.actor_id)
        dl = cast(CaseOutboxPersistence, self.datalayer)

        to = (
            case_content_recipients(
                self._audience_case(case), dl, excluding={actor_id}
            )
            if self._notify_participants
            else []
        )
        # One decision is one activity.
        activity_id, blob = self._build(to or None)
        # Sent before it is recorded: the entry records a completed act
        # (ADR-0119).  A pending id is an earlier attempt's send, recorded now.
        if to:
            self._emit_through_seam(activity_id, blob)
        try:
            # A nested commit inherits the outer execution's ``/sync_port``,
            # so the entry is announced to every participant replica
            # (SYNC-02-002).
            commit_emitted_activity(
                datalayer=dl,
                actor_id=actor_id,
                case_id=self._case_id,
                activity_id=self._ledger_object_id(activity_id),
                activity_blob=blob,
                event_type=self._event_type,
                check_freshness=self._CHECK_LEDGER_FRESHNESS,
            )
        except Exception:
            if to:
                self._withdraw_unrecorded(dl, activity_id)
            raise
        self.committed_activity_ids = [activity_id]
        self.feedback_message = (
            f"CASE_MANAGER committed '{self._event_type}' entry for"
            f" {activity_id!r} on case"
            f" '{self._case_id}' ({len(to)} participant(s) addressed)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def _withdraw_unrecorded(
        self, dl: CaseOutboxPersistence, activity_id: str
    ) -> None:
        """Take a decision whose commit failed back out of the outbox.

        An act on the copy model (ADR-0124) has not changed the case yet: it
        writes only once its entry commits, so a retry decides again and
        builds a new activity.  An arm not yet converted wrote first, and its
        own write stops a rerun.  Either way, left queued, the activity would
        reach participants with no entry that records it, so it is withdrawn,
        as the create-case trigger withdraws its ``Create`` (CLP-07-013).
        One delivery already took cannot be withdrawn, and is reported.
        """
        if dl.outbox_withdraw(activity_id):
            self.logger.warning(
                "%s: withdrew '%s' from the outbox: its '%s' entry on case"
                " '%s' did not commit",
                self.name,
                activity_id,
                self._event_type,
                self._case_id,
            )
            return
        self.logger.error(
            "%s: '%s' was already taken for delivery, but its '%s' entry on"
            " case '%s' did not commit",
            self.name,
            activity_id,
            self._event_type,
            self._case_id,
        )


__all__ = ["_CommitCaseManagerActivityBase"]
