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


"""Use cases for an invitee's answer to a case invitation.

No HTTP framework imports permitted here.
"""

import logging
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.case.actor_trigger_trees import (
    accept_case_invite_trigger_bt,
    reject_case_invite_trigger_bt,
)
from vultron.core.services.received_activity import (
    holds_received_activity,
)
from vultron.core.use_cases.triggers._base import SvcActivityTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseInviteTriggerRequest,
    RejectCaseInviteTriggerRequest,
)
from vultron.errors import (
    VultronNotFoundError,
)

logger = logging.getLogger(__name__)


class SvcAcceptCaseInviteUseCase(SvcActivityTriggerBase):
    """Accept a case invitation by emitting RmAcceptInviteToCaseActivity.

    The invitee actor reads the invite from the DataLayer and queues the
    Accept activity for delivery to the Case Actor.
    """

    def _prepare(self) -> None:
        request = cast(AcceptCaseInviteTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_

        # Held as the body intake archived (CLP-10-017): a stub Invite
        # precedes its case, so the inbox processes it on arrival
        # (PCR-06-005).
        if not holds_received_activity(self._dl, request.invite_id):
            raise VultronNotFoundError(
                "RmInviteToCaseActivity", request.invite_id
            )

        self._invite_id = request.invite_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return accept_case_invite_trigger_bt(
            invite_id=self._invite_id,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' accepted case invite '%s'",
            self._actor_id,
            self._invite_id,
        )


class SvcRejectCaseInviteUseCase(SvcActivityTriggerBase):
    """Reject a case invitation by emitting RmRejectInviteToCaseActivity.

    The invitee actor reads the invite from the DataLayer and queues the
    Reject activity for delivery to the Case Actor.
    """

    def _prepare(self) -> None:
        request = cast(RejectCaseInviteTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_

        # Held as the body intake archived (CLP-10-017): a stub Invite
        # precedes its case, so the inbox processes it on arrival
        # (PCR-06-005).
        if not holds_received_activity(self._dl, request.invite_id):
            raise VultronNotFoundError(
                "RmInviteToCaseActivity", request.invite_id
            )

        self._invite_id = request.invite_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return reject_case_invite_trigger_bt(
            invite_id=self._invite_id,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' rejected case invite '%s'",
            self._actor_id,
            self._invite_id,
        )
