"""
Handler functions for case and participant status activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.enums import MessageSemantics
from vultron.types import DispatchActivity

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_CASE_STATUS)
def create_case_status(dispatchable: DispatchActivity) -> None:
    """
    Process a Create(CaseStatus) activity.

    Persists the CaseStatus to the DataLayer. Idempotent: if a CaseStatus
    with the same ID already exists, the handler skips creation (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the Create(CaseStatus)
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        dl = get_datalayer()
        status = activity.as_object

        existing = dl.get(status.as_type.value, status.as_id)
        if existing is not None:
            logger.info(
                "CaseStatus '%s' already stored — skipping (idempotent)",
                status.as_id,
            )
            return None

        dl.create(status)
        logger.info("Stored CaseStatus '%s'", status.as_id)

    except Exception as e:
        logger.error(
            "Error in create_case_status for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
def add_case_status_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process an Add(CaseStatus, target=VulnerabilityCase) activity.

    Appends the CaseStatus to the case's case_status list and persists the
    updated case. Idempotent: re-adding a status already in the list
    succeeds without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the Add(CaseStatus,
                      target=VulnerabilityCase)
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        dl = get_datalayer()
        status = rehydrate(obj=activity.as_object)
        case = rehydrate(obj=activity.target)
        status_id = status.as_id if hasattr(status, "as_id") else str(status)
        case_id = case.as_id

        existing_ids = [
            (s.as_id if hasattr(s, "as_id") else s) for s in case.case_status
        ]
        if status_id in existing_ids:
            logger.info(
                "CaseStatus '%s' already in case '%s' — skipping (idempotent)",
                status_id,
                case_id,
            )
            return None

        case.case_status.append(status)
        dl.update(case_id, object_to_record(case))
        logger.info("Added CaseStatus '%s' to case '%s'", status_id, case_id)

    except Exception as e:
        logger.error(
            "Error in add_case_status_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.CREATE_PARTICIPANT_STATUS)
def create_participant_status(dispatchable: DispatchActivity) -> None:
    """
    Process a Create(ParticipantStatus) activity.

    Persists the ParticipantStatus to the DataLayer. Idempotent: if a
    ParticipantStatus with the same ID already exists, the handler skips
    creation (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the Create(ParticipantStatus)
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        dl = get_datalayer()
        status = activity.as_object

        existing = dl.get(status.as_type.value, status.as_id)
        if existing is not None:
            logger.info(
                "ParticipantStatus '%s' already stored — skipping (idempotent)",
                status.as_id,
            )
            return None

        dl.create(status)
        logger.info("Stored ParticipantStatus '%s'", status.as_id)

    except Exception as e:
        logger.error(
            "Error in create_participant_status for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT)
def add_participant_status_to_participant(
    dispatchable: DispatchActivity,
) -> None:
    """
    Process an Add(ParticipantStatus, target=CaseParticipant) activity.

    Appends the ParticipantStatus to the participant's participant_status
    list and persists the updated participant. Idempotent: re-adding a
    status already in the list succeeds without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the
                      Add(ParticipantStatus, target=CaseParticipant)
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        dl = get_datalayer()
        status = rehydrate(obj=activity.as_object)
        participant = rehydrate(obj=activity.target)
        status_id = status.as_id if hasattr(status, "as_id") else str(status)
        participant_id = participant.as_id

        existing_ids = [
            (s.as_id if hasattr(s, "as_id") else s)
            for s in participant.participant_status
        ]
        if status_id in existing_ids:
            logger.info(
                "ParticipantStatus '%s' already on participant '%s' — "
                "skipping (idempotent)",
                status_id,
                participant_id,
            )
            return None

        participant.participant_status.append(status)
        dl.update(participant_id, object_to_record(participant))
        logger.info(
            "Added ParticipantStatus '%s' to participant '%s'",
            status_id,
            participant_id,
        )

    except Exception as e:
        logger.error(
            "Error in add_participant_status_to_participant for activity %s: %s",
            activity.as_id,
            str(e),
        )
