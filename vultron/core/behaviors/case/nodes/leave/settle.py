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

"""Owner-close settle step: expire every pending embargo Invite (CM-23-014).

After a case closes, a pending Invite can only expire.  Waiting for its RSVP
deadline would keep the CASE_MANAGER working for a closed case, only to write
one more entry after ``case_fully_closed``.  So the owner-close sequence
(CM-23-002) expires each one first, between the CASE_MANAGER's own
``RM.CLOSED`` entry and ``case_fully_closed``.

Each expiry is the same commit → effect pair the lazy late-Accept path and
the overdue-invitation sweep (CM-28-015) run, through their shared
:class:`~vultron.core.behaviors.embargo.nodes.invitation_expiry.ExpireInvitationsNode`.
"""

from typing import ClassVar

from vultron.core.behaviors.embargo.nodes.invitation_expiry import (
    ExpireInvitationsNode,
    latest_invite_id,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle


class ExpirePendingInvitesOnCloseNode(ExpireInvitationsNode):
    """Expire every embargo Invite still awaiting a reply (CM-23-014).

    Runs in the owner-close sequence after
    :class:`~vultron.core.behaviors.case.nodes.leave.record.CommitRMClosureEntriesNode`
    and before ``case_fully_closed``, so every expired-invitation entry
    precedes ``case_fully_closed``.  The invitations are
    :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.pending_invitations`.

    The CASE_MANAGER gate is the received tree's own: the node sits in the
    close tree's ``manager_effects``, which the factory wraps in
    ``CloseCaseEffectsIfCaseManager`` (BT-17-008, CM-28-014).

    The deadline is not read: after close an Invite can only expire.  A row
    on a final register entry is frozen (ADR-0122) and is not pending, so the
    case Invite of a stub invitee, whose row sits on the embargo the close
    already required to end (CM-23-011), needs no settling either.  A
    pending Invite left unexpired by a refused commit does not justify
    keeping the case open, so the close goes on (best-effort, see the base).
    """

    _SPEC: ClassVar[str] = "CM-23-014"

    def _invitations(
        self, lifecycle: EmbargoLifecycle
    ) -> list[tuple[CaseParticipant, str]]:
        return lifecycle.pending_invitations(self._case_id)

    def _what(self) -> str:
        return "pending"


__all__ = ["ExpirePendingInvitesOnCloseNode", "latest_invite_id"]
