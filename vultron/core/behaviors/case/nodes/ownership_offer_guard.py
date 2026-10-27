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

"""The CASE_MANAGER's guards on an ownership-transfer proposal (CM-21-005, CM-21-014).

Provides:

- :class:`OwnershipProposalAdmissibleNode` — precondition guard that refuses
  a proposal whose inner Offer names another case, no actor the
  CASE_MANAGER can address, or a transferee that is not an active
  participant (ADR-0148, CM-21-021).
- :class:`NoOpenOwnershipOfferNode` — precondition guard that refuses a new
  proposal while an earlier ownership-transfer Offer for the case is open.
- :func:`case_manager_admits_ownership_proposal_guard` — both behind the
  CASE_MANAGER gate, for the received proposal tree's
  ``precondition_guards``.

The guards on a reply to the Offer (:class:`OfferParty`,
:class:`OwnershipOfferOpenNode`, :class:`OwnershipTransfereeActiveNode`,
:func:`case_manager_ownership_offer_open_guard`) live in
:mod:`~vultron.core.behaviors.case.nodes.ownership_reply_guard` and are
re-exported here.
"""

from datetime import datetime

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.ownership_reply_guard import (
    OfferParty,
    OwnershipOfferOpenNode,
    OwnershipTransfereeActiveNode,
    case_manager_ownership_offer_open_guard,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.idempotency import FlaggedRepeatGuardMixin
from vultron.core.models._helpers import now_utc
from vultron.core.participants.ownership_offer import (
    offer_made_from_proposal,
    open_ownership_offer,
)
from vultron.core.participants.recipients import why_may_not_act_on_case
from vultron.core.predicates.addressing import same_actor_id


class OwnershipProposalAdmissibleNode(DataLayerConditionWithPorts):
    """Guard: the proposal's inner Offer is one the CASE_MANAGER can make.

    The CASE_MANAGER validates the inner Offer rather than copying it
    (ADR-0148): its object must be the case the proposal names, and its
    ``target`` an actor the CASE_MANAGER can address — present, and not the
    CASE_MANAGER itself, since a received tree emits nothing whose only
    recipient is the executing actor (BT-17-008, ADR-0109; CM-33-003 refuses
    the role offer on the same ground), nor the proposing owner, who already
    owns the case.  The transferee must also be an active participant whose
    closure is not recorded (CM-21-021, CM-10-004): the Offer carries the case
    inline, so only an actor entitled to its content may be offered it, and
    an owner that means to transfer to anyone else invites it first.  The
    test is :func:`~vultron.core.participants.recipients.may_act_on_case`,
    the one the transferee's Accept passes again (:class:`OwnershipTransfereeActiveNode`).
    Anything else in the inner
    Offer (its id, ``actor`` and ``to``) is the sender's and is never read,
    so the Offer the CASE_MANAGER makes carries its own id (CM-21-005).

    Read-only, so it runs in ``precondition_guards`` behind the CASE_MANAGER
    gate (:func:`case_manager_admits_ownership_proposal_guard`): a refused
    proposal leaves no entry and sends nothing.

    Spec: CM-21-005, CM-21-019, CM-21-021, BT-17-008.
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

    def _refuse(
        self, reason: str, spec: str = "CM-21-005, ADR-0148"
    ) -> Status:
        self.feedback_message = f"{reason} — REFUSED ({spec})"
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
                " the transferee; it sends itself no Offer (BT-17-008)"
            )
        if same_actor_id(transferee, self._proposer_id):
            return self._refuse(
                f"the inner Offer names the proposer '{transferee}', which"
                f" already owns case '{self._case_id}'"
            )
        assert self.datalayer is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: the gate found this store's case
        why = why_may_not_act_on_case(case, self.datalayer, transferee)
        if why is not None:
            return self._refuse(
                f"the transferee '{transferee}' {why}, so it may not be"
                f" offered case '{self._case_id}', which only an active"
                " participant is sent; the owner invites it first",
                "CM-21-021, CM-10-004",
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
    (CLP-11-001): an Offer stays open until the ledger holds an answer or a
    withdrawal recorded after it, or *now* reaches the ``end_time`` the
    ledgered Offer carries (CM-21-017).  Once it is closed, a new proposal
    is admitted for any transferee, including the one that declined.

    A **redelivery** of a proposal the CASE_MANAGER already made its Offer
    from is not a new proposal and not a refusal (HP-01-003), but it must
    change nothing: the Offer is ledgered only once it was queued
    (SYNC-09-002), so it was sent, and it may since have been answered.  The
    guard sets :attr:`is_redelivery` and fails, so nothing downstream runs,
    and the handler reports the run as ``SKIPPED``.  A proposal whose Offer
    the ledger does not hold is judged as new: a fault making the Offer keeps
    neither it nor the proposal's entry (CLP-07-015), so a redelivery runs the
    act afresh.

    Read-only, so it runs in ``precondition_guards`` behind the CASE_MANAGER
    gate (:func:`case_manager_admits_ownership_proposal_guard`).
    """

    _REPEAT_FLAG = "is_redelivery"

    def __init__(
        self,
        case_id: str,
        proposal_id: str,
        proposer_id: str,
        now: datetime | None = None,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the proposal names.
            proposal_id: The proposal's own id, so a redelivery is
                recognised.
            proposer_id: The proposal's sender.
            now: The instant an earlier Offer's ``end_time`` is compared
                against; ``None`` reads the clock when the guard runs.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.proposal_id = proposal_id
        self.proposer_id = proposer_id
        self._now = now
        self.is_redelivery = False
        """``True`` when the last run found the Offer made from this
        proposal already ledgered: a benign no-op, not a refusal."""

    def update(self) -> Status:
        self.is_redelivery = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        made = offer_made_from_proposal(
            self.datalayer, self.case_id, self.proposal_id, self.proposer_id
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
        earlier = open_ownership_offer(
            self.datalayer, self.case_id, self._now or now_utc()
        )
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
    now: datetime | None = None,
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
            NoOpenOwnershipOfferNode(
                case_id=case_id,
                proposal_id=proposal_id,
                proposer_id=proposer_id,
                now=now,
            ),
            OwnershipProposalAdmissibleNode(
                case_id=case_id,
                proposed_case_id=proposed_case_id,
                transferee_id=transferee_id,
                proposer_id=proposer_id,
            ),
        ],
    )


__all__ = [
    "NoOpenOwnershipOfferNode",
    "OfferParty",
    "OwnershipOfferOpenNode",
    "OwnershipProposalAdmissibleNode",
    "OwnershipTransfereeActiveNode",
    "case_manager_admits_ownership_proposal_guard",
    "case_manager_ownership_offer_open_guard",
]
