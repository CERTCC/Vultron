"""Use cases for case actor/participant invitation and suggestion activities."""

import logging

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_accept_ownership_transfer_tree,
)
from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import _idempotent_create

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
        tree = create_accept_ownership_transfer_tree(
            case_id=case_id,
            new_owner_id=new_owner_id,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=new_owner_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "AcceptOwnershipTransferBT did not succeed"
                " for case '%s' new_owner '%s': %s",
                case_id,
                new_owner_id,
                BTBridge.get_failure_reason(tree),
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
