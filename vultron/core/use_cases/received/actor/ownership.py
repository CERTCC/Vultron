"""Use cases for the ownership-transfer activities (CM-21, ADR-0148)."""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_accept_ownership_transfer_tree,
    create_offer_ownership_transfer_tree,
    create_propose_ownership_transfer_tree,
    create_reject_ownership_transfer_tree,
    create_undo_ownership_transfer_tree,
)
from vultron.core.models._helpers import _as_id, now_utc
from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    ProposeCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    UndoCaseOwnershipTransferReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.ownership_offer import ownership_offer_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.predicates.addressing import normalise_actor_id
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    intake_verdict,
    ownership_answer_verdict,
    ownership_offer_verdict,
    verdict_from_bt,
)
from vultron.core.use_cases.received._offer_reply import (
    run_offer_reply_tree,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
    any_of,
)

logger = logging.getLogger(__name__)


class ProposeCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER makes the ownership-transfer Offer the owner proposed.

    The Case Owner proposes a transfer as ``Offer(Offer(VulnerabilityCase))``
    (ADR-0148).  The CASE_MANAGER admits it only from the Case Owner and only
    while no Offer for the case is open (CM-21-019, CM-21-014), validates the
    inner Offer — this case, a transferee it can address — ledgers the
    proposal, and makes the one ``Offer(VulnerabilityCase)`` of the transfer
    under an id it derives, with ``attributedTo`` the owner, and ledgers that
    Offer (CM-21-005).  Anyone else is ``REFUSED`` by the tree's sender
    guard before anything but intake's archive is written (CLP-10-018): no
    expiry, no ledger entry, no Offer.  A redelivery of a proposal the
    CASE_MANAGER already made its Offer from is ``SKIPPED`` (HP-01-003).
    """

    # Only the Case Owner proposes; a participant never receives a proposal,
    # so no sender is admitted there (CM-21-019, ADR-0129).
    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_case_manager=any_of(SenderEntitlementKind.CASE_OWNER)
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: ProposeCaseOwnershipTransferReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: ProposeCaseOwnershipTransferReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        # The transferee becomes the case owner if it accepts, so it is
        # normalised where it is extracted (OID-01-006).
        transferee_id = request.transferee_id
        if transferee_id is not None:
            transferee_id = normalise_actor_id(transferee_id)

        # The received tree, run once (CLP-10-005).  Its sender guard
        # refuses a sender that is not the Case Owner before anything is
        # written (CM-21-019, HP-01-006).  An earlier Offer past its
        # end_time is closed by that time alone, so it does not block this
        # proposal (CM-21-014, CM-21-017).  The CASE_MANAGER-gated MakeOwnershipTransferOfferNode
        # makes, queues and ledgers the Offer — no procedural outbox write
        # here.
        tree = create_propose_ownership_transfer_tree(
            case_id=case_id,
            proposed_case_id=request.proposed_case_id,
            transferee_id=transferee_id,
            proposal_id=request.activity_id,
            answer_deadline=request.proposed_answer_deadline,
            now=now_utc(),
            sender_rule=self.sender_entitlement,
            sender_id=request.actor_id,
        )
        result = self._bridge().execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = ownership_offer_verdict(
            tree,
            verdict_from_bt(tree, result, label="ProposeOwnershipTransferBT"),
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "ProposeOwnershipTransferBT refused for case '%s': %s",
                case_id,
                verdict.reason,
            )
        return verdict

    def _bridge(self) -> BTBridge:
        return BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )


class OfferCaseOwnershipTransferReceivedUseCase:
    """The transferee receives the CASE_MANAGER's ownership-transfer Offer.

    The one ``Offer(VulnerabilityCase)`` of a transfer, which the
    CASE_MANAGER made from the Case Owner's proposal (ADR-0148).  A
    participant takes it from the case's CASE_MANAGER alone (CM-21-019,
    PCR-03-001); intake's archive is the copy it answers, never stored under
    the id its sender chose (DL-06-006).  At the CASE_MANAGER no sender is
    admitted: an owner proposes, it does not offer.  Anyone else is
    ``REFUSED`` with nothing but intake's archive written (CLP-10-018).  A
    redelivery is ``SKIPPED`` (HP-01-003).
    """

    # Only the CASE_MANAGER makes the Offer; nobody sends it one
    # (CM-21-019, PCR-03-001, ADR-0129).
    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_participant=any_of(SenderEntitlementKind.CASE_MANAGER)
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

    def execute(self) -> HandlerResult:
        request = self._request
        # The tree's addressee door guard refuses a copy not addressed to
        # this store before it stores anything (HP-01-005, #3752); the sender
        # guard then admits the CASE_MANAGER alone (PCR-03-001).
        tree = create_offer_ownership_transfer_tree(
            case_id=_as_id(request.activity.object_),
            sender_rule=self.sender_entitlement,
            sender_id=request.actor_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="OfferOwnershipTransferBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "OfferOwnershipTransferBT refused Offer '%s': %s",
                request.activity_id,
                verdict.reason,
            )
            return verdict
        # The transferee keeps the Offer, which intake archived, so what it
        # did is what intake did (HP-01-003).
        return intake_verdict(tree, result, label="OfferOwnershipTransferBT")


class AcceptCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER applies an accepted ownership transfer (CM-21-002).

    At the CASE_MANAGER the sender must be the transferee named in an open
    ownership-transfer Offer it recorded for the case; at any other replica
    it must be the CASE_MANAGER (CM-21-011, PCR-03-001).  Anyone else is
    ``REFUSED`` with ownership unchanged, nothing committed and nothing sent
    (HP-01-006).  An Accept of an Offer already closed is ``REFUSED`` the
    same way and answered with the refusal notice (CM-21-014, CLP-05-001).
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
        now = now_utc()

        tree = create_accept_ownership_transfer_tree(
            case_id=case_id,
            offer_id=request.object_id,
            sender_id=request.actor_id,
            answer_id=request.activity_id,
            now=now,
            sender_rule=self.sender_entitlement,
        )
        return run_offer_reply_tree(
            dl=self._dl,
            request=request,
            tree=tree,
            case_id=case_id,
            subject="ownership transfer offer",
            refine=ownership_answer_verdict,
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
    nothing sent, and the Offer stays open (HP-01-006).  A Reject of an Offer
    already closed is ``REFUSED`` the same way and answered with the refusal
    notice (CM-21-014, CLP-05-001).

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
        now = now_utc()

        tree = create_reject_ownership_transfer_tree(
            case_id=case_id,
            offer_id=request.object_id,
            sender_id=request.actor_id,
            answer_id=request.activity_id,
            now=now,
            sender_rule=self.sender_entitlement,
        )
        return run_offer_reply_tree(
            dl=self._dl,
            request=request,
            tree=tree,
            case_id=case_id,
            subject="ownership transfer offer",
            refine=ownership_answer_verdict,
            label="RejectOwnershipTransferBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
            applied_note="rejected (ownership unchanged)",
        )


class UndoCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER ledgers a withdrawn ownership-transfer Offer (CM-21-015).

    The Case Owner sends ``Undo`` of its own proposal; the CASE_MANAGER
    withdraws the Offer it made from that proposal (ADR-0148).  At the
    CASE_MANAGER the sender must be the Case Owner that Offer was made for;
    at any other replica it must be the CASE_MANAGER.  Anyone else, or a
    withdrawal of an Offer already answered or withdrawn, is ``REFUSED`` with
    nothing committed; the withdrawal of a closed Offer is answered with the
    refusal notice, anyone else with nothing (CLP-05-001, HP-01-006).

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
        now = now_utc()
        proposal_id = request.proposal_id
        # The Undo names the owner's proposal; the CASE_MANAGER withdraws the
        # Offer it made from it, whose id it derives the way it did when it
        # made it (CM-21-015, ADR-0148).  At a replica the derivation names
        # no Offer it holds, but its sender guard admits the CASE_MANAGER
        # alone, so nothing is read for it.
        offer_id = (
            ownership_offer_id(
                resolve_receiving_actor_id(
                    self._dl, request.receiving_actor_id
                ),
                case_id,
                proposal_id,
                request.proposer_id,
            )
            if case_id is not None and proposal_id is not None
            else None
        )

        tree = create_undo_ownership_transfer_tree(
            case_id=case_id,
            offer_id=offer_id,
            sender_id=request.actor_id,
            undo_id=request.activity_id,
            now=now,
            sender_rule=self.sender_entitlement,
        )
        return run_offer_reply_tree(
            dl=self._dl,
            request=request,
            tree=tree,
            case_id=case_id,
            subject="ownership transfer offer",
            refine=ownership_answer_verdict,
            label="UndoOwnershipTransferBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
            applied_note="withdrew (ownership unchanged)",
        )
