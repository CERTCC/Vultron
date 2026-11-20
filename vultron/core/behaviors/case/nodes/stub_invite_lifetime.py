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

"""Guards over a stub Invite's lifetime (CM-11-014, CM-11-015, CM-11-016).

Read-only conditions for the CASE_MANAGER's received trees:

- :class:`StubInviteAnswerableNode` — refuses an ``Accept`` of a stub Invite
  that was superseded, naming the replacement.  An expired stub is not
  refused: its expiry consequence is *stale* (ASK-03-008).  A ``Reject`` is
  not guarded: declining to join does not depend on the terms (CM-11-016).

The re-invite check is
:class:`~vultron.core.behaviors.case.nodes.owner_invite_stub.InviteeAwaitsReplyNode`,
and the refusal of a joined or closed invitee is
:class:`~vultron.core.behaviors.case.nodes.owner_invite.InviteeIsInvitableNode`
(CM-11-015, CM-11-043).

The deadline rules live in :mod:`vultron.core.behaviors.case.stub_invite_lifetime`.
"""

from py_trees.common import Status

from vultron.core.behaviors.case.stub_invite_lifetime import (
    record_of,
    recorded_stub_invites,
    superseded_reason,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.node_logger import fail_with_reason


class StubInviteAnswerableNode(DataLayerConditionWithPorts):
    """Guard: the stub Invite an ``Accept`` answers can still be accepted.

    FAILURE, with the reason as ``feedback_message``, when the recorded Invite
    was superseded by a replacement (the refusal names it).  The Invite is
    read from this store, never from the copy the reply embeds (CM-11-047).
    """

    def __init__(
        self, invite_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invite_id = invite_id
        self.case_id = case_id

    def _refuse(self, why: str) -> Status:
        return fail_with_reason(self, why)

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        record = record_of(self.datalayer.read(self.invite_id))
        if record is None:
            return self._refuse(
                f"Invite '{self.invite_id}' is not a recorded stub Invite"
            )
        siblings = recorded_stub_invites(
            self.datalayer, self.case_id, self.actor_id, record.invitee_id
        )
        reason = superseded_reason(record, siblings)
        if reason is not None:
            return self._refuse(reason)
        return Status.SUCCESS


__all__ = [
    "StubInviteAnswerableNode",
]
