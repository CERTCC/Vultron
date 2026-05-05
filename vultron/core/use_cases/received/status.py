"""Use cases for case and participant status activities."""

import logging
from typing import Any, cast

from vultron.core.models.events.status import (
    AddCaseStatusToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
    CreateCaseStatusReceivedEvent,
    CreateParticipantStatusReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.cs import is_valid_pxa_transition
from vultron.core.states.em import is_valid_em_transition
from vultron.core.states.rm import is_valid_rm_transition
from vultron.core.use_cases._helpers import _as_id, _idempotent_create
from vultron.core.models.protocols import (
    ParticipantStatusModel,
    is_case_model,
    is_participant_model,
)

logger = logging.getLogger(__name__)


def _resolve_case_status_object(
    dl: CasePersistence,
    status_id: str,
    request: AddCaseStatusToCaseReceivedEvent,
) -> object:
    status_obj = dl.read(status_id)
    if hasattr(status_obj, "id_"):
        return status_obj
    return request.status


def _validate_case_status_transition(
    case: object, status_obj: object, case_id: str
) -> bool:
    current_status = getattr(case, "current_status", None)
    if current_status is None:
        return True

    if not _validate_optional_case_transition(
        "EM",
        current_status.em_state,
        getattr(status_obj, "em_state", None),
        case_id,
        is_valid_em_transition,
    ):
        return False

    return _validate_optional_case_transition(
        "PXA",
        current_status.pxa_state,
        getattr(status_obj, "pxa_state", None),
        case_id,
        is_valid_pxa_transition,
    )


def _validate_optional_case_transition(
    label: str,
    current_state: object,
    new_state: object,
    case_id: str,
    validator: Any,
) -> bool:
    if new_state is None or current_state == new_state:
        return True
    if validator(current_state, new_state):
        return True

    logger.warning(
        "Invalid %s transition %s → %s for case '%s'; skipping status append",
        label,
        current_state,
        new_state,
        case_id,
    )
    return False


class CreateCaseStatusReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CreateCaseStatusReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateCaseStatusReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.status_id,
            request.status,
            "CaseStatus",
            request.activity_id,
        )


class AddCaseStatusToCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: AddCaseStatusToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddCaseStatusToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        status_id = request.status_id
        case_id = request.case_id
        if status_id is None or case_id is None:
            logger.warning(
                "add_case_status_to_case: missing status_id or case_id"
            )
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
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

        status_obj = _resolve_case_status_object(self._dl, status_id, request)
        if case.case_statuses and not _validate_case_status_transition(
            case, status_obj, case_id
        ):
            return

        case.case_statuses.append(status_obj)
        self._dl.save(case)
        logger.info("Added CaseStatus '%s' to case '%s'", status_id, case_id)


class CreateParticipantStatusReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: CreateParticipantStatusReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: CreateParticipantStatusReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.status_id,
            request.status,
            "ParticipantStatus",
            request.activity_id,
        )


class AddParticipantStatusToParticipantReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AddParticipantStatusToParticipantReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AddParticipantStatusToParticipantReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        status_id = request.status_id
        participant_id = request.participant_id
        if status_id is None or participant_id is None:
            logger.warning(
                "add_participant_status_to_participant: missing status_id or participant_id"
            )
            return
        participant = self._dl.read(participant_id)

        if not is_participant_model(participant):
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
        if not hasattr(status_obj, "id_"):
            status_obj = request.status
        if status_obj is None:
            logger.warning(
                "add_participant_status_to_participant: status '%s' not found",
                status_id,
            )
            return
        if not hasattr(status_obj, "rm_state") or not hasattr(
            status_obj, "vfd_state"
        ):
            logger.warning(
                "add_participant_status_to_participant: status '%s' is not a ParticipantStatus",
                status_id,
            )
            return

        new_rm_state = getattr(status_obj, "rm_state", None)
        if new_rm_state is not None and participant.participant_statuses:
            if hasattr(participant, "participant_status") and getattr(
                participant, "participant_status"
            ):
                current_status = cast(Any, participant).participant_status
            else:
                current_status = participant.participant_statuses[-1]
            current_rm = current_status.rm_state
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

        participant.participant_statuses.append(
            cast(ParticipantStatusModel, status_obj)
        )
        self._dl.save(participant)
        logger.info(
            "Added ParticipantStatus '%s' to participant '%s'",
            status_id,
            participant_id,
        )
