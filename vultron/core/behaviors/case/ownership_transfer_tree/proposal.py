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

"""Tree factories for an ownership-transfer proposal and its Offer (ADR-0148).

The CASE_MANAGER's receipt of the Case Owner's proposal, from which it makes
the one ``Offer(VulnerabilityCase)`` of the transfer (CM-21-005, CM-21-014,
CM-21-019), and the transferee's receipt of that Offer.
"""

import logging
from datetime import datetime

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.ownership_offer_guard import (
    case_manager_admits_ownership_proposal_guard,
)
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    MakeOwnershipTransferOfferNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    SenderCheckContext,
)

logger = logging.getLogger(__name__)


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

        Intake → doors (the path stage admits the manager path alone)
            → sender guard (the Case Owner, CM-21-019)
            → NoOpenOwnershipOffer → OwnershipProposalAdmissible
            → GuardedCommit (the proposal)
            → CaseManagerGate[MakeOwnershipTransferOfferNode]

    The guards refuse a proposal while an earlier Offer for the case is
    open (CM-21-014), and one whose inner Offer names another case, no
    actor the CASE_MANAGER can address, or a transferee that is not an
    active participant (CM-21-021), so a refused proposal leaves no entry
    and makes no Offer.  The effect makes the Offer, queues it and
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
        now: The instant the case's earlier Offer's ``end_time`` is
            compared against by the open-Offer guard: an Offer past its
            deadline is closed, so it does not block this proposal
            (CM-21-014, CM-21-017).  ``None`` reads the clock when the guard
            runs.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (CM-21-019, HP-01-025).
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
    guards = case_manager_admits_ownership_proposal_guard(
        case_id=case_id,
        proposal_id=proposal_id,
        proposed_case_id=proposed_case_id,
        transferee_id=transferee_id,
        proposer_id=sender_id,
        now=now,
    )
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
        # The Case Owner proposes to the CASE_MANAGER, which alone
        # adjudicates the proposal and makes the Offer; no other receiver
        # is addressed, and the rule admits no sender there (CM-21-026,
        # PCR-08-001, HP-01-038).
        paths={ReceivedPath.CASE_MANAGER},
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
    alone, and a store that holds no such case refuses (CM-21-046,
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
        # The Offer is the CASE_MANAGER's, made to the transferee's own
        # replica; the CASE_MANAGER records it in the tree that emits it and
        # never receives one (CM-21-013, HP-01-038).
        paths={ReceivedPath.PARTICIPANT_REPLICA},
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
