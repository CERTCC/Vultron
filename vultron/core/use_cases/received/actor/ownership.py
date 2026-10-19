"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_accept_ownership_transfer_tree,
    create_offer_ownership_transfer_tree,
    create_reject_ownership_transfer_tree,
    create_undo_ownership_transfer_tree,
)
from vultron.core.models._helpers import _as_id, now_utc
from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    UndoCaseOwnershipTransferReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.predicates.addressing import normalise_actor_id
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    intake_verdict,
    not_case_manager,
    ownership_answer_verdict,
    ownership_offer_verdict,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)

logger = logging.getLogger(__name__)


class OfferCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER records and forwards an ownership-transfer Offer.

    At the CASE_MANAGER the sender must hold ``CVDRole.CASE_OWNER`` on the
    case; at any other replica, the transferee's, it must be the CASE_MANAGER
    forwarding it (CM-21-019, PCR-03-001).  Anyone else is ``REFUSED`` by the
    tree's sender guard before anything but intake's archive is written
    (CLP-10-018): no expiry, no ledger entry, no forward, the Offer not
    stored and the owner unchanged.  A redelivery of an Offer the
    CASE_MANAGER recorded from its sender is ``SKIPPED`` (HP-01-003).
    """

    # Only the Case Owner offers the case; the CASE_MANAGER never sends itself
    # one, and a replica takes the forward from the CASE_MANAGER alone
    # (CM-21-019, PCR-03-001, ADR-0129).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.CASE_OWNER
    )

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

        Two shapes arrive.  At the CASE_MANAGER, the Offer is the Case Owner's
        own: the owner is its `actor` and it carries no `attributed_to`
        (CM-21-005, CM-24-004), so the sender is the offerer.  At the
        transferee, it is the CASE_MANAGER's forward, a *delegated* message:
        the CaseActor is its `actor` and the owner who asked for the transfer
        is in `attributed_to` (CM-24-001, CM-24-002).  Reading `actor_id` alone
        there would attribute the owner's intent to the CaseActor, leaving no
        receiver able to recover who offered.

        `attributed_to` is honoured **only** in that delegated shape — when the
        sender is this case's CaseActor.  A peer that sets `attributed_to` on an
        Offer it sends under its own identity is claiming to speak for someone
        else, and relaying that unchecked would let any participant forge the
        offerer of record; nothing downstream re-checks it, because
        CLP-07-003 validates `payloadSnapshot.actor` and not `attributed_to`.
        Outside the delegated shape the sender is the offerer, which is also the
        correct answer when the case has no CaseActor at all (the retired
        send-directly arm; see CM-24-006).
        """
        request = self._request
        delegated_author = _as_id(request.activity.attributed_to)
        if delegated_author is None:
            return request.actor_id
        # Recorded as the offerer, so normalised where it is extracted, like
        # the sender id (OID-01-006).
        delegated_author = normalise_actor_id(delegated_author)
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
        # it to.  The tree's addressee door guard refuses a copy not addressed
        # to this store before it stores anything (HP-01-005, #3752); the
        # sender guard then refuses a sender's own copy at a replica, which
        # takes the Offer from the CASE_MANAGER alone (PCR-03-001).
        case_id = _as_id(request.activity.object_)
        # The transferee becomes the case owner if it accepts, so it is
        # normalised where it is extracted (OID-01-006).
        transferee_id = _as_id(request.activity.target)
        if transferee_id is not None:
            transferee_id = normalise_actor_id(transferee_id)
        original_actor_id = (
            self._resolve_offering_actor_id(case_id)
            if case_id is not None
            else None
        )

        # The received tree, run once (CLP-10-005).  Its sender guard
        # refuses a sender that is not the Case Owner before anything is
        # written (CM-21-019, HP-01-006).  A new Offer for the case is one of
        # the moments the CASE_MANAGER checks the open Offer's deadline
        # (CM-21-017): the tree's clock decision closes an expired one before
        # this Offer is judged against it (CM-21-014, CLP-10-025).  The
        # guarded commit fires only when receiving_actor_id is the CaseActor
        # (CheckIsCaseManagerNode gate), and the CM-gated
        # ForwardOfferToTransfereeNode in the effect section does the
        # CM-21-005 forward — no procedural outbox write here.
        tree = create_offer_ownership_transfer_tree(
            case_id=case_id,
            transferee_id=transferee_id,
            original_actor_id=original_actor_id,
            answer_deadline=request.answer_deadline,
            # An Offer naming no case is refused below, so only intake's
            # archive keeps it (CLP-10-018); storing it would let any sender
            # leave an Offer behind (#4737).
            store_offer=(
                StoreReceivedObjectNode(
                    request.activity_type,
                    request.activity_id,
                    request.activity,
                    "OfferCaseOwnershipTransfer",
                    request.activity_id,
                )
                if case_id is not None
                else None
            ),
            offer_id=request.activity_id,
            now=now_utc(),
            sender_rule=self.sender_entitlement,
            sender_id=request.actor_id,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        if case_id is None:
            # Intake archived the Offer; there is no case to act on.  A door
            # guard's refusal (an unaddressed copy, HP-01-005) is its own.
            verdict = applied_or_raise(
                tree, result, label="OfferOwnershipTransferBT"
            )
            if verdict.disposition is HandlerDisposition.REFUSED:
                return verdict
            logger.warning(
                "OfferCaseOwnershipTransferReceived: missing case_id"
                " on offer '%s' — refusing",
                request.activity_id,
            )
            return HandlerResult.refused(
                "Offer(ownership transfer) names no case"
            )
        verdict = ownership_offer_verdict(
            tree,
            verdict_from_bt(tree, result, label="OfferOwnershipTransferBT"),
        )
        if verdict.disposition is HandlerDisposition.SKIPPED:
            return verdict
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "OfferOwnershipTransferBT refused for case '%s': %s",
                case_id,
                verdict.reason,
            )
            return verdict
        if not_case_manager(tree):
            # The cascade is the CASE_MANAGER's; the transferee (admitted by
            # the tree's door and sender guards) only stores the forwarded
            # Offer, so what it did is what intake and the store did
            # (HP-01-003).
            return intake_verdict(
                tree, result, label="OfferOwnershipTransferBT"
            )
        return verdict


#: A received reply to an ownership-transfer Offer: the transferee's answer
#: or the offerer's withdrawal.
_OwnershipOfferReply = (
    AcceptCaseOwnershipTransferReceivedEvent
    | RejectCaseOwnershipTransferReceivedEvent
    | UndoCaseOwnershipTransferReceivedEvent
)


def _names_no_case(
    request: _OwnershipOfferReply,
    verb: str,
) -> HandlerResult:
    """The refusal of a reply to an Offer (*verb*) that names no case.

    Shared by the Accept, the Reject and the Undo, before any tree is built.
    """
    logger.warning(
        "%s(ownership transfer): '%s' from '%s' names no case",
        verb,
        request.activity_id,
        request.actor_id,
    )
    return HandlerResult.refused(f"{verb}(ownership transfer) names no case")


def _run_ownership_answer(
    *,
    dl: CaseOutboxPersistence,
    request: _OwnershipOfferReply,
    tree: py_trees.behaviour.Behaviour,
    label: str,
    sync_port: SyncActivityPort | None,
    wire_render_port: "WireRenderPort | None",
    applied_note: str | None = None,
    trigger_activity: "TriggerActivityPort | None" = None,
) -> HandlerResult:
    """Run the receive tree of a reply to an Offer and read its verdict.

    Shared by the Accept, the Reject and the Undo.  The tree's clock
    decision first ledgers the expiry of the case's open Offer if its
    deadline passed (CM-21-017, CLP-10-025), so a reply to it is refused as
    closed (CM-21-016).  A redelivery of the reply that already closed the
    Offer is ``SKIPPED`` (HP-01-003); a refusal is logged at WARNING with the
    sender and the case.  When *applied_note* is given, an applied reply is
    logged at INFO with it.  *trigger_activity* builds the entries the
    CASE_MANAGER records for the changes an applied reply causes.
    """
    receiving_actor_id = resolve_receiving_actor_id(
        dl, request.receiving_actor_id
    )
    bridge = BTBridge(
        datalayer=dl,
        trigger_activity=trigger_activity,
        wire_render_port=wire_render_port,
        sync_port=sync_port,
    )
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=receiving_actor_id,
        activity=request,
    )
    verdict = ownership_answer_verdict(
        tree, verdict_from_bt(tree, result, label=label)
    )
    if verdict.disposition is HandlerDisposition.REFUSED:
        logger.warning(
            "%s refused '%s' from '%s' for case '%s': %s",
            label,
            request.activity_id,
            request.actor_id,
            request.case_id,
            verdict.reason,
        )
    elif applied_note and verdict.disposition is HandlerDisposition.APPLIED:
        logger.info(
            "Actor '%s' %s ownership transfer offer '%s' for case '%s'",
            request.actor_id,
            applied_note,
            request.object_id,
            request.case_id,
        )
    return verdict


class AcceptCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER applies an accepted ownership transfer (CM-21-002).

    At the CASE_MANAGER the sender must be the transferee named in an open
    ownership-transfer Offer it recorded for the case; at any other replica
    it must be the CASE_MANAGER (CM-21-011, PCR-03-001).  Anyone else is
    ``REFUSED`` with ownership unchanged, nothing committed and nothing sent.
    The new owner is read from the recorded Offer, never from the sender.
    A redelivery of the Accept that already closed the Offer changes nothing
    and is ``SKIPPED`` (HP-01-003).
    """

    # The transferee is the addressee of the Offer (ADR-0129), checked at the
    # CASE_MANAGER against the Offer it recorded; a replica takes the change
    # from the CASE_MANAGER alone (PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.NAMED_ACTOR
    )

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
        # Builds the CASE_MANAGER's own entries for the changes the Accept
        # causes (CLP-07-013).
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        if case_id is None:
            return _names_no_case(request, "Accept")
        now = now_utc()
        tree = create_accept_ownership_transfer_tree(
            case_id=case_id,
            offer_id=request.object_id,
            sender_id=request.actor_id,
            answer_id=request.activity_id,
            now=now,
            sender_rule=self.sender_entitlement,
        )
        return _run_ownership_answer(
            dl=self._dl,
            request=request,
            tree=tree,
            label="AcceptOwnershipTransferBT",
            sync_port=self._sync_port,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
        )


class RejectCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER ledgers a declined ownership transfer (CM-21-012).

    The sender rule is the Accept's (CM-21-013): at the CASE_MANAGER the
    sender must be the transferee named in an open ownership-transfer Offer
    it recorded for the case; at any other replica it must be the
    CASE_MANAGER.  Anyone else is ``REFUSED`` with nothing committed and
    nothing sent, and the Offer stays open.

    An admitted Reject commits a ``reject_case_ownership_transfer`` entry and
    broadcasts ``Announce(CaseLedgerEntry)``, which closes the Offer on every
    replica (CM-21-014) and is how the offerer learns of the decline.
    Ownership is unchanged.  A redelivery of the Reject that already closed
    the Offer is ``SKIPPED`` (HP-01-003).
    """

    # The same two-sided transferee rule as the Accept (ADR-0129).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.NAMED_ACTOR
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectCaseOwnershipTransferReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: RejectCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        if case_id is None:
            return _names_no_case(request, "Reject")
        now = now_utc()
        tree = create_reject_ownership_transfer_tree(
            case_id=case_id,
            offer_id=request.object_id,
            sender_id=request.actor_id,
            answer_id=request.activity_id,
            now=now,
            sender_rule=self.sender_entitlement,
        )
        return _run_ownership_answer(
            dl=self._dl,
            request=request,
            tree=tree,
            label="RejectOwnershipTransferBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
            applied_note="rejected (ownership unchanged)",
        )


class UndoCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER ledgers a withdrawn ownership-transfer Offer (CM-21-015).

    At the CASE_MANAGER the sender must be the Case Owner that made an open
    ownership-transfer Offer it recorded for the case; at any other replica
    it must be the CASE_MANAGER.  Anyone else, or a withdrawal of an Offer
    already answered or withdrawn, is ``REFUSED`` with nothing committed and
    nothing sent.

    An admitted Undo commits an ``undo_case_ownership_transfer`` entry and
    broadcasts ``Announce(CaseLedgerEntry)``, which closes the Offer on every
    replica (CM-21-014): the transferee learns it can no longer accept, and
    the case may be offered again.  Ownership is unchanged.  A redelivery of
    the Undo that already closed the Offer is ``SKIPPED`` (HP-01-003).
    """

    # The offerer, which must still be the Case Owner (CM-21-015), checked at
    # the CASE_MANAGER against the Offer it recorded; a replica takes the
    # withdrawal from the CASE_MANAGER alone (PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: UndoCaseOwnershipTransferReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: UndoCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        if case_id is None:
            return _names_no_case(request, "Undo")
        now = now_utc()
        tree = create_undo_ownership_transfer_tree(
            case_id=case_id,
            offer_id=request.object_id,
            sender_id=request.actor_id,
            undo_id=request.activity_id,
            now=now,
            sender_rule=self.sender_entitlement,
        )
        return _run_ownership_answer(
            dl=self._dl,
            request=request,
            tree=tree,
            label="UndoOwnershipTransferBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
            applied_note="withdrew (ownership unchanged)",
        )
