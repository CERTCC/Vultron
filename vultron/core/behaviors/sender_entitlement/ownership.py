#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""The parties to a recorded ownership-transfer Offer (CM-21-011,
CM-21-013, CM-21-015, CM-21-019).
"""

from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.sender_entitlement.addressee import (
    NoStandingError,
    RecordedRequest,
    SenderIsRequestAddresseeNode,
    _case_and_manager,
    _refuse_if_closed,
)
from vultron.core.behaviors.sender_entitlement.base import (
    SenderEntitlementConditionNode,
)
from vultron.core.behaviors.sender_entitlement.case_owner import (
    _holds_case_owner_role,
)
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.authority import (
    resolve_case_manager_id,
)
from vultron.core.participants.ownership_offer import (
    RecordedOwnershipOffer,
    offer_made_from_proposal,
    recorded_ownership_offer,
)
from vultron.core.predicates.addressing import (
    same_actor_id,
)
from vultron.errors import VultronNotFoundError

# ---------------------------------------------------------------------------
# Condition nodes: the parties to a recorded ownership-transfer Offer
# ---------------------------------------------------------------------------


class SenderIsOwnershipOfferPartyNode(SenderIsRequestAddresseeNode):
    """Guard: sender is the party to a recorded ownership-transfer Offer that
    its reply needs.

    Shared by the transferee's answer (:class:`SenderIsOwnershipTransfereeNode`)
    and the offerer's withdrawal (:class:`SenderIsOwnershipOffererNode`).  The
    receive-tree factory composes it on the CASE_MANAGER's side of the
    declared rule; a replica takes the ownership change from the CASE_MANAGER
    alone, which the rule's participant side checks (PCR-03-001).

    It checks standing only: the sender is the party the subclass names to an
    ownership-transfer Offer the CASE_MANAGER recorded for the case.  The
    Offer is read from this store's ledger, never from the copy the reply
    embeds, which the sender wrote.  Whether the Offer is still open, and
    whether the reply is a redelivery of the one that closed it, is the
    precondition guard that runs right after the sender check
    (:class:`~vultron.core.behaviors.case.nodes.ownership_reply_guard.OwnershipOfferOpenNode`),
    so a sender with no standing is refused before any offer-state check.

    A case this store does not hold, or one that names no CASE_MANAGER,
    leaves nothing to establish the sender's standing against, so the sender
    is refused.

    Spec: CM-21-011, CM-21-013, CM-21-015, PCR-03-001, HP-01-006.
    """

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the reply names.
            offer_id: The Offer the reply names (``None`` when it names
                none, which refuses).
            sender_actor_id: The reply's sender.
            name: Optional node name.
        """
        super().__init__(sender_actor_id=sender_actor_id, name=name)
        self._case_id = case_id
        self._offer_id = offer_id
        self._case: VulnerabilityCase | None = None
        """The case :meth:`_recorded_offer` last read."""
        self._offer: RecordedOwnershipOffer | None = None
        """The Offer :meth:`_recorded_offer` last read."""

    def _recorded_offer(
        self,
    ) -> tuple[str, RecordedOwnershipOffer]:
        """The case's CASE_MANAGER and the Offer the reply names.

        Raises:
            NoStandingError: This store holds no such case, the case names no
                CASE_MANAGER, or the CASE_MANAGER recorded no such Offer.
        """
        assert self.datalayer is not None
        sender = self.sender_actor_id
        case, manager_id = _case_and_manager(
            self.datalayer, self._case_id, sender
        )
        if self._offer_id is None:
            raise NoStandingError(
                f"Sender '{sender}' names no ownership-transfer Offer"
            )
        try:
            offer = recorded_ownership_offer(
                self.datalayer, self._case_id, self._offer_id
            )
        except VultronNotFoundError as exc:
            raise NoStandingError(
                f"Sender '{sender}' names Offer '{self._offer_id}', which"
                f" this CASE_MANAGER never recorded for case"
                f" '{self._case_id}' ({exc})"
            ) from exc
        self._case = case
        self._offer = offer
        return manager_id, offer


class SenderIsOwnershipTransfereeNode(SenderIsOwnershipOfferPartyNode):
    """Guard: sender is the transferee of the ownership-transfer Offer it
    answers.

    The transferee is the addressee of the request, so the kind is
    ``NAMED_ACTOR`` (ADR-0129); see :class:`SenderIsOwnershipOfferPartyNode`.

    A transferee whose closure the case records is refused: it has left the
    case (CM-23-018).

    Spec: CM-21-011, CM-21-013, CM-23-018, HP-01-006.
    """

    _spec = "CM-21-011"

    def _recorded_request(self) -> RecordedRequest:
        _manager_id, offer = self._recorded_offer()
        return RecordedRequest(
            description=f"ownership-transfer Offer '{offer.offer_id}'",
            position="the transferee",
            addressees=(offer.transferee_id,),
        )

    def _confirm_standing(self, request: RecordedRequest) -> None:
        """Refuse a transferee whose closure the case records (CM-23-018).

        Raises:
            NoStandingError: The transferee has left the case (RM ``CLOSED``).
        """
        assert self.datalayer is not None and self._case is not None
        _refuse_if_closed(
            self.datalayer, self._case, self.sender_actor_id, "Transferee"
        )


class SenderIsOwnershipOffererNode(SenderIsOwnershipOfferPartyNode):
    """Guard: sender is the Case Owner that made the ownership-transfer Offer
    it withdraws.

    The offerer is the participant the recorded Offer speaks for — its
    ``attributedTo`` only when the CASE_MANAGER sent it on that participant's
    behalf, else its ``actor`` (CM-24-002).  The kind is ``CASE_OWNER``,
    checked against the recorded Offer; see
    :class:`SenderIsOwnershipOfferPartyNode`.

    The offerer must also hold ``CVDRole.CASE_OWNER`` now (CM-21-015): that is
    standing too, so it is checked here, before the Offer's state.  An
    offerer whose Offer an Accept closed no longer holds it, and is refused
    for that.

    A redelivery of the withdrawal the CASE_MANAGER already ledgered as
    closing the Offer is a duplicate, not a new withdrawal: its standing was
    established when it was admitted, and ownership may since have moved on
    through a later Offer.  The role is not re-checked for it, so the
    open-Offer guard reports it ``SKIPPED`` (HP-01-014).

    Spec: CM-21-015, PCR-03-001, HP-01-003, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.CASE_OWNER
    )
    _spec = "CM-21-015"

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        sender_actor_id: str,
        reply_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the Undo names.
            offer_id: The Offer the Undo names (``None`` refuses).
            sender_actor_id: The Undo's sender.
            reply_id: The Undo's own id, so a redelivery of the withdrawal
                that closed the Offer is recognised.
            name: Optional node name.
        """
        super().__init__(
            case_id=case_id,
            offer_id=offer_id,
            sender_actor_id=sender_actor_id,
            name=name,
        )
        self._reply_id = reply_id

    def _recorded_request(self) -> RecordedRequest:
        manager_id, offer = self._recorded_offer()
        offerer_id = offer.offerer_id(manager_id)
        return RecordedRequest(
            description=f"ownership-transfer Offer '{offer.offer_id}'",
            position="the offerer",
            addressees=(offerer_id,) if offerer_id is not None else (),
        )

    def _confirm_standing(self, request: RecordedRequest) -> None:
        assert self.datalayer is not None and self._case is not None
        assert self._offer is not None
        if self._offer.answer_id == self._reply_id:
            return  # the admitted withdrawal, redelivered (HP-01-014)
        sender = self.sender_actor_id
        if not _holds_case_owner_role(self.datalayer, self._case, sender):
            raise NoStandingError(
                f"Sender '{sender}' made {request.description} but does not"
                f" hold CASE_OWNER on case '{self._case_id}'"
            )


class SenderIsOfferingCaseOwnerNode(SenderEntitlementConditionNode):
    """Guard: the sender of an ownership-transfer proposal is the Case Owner.

    At the CASE_MANAGER only the actor holding ``CVDRole.CASE_OWNER`` on the
    case may propose to offer it (CM-21-019); the kind is ``CASE_OWNER``.  It
    runs on the CASE_MANAGER's side of the rule, which holds the case
    (Regime 1).

    A redelivery of a proposal the CASE_MANAGER already made its Offer from,
    on this sender's behalf, is a duplicate, not a new proposal: its standing
    was established when it was admitted, and the sender may since have
    handed ownership on, so the role is not re-checked and the open-Offer
    guard reports it ``SKIPPED`` (HP-01-014).  The same proposal id from any
    other sender is judged as a new proposal: the Offer id is derived from
    the proposer too
    (:func:`~vultron.core.participants.ownership_offer.ownership_offer_id`).

    Spec: CM-21-019, HP-01-003, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        case_id: str,
        proposal_id: str,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the proposal names.
            proposal_id: The proposal's own id, so a redelivery is
                recognised.
            sender_actor_id: The proposal's sender.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._proposal_id = proposal_id
        self._sender_actor_id = sender_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        sender = self._sender_actor_id
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        if _holds_case_owner_role(self.datalayer, case, sender):
            return Status.SUCCESS
        made = offer_made_from_proposal(
            self.datalayer, self._case_id, self._proposal_id, sender
        )
        manager_id = resolve_case_manager_id(case, self.datalayer)
        offerer = (
            made.offerer_id(manager_id)
            if made is not None and manager_id is not None
            else None
        )
        if offerer is not None and same_actor_id(offerer, sender):
            self.logger.debug(
                "%s: proposal '%s' was made into Offer '%s' for '%s'"
                " — redelivery (HP-01-014)",
                self.name,
                self._proposal_id,
                made.offer_id if made is not None else None,
                sender,
            )
            return Status.SUCCESS
        return self._refuse_citing(
            f"Sender '{sender}' is not the Case Owner of case"
            f" '{self._case_id}', so it may not propose to offer its"
            " ownership"
        )

    def _refuse_citing(self, reason: str) -> Status:
        """Append this check's citation to *reason*, then refuse by placement.

        One ``_refuse_citing`` per citation across the family, never a
        ``_refuse``: see
        :meth:`SenderEntitlementConditionNode._refuse_by_placement`.
        """
        return self._refuse_by_placement(
            f"{reason} — REFUSED (CM-21-019, HP-01-006)"
        )
