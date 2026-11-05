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

"""Close the receiver's pending embargo ask on the manager's refusal.

A participant that is not the CASE_MANAGER asks the manager for embargo
terms, or answers an embargo Invite, and records the activity it queued in
its pending-assertion store (EP-09-018, SYNC-11-002).  The manager's commit
of an *admitted* ask clears that entry when it is announced (SYNC-11-003).  A
*refused* one is never committed, so the entry closes when the CASE_MANAGER's
``Reject(Invite(EmbargoEvent))`` reaches the participant: of the proposal it
sent (EP-09-017, CLP-05-009), or of the Invite whose Accept it refuses
once P/X/A is set (EMB-02-004).  A ``Reject`` from anybody
else is a participant's answer, not the manager's refusal, and closes
nothing.
"""

import logging
from datetime import datetime

from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.embargo import (
    RejectInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.pending_assertion import get_pending_assertion_store
from vultron.core.participants.role_predicate import has_role
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

_PROPOSAL_SEMANTIC_TYPE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value
_ACCEPT_SEMANTIC_TYPE = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value


def close_refused_embargo_ask(
    dl: CasePersistence,
    request: RejectInviteToEmbargoOnCaseReceivedEvent,
    *,
    at: datetime,
) -> None:
    """Clear the pending entry for the ask the CASE_MANAGER refused.

    The ``Reject`` names an Invite: the participant's own proposal, recorded
    under its id, or the Invite the participant accepted, which its pending
    Accept names as its subject.  A no-op unless the ``Reject`` names a case
    this replica holds and the rejecting actor is that case's CASE_MANAGER;
    each clear is itself a no-op when no such entry is pending.

    *at* is the instant this delivery is being handled at, which the lookup
    for the pending Accept judges the entry's age against (SYNC-11-005); it
    reads no clock of its own (#5591).
    """
    case_id, invite_id = request.case_id, request.invite_id
    if not case_id or not invite_id:
        return
    # The one source of "is the sender the case's authority" (ARCH-24-008):
    # ``False`` when this replica holds no such case, and tolerant of the
    # roster spelling the manager with a trailing slash, which the sender id
    # never carries (OID-01-006, OID-01-007).
    if not has_role(request.actor_id, case_id, CVDRole.CASE_MANAGER, dl):
        return
    receiving_actor_id = resolve_receiving_actor_id(
        dl, request.receiving_actor_id
    )
    store = get_pending_assertion_store(receiving_actor_id)
    store.clear(case_id, _PROPOSAL_SEMANTIC_TYPE, invite_id)
    accept = store.pending_for_subject(
        case_id, _ACCEPT_SEMANTIC_TYPE, invite_id, at=at
    )
    if accept is not None:
        store.clear(case_id, _ACCEPT_SEMANTIC_TYPE, accept.object_id)
    logger.info(
        "CASE_MANAGER '%s' refused '%s''s embargo ask about Invite '%s' on"
        " case '%s'; closed its pending assertion (EP-09-019, EMB-02-004)",
        request.actor_id,
        receiving_actor_id,
        invite_id,
        case_id,
    )


__all__ = ["close_refused_embargo_ask"]
