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

        # Prefer the domain object from the event over dl.read, which may
        # return a raw TinyDB Document if reconstitution of the stored
        # VultronCaseStatus record fails (wire CaseStatus has different
        # field types).
        status_obj = self._dl.read(status_id)
        if not hasattr(status_obj, "id_"):
            status_obj = request.status

        if case.case_statuses:
            current_status = getattr(case, "current_status", None)
            if current_status is not None:
                new_em = getattr(status_obj, "em_state", None)
                if new_em is not None:
                    current_em = current_status.em_state
                    if current_em != new_em and not is_valid_em_transition(
                        current_em, new_em
                    ):
                        logger.warning(
                            "Invalid EM transition %s → %s for case '%s'; "
                            "skipping status append",
                            current_em,
                            new_em,
                            case_id,
                        )
                        return

                new_pxa = getattr(status_obj, "pxa_state", None)
                if new_pxa is not None:
                    current_pxa = current_status.pxa_state
                    if current_pxa != new_pxa and not is_valid_pxa_transition(
                        current_pxa, new_pxa
                    ):
                        logger.warning(
                            "Invalid PXA transition %s → %s for case '%s'; "
                            "skipping status append",
                            current_pxa,
                            new_pxa,
                            case_id,
                        )
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
