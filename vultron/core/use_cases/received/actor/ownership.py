"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_accept_ownership_transfer_tree,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    _resolve_case_manager_id,
    add_activity_to_outbox,
    resolve_receiving_actor_id,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class OfferCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: OfferCaseOwnershipTransferReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: OfferCaseOwnershipTransferReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

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

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        case_id = _as_id(request.activity.object_)
        if case_id is None:
            logger.warning(
                "OfferCaseOwnershipTransferReceived: missing case_id"
                " on offer '%s' — skipping cascade",
                request.activity_id,
            )
            return

        transferee_id = _as_id(request.activity.target)

        # Guarded-commit: CommitCaseLedgerEntryNode fires only when
        # receiving_actor_id is the CaseActor (CheckIsCaseManagerNode gate).
        tree = create_receive_activity_tree(
            name="OfferOwnershipTransferBT",
            case_id=case_id,
            precondition_guards=[],
            effect_nodes=[],
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )
        if result.status != Status.SUCCESS:
            logger.debug(
                "OfferOwnershipTransferBT did not fully succeed"
                " for case '%s': %s",
                case_id,
                BTBridge.get_failure_reason(tree),
            )
            return

        # Forward the Offer to the transferee — CaseActor only (CM-21-005).
        # Only runs when BT succeeded (ledger entry committed).
        # CaseActor builds a NEW Offer: actor=case_actor_id,
        # attributed_to=original_offerer, to=[transferee_id].
        # Queued in CaseActor's own outbox so the registered outbox monitor
        # delivers it to the transferee's inbox.
        if self._trigger_activity is None:
            logger.warning(
                "OfferCaseOwnershipTransferReceived: no trigger_activity"
                " port — cannot forward offer to transferee (CM-21-005)"
            )
            return
        case = self._dl.read_case(case_id)
        if case is not None:
            case_actor_id = _resolve_case_manager_id(case, self._dl)
            original_actor_id = request.actor_id
            if (
                case_actor_id is not None
                and case_actor_id == receiving_actor_id
                and transferee_id
                and original_actor_id is not None
            ):
                forwarded_id, _ = (
                    self._trigger_activity.offer_case_ownership_transfer(
                        case_id=case_id,
                        transferee_id=transferee_id,
                        actor=case_actor_id,
                        to=[transferee_id],
                        attributed_to=original_actor_id,
                    )
                )
                add_activity_to_outbox(case_actor_id, forwarded_id, self._dl)
                logger.info(
                    "OfferCaseOwnershipTransferReceived: forwarded"
                    " offer '%s' (as '%s') to transferee '%s' (CM-21-005)",
                    forwarded_id,
                    case_actor_id,
                    transferee_id,
                )


class AcceptCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptCaseOwnershipTransferReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AcceptCaseOwnershipTransferReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> None:
        request = self._request
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
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
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
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
        dl: CaseOutboxPersistence,
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
