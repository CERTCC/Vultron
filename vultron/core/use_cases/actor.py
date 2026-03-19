"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import cast

from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptSuggestActorToCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectSuggestActorToCaseReceivedEvent,
    SuggestActorToCaseReceivedEvent,
)
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._helpers import _as_id, _idempotent_create
from vultron.core.models.protocols import CaseModel

logger = logging.getLogger(__name__)


class SuggestActorToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: SuggestActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: SuggestActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "SuggestActorToCase",
            request.activity_id,
        )


class AcceptSuggestActorToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AcceptSuggestActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AcceptSuggestActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "AcceptSuggestActorToCase",
            request.activity_id,
        )


class RejectSuggestActorToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: RejectSuggestActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: RejectSuggestActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected recommendation to add actor '%s' to case",
            request.actor_id,
            request.object_id,
        )


class OfferCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: OfferCaseOwnershipTransferReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: OfferCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "OfferCaseOwnershipTransfer",
            request.activity_id,
        )


class AcceptCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AcceptCaseOwnershipTransferReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AcceptCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        case_id = request.inner_object_id
        new_owner_id = request.actor_id
        case = cast(CaseModel, self._dl.read(case_id))

        if case is None:
            logger.warning(
                "accept_case_ownership_transfer: case '%s' not found",
                case_id,
            )
            return

        current_owner_id = _as_id(case.attributed_to)
        if current_owner_id == new_owner_id:
            logger.info(
                "Case '%s' already owned by '%s' — skipping (idempotent)",
                case_id,
                new_owner_id,
            )
            return

        case.attributed_to = new_owner_id  # type: ignore[assignment]
        self._dl.save(case)
        logger.info(
            "Transferred ownership of case '%s' from '%s' to '%s'",
            case_id,
            current_owner_id,
            new_owner_id,
        )


class RejectCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: RejectCaseOwnershipTransferReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: RejectCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected ownership transfer offer '%s' — ownership unchanged",
            request.actor_id,
            request.object_id,
        )


class InviteActorToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: InviteActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: InviteActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "InviteActorToCase",
            request.activity_id,
        )


class AcceptInviteActorToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AcceptInviteActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        case_id = request.inner_target_id
        invitee_id = request.inner_object_id
        case = cast(CaseModel, self._dl.read(case_id))

        if case is None:
            logger.warning(
                "accept_invite_actor_to_case: case '%s' not found", case_id
            )
            return

        existing_ids = [_as_id(p) for p in case.case_participants]
        if (
            invitee_id in case.actor_participant_index
            or invitee_id in existing_ids
        ):
            logger.info(
                "Actor '%s' already participant in case '%s' — skipping (idempotent)",
                invitee_id,
                case_id,
            )
            return

        active_embargo_id = _as_id(case.active_embargo)

        participant = VultronParticipant(
            as_id=f"{case_id}/participants/{invitee_id.split('/')[-1]}",
            attributed_to=invitee_id,
            context=case_id,
        )
        if active_embargo_id:
            participant.accepted_embargo_ids.append(active_embargo_id)
        self._dl.create(participant)

        # Use string IDs to avoid wire-type serialization incompatibility
        case.case_participants.append(participant.as_id)
        case.actor_participant_index[invitee_id] = participant.as_id
        case.record_event(invitee_id, "participant_joined")
        if active_embargo_id:
            case.record_event(active_embargo_id, "embargo_accepted")
        self._dl.save(case)

        logger.info(
            "Added participant '%s' to case '%s' via accepted invite",
            invitee_id,
            case_id,
        )


class RejectInviteActorToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: RejectInviteActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: RejectInviteActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            request.actor_id,
            request.object_id,
        )
