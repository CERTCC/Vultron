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

"""The CASE_MANAGER's guards for ownership transfer (CM-21-005, CM-21-014).

Provides:

- :class:`OwnershipProposalAdmissibleNode` — precondition guard that refuses
  a proposal whose inner Offer names another case or no actor the
  CASE_MANAGER can address (ADR-0148).
- :class:`NoOpenOwnershipOfferNode` — precondition guard that refuses a new
  proposal while an earlier ownership-transfer Offer for the case is open.
- :func:`case_manager_admits_ownership_proposal_guard` — both behind the
  CASE_MANAGER gate, for the received proposal tree's
  ``precondition_guards``.
- :class:`OwnershipOfferOpenNode` — precondition guard that refuses a reply
  to an ownership-transfer Offer that is no longer open, and recognises a
  redelivery of the reply that closed it.
- :func:`case_manager_ownership_offer_open_guard` — that guard behind the
  CASE_MANAGER gate, for the reply trees' ``precondition_guards``.
"""

from datetime import datetime

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.ownership_offer_expiry import (
    OfferParty,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.idempotency import FlaggedRepeatGuardMixin
from vultron.core.models._helpers import now_utc
from vultron.core.participants.ownership_offer import (
    RecordedOwnershipOffer,
    offer_made_from_proposal,
    open_ownership_offer,
    recorded_ownership_offer,
)
from vultron.core.predicates.addressing import same_actor_id
from vultron.errors import VultronBTInternalError, VultronNotFoundError


class OwnershipProposalAdmissibleNode(DataLayerConditionWithPorts):
    """Guard: the proposal's inner Offer is one the CASE_MANAGER can make.

    The CASE_MANAGER validates the inner Offer rather than copying it
    (ADR-0148): its object must be the case the proposal names, and its
    ``target`` an actor the CASE_MANAGER can address — present, and not the
    CASE_MANAGER itself, which sends itself no Offer (CM-21-019), nor the
    proposing owner, who already owns the case.  Anything else in the inner
    Offer (its id, ``actor`` and ``to``) is the sender's and is never read,
    so the Offer the CASE_MANAGER makes carries its own id (CM-21-005).

    Read-only, so it runs in ``precondition_guards`` behind the CASE_MANAGER
    gate (:func:`case_manager_admits_ownership_proposal_guard`): a refused
    proposal leaves no entry and sends nothing.

    Spec: CM-21-005, CM-21-019.
    """

    def __init__(
        self,
        case_id: str,
        proposed_case_id: str | None,
        transferee_id: str | None,
        proposer_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the proposal names (its ``context``).
            proposed_case_id: The case the inner Offer names as its object.
            transferee_id: The inner Offer's ``target``.
            proposer_id: The proposal's sender.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._proposed_case_id = proposed_case_id
        self._transferee_id = transferee_id
        self._proposer_id = proposer_id

    def _refuse(self, reason: str) -> Status:
        self.feedback_message = f"{reason} — REFUSED (CM-21-005, ADR-0148)"
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.actor_id is not None
        if self._proposed_case_id != self._case_id:
            return self._refuse(
                f"the inner Offer names case '{self._proposed_case_id}', not"
                f" the proposal's case '{self._case_id}'"
            )
        transferee = self._transferee_id
        if not transferee:
            return self._refuse("the inner Offer names no transferee")
        if same_actor_id(transferee, self.actor_id):
            return self._refuse(
                f"the inner Offer names the CASE_MANAGER '{transferee}' as"
                " the transferee; it sends itself no Offer (CM-21-019)"
            )
        if same_actor_id(transferee, self._proposer_id):
            return self._refuse(
                f"the inner Offer names the proposer '{transferee}', which"
                f" already owns case '{self._case_id}'"
            )
        return Status.SUCCESS


class NoOpenOwnershipOfferNode(
    FlaggedRepeatGuardMixin, DataLayerConditionWithPorts
):
    """Guard: the case has no earlier ownership-transfer Offer still open.

    The CASE_MANAGER refuses a new proposal while an earlier Offer for the
    case is open, because two pending Offers would let two transferees
    accept the same case (CM-21-014, CM-21-001).  "Open" is read from the
    case ledger through
    :func:`~vultron.core.participants.ownership_offer.open_ownership_offer`
    (CLP-11-001): an Offer stays open until the ledger holds an answer,
    withdrawal or expiry recorded after it.  Once it is closed, a new
    proposal is admitted for any transferee, including the one that
    declined.

    A **redelivery** of a proposal the CASE_MANAGER already made its Offer
    from is not a new proposal and not a refusal (HP-01-003), but it must
    change nothing: the Offer is ledgered only once it was queued
    (SYNC-09-002), so it was sent, and it may since have been answered.  The
    guard sets :attr:`is_redelivery` and fails, so nothing downstream runs,
    and the handler reports the run as ``SKIPPED``.  A proposal whose Offer
    the ledger does not hold is judged as new, so a redelivery after a fault
    between the proposal's entry and the Offer's send makes the Offer then,
    under the same derived id.

    Read-only, so it runs in ``precondition_guards`` behind the CASE_MANAGER
    gate (:func:`case_manager_admits_ownership_proposal_guard`).
    """

    _REPEAT_FLAG = "is_redelivery"

    def __init__(
        self, case_id: str, proposal_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.proposal_id = proposal_id
        self.is_redelivery = False
        """``True`` when the last run found the Offer made from this
        proposal already ledgered: a benign no-op, not a refusal."""

    def update(self) -> Status:
        self.is_redelivery = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        made = offer_made_from_proposal(
            self.datalayer, self.case_id, self.proposal_id
        )
        if made is not None:
            self.is_redelivery = True
            self.feedback_message = (
                f"ownership-transfer proposal '{self.proposal_id}' was"
                f" already made into Offer '{made.offer_id}' for case"
                f" '{self.case_id}' — redelivery, nothing to apply"
                " (HP-01-003)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        earlier = open_ownership_offer(self.datalayer, self.case_id)
        if earlier is None:
            return Status.SUCCESS
        self.feedback_message = (
            f"case '{self.case_id}' already has an open ownership-transfer"
            f" Offer '{earlier.offer_id}' to '{earlier.transferee_id}';"
            " it must be answered before the case is offered again"
            " — REFUSED (CM-21-014)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


def case_manager_admits_ownership_proposal_guard(
    case_id: str,
    proposal_id: str,
    proposed_case_id: str | None,
    transferee_id: str | None,
    proposer_id: str,
) -> py_trees.behaviour.Behaviour:
    """Precondition guards: at the CASE_MANAGER, the proposal is admissible.

    The open-Offer check runs first, so a redelivery is recognised as such
    before its inner Offer is judged again; then the inner Offer is checked
    (:class:`OwnershipProposalAdmissibleNode`).  A refused proposal is
    neither committed nor made into an Offer (CM-21-005, CM-21-014).  A
    replica never receives a proposal (its sender guard admits no one); it
    skips the guards as ``SUCCESS``.
    """
    return create_case_manager_gated_tree(
        name="OwnershipProposalAdmissibleIfCaseManager",
        case_id=case_id,
        body_name="OwnershipProposalAdmissible",
        children=[
            NoOpenOwnershipOfferNode(case_id=case_id, proposal_id=proposal_id),
            OwnershipProposalAdmissibleNode(
                case_id=case_id,
                proposed_case_id=proposed_case_id,
                transferee_id=transferee_id,
                proposer_id=proposer_id,
            ),
        ],
    )


#: The requirement a refusal of a reply to a closed Offer cites, per party.
_CLOSED_SPEC: dict[OfferParty, str] = {
    OfferParty.TRANSFEREE: "CM-21-011",
    OfferParty.OFFERER: "CM-21-015",
}

#: The requirements a refusal of a reply after the deadline cites, per party:
#: the deadline binds an answer (CM-21-016), and an expired Offer is closed
#: (CM-21-017), so it cannot be withdrawn (CM-21-015).
_LATE_SPEC: dict[OfferParty, str] = {
    OfferParty.TRANSFEREE: "CM-21-016",
    OfferParty.OFFERER: "CM-21-015, CM-21-017",
}


class OwnershipOfferOpenNode(
    FlaggedRepeatGuardMixin, DataLayerConditionWithPorts
):
    """Guard: the ownership-transfer Offer a reply names is still open.

    Runs right after the reply's sender check, which has established that
    the sender is the party to the Offer the reply needs
    (:class:`~vultron.core.behaviors.sender_entitlement.SenderIsOwnershipOfferPartyNode`),
    so only a sender with standing learns the Offer's state.  The Offer is
    read from this store's ledger (CLP-11-001).

    - A **redelivery** of the reply that already closed the Offer is not a
      refusal (HP-01-003), but it must change nothing: by then ownership may
      have moved on through a later Offer, and re-applying the old reply
      would hand it back with no ledger entry.  The guard sets
      :attr:`is_redelivery` and fails, so nothing downstream runs, and the
      handler reports the run as ``SKIPPED``.
    - A reply to an Offer an answer, withdrawal or expiry already closed is
      refused (CM-21-014).
    - A reply after the Offer's ``end_time`` is refused (CM-21-016).

    The deadline is read here as well as by the CASE_MANAGER's expiry, the
    clock decision that runs first in the same tree and ledgers it
    (:class:`~vultron.core.behaviors.case.nodes.ownership_offer_expiry.ExpireOverdueOwnershipOfferNode`,
    CLP-10-025): a reply after ``end_time`` is refused even when that record could not be
    committed, so the deadline binds whatever the ledger holds.  A replica
    never reads it: it learns an expiry only from the entry (CM-21-017), so
    the guard runs behind the CASE_MANAGER gate
    (:func:`case_manager_ownership_offer_open_guard`).

    Spec: CM-21-011, CM-21-013, CM-21-014, CM-21-015, CM-21-016, HP-01-003.
    """

    _REPEAT_FLAG = "is_redelivery"

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        reply_id: str,
        sender_id: str,
        party: OfferParty,
        now: datetime | None = None,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the reply names.
            offer_id: The Offer the reply names.
            reply_id: The reply's own id, so a redelivery is recognised.
            sender_id: The reply's sender, named in a refusal; the sender
                check has already established its standing.
            party: The party whose reply it is; it picks the requirements a
                refusal cites.
            now: The instant the deadline is compared against: the one the
                CASE_MANAGER's expiry step used.  ``None`` reads the clock
                when the guard runs.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._offer_id = offer_id
        self._reply_id = reply_id
        self._sender_id = sender_id
        self._party = party
        self._now = now
        self.is_redelivery = False
        """``True`` when the last run found the reply already ledgered as
        the one that closed the Offer: a benign no-op, not a refusal."""

    def _refuse(self, reason: str, spec: str) -> Status:
        self.feedback_message = f"{reason} — REFUSED ({spec})"
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _refuse_late(self, offer: RecordedOwnershipOffer) -> Status:
        deadline = (
            offer.end_time.isoformat() if offer.end_time is not None else "?"
        )
        return self._refuse(
            f"Ownership-transfer Offer '{offer.offer_id}' for case"
            f" '{self._case_id}' expired at its end_time {deadline}; reply"
            f" '{self._reply_id}' from '{self._sender_id}' came too late",
            _LATE_SPEC[self._party],
        )

    def _recorded_offer(self) -> RecordedOwnershipOffer:
        """The Offer the reply names, as the CASE_MANAGER recorded it.

        Raises:
            VultronNotFoundError: The reply names no Offer, or the
                CASE_MANAGER recorded no such Offer.
        """
        assert self.datalayer is not None
        if self._offer_id is None:
            raise VultronNotFoundError(
                "ownership-transfer Offer", f"None (case '{self._case_id}')"
            )
        return recorded_ownership_offer(
            self.datalayer, self._case_id, self._offer_id
        )

    def update(self) -> Status:
        """Check the Offer is open; see the class docstring.

        Raises:
            VultronBTInternalError: The Offer the sender check found is not
                recorded, a local anomaly rather than the sender's refusal.
        """
        self.is_redelivery = False
        if (f := self._require_datalayer()) is not None:
            return f
        _case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: the gate found this store's case
        try:
            offer = self._recorded_offer()
        except VultronNotFoundError as exc:
            # The sender check ran first and found this Offer, so its absence
            # now is a local anomaly, not the sender's refusal: raise, so the
            # bridge flags an internal error instead of a REFUSED verdict.
            raise VultronBTInternalError(
                f"{self.name}: the Offer the sender check found is gone"
                f" ({exc})"
            ) from exc
        if offer.answer_id == self._reply_id:
            self.is_redelivery = True
            self.feedback_message = (
                f"Reply '{self._reply_id}' already closed ownership-transfer"
                f" Offer '{offer.offer_id}' — redelivery, nothing to apply"
                " (HP-01-003)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if offer.is_answered_other_than(self._reply_id):
            if offer.closed_by_expiry:
                return self._refuse_late(offer)
            return self._refuse(
                f"Ownership-transfer Offer '{offer.offer_id}' for case"
                f" '{self._case_id}' was already closed by"
                f" '{offer.answer_id}' ({offer.closed_by_semantic_type})",
                f"{_CLOSED_SPEC[self._party]}, CM-21-014",
            )
        if offer.is_past_deadline(self._now or now_utc()):
            return self._refuse_late(offer)
        return Status.SUCCESS


def case_manager_ownership_offer_open_guard(
    case_id: str,
    offer_id: str | None,
    reply_id: str,
    sender_id: str,
    party: OfferParty,
    now: datetime | None = None,
) -> py_trees.behaviour.Behaviour:
    """Precondition guard: at the CASE_MANAGER, the replied-to Offer is open.

    A replica skips it as ``SUCCESS``: it takes the change from the
    CASE_MANAGER alone, which the sender check establishes (PCR-03-001),
    and learns an Offer's closing only from the ledger (CM-21-017).  A
    receiver that does not hold the case is not its CASE_MANAGER (ADR-0087
    Regime 3).
    """
    return create_case_manager_gated_tree(
        name="OwnershipOfferOpenIfCaseManager",
        case_id=case_id,
        body_name="OwnershipOfferOpen",
        children=[
            OwnershipOfferOpenNode(
                case_id=case_id,
                offer_id=offer_id,
                reply_id=reply_id,
                sender_id=sender_id,
                party=party,
                now=now,
            )
        ],
        case_may_be_absent=True,
    )
