"""Use cases for the ownership-transfer activities (CM-21, ADR-0148, ADR-0199)."""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees

from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_accept_ownership_transfer_tree,
    create_propose_ownership_transfer_tree,
    create_reject_ownership_transfer_tree,
    create_undo_ownership_transfer_tree,
)
from vultron.core.behaviors.case.received_run import run_received_tree
from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    UndoCaseOwnershipTransferReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.participants.ownership_offer import ownership_offer_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
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


class OfferCaseOwnershipTransferReceivedUseCase:
    """Handle an ownership-transfer ``Offer(VulnerabilityCase)``.

    One wire shape, two senders, which the path the receiver is on tells
    apart (ADR-0199, HP-01-038):

    - **The Case Owner's Offer, at the CASE_MANAGER.**  It is the Owner's
      proposal (CM-21-005).  The CASE_MANAGER admits it only from the Case
      Owner and only while no Offer for the case is open (CM-21-019,
      CM-21-014), checks the transferee — one it can address, other than
      itself and the Owner, and an active participant (CM-21-021,
      CM-21-026) — ledgers the Owner's Offer, and makes its own
      ``Offer(VulnerabilityCase)`` under an id it derives from the Owner's,
      with ``attributedTo`` the owner and ``inReplyTo`` the Owner's Offer,
      and ledgers that Offer (CM-21-028, CM-21-029).  A sender that is not
      the Case Owner is ``REFUSED`` by the tree's sender guard before
      anything is written; the outcome stage leaves only a receipt stub
      (CLP-10-018).  A refusal by the other guards is answered with the
      refusal notice and commits nothing.  A redelivery of an Owner's Offer
      the CASE_MANAGER already made its Offer from is ``SKIPPED``
      (HP-01-014).
    - **The CASE_MANAGER's Offer, at the transferee.**  A participant takes
      it from the case's CASE_MANAGER alone (PCR-03-001); the body intake
      recorded is the copy it answers, never stored under the id its sender
      chose (DL-06-006).  Anyone else is ``REFUSED`` at the sender door with
      nothing written but the receipt stub.  A redelivery is ``SKIPPED``.
    """

    # At the CASE_MANAGER only the Case Owner offers the case (CM-21-019);
    # a participant takes the Offer from the CASE_MANAGER alone
    # (PCR-03-001, ADR-0129).
    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_case_manager=any_of(SenderEntitlementKind.CASE_OWNER),
        at_participant=any_of(SenderEntitlementKind.CASE_MANAGER),
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: OfferCaseOwnershipTransferReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: OfferCaseOwnershipTransferReceivedEvent = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        # The received tree, run once (CLP-10-005).  Its addressee door
        # refuses a copy not addressed to this store (HP-01-005), and its
        # sender guard admits the Case Owner at the CASE_MANAGER and the
        # CASE_MANAGER elsewhere (CM-21-019, PCR-03-001).  An earlier Offer
        # past its end_time is closed by that time alone, so it does not
        # block this one (CM-21-014, CM-21-017).  The CASE_MANAGER-gated
        # MakeOwnershipTransferOfferNode makes, queues and ledgers the
        # CASE_MANAGER's Offer — no procedural outbox write here.
        tree = create_propose_ownership_transfer_tree(
            case_id=request.case_id,
            transferee_id=request.transferee_id,
            proposal_id=request.activity_id,
            answer_deadline=request.answer_deadline,
            sender_rule=self.sender_entitlement,
            sender_id=request.actor_id,
        )
        # A redelivery of an Owner's Offer the CASE_MANAGER already made its
        # Offer from is a repeat its guard reports, so the runner reads it
        # SKIPPED (HP-01-014, CM-21-014).  The transferee keeps the Offer,
        # which intake recorded, so what it did is what intake did.
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="OfferOwnershipTransferBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )


class AcceptCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER applies an accepted ownership transfer (CM-21-002).

    The sender must be the transferee named in an open ownership-transfer
    Offer the CASE_MANAGER recorded for the case (CM-21-011).  The Accept is
    addressed to the CASE_MANAGER alone, so the path stage refuses it at any
    other receiver (HP-01-005); a replica learns the new owner from the
    ledger (PCR-03-001, RSH-08-003).  Any other sender is
    ``REFUSED`` with ownership unchanged, nothing committed and nothing sent
    (HP-01-006).  An Accept of an Offer already closed is ``REFUSED`` the
    same way and answered with the refusal notice (CM-21-014, CLP-05-001).
    The new owner is read from the recorded Offer, never from the sender.
    A redelivery of the Accept that already closed the Offer changes nothing
    and is ``SKIPPED`` (HP-01-014).
    """

    # The transferee is the addressee of the Offer (ADR-0129), checked at the
    # CASE_MANAGER against the Offer it recorded; no other receiver acts on
    # the Accept (PCR-03-001, TRIG-11-002).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
        SenderEntitlementKind.NAMED_ACTOR
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptCaseOwnershipTransferReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
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

        tree = create_accept_ownership_transfer_tree(
            case_id=case_id,
            offer_id=request.object_id,
            sender_id=request.actor_id,
            answer_id=request.activity_id,
            sender_rule=self.sender_entitlement,
        )
        return run_offer_reply_tree(
            dl=self._dl,
            request=request,
            tree=tree,
            case_id=case_id,
            subject="ownership transfer offer",
            label="AcceptOwnershipTransferBT",
            sync_port=self._sync_port,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
        )


class RejectCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER ledgers a declined ownership transfer (CM-21-012).

    The sender rule is the Accept's (CM-21-013): at the CASE_MANAGER the
    sender must be the transferee named in an open ownership-transfer Offer
    it recorded for the case, and the path stage refuses the Reject at any
    other receiver (HP-01-005).  Any other sender is ``REFUSED`` with
    nothing committed and nothing sent, and the Offer stays open
    (HP-01-006).  A Reject of an Offer
    already closed is ``REFUSED`` the same way and answered with the refusal
    notice (CM-21-014, CLP-05-001).

    An admitted Reject commits a ``reject_case_ownership_transfer`` entry and
    broadcasts ``Add(CaseLedgerEntry)``, which closes the Offer on every
    replica (CM-21-014) and is how the offerer learns of the decline.
    Ownership is unchanged.  A redelivery of the Reject that already closed
    the Offer is ``SKIPPED`` (HP-01-014).
    """

    # The same transferee rule as the Accept (ADR-0129, TRIG-11-005).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
        SenderEntitlementKind.NAMED_ACTOR
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectCaseOwnershipTransferReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: RejectCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id

        tree = create_reject_ownership_transfer_tree(
            case_id=case_id,
            offer_id=request.object_id,
            sender_id=request.actor_id,
            answer_id=request.activity_id,
            sender_rule=self.sender_entitlement,
        )
        return run_offer_reply_tree(
            dl=self._dl,
            request=request,
            tree=tree,
            case_id=case_id,
            subject="ownership transfer offer",
            label="RejectOwnershipTransferBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
            applied_note="rejected (ownership unchanged)",
        )


class UndoCaseOwnershipTransferReceivedUseCase:
    """The CASE_MANAGER ledgers a withdrawn ownership-transfer Offer (CM-21-015).

    The Case Owner sends ``Undo`` of its own Offer; the CASE_MANAGER
    withdraws the Offer it made from it (CM-21-037, ADR-0199).  At the
    CASE_MANAGER the sender must be the Case Owner that Offer was made for,
    and the path stage refuses the Undo at any other receiver (HP-01-005).
    Anyone else, or a
    withdrawal of an Offer already answered or withdrawn, is ``REFUSED`` with
    nothing committed; the withdrawal of a closed Offer is answered with the
    refusal notice, anyone else with nothing (CLP-05-001, HP-01-006).

    An admitted Undo commits an ``undo_case_ownership_transfer`` entry and
    broadcasts ``Add(CaseLedgerEntry)``, which closes the Offer on every
    replica (CM-21-014): the transferee learns it can no longer accept, and
    the case may be offered again.  Ownership is unchanged.  A redelivery of
    the Undo that already closed the Offer is ``SKIPPED`` (HP-01-014).
    """

    # The offerer, which must still be the Case Owner (CM-21-015), checked at
    # the CASE_MANAGER against the Offer it recorded; no other receiver acts
    # on the Undo (PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: UndoCaseOwnershipTransferReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: UndoCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.case_id
        proposal_id = request.proposal_id

        def build(receiving_actor_id: str) -> py_trees.behaviour.Behaviour:
            # The Undo names the owner's own Offer; the CASE_MANAGER
            # withdraws the Offer it made from it, whose id it derives the
            # way it did when it made it (CM-21-037, ADR-0199).  At a replica the
            # derivation names no Offer it holds, but the path stage refuses
            # it there first, so nothing is read for it.
            offer_id = (
                ownership_offer_id(
                    receiving_actor_id,
                    case_id,
                    proposal_id,
                    request.proposer_id,
                )
                if case_id is not None and proposal_id is not None
                else None
            )
            return create_undo_ownership_transfer_tree(
                case_id=case_id,
                offer_id=offer_id,
                sender_id=request.actor_id,
                undo_id=request.activity_id,
                sender_rule=self.sender_entitlement,
            )

        return run_offer_reply_tree(
            dl=self._dl,
            request=request,
            tree=build,
            case_id=case_id,
            subject="ownership transfer offer",
            label="UndoOwnershipTransferBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
            applied_note="withdrew (ownership unchanged)",
        )
