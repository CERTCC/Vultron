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

"""Invitee-side effect nodes for a received ``Invite(Actor, Case)``.

The invitee holds only the Invite's case stub until the CASE_MANAGER announces
the case (MV-10-003, MV-10-004), so it records two things and creates no case:
the narrative milestone (SL-04-006) and the trust anchor that lets it admit the
inviting CASE_MANAGER's later ``Announce`` before its replica exists
(PCR-03-004).  Composed by ``create_invite_actor_to_case_received_tree``
behind ``create_participant_replica_gated_tree`` (BTND-07-003).
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.narrative_log import log_invite_received
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox

logger = logging.getLogger(__name__)


class LogInviteReceivedNode(DataLayerAction):
    """Log the invitee's receipt of a case invitation at INFO (SL-04-006)."""

    def __init__(
        self,
        invitee_id: str,
        case_id: str,
        sender_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self.case_id = case_id
        self.sender_id = sender_id

    def update(self) -> Status:
        log_invite_received(
            logger, self.invitee_id, self.case_id, self.sender_id
        )
        logger.debug(
            "%s: invite holds case stub '%s'. Awaiting"
            " AnnounceVulnerabilityCase before creating the case (MV-10-004)",
            self.name,
            self.case_id,
        )
        return Status.SUCCESS


class RecordInviteTrustAnchorNode(DataLayerAction):
    """Record the inviting CASE_MANAGER as the case's expected Announce sender.

    Writes a :class:`VultronPendingCaseInbox` so
    ``AnnounceVulnerabilityCaseReceivedUseCase`` admits a later Announce from
    the same actor before the local case replica exists (PCR-03-004 path b).

    First invite wins: a record that already names a ``case_actor_id`` is kept
    unchanged.  A record with ``case_actor_id=None`` — created by the
    pre-bootstrap queue for an earlier ledger entry — gains the sender.
    """

    def __init__(
        self,
        case_id: str,
        case_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.case_actor_id = case_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        existing = self.datalayer.read(
            VultronPendingCaseInbox.build_id(self.case_id)
        )
        if not isinstance(existing, VultronPendingCaseInbox):
            self.datalayer.save(
                VultronPendingCaseInbox(
                    case_id=self.case_id,
                    case_actor_id=self.case_actor_id,
                )
            )
            self.logger.debug(
                "%s: trust anchor recorded for case '%s'",
                self.name,
                self.case_id,
            )
        elif existing.case_actor_id is None:
            self.datalayer.save(
                existing.model_copy(
                    update={"case_actor_id": self.case_actor_id}
                )
            )
            self.logger.debug(
                "%s: trust anchor added to the pending record for case '%s'",
                self.name,
                self.case_id,
            )
        return Status.SUCCESS
