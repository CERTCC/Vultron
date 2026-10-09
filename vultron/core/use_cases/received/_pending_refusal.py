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

"""Close the receiver's pending embargo proposal on the manager's refusal.

A participant that is not the CASE_MANAGER asks the manager for embargo
terms and records the ``Invite`` it queued in its pending-assertion store
(EP-09-008, SYNC-11-002).  The manager's commit of an *admitted* proposal
clears that entry when it is announced (SYNC-11-003).  A *refused* proposal
is never committed, so the entry closes when the CASE_MANAGER's
``Reject(Invite(EmbargoEvent))`` of it reaches the proposer (EP-09-008, last
sentence).  A ``Reject`` from anybody else is a participant's answer, not the
manager's refusal, and closes nothing.
"""

import logging

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.embargo import (
    RejectInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.pending_assertion import get_pending_assertion_store
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import resolve_receiving_actor_id

logger = logging.getLogger(__name__)

_PROPOSAL_EVENT_TYPE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value


def close_refused_embargo_proposal(
    dl: CasePersistence, request: RejectInviteToEmbargoOnCaseReceivedEvent
) -> None:
    """Clear the pending entry for the proposal the CASE_MANAGER refused.

    A no-op unless the ``Reject`` names a case this replica holds and the
    rejecting actor is that case's CASE_MANAGER; the store's ``clear`` is
    itself a no-op when no entry for the refused ``Invite`` is pending.
    """
    case_id, invite_id = request.case_id, request.invite_id
    if not case_id or not invite_id:
        return
    case = dl.read(case_id)
    if not isinstance(case, VulnerabilityCase):
        return
    if resolve_case_manager_id(case, dl) != request.actor_id:
        return
    receiving_actor_id = resolve_receiving_actor_id(
        dl, request.receiving_actor_id
    )
    get_pending_assertion_store(receiving_actor_id).clear(
        case_id, _PROPOSAL_EVENT_TYPE, invite_id
    )
    logger.info(
        "CASE_MANAGER '%s' refused embargo proposal '%s' on case '%s';"
        " closed '%s''s pending assertion (EP-09-008)",
        request.actor_id,
        invite_id,
        case_id,
        receiving_actor_id,
    )


__all__ = ["close_refused_embargo_proposal"]
