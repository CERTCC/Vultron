"""Use cases for case and participant status activities."""

import logging
from typing import cast

from vultron.core.models.events.status import (
    AddCaseStatusToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
    CreateCaseStatusReceivedEvent,
    CreateParticipantStatusReceivedEvent,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._types import CaseModel, ParticipantModel

logger = logging.getLogger(__name__)


def create_case_status(
    event: CreateCaseStatusReceivedEvent, dl: DataLayer
) -> None:
    try:
        existing = dl.get(event.object_type, event.object_id)
        if existing is not None:
            logger.info(
                "CaseStatus '%s' already stored — skipping (idempotent)",
                event.object_id,
            )
            return

        obj_to_store = event.status
        if obj_to_store is not None:
            dl.create(obj_to_store)
            logger.info("Stored CaseStatus '%s'", event.object_id)
        else:
            logger.warning(
                "create_case_status: no status object for event '%s'",
                event.activity_id,
            )

    except Exception as e:
        logger.error(
            "Error in create_case_status for activity %s: %s",
            event.activity_id,
            str(e),
        )


def add_case_status_to_case(
    event: AddCaseStatusToCaseReceivedEvent, dl: DataLayer
) -> None:
    try:
        status_id = event.object_id
        case_id = event.target_id
        case = cast(CaseModel, dl.read(case_id))

        if case is None:
            logger.warning(
                "add_case_status_to_case: case '%s' not found", case_id
            )
            return

        existing_ids = [
            (s.as_id if hasattr(s, "as_id") else s) for s in case.case_statuses
        ]
        if status_id in existing_ids:
            logger.info(
                "CaseStatus '%s' already in case '%s' — skipping (idempotent)",
                status_id,
                case_id,
            )
            return

        # Prefer the domain object from the event over dl.read, which may return
        # a raw TinyDB Document if reconstitution of the stored VultronCaseStatus
        # record fails (wire CaseStatus has different field types).
        status_obj = dl.read(status_id)
        if not hasattr(status_obj, "as_id"):
            status_obj = event.status
        case.case_statuses.append(status_obj)
        dl.save(case)
        logger.info("Added CaseStatus '%s' to case '%s'", status_id, case_id)

    except Exception as e:
        logger.error(
            "Error in add_case_status_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def create_participant_status(
    event: CreateParticipantStatusReceivedEvent,
    dl: DataLayer,
) -> None:
    try:
        existing = dl.get(event.object_type, event.object_id)
        if existing is not None:
            logger.info(
                "ParticipantStatus '%s' already stored — skipping (idempotent)",
                event.object_id,
            )
            return

        obj_to_store = event.status
        if obj_to_store is not None:
            dl.create(obj_to_store)
            logger.info("Stored ParticipantStatus '%s'", event.object_id)
        else:
            logger.warning(
                "create_participant_status: no status object for event '%s'",
                event.activity_id,
            )

    except Exception as e:
        logger.error(
            "Error in create_participant_status for activity %s: %s",
            event.activity_id,
            str(e),
        )


def add_participant_status_to_participant(
    event: AddParticipantStatusToParticipantReceivedEvent,
    dl: DataLayer,
) -> None:
    try:
        status_id = event.object_id
        participant_id = event.target_id
        participant = cast(ParticipantModel, dl.read(participant_id))

        if participant is None:
            logger.warning(
                "add_participant_status_to_participant: participant '%s' not found",
                participant_id,
            )
            return

        existing_ids = [
            (s.as_id if hasattr(s, "as_id") else s)
            for s in participant.participant_statuses
        ]
        if status_id in existing_ids:
            logger.info(
                "ParticipantStatus '%s' already on participant '%s' — skipping (idempotent)",
                status_id,
                participant_id,
            )
            return

        # Prefer the domain object from the event over dl.read, which may return
        # a raw TinyDB Document when VultronParticipantStatus reconstitution fails.
        status_obj = dl.read(status_id)
        if not hasattr(status_obj, "as_id"):
            status_obj = event.status
        participant.participant_statuses.append(status_obj)
        dl.save(participant)
        logger.info(
            "Added ParticipantStatus '%s' to participant '%s'",
            status_id,
            participant_id,
        )

    except Exception as e:
        logger.error(
            "Error in add_participant_status_to_participant for activity %s: %s",
            event.activity_id,
            str(e),
        )
