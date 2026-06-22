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

"""Actor-participation emit nodes for case behavior trees.

Provides leaf action nodes that emit outbound activities for actor
invitation and invite-acceptance workflows, and for applying received
ownership-transfer decisions to the case record.

Composite subtrees assembling these leaf nodes are defined in the sibling
``actor_trigger_trees.py`` and ``ownership_transfer_tree.py`` modules at
the process-area root per BTND-07-003:

- ``invite_actor_to_case_trigger_bt``
- ``accept_case_invite_trigger_bt``
- ``create_accept_ownership_transfer_tree``
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import _as_id


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


class AcceptCaseOwnershipTransferNode(DataLayerAction):
    """Apply an ownership-transfer acceptance to the case record.

    Reads the case from the DataLayer, updates ``case.attributed_to`` to
    the new owner, and persists the updated case.  Idempotent: when the
    case is already owned by ``new_owner_id``, returns ``SUCCESS`` without
    mutation.

    Returns ``SUCCESS`` on success or when already idempotent, ``FAILURE``
    when the DataLayer is unavailable or the case is not found.
    """

    def __init__(
        self,
        case_id: str,
        new_owner_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.new_owner_id = new_owner_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"case '{self.case_id}' not found"
            self.logger.warning(
                "%s: case '%s' not found",
                self.name,
                self.case_id,
            )
            return Status.FAILURE

        current_owner_id = _as_id(case.attributed_to)
        if current_owner_id == self.new_owner_id:
            self.logger.info(
                "%s: case '%s' already owned by '%s' — skipping (idempotent)",
                self.name,
                self.case_id,
                self.new_owner_id,
            )
            return Status.SUCCESS

        case.attributed_to = self.new_owner_id  # type: ignore[assignment]
        self.datalayer.save(case)
        self.logger.info(
            "%s: transferred ownership of case '%s' from '%s' to '%s'",
            self.name,
            self.case_id,
            current_owner_id,
            self.new_owner_id,
        )
        return Status.SUCCESS
