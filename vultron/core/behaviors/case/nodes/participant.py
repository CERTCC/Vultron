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
Participant management action nodes and helpers for case behavior trees.

Provides helpers and action nodes that create and attach case participants,
manage participant statuses, and emit participant-add notifications.

Per specs/case-management.yaml CM-02-008, BTND-05-002.
"""

import logging
from typing import TYPE_CHECKING, Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.actor_config import ActorConfig
from vultron.core.models.enums import VultronObjectType
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.models.protocols import CaseModel, has_outbox, is_case_model
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import (
    _as_id,
    _report_phase_status_id,
    update_participant_rm_state,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


# ============================================================================
# Shared helper functions
# ============================================================================


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


# ============================================================================
# Action Nodes
# ============================================================================


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
