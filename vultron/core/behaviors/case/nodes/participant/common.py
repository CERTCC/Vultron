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

"""Shared helpers for participant BT nodes."""

import logging
from typing import TYPE_CHECKING, cast

from vultron.core.models.enums import VultronObjectType
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.protocols import (
    CaseModel,
    is_case_model,
    is_participant_status_model,
)
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.core.use_cases._helpers import _report_phase_status_id

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort


def _create_and_attach_participant(
    dl: CasePersistence,
    participant: VultronParticipant,
    case_id: str,
    actor_id_for_index: str,
    node_logger: logging.Logger,
) -> CaseModel | None:
    """
    Create participant if needed and attach it to the case (unsaved return).

    The caller is responsible for calling ``dl.save(case)`` after any further
    case updates are applied.
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

    existing_participant_id = stored_case.actor_participant_index.get(
        actor_id_for_index
    )
    if existing_participant_id is not None:
        existing_participant = dl.read(existing_participant_id)
        if existing_participant is not None:
            stored_case.add_participant(existing_participant)
            node_logger.debug(
                "Participant already registered for actor '%s' in case '%s'",
                actor_id_for_index,
                case_id,
            )
            return stored_case

    stored_case.add_participant(participant)

    node_logger.info(
        "CaseParticipant '%s' attached to case '%s'",
        participant.id_,
        stored_case.id_,
    )
    return stored_case


def _get_or_create_accepted_status(
    dl: CasePersistence,
    actor_id: str,
    report_id: str | None,
    node_name: str,
    node_logger: logging.Logger,
    cvd_role: list[CVDRole],
    em_consent_state: PEC | None,
) -> ParticipantStatus | None:
    if report_id is None:
        return None

    # CLP-07-007: context must use the case URI once a case exists.
    case_obj = dl.find_case_by_report_id(report_id)
    context = case_obj.id_ if is_case_model(case_obj) else report_id

    accepted_status_id = _report_phase_status_id(
        actor_id,
        report_id,
        RM.ACCEPTED.value,
    )
    existing = dl.read(accepted_status_id)
    if is_participant_status_model(existing):
        should_update_role = existing.cvd_role != cvd_role
        should_backfill_consent = (
            existing.em_consent_state is None and em_consent_state is not None
        )
        # AC-3: backfill context if it still holds the report URI.
        should_backfill_context = (
            existing.context == report_id and context != report_id
        )
        if (
            should_update_role
            or should_backfill_consent
            or should_backfill_context
        ):
            existing.cvd_role = cvd_role
            if should_backfill_consent:
                existing.em_consent_state = em_consent_state
            if should_backfill_context:
                existing.context = context
            dl.save(existing)
        # Construct a fresh core ParticipantStatus for callers that require
        # the core type (e.g. CaseParticipant.participant_statuses).  The
        # DataLayer vocabulary registry may return the wire-layer subclass;
        # we normalise here so downstream code never sees a wire-layer type.
        return ParticipantStatus(
            id_=existing.id_,
            context=existing.context,
            rm_state=existing.rm_state,
            vfd_state=existing.vfd_state,
            attributed_to=getattr(existing, "attributed_to", actor_id),
            cvd_role=existing.cvd_role,
            em_consent_state=existing.em_consent_state,
        )

    node_logger.info(
        "%s: Creating fresh RM.ACCEPTED status for actor '%s' "
        "(report-phase status not pre-created)",
        node_name,
        actor_id,
    )
    accepted_status = ParticipantStatus(
        id_=accepted_status_id,
        context=context,
        rm_state=RM.ACCEPTED,
        attributed_to=actor_id,
        cvd_role=cvd_role,
        em_consent_state=em_consent_state,
    )
    try:
        dl.create(accepted_status)
    except ValueError:
        pass
    return accepted_status


def resolve_participant_state_from_dl(
    dl: CasePersistence,
    participant_id: str,
) -> tuple[RM, CS_vfd]:
    """Return (current_rm, current_vfd) from the participant's latest status."""
    participant_obj = dl.read(participant_id)
    if participant_obj is not None and hasattr(
        participant_obj, "participant_statuses"
    ):
        statuses = getattr(participant_obj, "participant_statuses")
        if statuses:
            latest = statuses[-1]
            raw_rm = getattr(latest, "rm_state", RM.START)
            raw_vfd = getattr(latest, "vfd_state", CS_vfd.vfd)
            rm_state = raw_rm if isinstance(raw_rm, RM) else RM.START
            vfd_state = raw_vfd if isinstance(raw_vfd, CS_vfd) else CS_vfd.vfd
            return rm_state, vfd_state
    return RM.START, CS_vfd.vfd


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
