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
from datetime import datetime, timedelta, timezone
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.models.activity import VultronActivity
from vultron.core.models.embargo_event import VultronEmbargoEvent
from vultron.core.models.enums import VultronObjectType
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
from vultron.core.use_cases._helpers import (
    _report_phase_status_id,
    update_participant_rm_state,
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
            if existing is None:
                self.logger.debug(
                    f"{self.name}: Case {self.case_id} not found, proceeding"
                )
                return Status.FAILURE

            # A case record that exists but has no participants was
            # pre-stored by the inbox endpoint as a dehydrated reference.
            # It still needs full initialisation (participant creation,
            # CaseActor setup, etc.), so return FAILURE to let the
            # CreateCaseFlow run.
            participants = getattr(existing, "case_participants", None) or []
            if not participants:
                self.logger.debug(
                    f"{self.name}: Case {self.case_id} exists but has no"
                    " participants — proceeding with initialisation"
                )
                return Status.FAILURE

            self.logger.info(
                f"{self.name}: Case {self.case_id} already exists"
                " — skipping creation (idempotent)"
            )
            return Status.SUCCESS

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
    add it to the case's case_participants list and advance RM to ACCEPTED.

    Seeds the participant with the deterministic RM.VALID status created by
    TransitionRMtoValid (reusing the same record rather than duplicating it),
    then immediately appends an RM.ACCEPTED transition — creating the case
    is the vendor's act of engaging it.

    Must run after PersistCase so the case already exists in the DataLayer.

    Per specs/case-management.md CM-02-008 (SHOULD).
    """

    def __init__(
        self,
        report_id: str | None = None,
        case_obj: VultronCase | None = None,
        advance_to_accepted: bool = False,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.case_obj = case_obj
        self.advance_to_accepted = advance_to_accepted

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

            # Reuse the deterministic RM.VALID status from TransitionRMtoValid
            # (if report_id is known), otherwise create a fresh one.
            initial_status: VultronParticipantStatus | None = None
            if self.report_id is not None:
                valid_status_id = _report_phase_status_id(
                    self.actor_id, self.report_id, RM.VALID.value
                )
                existing = self.datalayer.read(valid_status_id)
                if existing is not None and isinstance(
                    existing, VultronParticipantStatus
                ):
                    initial_status = existing
            if initial_status is None:
                initial_status = VultronParticipantStatus(
                    context=case_id,
                    rm_state=RM.VALID,
                    attributed_to=self.actor_id,
                )

            participant = VultronParticipant(
                attributed_to=self.actor_id,
                context=case_id,
                case_roles=[CVDRoles.VENDOR],
                participant_statuses=[initial_status],
            )
            if self.datalayer.read(participant.id_) is None:
                self.datalayer.create(participant)
                self.logger.info(
                    "Created CaseParticipant '%s' for actor '%s'"
                    " (roles: [VENDOR], rm_state: RM.VALID)",
                    participant.id_,
                    self.actor_id,
                )
            else:
                self.logger.debug(
                    "%s: VendorParticipant %s already exists — skipping"
                    " creation",
                    self.name,
                    participant.id_,
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
                "CaseParticipant '%s' attached to case '%s'",
                participant.id_,
                stored_case.id_,
            )

            # Optionally advance vendor RM to ACCEPTED — creating the case
            # is the act of engaging it in the validate-report BT, so no
            # separate engage-case trigger is needed.  The create-case BT
            # seeds VALID only (ADR-0013).
            if self.advance_to_accepted:
                advanced = update_participant_rm_state(
                    case_id, self.actor_id, RM.ACCEPTED, self.datalayer
                )
                if advanced:
                    self.logger.info(
                        "Vendor RM: VALID → ACCEPTED for actor '%s' in case"
                        " '%s' (case creation = case engagement)",
                        self.actor_id,
                        case_id,
                    )
                else:
                    self.logger.warning(
                        "%s: Could not advance vendor RM to ACCEPTED for"
                        " actor '%s' in case '%s'",
                        self.name,
                        self.actor_id,
                        case_id,
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


_DEFAULT_EMBARGO_DAYS = 90


class InitializeDefaultEmbargoNode(DataLayerAction):
    """
    Create a default embargo event for the newly created case.

    Looks up the actor's EmbargoPolicy from the DataLayer to determine the
    preferred duration (defaulting to 90 days if no policy is found).
    Creates a ``VultronEmbargoEvent``, attaches it to the case as
    ``active_embargo``, and queues an Announce activity to the actor's
    outbox so downstream actors are notified.

    Must run after CreateCaseNode so case_id is available in the blackboard.

    Per specs/case-management.md CM-02 and notes/two-actor-feedback.md
    D5-6h requirements.
    """

    def __init__(self, name: str | None = None) -> None:
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

            # Determine embargo duration from stored policy (wire-layer object
            # accessed via raw dict to avoid importing the wire type).
            duration_days = _DEFAULT_EMBARGO_DAYS
            policies = self.datalayer.by_type(VultronObjectType.EMBARGO_POLICY)
            if policies:
                first = next(iter(policies.values()))
                duration_days = int(
                    first.get("preferred_duration_days", _DEFAULT_EMBARGO_DAYS)
                )

            end_time = datetime.now(tz=timezone.utc) + timedelta(
                days=duration_days
            )
            embargo = VultronEmbargoEvent(end_time=end_time, context=case_id)

            try:
                self.datalayer.create(embargo)
            except ValueError:
                self.logger.debug(
                    "%s: Embargo %s already exists — skipping creation",
                    self.name,
                    embargo.id_,
                )

            self.logger.info(
                "Initialized default embargo '%s' for case '%s'"
                " (end_time: %s, duration: %d days)",
                embargo.id_,
                case_id,
                end_time.isoformat(),
                duration_days,
            )

            # Attach embargo to the case.
            stored_case = self.datalayer.read(case_id)
            if not is_case_model(stored_case):
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            if stored_case.active_embargo is None:
                stored_case.active_embargo = embargo.id_
                self.datalayer.save(stored_case)
                self.logger.info(
                    "Attached embargo '%s' to case '%s' as active_embargo",
                    embargo.id_,
                    case_id,
                )

            # Emit Announce activity so participants are notified.
            announce = VultronActivity(
                type_="Announce",
                actor=self.actor_id,
                object_=embargo.id_,
                target=case_id,
            )
            try:
                self.datalayer.create(announce)
            except ValueError:
                pass  # idempotent

            actor_obj = self.datalayer.read(
                self.actor_id, raise_on_missing=True
            )
            if has_outbox(actor_obj):
                actor_obj.outbox.items.append(announce.id_)
                self.datalayer.save(actor_obj)
            self.datalayer.record_outbox_item(self.actor_id, announce.id_)
            self.logger.info(
                "Queued Announce(embargo '%s' for case '%s',"
                " duration %d days) activity '%s' to actor '%s' outbox"
                " (default embargo notification)",
                embargo.id_,
                case_id,
                duration_days,
                announce.id_,
                self.actor_id,
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error initializing default embargo: {e}"
            )
            return Status.FAILURE


class CreateFinderParticipantNode(DataLayerAction):
    """
    Create and persist a FinderReporter CaseParticipant for the finder actor,
    then attach it to the case.

    Reads the offer to determine the finder's actor ID (``offer.actor``).
    Seeds the participant with the report-phase RM.ACCEPTED status that was
    created during ``SubmitReportReceivedUseCase`` (deterministic ID via
    ``_report_phase_status_id``), preserving the finder's engagement history
    from the report phase.

    Creates an Add activity for the notification and queues it to the actor's
    outbox so downstream actors are notified.

    Must run after CreateCaseNode and CreateInitialVendorParticipant.

    Per notes/two-actor-feedback.md D5-6h requirements.
    """

    def __init__(
        self, report_id: str, offer_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.offer_id = offer_id

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

            # Determine finder's actor_id from the offer.
            # VultronOffer (type_ = "Offer") is not in the AS2 vocabulary
            # registry, so dl.read() cannot reconstruct it.  Use by_type() to
            # get the raw data dict directly from the "Offer" table.
            offer_records = self.datalayer.by_type("Offer")
            offer_data = offer_records.get(self.offer_id)
            if offer_data is None:
                self.logger.error(
                    f"{self.name}: Offer {self.offer_id} not found in DataLayer"
                )
                return Status.FAILURE
            finder_actor_id = offer_data.get("actor")
            if not finder_actor_id:
                self.logger.error(
                    f"{self.name}: Could not determine finder actor_id from"
                    f" offer {self.offer_id}"
                )
                return Status.FAILURE

            # Reuse the report-phase RM.ACCEPTED status created during
            # SubmitReportReceivedUseCase (deterministic ID).
            accepted_status_id = _report_phase_status_id(
                finder_actor_id, self.report_id, RM.ACCEPTED.value
            )
            accepted_status = self.datalayer.read(accepted_status_id)
            if accepted_status is None or not isinstance(
                accepted_status, VultronParticipantStatus
            ):
                # Fallback: create a fresh RM.ACCEPTED status.
                self.logger.warning(
                    "%s: Report-phase RM.ACCEPTED status for finder '%s' not"
                    " found — creating a fresh status record",
                    self.name,
                    finder_actor_id,
                )
                accepted_status = VultronParticipantStatus(
                    id_=accepted_status_id,
                    context=self.report_id,
                    rm_state=RM.ACCEPTED,
                    attributed_to=finder_actor_id,
                )
                try:
                    self.datalayer.create(accepted_status)
                except ValueError:
                    pass  # idempotent — already exists

            participant = VultronParticipant(
                attributed_to=finder_actor_id,
                context=case_id,
                case_roles=[CVDRoles.FINDER, CVDRoles.REPORTER],
                participant_statuses=[accepted_status],
            )

            if self.datalayer.read(participant.id_) is None:
                self.datalayer.create(participant)
                self.logger.info(
                    "Created FinderReporter CaseParticipant '%s' for actor"
                    " '%s' (roles: [FINDER, REPORTER], rm_state: RM.ACCEPTED)",
                    participant.id_,
                    finder_actor_id,
                )
            else:
                self.logger.debug(
                    "%s: FinderParticipant %s already exists — skipping",
                    self.name,
                    participant.id_,
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
                stored_case.actor_participant_index.get(finder_actor_id)
                != participant.id_
            ):
                stored_case.actor_participant_index[finder_actor_id] = (
                    participant.id_
                )
            stored_case.record_event(participant.id_, "participant_added")
            self.datalayer.save(stored_case)
            self.logger.info(
                "FinderReporter CaseParticipant '%s' attached to case '%s'",
                participant.id_,
                case_id,
            )

            # Emit Add activity to notify participants.
            add_notification = VultronActivity(
                type_="Add",
                actor=self.actor_id,
                object_=participant.id_,
                target=case_id,
            )
            try:
                self.datalayer.create(add_notification)
            except ValueError:
                pass  # idempotent

            actor_obj = self.datalayer.read(
                self.actor_id, raise_on_missing=True
            )
            if has_outbox(actor_obj):
                actor_obj.outbox.items.append(add_notification.id_)
                self.datalayer.save(actor_obj)
            self.datalayer.record_outbox_item(
                self.actor_id, add_notification.id_
            )
            self.logger.info(
                "Queued Add(CaseParticipant '%s' for actor '%s' to case '%s')"
                " activity '%s' to actor '%s' outbox"
                " (finder participant notification)",
                participant.id_,
                finder_actor_id,
                case_id,
                add_notification.id_,
                self.actor_id,
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating FinderParticipant: {e}"
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
            activity_id = self.blackboard.get("activity_id")
            if activity_id is None:
                self.logger.error(
                    f"{self.name}: activity_id not found in blackboard"
                )
                return Status.FAILURE

            case_id = self.blackboard.get("case_id")

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
                "Queued Create(Case '%s') activity '%s' to actor '%s' outbox"
                " (case creation notification)",
                case_id,
                activity_id,
                self.actor_id,
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error updating actor outbox: {e}")
            return Status.FAILURE
