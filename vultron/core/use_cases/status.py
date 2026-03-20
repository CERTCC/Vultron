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
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.core.use_cases._helpers import _as_id, _idempotent_create
from vultron.core.models.protocols import CaseModel, ParticipantModel

logger = logging.getLogger(__name__)


class CreateCaseStatusReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: CreateCaseStatusReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateCaseStatusReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.object_id,
            request.status,
            "CaseStatus",
            request.activity_id,
        )


class AddCaseStatusToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AddCaseStatusToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddCaseStatusToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        status_id = request.object_id
        case_id = request.target_id
        case = cast(CaseModel, self._dl.read(case_id))

        if case is None:
            logger.warning(
                "add_case_status_to_case: case '%s' not found", case_id
            )
            return

        existing_ids = [_as_id(s) for s in case.case_statuses]
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
        logger.info("Added CaseStatus '%s' to case '%s'", status_id, case_id)


class CreateParticipantStatusReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: CreateParticipantStatusReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateParticipantStatusReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.object_id,
            request.status,
            "ParticipantStatus",
            request.activity_id,
        )


class AddParticipantStatusToParticipantReceivedUseCase:
    def __init__(
        self,
        dl: DataLayer,
        request: AddParticipantStatusToParticipantReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AddParticipantStatusToParticipantReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        status_id = request.object_id
        participant_id = request.target_id
        participant = cast(ParticipantModel, self._dl.read(participant_id))

        if participant is None:
            logger.warning(
                "add_participant_status_to_participant: participant '%s' not found",
                participant_id,
            )
            return

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
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

        new_rm_state = getattr(status_obj, "rm_state", None)
        if new_rm_state is not None and participant.participant_statuses:
            current_rm = participant.participant_statuses[-1].rm_state
            if current_rm != new_rm_state and not is_valid_rm_transition(
                current_rm, new_rm_state
            ):
                logger.warning(
                    "Invalid RM transition %s → %s for participant '%s'; "
                    "skipping status append",
                    current_rm,
                    new_rm_state,
                    participant_id,
                )
                return

        participant.participant_statuses.append(status_obj)
        self._dl.save(participant)
        logger.info(
            "Added ParticipantStatus '%s' to participant '%s'",
            status_id,
            participant_id,
        )
