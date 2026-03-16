"""Use cases for embargo management activities."""

import logging
from typing import cast

from vultron.bt.embargo_management.states import EM
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    AddEmbargoEventToCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._types import CaseModel, ParticipantModel

logger = logging.getLogger(__name__)


class CreateEmbargoEventReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: CreateEmbargoEventReceivedEvent) -> None:
        try:
            existing = self._dl.get(request.object_type, request.object_id)
            if existing is not None:
                logger.info(
                    "EmbargoEvent '%s' already stored — skipping (idempotent)",
                    request.object_id,
                )
                return

            obj_to_store = request.embargo
            if obj_to_store is not None:
                self._dl.create(obj_to_store)
                logger.info("Stored EmbargoEvent '%s'", request.object_id)
            else:
                logger.warning(
                    "create_embargo_event: no embargo object for event '%s'",
                    request.activity_id,
                )

        except Exception as e:
            logger.error(
                "Error in create_embargo_event for activity %s: %s",
                request.activity_id,
                str(e),
            )


class AddEmbargoEventToCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: AddEmbargoEventToCaseReceivedEvent) -> None:
        try:
            embargo_id = request.object_id
            case_id = request.target_id
            case = cast(CaseModel, self._dl.read(case_id))

            if case is None:
                logger.warning(
                    "add_embargo_event_to_case: case '%s' not found", case_id
                )
                return

            current_embargo_id = (
                case.active_embargo.as_id
                if hasattr(case.active_embargo, "as_id")
                else (
                    str(case.active_embargo)
                    if case.active_embargo is not None
                    else None
                )
            )
            if current_embargo_id == embargo_id:
                logger.info(
                    "Case '%s' already has embargo '%s' active — skipping (idempotent)",
                    case_id,
                    embargo_id,
                )
                return

            case.set_embargo(embargo_id)
            self._dl.save(case)
            logger.info(
                "Activated embargo '%s' on case '%s'", embargo_id, case_id
            )

        except Exception as e:
            logger.error(
                "Error in add_embargo_event_to_case for activity %s: %s",
                request.activity_id,
                str(e),
            )


class RemoveEmbargoEventFromCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(
        self, request: RemoveEmbargoEventFromCaseReceivedEvent
    ) -> None:
        try:
            embargo_id = request.object_id
            case_id = request.origin_id
            case = cast(CaseModel, self._dl.read(case_id))

            if case is None:
                logger.warning(
                    "remove_embargo_event_from_case: case '%s' not found",
                    case_id,
                )
                return

            current_embargo_id = (
                case.active_embargo.as_id
                if hasattr(case.active_embargo, "as_id")
                else (
                    str(case.active_embargo)
                    if case.active_embargo is not None
                    else None
                )
            )
            if current_embargo_id != embargo_id:
                logger.info(
                    "Case '%s' does not have embargo '%s' active — skipping",
                    case_id,
                    embargo_id,
                )
                return

            case.active_embargo = None  # type: ignore[attr-defined]
            case.current_status.em_state = EM.EMBARGO_MANAGEMENT_NONE  # type: ignore[union-attr]
            self._dl.save(case)
            logger.info(
                "Removed embargo '%s' from case '%s'", embargo_id, case_id
            )

        except Exception as e:
            logger.error(
                "Error in remove_embargo_event_from_case for activity %s: %s",
                request.activity_id,
                str(e),
            )


class AnnounceEmbargoEventToCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(
        self, request: AnnounceEmbargoEventToCaseReceivedEvent
    ) -> None:
        try:
            logger.info(
                "Received embargo announcement '%s' on case '%s'",
                request.activity_id,
                request.context_id,
            )
        except Exception as e:
            logger.error(
                "Error in announce_embargo_event_to_case for activity %s: %s",
                request.activity_id,
                str(e),
            )


class InviteToEmbargoOnCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: InviteToEmbargoOnCaseReceivedEvent) -> None:
        try:
            existing = self._dl.get(request.activity_type, request.activity_id)
            if existing is not None:
                logger.info(
                    "EmProposeEmbargoActivity '%s' already stored — skipping (idempotent)",
                    request.activity_id,
                )
                return

            obj_to_store = request.activity
            if obj_to_store is not None:
                self._dl.create(obj_to_store)
                logger.info(
                    "Stored embargo proposal '%s' (actor=%s, context=%s)",
                    request.activity_id,
                    request.actor_id,
                    request.context_id,
                )
            else:
                logger.warning(
                    "invite_to_embargo_on_case: no activity object for '%s'",
                    request.activity_id,
                )

        except Exception as e:
            logger.error(
                "Error in invite_to_embargo_on_case for activity %s: %s",
                request.activity_id,
                str(e),
            )


class AcceptInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(
        self, request: AcceptInviteToEmbargoOnCaseReceivedEvent
    ) -> None:
        try:
            embargo_id = request.inner_object_id

            if request.inner_context_id:
                case = cast(CaseModel, self._dl.read(request.inner_context_id))
            else:
                invite = self._dl.read(request.object_id)
                if invite is None:
                    logger.error(
                        "accept_invite_to_embargo_on_case: invite '%s' not found",
                        request.object_id,
                    )
                    return
                context_id = getattr(invite, "context", None)
                context_id = (
                    context_id.as_id
                    if hasattr(context_id, "as_id")
                    else str(context_id) if context_id else None
                )
                if context_id is None:
                    logger.error(
                        "accept_invite_to_embargo_on_case: cannot determine case from invite '%s'",
                        request.object_id,
                    )
                    return
                case = cast(CaseModel, self._dl.read(context_id))

            if case is None:
                logger.error(
                    "accept_invite_to_embargo_on_case: case not found"
                )
                return
            case_id = case.as_id

            current_embargo_id = (
                case.active_embargo.as_id
                if hasattr(case.active_embargo, "as_id")
                else (
                    str(case.active_embargo)
                    if case.active_embargo is not None
                    else None
                )
            )
            if current_embargo_id == embargo_id:
                logger.info(
                    "Case '%s' already has embargo '%s' active — skipping (idempotent)",
                    case_id,
                    embargo_id,
                )
                return

            case.set_embargo(embargo_id)

            accepting_actor_id = request.actor_id
            participant_id = case.actor_participant_index.get(
                accepting_actor_id
            )
            if participant_id:
                participant = cast(
                    ParticipantModel, self._dl.read(participant_id)
                )
                if (
                    participant is not None
                    and embargo_id not in participant.accepted_embargo_ids
                ):
                    participant.accepted_embargo_ids.append(embargo_id)
                    self._dl.save(participant)
                    logger.info(
                        "Recorded embargo acceptance '%s' for participant '%s'",
                        embargo_id,
                        accepting_actor_id,
                    )
            else:
                logger.warning(
                    "Accepting actor '%s' has no CaseParticipant in case '%s' — "
                    "cannot record embargo acceptance",
                    accepting_actor_id,
                    case_id,
                )

            case.record_event(embargo_id, "embargo_accepted")
            self._dl.save(case)
            logger.info(
                "Accepted embargo proposal '%s'; activated embargo '%s' on case '%s'",
                request.object_id,
                embargo_id,
                case_id,
            )

        except Exception as e:
            logger.error(
                "Error in accept_invite_to_embargo_on_case for activity %s: %s",
                request.activity_id,
                str(e),
            )


class RejectInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(
        self, request: RejectInviteToEmbargoOnCaseReceivedEvent
    ) -> None:
        try:
            logger.info(
                "Actor '%s' rejected embargo proposal '%s'",
                request.actor_id,
                request.object_id,
            )
        except Exception as e:
            logger.error(
                "Error in reject_invite_to_embargo_on_case for activity %s: %s",
                request.activity_id,
                str(e),
            )
