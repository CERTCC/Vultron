"""Use cases for embargo management activities."""

import logging
from typing import cast

from transitions import MachineError

from vultron.core.states.em import EM, create_em_machine
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
from vultron.core.use_cases._helpers import _as_id, _idempotent_create
from vultron.core.models.protocols import CaseModel, ParticipantModel

logger = logging.getLogger(__name__)


class _EMAdapter:
    """Adapter that lets the EM transitions machine operate on a plain .state attribute.

    Seed with the current EM state, pass to ``machine.add_model(initial=...)``,
    trigger the desired transition, then read back ``.state``.
    """

    def __init__(self, initial: EM) -> None:
        self.state = initial


class CreateEmbargoEventReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: CreateEmbargoEventReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateEmbargoEventReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.object_id,
            request.embargo,
            "EmbargoEvent",
            request.activity_id,
        )


class AddEmbargoEventToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AddEmbargoEventToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddEmbargoEventToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        embargo_id = request.object_id
        case_id = request.target_id
        case = cast(CaseModel, self._dl.read(case_id))

        if case is None:
            logger.warning(
                "add_embargo_event_to_case: case '%s' not found", case_id
            )
            return

        current_embargo_id = _as_id(case.active_embargo)
        if current_embargo_id == embargo_id:
            logger.info(
                "Case '%s' already has embargo '%s' active — skipping (idempotent)",
                case_id,
                embargo_id,
            )
            return

        case.set_embargo(embargo_id)
        case.current_status.em_state = EM.ACTIVE
        self._dl.save(case)
        logger.info("Activated embargo '%s' on case '%s'", embargo_id, case_id)


class RemoveEmbargoEventFromCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: RemoveEmbargoEventFromCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: RemoveEmbargoEventFromCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        embargo_id = request.object_id
        case_id = request.origin_id
        case = cast(CaseModel, self._dl.read(case_id))

        if case is None:
            logger.warning(
                "remove_embargo_event_from_case: case '%s' not found",
                case_id,
            )
            return

        # Remove from proposed_embargoes if present.
        proposed = [_as_id(e) for e in case.proposed_embargoes]
        if embargo_id in proposed:
            case.proposed_embargoes = [
                e for e in case.proposed_embargoes if _as_id(e) != embargo_id
            ]
            logger.info(
                "Removed embargo '%s' from proposed_embargoes of case '%s'",
                embargo_id,
                case_id,
            )

        # Clear active_embargo if it matches the removed embargo.
        current_embargo_id = _as_id(case.active_embargo)
        if current_embargo_id != embargo_id:
            self._dl.save(case)
            return

        em_state = case.current_status.em_state
        adapter = _EMAdapter(em_state)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_state)

        try:
            # PROPOSED → NONE is a valid machine transition (REJECT trigger).
            adapter.reject()
            new_em_state = EM(adapter.state)
        except MachineError:
            # No machine path back to NONE from this state.
            # NONE is already the target (idempotent); anything else is an
            # administrative override that bypasses the normal EM lifecycle.
            if em_state != EM.NONE:
                logger.warning(
                    "Admin override: resetting EM state from '%s' to NONE on"
                    " case '%s' (no valid machine transition available;"
                    " use SvcTerminateEmbargoUseCase for normal termination)",
                    em_state,
                    case_id,
                )
            new_em_state = EM.NONE

        case.active_embargo = None  # type: ignore[attr-defined]
        case.current_status.em_state = new_em_state
        self._dl.save(case)
        logger.info(
            "Removed active embargo '%s' from case '%s' (EM %s → %s)",
            embargo_id,
            case_id,
            em_state,
            new_em_state,
        )


class AnnounceEmbargoEventToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AnnounceEmbargoEventToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AnnounceEmbargoEventToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Received embargo announcement '%s' on case '%s'",
            request.activity_id,
            request.context_id,
        )


class InviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: InviteToEmbargoOnCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: InviteToEmbargoOnCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "InviteToEmbargoOnCase",
            request.activity_id,
        )


class AcceptInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AcceptInviteToEmbargoOnCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteToEmbargoOnCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
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
            context_id = _as_id(context_id)
            if context_id is None:
                logger.error(
                    "accept_invite_to_embargo_on_case: cannot determine case from invite '%s'",
                    request.object_id,
                )
                return
            case = cast(CaseModel, self._dl.read(context_id))

        if case is None:
            logger.error("accept_invite_to_embargo_on_case: case not found")
            return
        case_id = case.as_id

        current_embargo_id = _as_id(case.active_embargo)
        if current_embargo_id == embargo_id:
            logger.info(
                "Case '%s' already has embargo '%s' active — skipping (idempotent)",
                case_id,
                embargo_id,
            )
            return

        case.set_embargo(embargo_id)
        case.current_status.em_state = EM.ACTIVE

        accepting_actor_id = request.actor_id
        participant_id = case.actor_participant_index.get(accepting_actor_id)
        if participant_id:
            participant = cast(ParticipantModel, self._dl.read(participant_id))
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


class RejectInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: RejectInviteToEmbargoOnCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: RejectInviteToEmbargoOnCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected embargo proposal '%s'",
            request.actor_id,
            request.object_id,
        )
