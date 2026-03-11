"""
Handler functions for case and participant status activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

from vultron.api.v2.datalayer.abc import DataLayer

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_CASE_STATUS)
def create_case_status(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process a Create(CaseStatus) activity.

    Persists the CaseStatus to the DataLayer. Idempotent: if a CaseStatus
    with the same ID already exists, the handler skips creation (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the Create(CaseStatus)
    """
    payload = dispatchable.payload

    try:
        existing = dl.get(payload.object_type, payload.object_id)
        if existing is not None:
            logger.info(
                "CaseStatus '%s' already stored — skipping (idempotent)",
                payload.object_id,
            )
            return None

        dl.create(dispatchable.wire_object)
        logger.info("Stored CaseStatus '%s'", payload.object_id)

    except Exception as e:
        logger.error(
            "Error in create_case_status for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
def add_case_status_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an Add(CaseStatus, target=VulnerabilityCase) activity.

    Appends the CaseStatus to the case's case_statuses list and persists the
    updated case. Idempotent: re-adding a status already in the list
    succeeds without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the Add(CaseStatus,
                      target=VulnerabilityCase)
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record

    payload = dispatchable.payload

    try:
        status = rehydrate(payload.object_id)
        case = rehydrate(payload.target_id)
        status_id = payload.object_id
        case_id = payload.target_id

        existing_ids = [
            (s.as_id if hasattr(s, "as_id") else s) for s in case.case_statuses
        ]
        if status_id in existing_ids:
            logger.info(
                "CaseStatus '%s' already in case '%s' — skipping (idempotent)",
                status_id,
                case_id,
            )
            return None

        case.case_statuses.append(status)
        dl.update(case_id, object_to_record(case))
        logger.info("Added CaseStatus '%s' to case '%s'", status_id, case_id)

    except Exception as e:
        logger.error(
            "Error in add_case_status_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.CREATE_PARTICIPANT_STATUS)
def create_participant_status(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a Create(ParticipantStatus) activity.

    Persists the ParticipantStatus to the DataLayer. Idempotent: if a
    ParticipantStatus with the same ID already exists, the handler skips
    creation (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the Create(ParticipantStatus)
    """
    payload = dispatchable.payload

    try:
        existing = dl.get(payload.object_type, payload.object_id)
        if existing is not None:
            logger.info(
                "ParticipantStatus '%s' already stored — skipping (idempotent)",
                payload.object_id,
            )
            return None

        dl.create(dispatchable.wire_object)
        logger.info("Stored ParticipantStatus '%s'", payload.object_id)

    except Exception as e:
        logger.error(
            "Error in create_participant_status for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT)
def add_participant_status_to_participant(
    dispatchable: DispatchActivity,
    dl: DataLayer,
) -> None:
    """
    Process an Add(ParticipantStatus, target=CaseParticipant) activity.

    Appends the ParticipantStatus to the participant's participant_statuses
    list and persists the updated participant. Idempotent: re-adding a
    status already in the list succeeds without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the
                      Add(ParticipantStatus, target=CaseParticipant)
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record

    payload = dispatchable.payload

    try:
        status = rehydrate(payload.object_id)
        participant = rehydrate(payload.target_id)
        status_id = payload.object_id
        participant_id = payload.target_id

        existing_ids = [
            (s.as_id if hasattr(s, "as_id") else s)
            for s in participant.participant_statuses
        ]
        if status_id in existing_ids:
            logger.info(
                "ParticipantStatus '%s' already on participant '%s' — "
                "skipping (idempotent)",
                status_id,
                participant_id,
            )
            return None

        participant.participant_statuses.append(status)
        dl.update(participant_id, object_to_record(participant))
        logger.info(
            "Added ParticipantStatus '%s' to participant '%s'",
            status_id,
            participant_id,
        )

    except Exception as e:
        logger.error(
            "Error in add_participant_status_to_participant for activity %s: %s",
            payload.activity_id,
            str(e),
        )
