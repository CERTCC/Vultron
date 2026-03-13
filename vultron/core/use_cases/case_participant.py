"""Use cases for case participant management activities."""

import logging
from typing import cast

from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._types import CaseModel

logger = logging.getLogger(__name__)


def create_case_participant(
    event: CreateCaseParticipantReceivedEvent, dl: DataLayer, wire_object=None
) -> None:
    try:
        existing = dl.get(event.object_type, event.object_id)
        if existing is not None:
            logger.info(
                "Participant '%s' already exists — skipping (idempotent)",
                event.object_id,
            )
            return

        obj_to_store = (
            wire_object if wire_object is not None else event.participant
        )
        if obj_to_store is not None:
            dl.create(obj_to_store)
            logger.info("Created participant '%s'", event.object_id)
        else:
            logger.warning(
                "create_case_participant: no participant object for event '%s'",
                event.activity_id,
            )

    except Exception as e:
        logger.error(
            "Error in create_case_participant for activity %s: %s",
            event.activity_id,
            str(e),
        )


def add_case_participant_to_case(
    event: AddCaseParticipantToCaseReceivedEvent, dl: DataLayer
) -> None:
    try:
        participant_id = event.object_id
        case_id = event.target_id
        participant = dl.read(participant_id)
        case = cast(CaseModel, dl.read(case_id))

        if case is None:
            logger.warning(
                "add_case_participant_to_case: case '%s' not found", case_id
            )
            return

        existing_ids = [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]
        if participant_id in existing_ids:
            logger.info(
                "Participant '%s' already in case '%s' — skipping (idempotent)",
                participant_id,
                case_id,
            )
            return

        # Use string ID to avoid wire-type serialization incompatibility
        case.case_participants.append(participant_id)
        if (
            hasattr(participant, "attributed_to")
            and participant.attributed_to is not None
        ):
            actor_id = (
                participant.attributed_to.as_id
                if hasattr(participant.attributed_to, "as_id")
                else str(participant.attributed_to)
            )
            case.actor_participant_index[actor_id] = participant_id
        dl.save(case)
        logger.info(
            "Added participant '%s' to case '%s'", participant_id, case_id
        )

    except Exception as e:
        logger.error(
            "Error in add_case_participant_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def remove_case_participant_from_case(
    event: RemoveCaseParticipantFromCaseReceivedEvent, dl: DataLayer
) -> None:
    try:
        participant_id = event.object_id
        case_id = event.target_id
        case = cast(CaseModel, dl.read(case_id))

        if case is None:
            logger.warning(
                "remove_case_participant_from_case: case '%s' not found",
                case_id,
            )
            return

        existing_ids = [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]
        if participant_id not in existing_ids:
            logger.info(
                "Participant '%s' not in case '%s' — skipping (idempotent)",
                participant_id,
                case_id,
            )
            return

        case.remove_participant(participant_id)
        dl.save(case)
        logger.info(
            "Removed participant '%s' from case '%s'", participant_id, case_id
        )

    except Exception as e:
        logger.error(
            "Error in remove_case_participant_from_case for activity %s: %s",
            event.activity_id,
            str(e),
        )
