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

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import get_pending_assertion_store
from vultron.core.participants.role_predicate import has_role
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

_PROPOSAL_SEMANTIC_TYPE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value
_ACCEPT_SEMANTIC_TYPE = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value


def close_refused_embargo_ask(
    datalayer: CasePersistence,
    *,
    receiving_actor_id: str,
    case_id: str,
    invite_id: str,
    rejecting_actor_id: str,
    at: datetime,
) -> bool:
    """Clear *receiving_actor_id*'s pending entry for the ask the manager refused.

    The ``Reject`` names an Invite: the participant's own proposal, recorded
    under its id, or the Invite the participant accepted, which its pending
    Accept names as its subject.  A no-op unless *rejecting_actor_id* is the
    CASE_MANAGER of a case this replica holds; each clear is itself a no-op
    when no such entry is pending.

    *at* is the instant this delivery is being handled at, which the lookup
    for the pending Accept judges the entry's age against (SYNC-11-005); it
    reads no clock of its own (#5591).

    Returns:
        True when the rejecting actor is the case's CASE_MANAGER, so the
        Reject was the manager's refusal and its pending ask is closed.
    """
    # The one source of "is the sender the case's authority" (ARCH-24-008):
    # ``False`` when this replica holds no such case.  The roster and the
    # sender id are both canonical (OID-01-006, OID-01-007, #5919).
    if not has_role(
        rejecting_actor_id, case_id, CVDRole.CASE_MANAGER, datalayer
    ):
        return False
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
        rejecting_actor_id,
        receiving_actor_id,
        invite_id,
        case_id,
    )
    return True


class ClosePendingEmbargoAskNode(DataLayerActionWithPorts):
    """Close the executing participant's pending ask the manager's Reject refuses.

    Runs on the participant-replica path of the received
    ``Reject(Invite(EmbargoEvent))`` tree, after the door guards admitted the
    Reject and intake recorded it, and before the tree states the replica's
    refusal (EP-09-019, EMB-02-004): the Reject records nothing in the case
    there, but a CASE_MANAGER's Reject still closes the ask the participant
    is waiting on.  The stages between intake and this node (ledger
    position, sender sequence, clock decisions) run only at the
    CASE_MANAGER, so at a replica only an intake fault stops the run short
    of it, and a delivery that was never recorded has not arrived.  It
    decides nothing, so it always succeeds.  It runs among the guards
    yet writes: the pending-assertion store it clears is a per-actor
    duplicate suppressor, not case state (CLP-06-002), so the write is no
    effect of the act.

    Args:
        case_id: The case the Reject names.
        invite_id: The Invite the Reject names.
        rejecting_actor_id: The Reject's sender.
    """

    def __init__(
        self,
        case_id: str,
        invite_id: str,
        rejecting_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._invite_id = invite_id
        self._rejecting_actor_id = rejecting_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        closed = close_refused_embargo_ask(
            self.datalayer,
            receiving_actor_id=self.actor_id,
            case_id=self._case_id,
            invite_id=self._invite_id,
            rejecting_actor_id=self._rejecting_actor_id,
            at=self._require_act_instant(),
        )
        self.feedback_message = (
            f"closed the pending ask about Invite '{self._invite_id}'"
            if closed
            else f"'{self._rejecting_actor_id}' is not the CASE_MANAGER;"
            " no pending ask closed"
        )
        return Status.SUCCESS


__all__ = ["ClosePendingEmbargoAskNode", "close_refused_embargo_ask"]
