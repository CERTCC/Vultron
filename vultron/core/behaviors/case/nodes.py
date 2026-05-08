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

Per specs/behavior-tree-integration.yaml BT-07 and specs/case-management.yaml
CM-02 requirements.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, cast

import isodate  # type: ignore[import-untyped]

import py_trees
from py_trees.common import Status

from vultron.core.models.actor_config import ActorConfig
from vultron.core.models.embargo_event import VultronEmbargoEvent
from vultron.core.models.enums import VultronObjectType
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.models.protocols import CaseModel, has_outbox, is_case_model
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronCreateCaseActivity,
    VultronParticipant,
)
from vultron.core.states.em import EM, EMAdapter, create_em_machine
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerCondition,
)
from vultron.core.behaviors.helpers import UpdateActorOutbox  # noqa: F401
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.use_cases._helpers import (
    _as_id,
    _report_phase_status_id,
    update_participant_rm_state,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


# ============================================================================
# Condition Nodes
# ============================================================================


class CheckCaseAlreadyExists(DataLayerCondition):
    """
    Check if a VulnerabilityCase already exists in DataLayer.

    Returns SUCCESS if the case already exists (idempotency early exit).
    Returns FAILURE if the case does not exist (proceed with creation).

    Per specs/idempotency.yaml ID-04-004.
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


class CheckCaseExistsForReport(DataLayerCondition):
    """
    Check if a VulnerabilityCase already exists for the given report.

    Uses ``find_case_by_report_id`` to check whether a case linked to the
    report already exists with participants. Returns SUCCESS if so (idempotency
    early exit), FAILURE otherwise.

    Per specs/idempotency.yaml ID-04-004.
    """

    def __init__(self, report_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            existing = self.datalayer.find_case_by_report_id(self.report_id)
            if existing is None:
                self.logger.debug(
                    f"{self.name}: No case found for report {self.report_id}"
                )
                return Status.FAILURE

            # A case record that exists but has no participants was
            # pre-stored by the inbox endpoint as a dehydrated reference.
            # It still needs full initialisation, so return FAILURE.
            participants = getattr(existing, "case_participants", None) or []
            if not participants:
                self.logger.debug(
                    f"{self.name}: Case for report {self.report_id} exists"
                    " but has no participants — proceeding with initialisation"
                )
                return Status.FAILURE

            self.logger.info(
                "%s: Case %s already exists for report %s"
                " — skipping (idempotent)",
                self.name,
                existing.id_,
                self.report_id,
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

    Per specs/case-management.yaml CM-02-001.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            self.datalayer.save(self.case_obj)
            self.logger.info(
                f"{self.name}: Persisted VulnerabilityCase"
                f" {self.case_obj.id_}"
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

    When ``case_id`` is not supplied at construction time the node reads
    ``case_id`` from the blackboard (written by a preceding
    ``CreateCaseNode``).  After the CaseActor is created its ID is written
    to the blackboard as ``case_actor_id`` so that subsequent nodes (e.g.
    ``SendOfferCaseManagerRoleNode``) can address it without a DataLayer
    scan.

    Per specs/case-management.yaml CM-02-001.
    """

    def __init__(
        self,
        case_id: str | None = None,
        actor_id: str = "",
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self._case_id_arg = case_id
        # actor_id from constructor is overridden by blackboard in initialise()

    def setup(self, **kwargs: Any) -> None:
        """Register blackboard keys including optional case_id read."""
        super().setup(**kwargs)
        if self._case_id_arg is None:
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.READ
            )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        case_id = self._case_id_arg
        if case_id is None:
            case_id = self.blackboard.get("case_id")
        if not case_id:
            self.logger.error(
                f"{self.name}: case_id not available from constructor"
                " or blackboard"
            )
            return Status.FAILURE

        try:
            case_actor = VultronCaseActor(
                name=f"CaseActor for {case_id}",
                attributed_to=self.actor_id,
                context=case_id,
            )
            try:
                self.datalayer.create(case_actor)
                self.logger.info(
                    f"{self.name}: Created CaseActor {case_actor.id_}"
                    f" for case {case_id}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CaseActor {case_actor.id_}"
                    f" already exists: {e}"
                )

            # Register the CaseActor as a CaseActorParticipant so receivers
            # can extract trusted_case_actor_id from the case snapshot during
            # bootstrap trust establishment (CBT-01-003).
            self._register_case_actor_participant(case_id, case_actor.id_)

            # Publish case_actor_id to the blackboard for downstream nodes.
            self.blackboard.case_actor_id = case_actor.id_

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error creating CaseActor: {e}")
            return Status.FAILURE

    def _register_case_actor_participant(
        self, case_id: str, case_actor_id: str
    ) -> None:
        """Add a VultronParticipant with COORDINATOR+CASE_MANAGER roles to the case.

        Uses core-layer ``VultronParticipant`` with both roles set so the
        bootstrap receiver can identify the CaseActor from the case snapshot
        without requiring a wire-layer import (CBT-01-003).
        """
        if self.datalayer is None:
            return

        case = self.datalayer.read(case_id)
        if not is_case_model(case):
            self.logger.warning(
                f"{self.name}: Case '{case_id}' not found; "
                "cannot register CaseActor participant"
            )
            return

        participant_id = f"{case_id}/participants/case-actor"
        existing = self.datalayer.read(participant_id)
        if existing is not None:
            return

        participant = VultronParticipant(
            id_=participant_id,
            attributed_to=case_actor_id,
            context=case_id,
            name=f"CaseActor for {case_id}",
            case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
        )
        try:
            self.datalayer.create(participant)
        except ValueError:
            pass  # already exists — idempotent

        case.case_participants.append(participant_id)
        case.actor_participant_index[case_actor_id] = participant_id
        self.datalayer.save(case)
        self.logger.info(
            f"{self.name}: Registered CaseActor participant '{participant_id}'"
            f" (roles: COORDINATOR, CASE_MANAGER) for case '{case_id}'"
        )


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

            # Read full case to embed as object_ and derive addressees from
            # actor_participant_index, mirroring CreateCaseActivity in
            # report/nodes.py (D5-6-CASEPROP).
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

            activity = VultronCreateCaseActivity(
                actor=self.actor_id,
                object_=case_obj if case_obj is not None else case_id,
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


class SendOfferCaseManagerRoleNode(DataLayerAction):
    """Send an Offer(VulnerabilityCase, target=CaseParticipant) to the Case Actor.

    Reads ``case_id`` and ``case_actor_id`` from the blackboard (written by
    ``CreateCaseNode`` and ``CreateCaseActorNode`` respectively), builds the
    deterministic participant ID, then calls
    ``trigger_activity_factory.offer_case_manager_role`` to create and persist
    the Offer activity.  Writes ``activity_id`` to the blackboard so that the
    following ``UpdateActorOutbox`` node can flush it to the actor's outbox.

    Per DEMOMA-08-002, DEMOMA-08-003; Issue #469.
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        """Register blackboard keys: read case_id + case_actor_id, write activity_id."""
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
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

        if not case_id or not case_actor_id:
            self.logger.error(
                f"{self.name}: case_id or case_actor_id missing from"
                " blackboard"
            )
            return Status.FAILURE

        # The Case Actor participant ID is deterministic (set by CreateCaseActorNode).
        participant_id = f"{case_id}/participants/case-actor"

        try:
            activity_id = (
                self.trigger_activity_factory.offer_case_manager_role(
                    case_id=case_id,
                    participant_id=participant_id,
                    actor=self.actor_id,
                    to=[case_actor_id],
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


class SetCaseAttributedTo(DataLayerAction):
    """
    Set VulnerabilityCase.attributed_to to the receiving actor's ID.

    Must run before PersistCase so the stored case already carries the
    vendor/coordinator owner reference.

    Per specs/case-management.yaml CM-02-008.
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


def _create_and_attach_participant(
    dl: CasePersistence,
    participant: "VultronParticipant",
    case_id: str,
    actor_id_for_index: str,
    node_logger: logging.Logger,
) -> "CaseModel | None":
    """
    Create a VultronParticipant in the DataLayer if it does not exist,
    attach it to the case, and return the **unsaved** updated case object.

    The caller is responsible for any additional case mutations (e.g.,
    ``record_event``, RM advancement) and for calling ``dl.save(case)``
    after this function returns.

    Args:
        dl: DataLayer instance for persistence.
        participant: The participant object to create and attach.
        case_id: ID of the case to attach the participant to.
        actor_id_for_index: Actor ID key for the case's
            ``actor_participant_index``.
        node_logger: Logger from the calling BT node.

    Returns:
        The updated (unsaved) case object on success, or ``None`` if the
        case was not found.
    """
    if dl.read(participant.id_) is None:
        dl.create(participant)
        node_logger.info(
            "Created CaseParticipant '%s' for actor '%s'",
            participant.id_,
            participant.attributed_to,
        )
    else:
        node_logger.debug(
            "CaseParticipant %s already exists — skipping creation",
            participant.id_,
        )

    stored_case = dl.read(case_id)
    if not is_case_model(stored_case):
        node_logger.error("Case %s not found in DataLayer", case_id)
        return None

    existing_ids = {
        p.id_ if hasattr(p, "id_") else p
        for p in stored_case.case_participants
    }
    if participant.id_ not in existing_ids:
        stored_case.case_participants.append(participant.id_)
    if (
        stored_case.actor_participant_index.get(actor_id_for_index)
        != participant.id_
    ):
        stored_case.actor_participant_index[actor_id_for_index] = (
            participant.id_
        )

    node_logger.info(
        "CaseParticipant '%s' attached to case '%s'",
        participant.id_,
        stored_case.id_,
    )
    return stored_case


def _resolve_case_id(
    blackboard: Any, case_obj: VultronCase | None = None
) -> str | None:
    case_id = case_obj.id_ if case_obj is not None else None
    return case_id or blackboard.get("case_id")


def _build_owner_initial_status(
    dl: CasePersistence,
    actor_id: str,
    case_id: str,
    report_id: str | None,
    initial_rm_state: RM,
) -> VultronParticipantStatus:
    if report_id is not None:
        status_id = _report_phase_status_id(
            actor_id,
            report_id,
            initial_rm_state.value,
        )
        if dl.read(status_id) is not None:
            return VultronParticipantStatus(
                id_=status_id,
                context=case_id,
                rm_state=initial_rm_state,
                attributed_to=actor_id,
            )

    return VultronParticipantStatus(
        context=case_id,
        rm_state=initial_rm_state,
        attributed_to=actor_id,
    )


def _effective_case_roles(actor_config: ActorConfig | None) -> list[CVDRole]:
    base_roles = actor_config.default_case_roles if actor_config else []
    return list(dict.fromkeys(base_roles + [CVDRole.CASE_OWNER]))


def _save_owner_case(
    dl: CasePersistence,
    stored_case: CaseModel,
    case_id: str,
    actor_id: str,
    advance_to_accepted: bool,
    node_name: str,
    node_logger: logging.Logger,
) -> None:
    dl.save(stored_case)
    if not advance_to_accepted:
        return

    advanced = update_participant_rm_state(case_id, actor_id, RM.ACCEPTED, dl)
    if advanced:
        node_logger.info(
            "Owner RM: VALID → ACCEPTED for actor '%s' in case '%s' "
            "(case creation = case engagement)",
            actor_id,
            case_id,
        )
        return

    node_logger.warning(
        "%s: Could not advance owner RM to ACCEPTED for actor '%s' in case '%s'",
        node_name,
        actor_id,
        case_id,
    )


def _preferred_embargo_duration(
    dl: CasePersistence, node_name: str, node_logger: logging.Logger
) -> timedelta:
    duration = timedelta(days=_DEFAULT_EMBARGO_DAYS)
    policies = list(dl.list_objects(VultronObjectType.EMBARGO_POLICY))
    if not policies:
        return duration

    preferred = getattr(policies[0], "preferred_duration", None)
    if isinstance(preferred, timedelta):
        return preferred

    node_logger.warning(
        "%s: EmbargoPolicy preferred_duration %r is not a timedelta; "
        "falling back to default %d days",
        node_name,
        preferred,
        _DEFAULT_EMBARGO_DAYS,
    )
    return duration


def _activate_default_embargo(stored_case: CaseModel, embargo_id: str) -> None:
    stored_case.active_embargo = embargo_id
    em_machine = create_em_machine()
    em_adapter = EMAdapter(EM.NONE)
    em_machine.add_model(em_adapter, initial=EM.NONE)
    getattr(em_adapter, "propose")()
    getattr(em_adapter, "accept")()
    stored_case.current_status.em_state = EM(em_adapter.state)
    stored_case.record_event(embargo_id, "embargo_initialized")


def _get_or_create_accepted_status(
    dl: CasePersistence,
    actor_id: str,
    report_id: str | None,
    node_name: str,
    node_logger: logging.Logger,
) -> VultronParticipantStatus | None:
    if report_id is None:
        return None

    accepted_status_id = _report_phase_status_id(
        actor_id,
        report_id,
        RM.ACCEPTED.value,
    )
    existing = dl.read(accepted_status_id)
    if isinstance(existing, VultronParticipantStatus):
        return existing

    node_logger.info(
        "%s: Creating fresh RM.ACCEPTED status for actor '%s' "
        "(report-phase status not pre-created)",
        node_name,
        actor_id,
    )
    accepted_status = VultronParticipantStatus(
        id_=accepted_status_id,
        context=report_id,
        rm_state=RM.ACCEPTED,
        attributed_to=actor_id,
    )
    try:
        dl.create(accepted_status)
    except ValueError:
        pass
    return accepted_status


def _queue_participant_add_notification(
    dl: CasePersistence,
    node_name: str,
    node_logger: logging.Logger,
    sender_actor_id: str,
    participant_actor_id: str,
    participant_id: str,
    case_id: str,
    trigger_activity: "TriggerActivityPort | None" = None,
) -> bool:
    stored_participant = dl.read(participant_id)
    if (
        getattr(stored_participant, "type_", None)
        != VultronObjectType.CASE_PARTICIPANT
    ):
        node_logger.error(
            "%s: Could not resolve stored CaseParticipant '%s'",
            node_name,
            participant_id,
        )
        return False

    if trigger_activity is None:
        node_logger.error(
            "%s: trigger_activity_factory not available for participant"
            " add notification",
            node_name,
        )
        return False

    add_notification_id = trigger_activity.add_participant_to_case(
        participant_id=participant_id,
        case_id=case_id,
        actor=sender_actor_id,
        to=[participant_actor_id],
    )

    actor_obj = dl.read(sender_actor_id, raise_on_missing=True)
    if has_outbox(actor_obj):
        actor_obj.outbox.items.append(add_notification_id)
        dl.save(actor_obj)
    cast(CaseOutboxPersistence, dl).record_outbox_item(
        sender_actor_id, add_notification_id
    )
    node_logger.info(
        "Queued Add(CaseParticipant '%s' for actor '%s' to case '%s') "
        "activity '%s' to actor '%s' outbox",
        participant_id,
        participant_actor_id,
        case_id,
        add_notification_id,
        sender_actor_id,
    )
    return True


class CreateCaseOwnerParticipant(DataLayerAction):
    """
    Create and persist a case-owner participant for the receiving actor,
    then add it to the case's case_participants list.

    Roles are sourced from ``actor_config.default_case_roles``
    (CFG-07-004); ``CVDRole.CASE_OWNER`` is always appended
    (BTND-05-002).  When ``actor_config`` is ``None`` the participant
    receives only the ``CASE_OWNER`` role.

    Seeds the participant with the deterministic status record for the
    given ``initial_rm_state`` (defaulting to ``RM.VALID``). When
    ``report_id`` is provided, the node first looks for an existing status
    record in the DataLayer (created by an earlier use case) and reuses it
    to avoid duplicating history. If no existing record is found, a fresh
    ``VultronParticipantStatus`` is created.

    Optionally advances the actor's RM to ACCEPTED
    (``advance_to_accepted=True``) after the participant is created — use
    this in the validate-report BT where case creation is the act of
    engaging the case.

    Must run after the case exists in the DataLayer (``PersistCase`` or
    ``CreateCaseNode``).

    Per specs/case-management.yaml CM-02-008 (SHOULD),
    specs/behavior-tree-node-design.yaml BTND-05-002 (MUST), and
    specs/configuration.yaml CFG-07-004 (MUST).
    """

    def __init__(
        self,
        actor_config: ActorConfig | None = None,
        report_id: str | None = None,
        case_obj: VultronCase | None = None,
        advance_to_accepted: bool = False,
        initial_rm_state: RM = RM.VALID,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.actor_config = actor_config
        self.report_id = report_id
        self.case_obj = case_obj
        self.advance_to_accepted = advance_to_accepted
        self.initial_rm_state = initial_rm_state

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
            case_id = _resolve_case_id(self.blackboard, self.case_obj)
            if case_id is None:
                self.logger.error(f"{self.name}: case_id not available")
                return Status.FAILURE

            initial_status = _build_owner_initial_status(
                self.datalayer,
                self.actor_id,
                case_id,
                self.report_id,
                self.initial_rm_state,
            )
            participant = VultronParticipant(
                attributed_to=self.actor_id,
                context=case_id,
                case_roles=_effective_case_roles(self.actor_config),
                participant_statuses=[initial_status],
            )

            stored_case = _create_and_attach_participant(
                self.datalayer,
                participant,
                case_id,
                self.actor_id,
                self.logger,
            )
            if stored_case is None:
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            _save_owner_case(
                self.datalayer,
                stored_case,
                case_id,
                self.actor_id,
                self.advance_to_accepted,
                self.name,
                self.logger,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating case-owner participant: {e}"
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

    Per specs/case-management.yaml CM-02-009.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
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
            # The activity key is optional — the node handles its absence.
            try:
                activity = self.blackboard.get("activity")
            except KeyError:
                activity = None
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
    Creates a ``VultronEmbargoEvent`` and attaches it to the case as
    ``active_embargo``.

    Participants learn about the embargo from ``VulnerabilityCase.active_embargo``
    embedded in the ``Create(Case)`` activity queued by ``CreateCaseActivity``
    (the subsequent node in the validate-report BT sequence). A separate
    ``Announce(embargo)`` is therefore redundant and is not emitted here.

    Must run after CreateCaseNode so case_id is available in the blackboard.

    Per specs/case-management.yaml CM-02, OX-03-001, and
    notes/protocol-event-cascades.md D5-6-EMBARGORCP.
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

            duration = _preferred_embargo_duration(
                self.datalayer, self.name, self.logger
            )
            end_time = datetime.now(tz=timezone.utc) + duration
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
                " (end_time: %s, duration: %s)",
                embargo.id_,
                case_id,
                end_time.isoformat(),
                isodate.duration_isoformat(duration),
            )

            stored_case = self.datalayer.read(case_id)
            if not is_case_model(stored_case):
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            if stored_case.active_embargo is None:
                _activate_default_embargo(stored_case, embargo.id_)
                self.datalayer.save(stored_case)
                self.logger.info(
                    "Attached embargo '%s' to case '%s' as active_embargo"
                    " (em_state: %s)",
                    embargo.id_,
                    case_id,
                    stored_case.current_status.em_state,
                )
                self._seed_owner_as_signatory(stored_case, case_id)

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error initializing default embargo: {e}"
            )
            return Status.FAILURE

    def _seed_owner_as_signatory(
        self, stored_case: "CaseModel", case_id: str
    ) -> None:
        """Seed the case-owner participant as SIGNATORY (CM-14-003).

        The owner created the embargo, so a separate accept step is
        paradoxical.  This method reads the owner participant from the
        DataLayer and sets ``embargo_consent_state`` to ``PEC.SIGNATORY``
        directly, bypassing the INVITE step.
        """
        if self.datalayer is None or self.actor_id is None:
            return
        participant_id = stored_case.actor_participant_index.get(self.actor_id)
        if not participant_id:
            self.logger.warning(
                "%s: No participant found for owner '%s' in case '%s'"
                " — cannot seed SIGNATORY",
                self.name,
                self.actor_id,
                case_id,
            )
            return
        participant = self.datalayer.read(participant_id)
        if participant is None or not hasattr(
            participant, "embargo_consent_state"
        ):
            self.logger.warning(
                "%s: Participant '%s' not found or lacks embargo_consent_state"
                " — cannot seed SIGNATORY",
                self.name,
                participant_id,
            )
            return
        embargo_id = _as_id(stored_case.active_embargo)
        cast(Any, participant).embargo_consent_state = PEC.SIGNATORY
        if (
            embargo_id
            and embargo_id not in cast(Any, participant).accepted_embargo_ids
        ):
            cast(Any, participant).accepted_embargo_ids.append(embargo_id)
        self.datalayer.save(participant)
        self.logger.info(
            "Seeded case-owner participant '%s' (actor '%s') as SIGNATORY"
            " for embargo in case '%s' (CM-14-003)",
            participant_id,
            self.actor_id,
            case_id,
        )


class CreateCaseParticipantNode(DataLayerAction):
    """
    Create and persist a CaseParticipant for the given actor, then attach
    it to the case.

    Parameterized by ``actor_id`` (the actor being added as a participant)
    and ``roles`` (the CVD roles to assign).

    When ``report_id`` is supplied, the node reuses the deterministic
    report-phase ``VultronParticipantStatus`` for ``RM.ACCEPTED`` that was
    created during ``SubmitReportReceivedUseCase``, preserving engagement
    history.

    Emits ``AddParticipantToCaseActivity(object_=<CaseParticipant>)`` to
    the actor's outbox so downstream actors are notified.  Using the typed
    activity (not a bare ``VultronActivity``) satisfies MV-09-001 and
    avoids the ``VultronOutboxObjectIntegrityError`` caused by bare-string
    ``object_`` fields after dehydration.

    Must run after ``CreateCaseNode`` (so ``case_id`` is on the blackboard)
    and after ``CreateCaseOwnerParticipant``.
    """

    def __init__(
        self,
        actor_id: str,
        roles: list[CVDRole],
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_actor_id = actor_id
        self.roles = roles
        self.report_id = report_id

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

            accepted_status = _get_or_create_accepted_status(
                self.datalayer,
                self.participant_actor_id,
                self.report_id,
                self.name,
                self.logger,
            )
            participant = VultronParticipant(
                attributed_to=self.participant_actor_id,
                context=case_id,
                case_roles=self.roles,
                participant_statuses=(
                    [accepted_status] if accepted_status is not None else []
                ),
            )

            stored_case = _create_and_attach_participant(
                self.datalayer,
                participant,
                case_id,
                self.participant_actor_id,
                self.logger,
            )
            if stored_case is None:
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            stored_case.record_event(participant.id_, "participant_added")
            self.datalayer.save(stored_case)

            # CM-14-005: seed the new participant as SIGNATORY when a
            # default embargo is already active at case initialization time.
            if stored_case.active_embargo is not None:
                active_embargo_id = _as_id(stored_case.active_embargo)
                participant.embargo_consent_state = PEC.SIGNATORY
                if (
                    active_embargo_id
                    and active_embargo_id
                    not in participant.accepted_embargo_ids
                ):
                    participant.accepted_embargo_ids.append(active_embargo_id)
                self.datalayer.save(participant)
                self.logger.info(
                    "Seeded participant '%s' (actor '%s') as SIGNATORY"
                    " for active embargo in case '%s' (CM-14-005)",
                    participant.id_,
                    self.participant_actor_id,
                    case_id,
                )

            if not _queue_participant_add_notification(
                self.datalayer,
                self.name,
                self.logger,
                self.actor_id,
                self.participant_actor_id,
                participant.id_,
                case_id,
                trigger_activity=self.trigger_activity_factory,
            ):
                return Status.FAILURE

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating CaseParticipant: {e}"
            )
            return Status.FAILURE


class CommitCaseLogEntryNode(DataLayerAction):
    """
    Commit a hash-chained CaseLogEntry and fan it out to all case participants.

    Creates a :class:`~vultron.core.models.case_log_entry.VultronCaseLogEntry`,
    persists it, and queues one ``Announce(CaseLogEntry)`` activity per
    participant to the actor's outbox.  The :class:`OutboxMonitor` delivers
    queued activities reactively — this node only writes to the outbox.

    ``case_id`` is resolved in order:

    1. Constructor parameter (if provided at tree-build time).
    2. ``case_id`` key in the py_trees blackboard (written by a prior node
       such as :class:`CreateCaseNode` or :class:`PersistCase`).

    If ``case_id`` cannot be resolved, the node returns ``SUCCESS`` silently
    (no-op for trees that run in a non-case context).

    ``event_type`` and ``object_id`` are derived from the ``activity``
    blackboard key (the inbound :class:`~vultron.core.models.events.base.VultronEvent`
    placed there by :class:`~vultron.core.behaviors.bridge.BTBridge`).

    Per specs/sync-log-replication.yaml SYNC-02-002, SYNC-02-003.
    """

    def __init__(
        self,
        case_id: str | None = None,
        name: str | None = None,
    ):
        """
        Args:
            case_id: ID of the ``VulnerabilityCase`` to log against.  When
                ``None`` the node reads ``case_id`` from the blackboard.
            name: Optional display name for the node.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._sync_port: Any = None

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="sync_port", access=py_trees.common.Access.READ
        )

    def initialise(self) -> None:
        super().initialise()
        try:
            self._sync_port = self.blackboard.sync_port
        except (AttributeError, KeyError):
            self._sync_port = None

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self._case_id or self.blackboard.get("case_id")
        except KeyError:
            case_id = self._case_id
        if not case_id:
            self.logger.debug(
                f"{self.name}: no case_id available — skipping log entry"
            )
            return Status.SUCCESS

        try:
            activity = self.blackboard.get("activity")
        except KeyError:
            activity = None
        if activity is not None:
            object_id: str = getattr(activity, "activity_id", case_id)
            semantic_type = getattr(activity, "semantic_type", None)
            event_type: str = (
                semantic_type.value
                if semantic_type is not None
                else getattr(activity, "activity_type", "case_event")
                or "case_event"
            )
        else:
            object_id = case_id
            event_type = "case_event"

        tree = create_commit_log_entry_tree(
            case_id=case_id,
            object_id=object_id,
            event_type=event_type,
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(
            tree=tree,
            actor_id=self.actor_id,
            sync_port=self._sync_port,
        )
        if result.status == Status.SUCCESS:
            self.logger.info(
                "%s: committed log entry '%s' for case '%s'",
                self.name,
                event_type,
                case_id,
            )
            return Status.SUCCESS
        self.logger.error(
            "%s: failed to commit log entry for case '%s': %s",
            self.name,
            case_id,
            result.feedback_message,
        )
        return Status.FAILURE
