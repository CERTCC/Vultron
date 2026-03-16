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


class CreateCaseStatusReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: CreateCaseStatusReceivedEvent) -> None:
        try:
            existing = self._dl.get(request.object_type, request.object_id)
            if existing is not None:
                logger.info(
                    "CaseStatus '%s' already stored — skipping (idempotent)",
                    request.object_id,
                )
                return

            obj_to_store = request.status
            if obj_to_store is not None:
                self._dl.create(obj_to_store)
                logger.info("Stored CaseStatus '%s'", request.object_id)
            else:
                logger.warning(
                    "create_case_status: no status object for event '%s'",
                    request.activity_id,
                )

        except Exception as e:
            logger.error(
                "Error in create_case_status for activity %s: %s",
                request.activity_id,
                str(e),
            )


class AddCaseStatusToCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: AddCaseStatusToCaseReceivedEvent) -> None:
        try:
            status_id = request.object_id
            case_id = request.target_id
            case = cast(CaseModel, self._dl.read(case_id))

            if case is None:
                logger.warning(
                    "add_case_status_to_case: case '%s' not found", case_id
                )
                return

            existing_ids = [
                (s.as_id if hasattr(s, "as_id") else s)
                for s in case.case_statuses
            ]
            if status_id in existing_ids:
                logger.info(
                    "CaseStatus '%s' already in case '%s' — skipping (idempotent)",
                    status_id,
                    case_id,
                )
                return

            # Prefer the domain object from the event over dl.read, which may
            # return a raw TinyDB Document if reconstitution of the stored
            # VultronCaseStatus record fails (wire CaseStatus has different
            # field types).
            status_obj = self._dl.read(status_id)
            if not hasattr(status_obj, "as_id"):
                status_obj = request.status
            case.case_statuses.append(status_obj)
            self._dl.save(case)
            logger.info(
                "Added CaseStatus '%s' to case '%s'", status_id, case_id
            )

        except Exception as e:
            logger.error(
                "Error in add_case_status_to_case for activity %s: %s",
                request.activity_id,
                str(e),
            )


class CreateParticipantStatusReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: CreateParticipantStatusReceivedEvent) -> None:
        try:
            existing = self._dl.get(request.object_type, request.object_id)
            if existing is not None:
                logger.info(
                    "ParticipantStatus '%s' already stored — skipping (idempotent)",
                    request.object_id,
                )
                return

            obj_to_store = request.status
            if obj_to_store is not None:
                self._dl.create(obj_to_store)
                logger.info("Stored ParticipantStatus '%s'", request.object_id)
            else:
                logger.warning(
                    "create_participant_status: no status object for event '%s'",
                    request.activity_id,
                )

        except Exception as e:
            logger.error(
                "Error in create_participant_status for activity %s: %s",
                request.activity_id,
                str(e),
            )


class AddParticipantStatusToParticipantReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(
        self, request: AddParticipantStatusToParticipantReceivedEvent
    ) -> None:
        try:
            status_id = request.object_id
            participant_id = request.target_id
            participant = cast(ParticipantModel, self._dl.read(participant_id))

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

            # Prefer the domain object from the event over dl.read, which may
            # return a raw TinyDB Document when VultronParticipantStatus
            # reconstitution fails.
            status_obj = self._dl.read(status_id)
            if not hasattr(status_obj, "as_id"):
                status_obj = request.status
            participant.participant_statuses.append(status_obj)
            self._dl.save(participant)
            logger.info(
                "Added ParticipantStatus '%s' to participant '%s'",
                status_id,
                participant_id,
            )

        except Exception as e:
            logger.error(
                "Error in add_participant_status_to_participant for activity %s: %s",
                request.activity_id,
                str(e),
            )
