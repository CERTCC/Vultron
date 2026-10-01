"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_accept_ownership_transfer_tree,
    create_offer_ownership_transfer_tree,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    is_recipient,
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    not_case_manager,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


class OfferCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: OfferCaseOwnershipTransferReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: OfferCaseOwnershipTransferReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def _resolve_offering_actor_id(self, case_id: str) -> str | None:
        """Return the actor whose intent the forwarded Offer should carry.

        The inbound Offer is normally a *delegated* message: the CaseActor is its
        `actor` and the participant who asked for the transfer is in
        `attributed_to` (CM-24-001, CM-24-002).  Reading `actor_id` alone would
        make the CaseActor forward an Offer attributing that participant's intent
        to itself, leaving no receiver able to recover who offered.

        `attributed_to` is honoured **only** in that delegated shape — when the
        sender is this case's CaseActor.  A peer that sets `attributed_to` on an
        Offer it sends under its own identity is claiming to speak for someone
        else, and relaying that unchecked would let any participant forge the
        offerer of record; nothing downstream re-checks it, because
        CLP-07-003 validates `payloadSnapshot.actor` and not `attributed_to`.
        Outside the delegated shape the sender is the offerer, which is also the
        correct answer when the case has no CaseActor at all (CM-24-003).
        """
        request = self._request
        delegated_author = _as_id(request.activity.attributed_to)
        if delegated_author is None:
            return request.actor_id
        case = self._dl.read_case(case_id)
        case_actor_id = (
            resolve_case_manager_id(case, self._dl)
            if case is not None
            else None
        )
        if case_actor_id is not None and request.actor_id == case_actor_id:
            return delegated_author
        logger.warning(
            "OfferCaseOwnershipTransferReceived: ignoring attributed_to '%s'"
            " on an Offer sent by '%s', which is not case '%s''s CaseActor"
            " ('%s') — only a delegated Offer may name another actor as the"
            " offerer (CM-24-001, CM-24-002)",
            delegated_author,
            request.actor_id,
            case_id,
            case_actor_id,
        )
        return request.actor_id

    def execute(self) -> HandlerResult:
        request = self._request
        # Resolve the receiver before any write: it raises when no actor owns
        # this store, and a refusal must not leave the Offer behind (#2667).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        # Two receivers are entitled to this Offer: the CASE_MANAGER it is
        # addressed to (CM-21-005) and the transferee the CASE_MANAGER forwards
        # it to.  Both are named in `to`; anyone else holds a misaddressed
        # copy, refuses, and stores nothing (HP-01-005, #3752).
        if not is_recipient(receiving_actor_id, request.activity):
            verdict = HandlerResult.refused(
                f"'{receiving_actor_id}' is not a recipient of ownership"
                f"-transfer Offer '{request.activity_id}'"
            )
            logger.warning(
                "OfferCaseOwnershipTransferReceived: refused '%s': %s",
                request.activity_id,
                verdict.reason,
            )
            return verdict

        stored = _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "OfferCaseOwnershipTransfer",
            request.activity_id,
        )

        case_id = _as_id(request.activity.object_)
        if case_id is None:
            logger.warning(
                "OfferCaseOwnershipTransferReceived: missing case_id"
                " on offer '%s' — refusing",
                request.activity_id,
            )
            return HandlerResult.refused(
                "Offer(ownership transfer) names no case"
            )

        transferee_id = _as_id(request.activity.target)
        original_actor_id = self._resolve_offering_actor_id(case_id)

        # One tree, run once (CLP-10-005).  The guarded commit fires only when
        # receiving_actor_id is the CaseActor (CheckIsCaseManagerNode gate), and
        # the CM-gated ForwardOfferToTransfereeNode in the effect section does
        # the CM-21-005 forward — no procedural outbox write here.
        tree = create_offer_ownership_transfer_tree(
            case_id=case_id,
            transferee_id=transferee_id,
            original_actor_id=original_actor_id,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )
        verdict = verdict_from_bt(
            tree, result, label="OfferOwnershipTransferBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "OfferOwnershipTransferBT refused for case '%s': %s",
                case_id,
                verdict.reason,
            )
            return verdict
        if not_case_manager(tree):
            # The cascade is the CASE_MANAGER's; the transferee (an addressee,
            # checked above) only stores the forwarded Offer.
            return stored
        return verdict


class AcceptCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptCaseOwnershipTransferReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AcceptCaseOwnershipTransferReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
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
            return HandlerResult.refused(
                "Accept(ownership transfer) names no case"
            )
        tree = create_accept_ownership_transfer_tree(
            case_id=case_id,
            new_owner_id=new_owner_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, wire_render_port=self._wire_render_port
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )
        verdict = verdict_from_bt(
            tree, result, label="AcceptOwnershipTransferBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "AcceptOwnershipTransferBT refused for case '%s' new_owner"
                " '%s': %s",
                case_id,
                new_owner_id,
                verdict.reason,
            )
        return verdict


class RejectCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectCaseOwnershipTransferReceivedEvent,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: RejectCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        logger.info(
            "Actor '%s' rejected ownership transfer offer '%s' — ownership unchanged",
            request.actor_id,
            request.offer_id,
        )
        return HandlerResult.skipped(
            "ownership transfer declined; nothing to undo"
        )
