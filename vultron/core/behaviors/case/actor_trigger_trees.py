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

"""Trigger-side behavior trees for actor-participation workflows.

Three trigger trees are provided:

- ``suggest_actor_to_case_trigger_bt`` — SenderSideBT wrapper for
  Offer(Actor, Case) routed through the Case Manager (PCR-08-001).
- ``invite_actor_to_case_trigger_bt`` — direct-route Sequence for
  Invite(Actor, Case) sent from the Case Actor identity.
- ``accept_case_invite_trigger_bt`` — Sequence for Accept(Invite)
  sent by the invitee.

Per specs/behavior-tree-integration.yaml BT-15-001, BT-15-002.
"""

import logging
from typing import Callable, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)


class EmitInviteActorToCaseNode(DataLayerAction):
    """Create Invite(Actor, Case) and queue in the Case Actor's outbox.

    Uses ``trigger_activity_factory.invite_actor_to_case()`` with
    ``actor=self.actor_id`` (expected to be the Case Actor URI) and
    ``to=[invitee_id]``.  An optional ``attributed_to`` carries the
    original requesting actor when the invite is sent from the Case
    Actor identity (PCR-08-007).
    """

    def __init__(
        self,
        invitee_id: str,
        case_id: str,
        attributed_to: str | None = None,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self.case_id = case_id
        self.attributed_to = attributed_to
        self._captured = captured

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        factory = self.trigger_activity_factory
        if factory is None:
            self.feedback_message = (
                "trigger_activity_factory not in blackboard"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        try:
            activity_id, activity_dict = factory.invite_actor_to_case(
                invitee_id=self.invitee_id,
                case_id=self.case_id,
                actor=self.actor_id,
                to=[self.invitee_id],
                attributed_to=self.attributed_to,
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            if self._captured is not None:
                self._captured["activity"] = activity_dict
            self.logger.info(
                "Actor '%s' emitted Invite(Actor, Case) to '%s' for case '%s'",
                self.actor_id,
                self.invitee_id,
                self.case_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.feedback_message = f"EmitInviteActorToCase failed: {e}"
            self.logger.error(self.feedback_message)
            return Status.FAILURE


class EmitAcceptCaseInviteNode(DataLayerAction):
    """Create Accept(Invite) and queue in the invitee's outbox.

    Uses ``trigger_activity_factory.accept_case_invite()`` — the factory
    derives the recipient from the persisted invite object.
    """

    def __init__(
        self,
        invite_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invite_id = invite_id
        self._captured = captured

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        factory = self.trigger_activity_factory
        if factory is None:
            self.feedback_message = (
                "trigger_activity_factory not in blackboard"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        try:
            activity_id, activity_dict = factory.accept_case_invite(
                invite_id=self.invite_id,
                actor=self.actor_id,
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            if self._captured is not None:
                self._captured["activity"] = activity_dict
            self.logger.info(
                "Actor '%s' accepted case invite '%s'",
                self.actor_id,
                self.invite_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.feedback_message = f"EmitAcceptCaseInvite failed: {e}"
            self.logger.error(self.feedback_message)
            return Status.FAILURE


def suggest_actor_to_case_trigger_bt(
    case_id: str,
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the suggest-actor workflow.

    Routes Offer(Actor, Case) through the Case Manager via
    :func:`~vultron.core.behaviors.sender.send_tree.sender_side_bt`
    (PCR-08-001).

    Args:
        case_id: ID of the VulnerabilityCase.
        activity_builder: Closure called with the resolved Case Manager ID;
            returns the list of outbound activity IDs.

    Returns:
        SenderSideBT Sequence.
    """
    return sender_side_bt(case_id=case_id, activity_builder=activity_builder)


def invite_actor_to_case_trigger_bt(
    invitee_id: str,
    case_id: str,
    attributed_to: str | None = None,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the invite-actor workflow.

    Emits Invite(Actor, Case) from the Case Actor's identity directly to
    the invitee (no Case Manager resolution needed — the Case Actor IS the
    routing endpoint here per PCR-08-007).

    Args:
        invitee_id: Actor URI of the participant being invited.
        case_id: ID of the VulnerabilityCase.
        attributed_to: Optional original requesting actor URI.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitInviteActorToCaseNode.
    """
    root = py_trees.composites.Sequence(
        name="InviteActorToCaseTriggerBT",
        memory=False,
        children=[
            EmitInviteActorToCaseNode(
                invitee_id=invitee_id,
                case_id=case_id,
                attributed_to=attributed_to,
                captured=captured,
            ),
        ],
    )
    logger.debug(
        "Created InviteActorToCaseTriggerBT for invitee=%s case=%s",
        invitee_id,
        case_id,
    )
    return root


def accept_case_invite_trigger_bt(
    invite_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the accept-case-invite workflow.

    Emits Accept(Invite) from the invitee's identity; the factory derives
    the recipient from the persisted invite object.

    Args:
        invite_id: ID of the RmInviteToCaseActivity being accepted.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitAcceptCaseInviteNode.
    """
    root = py_trees.composites.Sequence(
        name="AcceptCaseInviteTriggerBT",
        memory=False,
        children=[
            EmitAcceptCaseInviteNode(
                invite_id=invite_id,
                captured=captured,
            ),
        ],
    )
    logger.debug("Created AcceptCaseInviteTriggerBT for invite=%s", invite_id)
    return root
