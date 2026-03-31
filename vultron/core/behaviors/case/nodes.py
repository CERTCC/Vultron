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
Case management behavior tree nodes.

Provides condition and action nodes for the create_case workflow,
implementing idempotency guards, persistence, and outbox management
for VulnerabilityCase creation.

Per specs/behavior-tree-integration.md BT-07 and specs/case-management.md
CM-02 requirements.
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.models.protocols import has_outbox, is_case_model
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronCreateCaseActivity,
    VultronParticipant,
)
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRoles
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerCondition,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Condition Nodes
# ============================================================================


class CheckCaseAlreadyExists(DataLayerCondition):
    """
    Check if a VulnerabilityCase already exists in DataLayer.

    Returns SUCCESS if the case already exists (idempotency early exit).
    Returns FAILURE if the case does not exist (proceed with creation).

    Per specs/idempotency.md ID-04-004.
    """

    def __init__(self, case_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            existing = self.datalayer.read(self.case_id)
            if existing is not None:
                self.logger.info(
                    f"{self.name}: Case {self.case_id} already exists"
                    " — skipping creation (idempotent)"
                )
                return Status.SUCCESS

            self.logger.debug(
                f"{self.name}: Case {self.case_id} not found, proceeding"
            )
            return Status.FAILURE

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error checking case existence: {e}"
            )
            return Status.FAILURE


class ValidateCaseObject(DataLayerCondition):
    """
    Validate the incoming VulnerabilityCase object has required fields.

    Returns SUCCESS if the case object passes validation.
    Returns FAILURE if required fields are missing.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        try:
            if self.case_obj is None:
                self.logger.error(f"{self.name}: case_obj is None")
                return Status.FAILURE

            if not getattr(self.case_obj, "id_", None):
                self.logger.error(f"{self.name}: Case object missing id_")
                return Status.FAILURE

            self.logger.debug(
                f"{self.name}: Case {self.case_obj.id_} passes validation"
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error validating case: {e}")
            return Status.FAILURE


# ============================================================================
# Action Nodes
# ============================================================================


class PersistCase(DataLayerAction):
    """
    Persist a VulnerabilityCase to the DataLayer.

    Creates the case record in DataLayer and stores the case_id in the
    blackboard for subsequent nodes.

    Per specs/case-management.md CM-02-001.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            self.datalayer.create(self.case_obj)
            self.logger.info(
                f"{self.name}: Persisted VulnerabilityCase"
                f" {self.case_obj.id_}"
            )

            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.case_id = self.case_obj.id_

            return Status.SUCCESS

        except ValueError as e:
            self.logger.warning(
                f"{self.name}: Case {self.case_obj.id_} already exists: {e}"
            )
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.case_id = self.case_obj.id_
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error persisting case: {e}")
            return Status.FAILURE


class CreateCaseActorNode(DataLayerAction):
    """
    Create a CaseActor (Service) for the new VulnerabilityCase.

    Each VulnerabilityCase MUST have exactly one associated CaseActor.
    The CaseActor is an ActivityStreams Service that manages case
    communications (inbox/outbox).

    Per specs/case-management.md CM-02-001.
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            case_actor = VultronCaseActor(
                name=f"CaseActor for {self.case_id}",
                attributed_to=self.actor_id,
                context=self.case_id,
            )
            try:
                self.datalayer.create(case_actor)
                self.logger.info(
                    f"{self.name}: Created CaseActor {case_actor.id_}"
                    f" for case {self.case_id}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CaseActor {case_actor.id_}"
                    f" already exists: {e}"
                )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error creating CaseActor: {e}")
            return Status.FAILURE


class EmitCreateCaseActivity(DataLayerAction):
    """
    Generate a CreateCaseActivity activity and persist it to the DataLayer.

    Reads case_id from the blackboard (set by PersistCase), creates a
    CreateCaseActivity activity, and stores the activity_id in the blackboard for
    UpdateActorOutbox.
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(
                    f"{self.name}: case_id not found in blackboard"
                )
                return Status.FAILURE

            activity = VultronCreateCaseActivity(
                actor=self.actor_id,
                object_=case_id,
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

            self.blackboard.register_key(
                key="activity_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.activity_id = activity.id_

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating CreateCaseActivity activity: {e}"
            )
            return Status.FAILURE


class SetCaseAttributedTo(DataLayerAction):
    """
    Set VulnerabilityCase.attributed_to to the receiving actor's ID.

    Must run before PersistCase so the stored case already carries the
    vendor/coordinator owner reference.

    Per specs/case-management.md CM-02-008.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error(f"{self.name}: actor_id not available")
            return Status.FAILURE

        self.case_obj.attributed_to = self.actor_id
        self.logger.debug(
            f"{self.name}: Set attributed_to={self.actor_id}"
            f" on case {self.case_obj.id_}"
        )
        return Status.SUCCESS


class CreateInitialVendorParticipant(DataLayerAction):
    """
    Create and persist a VendorParticipant for the receiving actor, then
    add it to the case's case_participants list.

    Seeds the participant with an initial ParticipantStatus of
    rm_state=RM.VALID, carrying the report-validation state forward into
    the case-engagement phase (per ADR-0013).

    Must run after PersistCase so the case already exists in the DataLayer.

    Per specs/case-management.md CM-02-008 (SHOULD).
    """

    def __init__(
        self, case_obj: VultronCase | None = None, name: str | None = None
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self.case_obj.id_ if self.case_obj is not None else None
            if case_id is None:
                case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(f"{self.name}: case_id not available")
                return Status.FAILURE

            participant = VultronParticipant(
                attributed_to=self.actor_id,
                context=case_id,
                case_roles=[CVDRoles.VENDOR],
                participant_statuses=[
                    VultronParticipantStatus(
                        context=case_id,
                        rm_state=RM.VALID,
                    )
                ],
            )
            if self.datalayer.read(participant.id_) is None:
                self.datalayer.create(participant)
                self.logger.info(
                    f"{self.name}: Created VendorParticipant"
                    f" {participant.id_} for actor {self.actor_id}"
                    f" (rm_state=RM.VALID)"
                )
            else:
                self.logger.debug(
                    f"{self.name}: VendorParticipant {participant.id_}"
                    " already exists — skipping creation"
                )

            stored_case = self.datalayer.read(case_id)
            if not is_case_model(stored_case):
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            existing_ids = {
                p.id_ if hasattr(p, "id_") else p
                for p in stored_case.case_participants
            }
            if participant.id_ not in existing_ids:
                stored_case.case_participants.append(participant.id_)
            if (
                stored_case.actor_participant_index.get(self.actor_id)
                != participant.id_
            ):
                stored_case.actor_participant_index[self.actor_id] = (
                    participant.id_
                )
            self.datalayer.save(stored_case)
            self.logger.info(
                f"{self.name}: Ensured VendorParticipant {participant.id_}"
                f" is linked to case {stored_case.id_}"
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating VendorParticipant: {e}"
            )
            return Status.FAILURE


class RecordCaseCreationEvents(DataLayerAction):
    """
    Backfill pre-case events into the case event log at case creation.

    Records a trusted-timestamp event for the case creation itself.
    If the triggering activity has an ``in_reply_to`` reference (e.g. an
    originating Offer), that event is also backfilled as an
    ``"offer_received"`` entry.

    Must run after PersistCase so the case exists in the DataLayer.
    Reads ``case_id`` and optionally ``activity`` from the blackboard.

    Per specs/case-management.md CM-02-009.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(
                    f"{self.name}: case_id not found in blackboard"
                )
                return Status.FAILURE

            case = self.datalayer.read(case_id)
            if not is_case_model(case):
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            # Backfill originating offer receipt if available.
            # Read directly from global storage — activity is optional and may
            # not be written to the blackboard when the tree is invoked without
            # an inbound activity. The blackboard storage key includes the root
            # namespace prefix "/".
            activity = py_trees.blackboard.Blackboard.storage.get(
                "/activity", None
            )
            if activity is not None:
                offer_ref = getattr(activity, "in_reply_to", None)
                if offer_ref is not None:
                    offer_id = (
                        offer_ref.id_
                        if hasattr(offer_ref, "id_")
                        else str(offer_ref)
                    )
                    case.record_event(offer_id, "offer_received")
                    self.logger.info(
                        f"{self.name}: Recorded offer_received event"
                        f" for {offer_id} on case {case_id}"
                    )

            # Record the case creation event
            case.record_event(case_id, "case_created")
            self.logger.info(
                f"{self.name}: Recorded case_created event on case {case_id}"
            )

            self.datalayer.save(case)
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error recording case creation events: {e}"
            )
            return Status.FAILURE


class UpdateActorOutbox(DataLayerAction):
    """
    Append the CreateCaseActivity activity to the actor's outbox.

    Reads activity_id from blackboard (set by EmitCreateCaseActivity) and
    appends it to the actor's outbox.items list.
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            activity_id = self.blackboard.get("activity_id")
            if activity_id is None:
                self.logger.error(
                    f"{self.name}: activity_id not found in blackboard"
                )
                return Status.FAILURE

            actor_obj = self.datalayer.read(
                self.actor_id, raise_on_missing=True
            )

            if not has_outbox(actor_obj):
                self.logger.error(
                    f"{self.name}: Actor {self.actor_id} has no outbox"
                )
                return Status.FAILURE

            actor_obj.outbox.items.append(activity_id)
            self.datalayer.save(actor_obj)
            # Also queue for delivery via outbox_handler
            self.datalayer.record_outbox_item(self.actor_id, activity_id)
            self.logger.info(
                f"{self.name}: Added activity {activity_id} to"
                f" actor {self.actor_id} outbox"
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error updating actor outbox: {e}")
            return Status.FAILURE
