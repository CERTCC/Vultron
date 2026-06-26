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

"""
CASE_MANAGER delegation action nodes for case behavior trees.

Provides action nodes for the CASE_MANAGER role delegation workflow:
offering, auto-accepting, and explicitly rejecting the delegation.

Composite subtrees assembling these leaf nodes are defined in the sibling
``communication_tree.py`` module at the process-area root per BTND-07-003:

- ``SendOfferCaseManagerRoleNode``

See DEMOMA-08-002, DEMOMA-08-003; Issue #469, Issue #1067.
"""

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)


class ResolveCaseManagerOfferContextNode(DataLayerAction):
    """Validate blackboard context and stage Offer recipients."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_participant_id",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="offer_case_manager_to", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        case_id = self.blackboard.get("case_id")
        case_actor_id = self.blackboard.get("case_actor_id")
        participant_id = self.blackboard.get("case_actor_participant_id")
        if (
            not isinstance(case_id, str)
            or not isinstance(case_actor_id, str)
            or not isinstance(participant_id, str)
        ):
            self.logger.error(
                f"{self.name}: case_id, case_actor_id, or"
                " case_actor_participant_id missing from blackboard"
            )
            return Status.FAILURE

        self.blackboard.offer_case_manager_to = [case_actor_id]
        return Status.SUCCESS


class CreateOfferCaseManagerActivityNode(DataLayerAction):
    """Create Offer(CaseManagerRole) via trigger_activity_factory."""

    def __init__(
        self,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._captured = captured

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_participant_id",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="offer_case_manager_to", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        if self.trigger_activity_factory is None:
            self.logger.error(
                f"{self.name}: trigger_activity_factory not available"
            )
            return Status.FAILURE

        case_id = self.blackboard.get("case_id")
        case_actor_id = self.blackboard.get("case_actor_id")
        participant_id = self.blackboard.get("case_actor_participant_id")
        recipients = self.blackboard.get("offer_case_manager_to")

        if (
            not isinstance(case_id, str)
            or not isinstance(case_actor_id, str)
            or not isinstance(participant_id, str)
            or not isinstance(recipients, list)
        ):
            self.logger.error(
                f"{self.name}: case_id, case_actor_id, or"
                " case_actor_participant_id missing from blackboard"
            )
            return Status.FAILURE

        try:
            activity_id = (
                self.trigger_activity_factory.offer_case_manager_role(
                    case_id=case_id,
                    participant_id=participant_id,
                    actor=case_actor_id,
                    to=recipients,
                )
            )
            self.blackboard.activity_id = activity_id
            if self._captured is not None:
                activity_obj = self.datalayer.read(activity_id)
                if activity_obj is not None and hasattr(
                    activity_obj, "model_dump"
                ):
                    self._captured["activity"] = activity_obj.model_dump(
                        mode="json",
                        by_alias=True,
                        serialize_as_any=True,
                        exclude_none=True,
                    )
            self.logger.info(
                "%s: Queued Offer(CaseManagerRole) '%s' to Case Actor '%s'"
                " for case '%s'",
                self.name,
                activity_id,
                case_actor_id,
                case_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error sending Offer(CaseManagerRole): {e}"
            )
            return Status.FAILURE


class AutoAcceptCaseManagerRoleNode(DataLayerAction):
    """Auto-accept a CASE_MANAGER role delegation offer on behalf of the local actor.

    When the local actor (the Case Actor entity) receives an
    ``Offer(CaseManagerRole)`` it MUST auto-accept so the offering Vendor
    receives confirmation.  This node creates the ``Accept`` activity via
    ``trigger_activity_factory`` and queues it in the local actor's outbox.

    Returns ``FAILURE`` when ``trigger_activity_factory`` is not available
    so that the enclosing Sequence propagates the failure rather than
    silently continuing.  Callers that want the guarded-commit subtree to
    run regardless of auto-accept status should wrap this node in a
    ``Selector`` with a ``Success`` fallback.

    See DEMOMA-08-002, DEMOMA-08-003; Issue #469, Issue #1021.
    """

    def __init__(
        self,
        offer_id: str,
        case_id: str,
        participant_id: str,
        vendor_id: str,
        name: str | None = None,
    ) -> None:
        """Initialise the node.

        Args:
            offer_id: ID of the ``Offer(CaseManagerRole)`` activity.
            case_id: ID of the VulnerabilityCase referenced by the offer.
            participant_id: ID of the CaseParticipant being offered the role.
            vendor_id: Actor ID of the offering Vendor (recipient of Accept).
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.offer_id = offer_id
        self.case_id = case_id
        self.participant_id = participant_id
        self.vendor_id = vendor_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: trigger_activity_factory not available"
                " — cannot auto-accept offer '%s'",
                self.name,
                self.offer_id,
            )
            return Status.FAILURE

        if not self.case_id or not self.participant_id:
            self.logger.warning(
                "%s: missing case_id or participant_id for offer '%s'"
                " — skipping auto-accept",
                self.name,
                self.offer_id,
            )
            return Status.FAILURE

        # Step 1: create and persist the Accept activity.
        # Nothing has been written yet; any exception here is safe to
        # convert to FAILURE so the AcceptOrReject Selector can fall back
        # to EmitRejectCaseManagerRoleNode.
        try:
            accept_id = self.trigger_activity_factory.accept_case_manager_role(
                offer_id=self.offer_id,
                case_id=self.case_id,
                participant_id=self.participant_id,
                vendor_id=self.vendor_id,
                actor=self.actor_id,
                to=[self.vendor_id],
            )
        except Exception as exc:
            self.logger.error(
                "%s: error creating Accept activity for offer '%s': %s",
                self.name,
                self.offer_id,
                exc,
            )
            return Status.FAILURE

        # Step 2: enqueue the Accept activity to the outbox.
        # The Accept is now persisted in the DataLayer.  If outbox enqueue
        # fails here, we MUST NOT return FAILURE — the AcceptOrReject
        # Selector would then fall through to EmitRejectCaseManagerRoleNode,
        # producing contradictory protocol state (Accept stored, Reject sent).
        # Let the exception propagate so BTBridge fails the tree hard,
        # preserving the persisted Accept without triggering a spurious Reject.
        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
            self.actor_id, accept_id
        )

        self.logger.info(
            "%s: auto-accepted offer '%s' as actor '%s';"
            " queued Accept '%s' to outbox",
            self.name,
            self.offer_id,
            self.actor_id,
            accept_id,
        )
        return Status.SUCCESS


class EmitRejectCaseManagerRoleNode(DataLayerAction):
    """Emit a Reject(Offer(CaseManagerRole)) to the offering Vendor.

    Used as the fallback branch of the ``AcceptOrReject`` Selector after
    :class:`AutoAcceptCaseManagerRoleNode`.  When the Case Actor cannot
    auto-accept the role delegation offer (for example, the accept call fails
    due to a business constraint), this node sends an explicit ``Reject`` so
    the offering Vendor is notified rather than receiving silence.

    Returns ``FAILURE`` on any error so callers can observe the failure.

    See DEMOMA-08-002, DEMOMA-08-003; Issue #1067.
    """

    def __init__(
        self,
        offer_id: str,
        case_id: str,
        participant_id: str,
        vendor_id: str,
        name: str | None = None,
    ) -> None:
        """Initialise the node.

        Args:
            offer_id: ID of the ``Offer(CaseManagerRole)`` activity.
            case_id: ID of the VulnerabilityCase referenced by the offer.
            participant_id: ID of the CaseParticipant being offered the role.
            vendor_id: Actor ID of the offering Vendor (recipient of Reject).
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.offer_id = offer_id
        self.case_id = case_id
        self.participant_id = participant_id
        self.vendor_id = vendor_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: trigger_activity_factory not available"
                " — cannot emit Reject for offer '%s'",
                self.name,
                self.offer_id,
            )
            return Status.FAILURE

        if not self.case_id or not self.participant_id:
            self.logger.warning(
                "%s: missing case_id or participant_id for offer '%s'"
                " — cannot emit Reject",
                self.name,
                self.offer_id,
            )
            return Status.FAILURE

        try:
            reject_id = self.trigger_activity_factory.reject_case_manager_role(
                offer_id=self.offer_id,
                case_id=self.case_id,
                participant_id=self.participant_id,
                vendor_id=self.vendor_id,
                actor=self.actor_id,
                to=[self.vendor_id],
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, reject_id
            )
            self.logger.info(
                "%s: emitted Reject(Offer(CaseManagerRole)) '%s'"
                " to vendor '%s' for offer '%s'",
                self.name,
                reject_id,
                self.vendor_id,
                self.offer_id,
            )
            return Status.SUCCESS
        except Exception as exc:
            self.logger.error(
                "%s: error emitting Reject for offer '%s': %s",
                self.name,
                self.offer_id,
                exc,
            )
            return Status.FAILURE
