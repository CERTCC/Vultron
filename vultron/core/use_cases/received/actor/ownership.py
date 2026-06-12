"""Use cases for case actor/participant invitation and suggestion activities."""

import logging

from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
)
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import _as_id, _idempotent_create

logger = logging.getLogger(__name__)


class OfferCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: OfferCaseOwnershipTransferReceivedEvent,
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
        self,
        dl: CasePersistence,
        request: AcceptCaseOwnershipTransferReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AcceptCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        case_id = request.case_id
        new_owner_id = request.actor_id
        if case_id is None:
            logger.warning(
                "accept_case_ownership_transfer: missing case_id on request"
            )
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
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
        self,
        dl: CasePersistence,
        request: RejectCaseOwnershipTransferReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected ownership transfer offer '%s' — ownership unchanged",
            request.actor_id,
            request.offer_id,
        )
