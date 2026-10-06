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

"""The ER a receiver sends when it refuses an embargo Invite or its Accept.

Once P/X/A is set, a received ``Invite(EmbargoEvent)`` (EMB-01-002) or
``Accept`` of one (EMB-02-002) is answered with ER, a ``Reject`` of the Invite.
The ``Reject`` is the receiver's record of its decision: it carries an id derived
from the rejecting actor and the Invite, so a re-delivery finds it already sent
and is skipped rather than answered twice (HP-01-003, CLP-13-001).  The ER is
queued by a node of this tree, not by the use case's ``execute()`` (CLP-10-020).
"""

import logging

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.invite_answer import (
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.embargo.nodes.proposal import (
    CreateAndStoreInviteNode,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.models.embargo_event import EmbargoEvent

logger = logging.getLogger(__name__)


class EmbargoInviteNotYetRefusedNode(
    SilentIdempotencyGuardMixin, DataLayerActionWithPorts
):
    """Idempotency guard: this actor has not yet sent ER for this Invite.

    FAILURE means the ER was already sent; the handler reads it as a
    re-delivery (CLP-13-001, HP-01-003).  The ER is sealed before it is
    queued, so an ER sealed but no longer pending is queued again under its
    own id rather than taken as delivered (ID-04-005).  A missing
    trigger-activity port sends nothing, so there is nothing to repeat.
    """

    def __init__(self, invite_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._invite_id = invite_id

    def update(self) -> Status:
        if self.trigger_activity_factory is None or self.actor_id is None:
            return Status.SUCCESS
        if self.trigger_activity_factory.requeue_embargo_refusal(
            self.actor_id, self._invite_id
        ):
            self.feedback_message = (
                f"ER for Invite '{self._invite_id}' was already sent by"
                f" '{self.actor_id}'"
            )
            return self._idempotent_failure(
                self.logger,
                "%s: %s — skipping (CLP-13-001)",
                self.name,
                self.feedback_message,
            )
        return Status.SUCCESS


def embargo_invite_refusal_tree(
    case_id: str,
    invite_id: str,
    recipient_id: str | None,
    *,
    store_invite: bool,
    embargo: EmbargoEvent | None = None,
    answer: bool = True,
) -> py_trees.behaviour.Behaviour:
    """Create the BT that archives a refused message and answers it with ER.

    The shared receive factory archives what arrived first, so the receiver
    holds the Invite (or the Accept) even when it answers nothing (CLP-10-018).
    No ledger entry is committed: a refusal is a decision about a message, not
    a case event (CLP-13-001).

    Args:
        case_id: The case the embargo was proposed for.
        invite_id: The Invite being refused.
        recipient_id: Who the ER goes to; ``None`` for the case's CASE_MANAGER.
        store_invite: ``True`` on the receive of the Invite itself, which
            stores it as the activity it is so the ER can be built from it.
            ``False`` on the receive of an Accept, where the receiver sent
            the Invite and holds it.
        embargo: The inline terms the received Invite carries, if any; stored
            so the ER can be built from the stored Invite.
        answer: ``False`` to store what arrived and send nothing, for an
            Invite not addressed to this actor (EP-09-010).
    """
    guards: list[py_trees.behaviour.Behaviour] = []
    effects: list[py_trees.behaviour.Behaviour] = []
    if store_invite:
        effects.append(CreateAndStoreInviteNode())
    if embargo is not None:
        effects.append(PersistEmbargoEventNode(embargo=embargo))
    if answer:
        guards.append(EmbargoInviteNotYetRefusedNode(invite_id=invite_id))
        effects.append(
            SendEmbargoInviteAnswerNode(
                case_id=case_id,
                invite_id=invite_id,
                accept=False,
                recipient_id=recipient_id,
                name="SendEmbargoRefusalER",
            )
        )
    return create_receive_activity_tree(
        name="RefuseEmbargoInviteBT",
        case_id=None,
        precondition_guards=guards,
        effect_nodes=effects,
    )


__all__ = ["EmbargoInviteNotYetRefusedNode", "embargo_invite_refusal_tree"]
