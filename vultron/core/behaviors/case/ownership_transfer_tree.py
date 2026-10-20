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

"""Tree factories for ownership-transfer received activities (ADR-0148).

Provides:

- :func:`create_propose_ownership_transfer_tree` — BT for
  ``ProposeCaseOwnershipTransferReceivedUseCase``: the CASE_MANAGER admits
  the Case Owner's proposal only from the owner and only while no Offer for
  the case is open (CM-21-014, CM-21-019), ledgers it, and makes the one
  ``Offer(VulnerabilityCase)`` of the transfer through
  ``MakeOwnershipTransferOfferNode`` in ``manager_effects``, so the
  factory's CASE_MANAGER gate lets only the CASE_MANAGER make it (CM-21-005,
  BT-17-008).
- :func:`create_offer_ownership_transfer_tree` — BT for
  ``OfferCaseOwnershipTransferReceivedUseCase``: the transferee takes the
  CASE_MANAGER's Offer, which intake archives for it to answer; its sender
  guard admits the case's CASE_MANAGER alone, and nobody at the
  CASE_MANAGER (CM-21-019).
- :func:`create_accept_ownership_transfer_tree` — BT for
  ``AcceptCaseOwnershipTransferReceivedUseCase``.
- :func:`create_reject_ownership_transfer_tree` — BT for
  ``RejectCaseOwnershipTransferReceivedUseCase``: the Accept's tree with no
  effects, so the declined Offer is ledgered and closed (CM-21-012).
- :func:`create_undo_ownership_transfer_tree` — BT for
  ``UndoCaseOwnershipTransferReceivedUseCase``: the owner's withdrawal of
  its proposal, ledgered like the Reject so it closes the Offer made from
  it (CM-21-015).

The proposal and the three replies carry the CASE_MANAGER's lazy expiry of
the case's open Offer (CM-21-017) as a clock decision
(:class:`~vultron.core.behaviors.case.nodes.ownership_offer_expiry.ExpireOverdueOwnershipOfferNode`):
the factory runs it after the door guards and before the open-Offer guards,
at the CASE_MANAGER only, so an expired Offer is ledgered closed before the
activity is judged against it (CLP-10-025, ADR-0135).
"""

import logging
from datetime import datetime
from typing import NamedTuple

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.ownership_offer_expiry import (
    ExpireOverdueOwnershipOfferNode,
    ExpiryPrompt,
    OfferParty,
)
from vultron.core.behaviors.case.nodes.ownership_offer_guard import (
    case_manager_admits_ownership_proposal_guard,
    case_manager_ownership_offer_open_guard,
)
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    AcceptRecordedOwnershipOfferNode,
    MakeOwnershipTransferOfferNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    OwnershipOfferRequest,
    SenderCheckContext,
)

logger = logging.getLogger(__name__)


class _ReplyStages(NamedTuple):
    """What every reply to an Offer passes the received-tree factory."""

    sender_context: SenderCheckContext
    clock_decisions: list[py_trees.behaviour.Behaviour]
    precondition_guards: list[py_trees.behaviour.Behaviour]


def _reply_stages(
    case_id: str,
    offer_id: str | None,
    sender_id: str,
    reply_id: str,
    party: OfferParty,
    now: datetime | None,
) -> _ReplyStages:
    """The sender context, clock decision and guards of a reply to an Offer.

    The sender check reads the Offer the CASE_MANAGER recorded, so a sender
    that is not its party is refused first; at a replica the sender must be
    the CASE_MANAGER, and a case this store does not hold refuses
    (PCR-03-001).  The CASE_MANAGER then ledgers the expiry of the case's
    open Offer if its deadline passed, a clock decision the reply prompts
    only when it names the open Offer and comes from *party* (CM-21-017,
    HP-01-006, CLP-10-025).  The open-Offer check runs last, at the
    CASE_MANAGER only (CM-21-014, CM-21-016, HP-01-003), so a reply to an
    Offer that just expired is refused as closed.
    """
    context = SenderCheckContext(
        sender_id=sender_id,
        case_id=case_id,
        request=OwnershipOfferRequest(offer_id=offer_id, reply_id=reply_id),
        case_manager_required=True,
    )
    expiry = ExpireOverdueOwnershipOfferNode(
        case_id=case_id,
        now=now,
        prompt=ExpiryPrompt(
            sender_id=sender_id, offer_id=offer_id, party=party
        ),
    )
    guards = [
        case_manager_ownership_offer_open_guard(
            case_id=case_id,
            offer_id=offer_id,
            reply_id=reply_id,
            sender_id=sender_id,
            party=party,
            now=now,
        )
    ]
    return _ReplyStages(context, [expiry], guards)


def create_accept_ownership_transfer_tree(
    case_id: str | None,
    offer_id: str | None,
    sender_id: str,
    answer_id: str,
    now: datetime | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``AcceptCaseOwnershipTransferReceivedUseCase``.

    Uses the standard ``create_receive_activity_tree`` factory to enforce the
    CLP-10-006 ordering: the sender guard runs before anything is committed
    (CM-21-011, HP-01-006), and the guarded commit (CaseLedgerEntry +
    Announce broadcast) fires before ``AcceptRecordedOwnershipOfferNode``
    applies the change (CM-21-007) to the transferee the recorded Offer
    names, never to the sender.

    Args:
        case_id: URI of the case whose ownership is being transferred; ``None``
            builds the tree that archives the reply and refuses it
            (CLP-10-018).
        offer_id: The Offer the Accept names, the CASE_MANAGER's own.
        sender_id: The Accept's sender.  The sender guard checks it: at the
            CASE_MANAGER it must be the transferee of the Offer it recorded,
            which the open-Offer guard then requires to be open; at a
            replica it must be the CASE_MANAGER.
        answer_id: The Accept's own id, so a redelivery is recognised.
        now: The instant the Offer's ``end_time`` is compared against, by
            the expiry clock decision and the open-Offer guard alike; an
            Accept at or after it is refused (CM-21-016).  ``None`` reads the
            clock when each node runs.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    if case_id is None:
        # Intake archives the reply; there is no case to judge it
        # against (CLP-10-018).
        return create_incomplete_activity_received_tree(
            "AcceptOwnershipTransferBT",
            "Accept(ownership transfer) names no case",
        )
    stages = _reply_stages(
        case_id, offer_id, sender_id, answer_id, OfferParty.TRANSFEREE, now
    )
    tree = create_receive_activity_tree(
        name="AcceptOwnershipTransferBT",
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=stages.sender_context,
        clock_decisions=stages.clock_decisions,
        precondition_guards=stages.precondition_guards,
        # A receiver that does not hold the case is simply not its
        # CASE_MANAGER (ADR-0087 Regime 3), for both the guarded commit and
        # the gated effect: read the absence as "not the CASE_MANAGER" at
        # debug rather than a Regime-1 anomaly.
        case_may_be_absent=True,
        # RSH-08-003: the ownership change is canonical case state only the
        # CASE_MANAGER writes; it is committed and replayed from the ledger
        # (OwnershipTransfer slot), so a replica learns the new owner from the
        # fan-out, not from a direct Accept (#3814).
        manager_effects=[
            AcceptRecordedOwnershipOfferNode(
                case_id=case_id, offer_id=offer_id
            )
        ],
        manager_case_id=case_id,
        manager_gate_name="AcceptOwnershipTransferIfCaseManager",
        manager_case_may_be_absent=True,
    )
    logger.debug(
        "Created AcceptOwnershipTransferBT for case='%s' offer='%s'",
        case_id,
        offer_id,
    )
    return tree


def create_reject_ownership_transfer_tree(
    case_id: str | None,
    offer_id: str | None,
    sender_id: str,
    answer_id: str,
    now: datetime | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``RejectCaseOwnershipTransferReceivedUseCase``.

    The Accept's tree with no effects: the sender guard admits only the
    transferee of an open Offer the CASE_MANAGER recorded (CM-21-013), and the
    guarded commit ledgers the Reject and broadcasts
    ``Announce(CaseLedgerEntry)`` (CM-21-012, CLP-02-012).  That entry closes
    the Offer (CM-21-014); ownership is unchanged, so nothing else is written.

    Args:
        case_id: URI of the case the declined Offer would have transferred; ``None``
            builds the tree that archives the reply and refuses it
            (CLP-10-018).
        offer_id: The Offer the Reject names, the CASE_MANAGER's own.
        sender_id: The Reject's sender, checked as for the Accept.
        answer_id: The Reject's own id, so a redelivery is recognised.
        now: As for the Accept: a Reject after the deadline is refused.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    if case_id is None:
        # Intake archives the reply; there is no case to judge it
        # against (CLP-10-018).
        return create_incomplete_activity_received_tree(
            "RejectOwnershipTransferBT",
            "Reject(ownership transfer) names no case",
        )
    stages = _reply_stages(
        case_id, offer_id, sender_id, answer_id, OfferParty.TRANSFEREE, now
    )
    tree = create_receive_activity_tree(
        name="RejectOwnershipTransferBT",
        case_id=case_id,
        # The Accept's sender rule (CM-21-013) and open-Offer guard, so a
        # closed Offer refuses either answer and a redelivery is recognised.
        sender_rule=sender_rule,
        sender_context=stages.sender_context,
        clock_decisions=stages.clock_decisions,
        precondition_guards=stages.precondition_guards,
        # As for the Accept: a receiver not holding the case is not its
        # CASE_MANAGER (ADR-0087 Regime 3).
        case_may_be_absent=True,
    )
    logger.debug(
        "Created RejectOwnershipTransferBT for case='%s' offer='%s'",
        case_id,
        offer_id,
    )
    return tree


def create_undo_ownership_transfer_tree(
    case_id: str | None,
    offer_id: str | None,
    sender_id: str,
    undo_id: str,
    now: datetime | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``UndoCaseOwnershipTransferReceivedUseCase``.

    The owner withdraws its proposal, and with it the open Offer the
    CASE_MANAGER made from it (CM-21-015, ADR-0148).  The sender guard
    admits only the Case Owner that Offer was made for; the guarded commit
    ledgers the withdrawal and broadcasts ``Announce(CaseLedgerEntry)``.
    That entry closes the Offer (CM-21-014), so a later Accept or Reject of
    it is refused and the case may be offered again.  Ownership is
    unchanged.

    Args:
        case_id: URI of the case the withdrawn Offer would have transferred; ``None``
            builds the tree that archives the reply and refuses it
            (CLP-10-018).
        offer_id: The Offer the CASE_MANAGER made from the proposal the Undo
            names
            (:func:`~vultron.core.participants.ownership_offer.ownership_offer_id`).
        sender_id: The Undo's sender: at the CASE_MANAGER it must be the
            offerer, still the Case Owner; at a replica, the CASE_MANAGER.
        undo_id: The Undo's own id, so a redelivery is recognised.
        now: As for the Accept: an expired Offer cannot be withdrawn.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    if case_id is None:
        # Intake archives the reply; there is no case to judge it
        # against (CLP-10-018).
        return create_incomplete_activity_received_tree(
            "UndoOwnershipTransferBT", "Undo(ownership transfer) names no case"
        )
    stages = _reply_stages(
        case_id, offer_id, sender_id, undo_id, OfferParty.OFFERER, now
    )
    tree = create_receive_activity_tree(
        name="UndoOwnershipTransferBT",
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=stages.sender_context,
        clock_decisions=stages.clock_decisions,
        precondition_guards=stages.precondition_guards,
        # As for the Reject: no effect follows the commit, and a receiver
        # not holding the case is not its CASE_MANAGER (ADR-0087 Regime 3).
        case_may_be_absent=True,
    )
    logger.debug(
        "Created UndoOwnershipTransferBT for case='%s' offer='%s'",
        case_id,
        offer_id,
    )
    return tree


def proposal_sender_context(
    sender_id: str, case_id: str, proposal_id: str | None
) -> SenderCheckContext:
    """The context an ownership-transfer proposal's sender is checked in.

    At the CASE_MANAGER the sender must be the Case Owner, unless it
    redelivers a proposal the CASE_MANAGER already made its Offer from on
    the sender's behalf (*proposal_id*, HP-01-003, CM-21-019).  The received
    tree's sender guard reads it.
    """
    return SenderCheckContext(
        sender_id=sender_id,
        case_id=case_id,
        ownership_proposal_id=proposal_id,
        case_manager_required=True,
    )


def create_propose_ownership_transfer_tree(
    case_id: str | None,
    proposed_case_id: str | None,
    transferee_id: str | None,
    proposal_id: str,
    answer_deadline: datetime | None = None,
    now: datetime | None = None,
    *,
    sender_rule: SenderRule,
    sender_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``ProposeCaseOwnershipTransferReceivedUseCase``.

    The CASE_MANAGER executes the owner's proposal (ADR-0148)::

        Intake → doors → sender guard (the Case Owner, CM-21-019)
            → expiry clock decision (CM-21-017)
            → CaseManagerGate[NoOpenOwnershipOffer, OwnershipProposalAdmissible]
            → GuardedCommit (the proposal)
            → CaseManagerGate[MakeOwnershipTransferOfferNode]

    The guards refuse a proposal while an earlier Offer for the case is
    open (CM-21-014), and one whose inner Offer names another case or no
    actor the CASE_MANAGER can address, so a refused proposal leaves no
    entry and makes no Offer.  The effect makes the Offer, queues it and
    commits it as the ``offer_case_ownership_transfer`` entry (SYNC-09-002).
    An Offer already made from this proposal is a redelivery, ``SKIPPED``
    (HP-01-003).

    Args:
        case_id: URI of the case the proposal names (its ``context``);
            ``None`` for a proposal that names no case, which intake
            archives (CLP-10-018); nothing is committed or made.
        proposed_case_id: The case the inner Offer names as its object; it
            must be *case_id*.
        transferee_id: The inner Offer's ``target``, the proposed new owner.
        proposal_id: The proposal's own id: a redelivery is recognised by
            the Offer derived from it.
        answer_deadline: The inner Offer's ``end_time`` in UTC, if it
            carries one (CM-21-016); the Offer the CASE_MANAGER makes
            carries it.
        now: The instant the case's open Offer's ``end_time`` is compared
            against by the expiry clock decision: a new proposal is one of
            the moments the CASE_MANAGER checks it, so an expired Offer is
            closed before this proposal is judged against it (CM-21-017,
            CM-21-014, CLP-10-025).  ``None`` reads the clock when it runs.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (CM-21-019, HP-01-008).
        sender_id: The proposal's sender, which the guard checks
            (:func:`proposal_sender_context`).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    if case_id is None:
        # Intake archives the proposal; there is no case to judge it
        # against (CLP-10-018).
        return create_incomplete_activity_received_tree(
            "ProposeOwnershipTransferBT",
            "ownership-transfer proposal names no case",
        )
    guards = [
        case_manager_admits_ownership_proposal_guard(
            case_id=case_id,
            proposal_id=proposal_id,
            proposed_case_id=proposed_case_id,
            transferee_id=transferee_id,
            proposer_id=sender_id,
        )
    ]
    # The guards refuse a proposal naming no transferee before this runs,
    # so the effect is built only when there is an Offer to make.
    effects: list[py_trees.behaviour.Behaviour] = (
        [
            MakeOwnershipTransferOfferNode(
                case_id=case_id,
                transferee_id=transferee_id,
                owner_id=sender_id,
                proposal_id=proposal_id,
                end_time=answer_deadline,
            )
        ]
        if transferee_id
        else []
    )
    tree = create_receive_activity_tree(
        name="ProposeOwnershipTransferBT",
        case_id=case_id,
        clock_decisions=[
            ExpireOverdueOwnershipOfferNode(case_id=case_id, now=now)
        ],
        sender_rule=sender_rule,
        sender_context=proposal_sender_context(
            sender_id, case_id, proposal_id
        ),
        precondition_guards=guards,
        manager_effects=effects,
        manager_case_id=case_id if effects else None,
        manager_gate_name=(
            "MakeOwnershipTransferOfferIfCaseManager" if effects else None
        ),
    )
    logger.debug(
        "Created ProposeOwnershipTransferBT for case='%s' transferee='%s'"
        " owner='%s'",
        case_id,
        transferee_id,
        sender_id,
    )
    return tree


def create_offer_ownership_transfer_tree(
    case_id: str | None,
    *,
    sender_rule: SenderRule,
    sender_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``OfferCaseOwnershipTransferReceivedUseCase``.

    The transferee receives the one ``Offer(VulnerabilityCase)`` of the
    transfer, which the CASE_MANAGER made from the owner's proposal
    (ADR-0148).  Intake archives it, which is the copy the transferee
    answers (CLP-10-017); its sender guard admits the case's CASE_MANAGER
    alone, and a store that holds no such case refuses (CM-21-019,
    PCR-03-001).  At the CASE_MANAGER the rule admits nobody: an owner
    proposes, it does not offer.  Nothing is committed: the CASE_MANAGER
    ledgered the Offer when it made it.

    Args:
        case_id: URI of the case whose ownership is offered; ``None`` for an
            Offer that names no case, which intake archives (CLP-10-018).
        sender_rule: The use case's declared sender rule (HP-01-008).
        sender_id: The Offer's sender, which the guard checks.

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    if case_id is None:
        return create_incomplete_activity_received_tree(
            "OfferOwnershipTransferBT",
            "Offer(ownership transfer) names no case",
        )
    tree = create_receive_activity_tree(
        name="OfferOwnershipTransferBT",
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id, case_manager_required=True
        ),
        precondition_guards=[],
    )
    logger.debug(
        "Created OfferOwnershipTransferBT for case='%s' sender='%s'",
        case_id,
        sender_id,
    )
    return tree
