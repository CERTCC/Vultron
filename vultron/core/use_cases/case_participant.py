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


class CreateCaseParticipantReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: CreateCaseParticipantReceivedEvent) -> None:
        try:
            existing = self._dl.get(request.object_type, request.object_id)
            if existing is not None:
                logger.info(
                    "Participant '%s' already exists — skipping (idempotent)",
                    request.object_id,
                )
                return

            obj_to_store = request.participant
            if obj_to_store is not None:
                self._dl.create(obj_to_store)
                logger.info("Created participant '%s'", request.object_id)
            else:
                logger.warning(
                    "create_case_participant: no participant object for event '%s'",
                    request.activity_id,
                )

        except Exception as e:
            logger.error(
                "Error in create_case_participant for activity %s: %s",
                request.activity_id,
                str(e),
            )


class AddCaseParticipantToCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: AddCaseParticipantToCaseReceivedEvent) -> None:
        try:
            participant_id = request.object_id
            case_id = request.target_id
            participant = self._dl.read(participant_id)
            case = cast(CaseModel, self._dl.read(case_id))

            if case is None:
                logger.warning(
                    "add_case_participant_to_case: case '%s' not found",
                    case_id,
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
            self._dl.save(case)
            logger.info(
                "Added participant '%s' to case '%s'", participant_id, case_id
            )

        except Exception as e:
            logger.error(
                "Error in add_case_participant_to_case for activity %s: %s",
                request.activity_id,
                str(e),
            )


class RemoveCaseParticipantFromCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(
        self, request: RemoveCaseParticipantFromCaseReceivedEvent
    ) -> None:
        try:
            participant_id = request.object_id
            case_id = request.target_id
            case = cast(CaseModel, self._dl.read(case_id))

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
            self._dl.save(case)
            logger.info(
                "Removed participant '%s' from case '%s'",
                participant_id,
                case_id,
            )

        except Exception as e:
            logger.error(
                "Error in remove_case_participant_from_case for activity %s: %s",
                request.activity_id,
                str(e),
            )
