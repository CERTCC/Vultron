"""Use cases for case participant management activities."""

import logging

from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.models.protocols import is_case_model
from vultron.core.use_cases._helpers import _as_id, _idempotent_create

logger = logging.getLogger(__name__)


class CreateCaseParticipantReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CreateCaseParticipantReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateCaseParticipantReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.participant_id,
            request.participant,
            "CaseParticipant",
            request.activity_id,
        )


class AddCaseParticipantToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AddCaseParticipantToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AddCaseParticipantToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        participant_id = request.participant_id
        case_id = request.case_id
        if participant_id is None or case_id is None:
            logger.warning(
                "add_case_participant_to_case: missing participant_id or case_id"
            )
            return
        participant = self._dl.read(participant_id)
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "add_case_participant_to_case: case '%s' not found",
                case_id,
            )
            return

        existing_ids = [_as_id(p) for p in case.case_participants]
        if participant_id in existing_ids:
            logger.info(
                "Participant '%s' already in case '%s' — skipping (idempotent)",
                participant_id,
                case_id,
            )
            return

        # Use string ID to avoid wire-type serialization incompatibility
        case.case_participants.append(participant_id)
        if participant is not None:
            actor_id = _as_id(getattr(participant, "attributed_to", None))
            if actor_id is not None:
                case.actor_participant_index[actor_id] = participant_id
        case.record_event(participant_id, "participant_added")
        self._dl.save(case)
        logger.info(
            "Added participant '%s' to case '%s'", participant_id, case_id
        )


class RemoveCaseParticipantFromCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RemoveCaseParticipantFromCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RemoveCaseParticipantFromCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        participant_id = request.participant_id
        case_id = request.case_id
        if participant_id is None or case_id is None:
            logger.warning(
                "remove_case_participant_from_case: missing participant_id or case_id"
            )
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "remove_case_participant_from_case: case '%s' not found",
                case_id,
            )
            return

        existing_ids = [_as_id(p) for p in case.case_participants]
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
