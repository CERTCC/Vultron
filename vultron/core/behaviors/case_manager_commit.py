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
activity as the executing actor, commit the sealed blob, and queue it only
when it has an audience.  An act every replica learns from the entry alone
is addressed to nobody and only committed; the ledger fan-out is its
delivery.  The embargo decisions (``embargo/nodes/manager_commit.py``), the
case closure (``case/nodes/leave/fully_closed.py``) and the late-Accept
acknowledgement (``embargo/nodes/late_accept.py``) all subclass it.

Like the relay node, it catches nothing: a failed factory call or commit is
not a protocol refusal, so the exception escapes to ``BTBridge`` and the
handler raises (BT-14-001).
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.participants.recipients import case_content_recipients
from vultron.core.ports.case_outbox import CaseOutboxPersistence


class _CommitCaseManagerActivityBase(_EmitSingleActivityBase):
    """Build → commit → (queue) one activity the CASE_MANAGER decides on.

    Subclasses supply :meth:`_build`.  With ``notify_participants`` the
    activity is addressed to every case-content recipient except the
    executing actor, and queued when that audience is not empty; otherwise it
    is addressed to nobody and only committed.

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

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        """Return ``(activity_id, sealed_blob)`` for an activity sent *to*."""
        raise NotImplementedError

    def _build_all(self, to: list[str] | None) -> list[tuple[str, str]]:
        """Return every ``(activity_id, sealed_blob)`` this decision commits.

        One decision is one activity, except an abandonment, which answers
        every open proposal at once (EMB-16-001) and overrides this.
        """
        return [self._build(to)]

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return f
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        actor_id = cast(str, self.actor_id)
        dl = cast(CaseOutboxPersistence, self.datalayer)

        to = (
            case_content_recipients(case, dl, excluding={actor_id})
            if self._notify_participants
            else []
        )
        committed = []
        for activity_id, blob in self._build_all(to or None):
            # A nested commit inherits the outer execution's ``/sync_port``,
            # so the entry is announced to every participant replica
            # (SYNC-02-002).
            commit_emitted_activity(
                datalayer=dl,
                actor_id=actor_id,
                case_id=self._case_id,
                activity_id=activity_id,
                activity_blob=blob,
                event_type=self._event_type,
                check_freshness=self._CHECK_LEDGER_FRESHNESS,
            )
            if to:
                self._emit_through_seam(activity_id, blob)
            committed.append(activity_id)
        self.feedback_message = (
            f"CASE_MANAGER committed '{self._event_type}' entry for"
            f" {', '.join(repr(i) for i in committed)} on case"
            f" '{self._case_id}' ({len(to)} participant(s) addressed)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = ["_CommitCaseManagerActivityBase"]
