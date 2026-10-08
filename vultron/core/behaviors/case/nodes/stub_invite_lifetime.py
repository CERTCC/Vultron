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
  that was superseded (naming the replacement) or has expired (its expiry
  consequence is *void*, ASK-03-002).  A ``Reject`` is not guarded: declining
  to join does not depend on the terms (CM-11-016).
- :class:`ReinviteAwaitingNode` — the invitee has a record and has not
  answered, so a fresh stub goes out on that record (CM-11-015).
- :class:`ReinviteNotToClosedParticipantNode` — refuses a re-invite of a
  participant at ``RM.CLOSED`` (CM-11-015, ADR-0085).

The deadline rules live in :mod:`vultron.core.behaviors.case.stub_invite_lifetime`.
"""

from py_trees.common import Status

from vultron.core.behaviors.case.stub_invite_lifetime import (
    awaiting_stub_reply,
    invitee_record,
    record_of,
    recorded_stub_invites,
    unanswerable_reason,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models._helpers import now_utc


class StubInviteAnswerableNode(DataLayerConditionWithPorts):
    """Guard: the stub Invite an ``Accept`` answers can still be accepted.

    FAILURE, with the reason as ``feedback_message``, when the recorded Invite
    was superseded by a replacement (the refusal names it) or its reply
    deadline has passed (the invitee must be re-invited).  The Invite is read
    from this store, never from the copy the reply embeds (CM-11-017).
    """

    def __init__(
        self, invite_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invite_id = invite_id
        self.case_id = case_id

    def _refuse(self, why: str) -> Status:
        self.feedback_message = why
        self.logger.warning("%s: %s", self.name, why)
        return Status.FAILURE

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
        reason = unanswerable_reason(record, siblings, now_utc())
        if reason is not None:
            return self._refuse(reason)
        return Status.SUCCESS


class ReinviteAwaitingNode(DataLayerConditionWithPorts):
    """Condition: the invitee has an inert record and has not answered.

    SUCCESS when *invitee_id* has a participant record in the case that has
    neither joined nor closed, so a re-invite is a fresh stub Invite on that
    record (CM-11-015).  FAILURE otherwise, leaving the first-invite path.
    """

    def __init__(
        self, invitee_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        record = invitee_record(self.datalayer, case, self.invitee_id)
        return (
            Status.SUCCESS if awaiting_stub_reply(record) else Status.FAILURE
        )


class ReinviteNotToClosedParticipantNode(DataLayerConditionWithPorts):
    """Guard: refuse a re-invite of a participant at ``RM.CLOSED``.

    ``CLOSED`` is terminal with no rejoin path (ADR-0085), and a stub reject
    is a closure (CM-11-007), so the record cannot be invited again.  SUCCESS
    for anyone else, including an invitee with no record yet.
    """

    def __init__(
        self, invitee_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        record = invitee_record(self.datalayer, case, self.invitee_id)
        if record is not None and record.rm_closed:
            self.feedback_message = (
                f"'{self.invitee_id}' is at RM.CLOSED in case"
                f" '{self.case_id}' and cannot be re-invited (CM-11-015,"
                " ADR-0085)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


__all__ = [
    "ReinviteAwaitingNode",
    "ReinviteNotToClosedParticipantNode",
    "StubInviteAnswerableNode",
]
