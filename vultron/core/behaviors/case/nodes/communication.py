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
Communication action nodes for case behavior trees.

Provides action nodes that emit outbound activities related to case creation,
case-manager role offers, and case-manager role auto-acceptance.

Composite subtrees assembling these leaf nodes are defined in the sibling
``communication_tree.py`` module at the process-area root per BTND-07-003:

- ``EmitCreateCaseActivity``
- ``SendOfferCaseManagerRoleNode``
"""

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.models.vultron_types import VultronCreateCaseActivity
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)


class CollectCaseAddresseesNode(DataLayerAction):
    """Resolve case object and peer addressees for Create(Case) emission."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="create_case_obj", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="create_case_addressees", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
        except KeyError:
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE
        if not isinstance(case_id, str):
            self.logger.error(
                f"{self.name}: case_id must be a string, got {type(case_id)}"
            )
            return Status.FAILURE

        case_obj = self.datalayer.read(case_id)
        if is_case_model(case_obj):
            addressees = [
                actor_id
                for actor_id in case_obj.actor_participant_index.keys()
                if actor_id != self.actor_id
            ]
        else:
            addressees = []

        if addressees:
            self.logger.info(
                f"{self.name}: Notifying addressees: {addressees}"
            )

        self.blackboard.create_case_obj = case_obj
        self.blackboard.create_case_addressees = addressees
        return Status.SUCCESS


class CreateAndPersistCaseActivityNode(DataLayerAction):
    """Build and persist Create(Case), then publish activity_id to blackboard."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="create_case_obj", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="create_case_addressees", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.WRITE
        )

    def _read_case_id(self) -> str | None:
        try:
            case_id = self.blackboard.get("case_id")
        except KeyError:
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return None
        if not isinstance(case_id, str):
            self.logger.error(
                f"{self.name}: case_id must be a string, got {type(case_id)}"
            )
            return None
        return case_id

    def _read_case_obj(self) -> Any | None:
        try:
            return self.blackboard.get("create_case_obj")
        except KeyError:
            return None

    def _read_addressees(self) -> list[str] | None:
        try:
            addressees = self.blackboard.get("create_case_addressees")
        except KeyError:
            return []
        if not isinstance(addressees, list):
            self.logger.error(
                f"{self.name}: create_case_addressees must be a list"
            )
            return None
        return addressees

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        case_id = self._read_case_id()
        if case_id is None:
            return Status.FAILURE

        case_obj = self._read_case_obj()
        addressees = self._read_addressees()
        if addressees is None:
            return Status.FAILURE

        activity = VultronCreateCaseActivity(
            actor=self.actor_id,
            object_=case_obj if case_obj is not None else case_id,
            context=case_id,
            to=addressees if addressees else None,
        )
        try:
            self.datalayer.create(activity)
            self.logger.info(
                f"{self.name}: Created CreateCaseActivity activity"
                f" {activity.id_}"
            )
        except ValueError as e:
            self.logger.warning(
                f"{self.name}: CreateCaseActivity activity {activity.id_}"
                f" already exists: {e}"
            )

        self.blackboard.activity_id = activity.id_
        return Status.SUCCESS


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

        try:
            accept_id = self.trigger_activity_factory.accept_case_manager_role(
                offer_id=self.offer_id,
                case_id=self.case_id,
                participant_id=self.participant_id,
                vendor_id=self.vendor_id,
                actor=self.actor_id,
                to=[self.vendor_id],
            )
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
        except Exception as exc:
            self.logger.error(
                "%s: error auto-accepting offer '%s': %s",
                self.name,
                self.offer_id,
                exc,
            )
            return Status.FAILURE
