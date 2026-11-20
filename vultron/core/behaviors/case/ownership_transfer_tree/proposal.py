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

"""The received tree of an ownership-transfer Offer (ADR-0199, ADR-0148).

One wire shape, two senders: the Case Owner's own ``Offer(VulnerabilityCase)``,
which the CASE_MANAGER judges and makes its own Offer from (CM-21-005,
CM-21-014, CM-21-019, CM-21-028), and that Offer at the transferee, which
intake records for it to answer.
"""

import logging
from datetime import datetime

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.held_case import (
    CaseNamedByReference,
)
from vultron.core.behaviors.case.nodes.ownership_offer_guard import (
    case_manager_admits_ownership_proposal_guard,
)
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    MakeOwnershipTransferOfferNode,
)
from vultron.core.behaviors.case.nodes.path_branch import OnPaths
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
    """The context an ownership-transfer Offer's sender is checked in.

    At the CASE_MANAGER the sender must be the Case Owner, unless it
    redelivers an Offer the CASE_MANAGER already made its own Offer from on
    the sender's behalf (*proposal_id*, HP-01-003, CM-21-019).  At the
    transferee the sender must be the case's CASE_MANAGER, and a store that
    holds no such case refuses (``case_manager_required``, PCR-03-001).  The
    received tree's sender guard reads it.
    """
    return SenderCheckContext(
        sender_id=sender_id,
        case_id=case_id,
        ownership_proposal_id=proposal_id,
        case_manager_required=True,
    )


def create_propose_ownership_transfer_tree(
    case_id: str | None,
    transferee_id: str | None,
    proposal_id: str,
    answer_deadline: datetime | None = None,
    *,
    sender_rule: SenderRule,
    sender_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``OfferCaseOwnershipTransferReceivedUseCase``.

    The Case Owner's Offer and the CASE_MANAGER's Offer made from it share
    one shape (ADR-0199), so one tree takes both, and the path the receiver
    is on tells them apart (HP-01-038)::

        Doors (the path stage admits the manager and participant paths)
            → sender guard (at the CASE_MANAGER the Case Owner, CM-21-019;
              at the transferee the CASE_MANAGER, PCR-03-001)
            → intake
            → OnPaths[CASE_MANAGER](NoOpenOwnershipOffer,
                                    OwnershipProposalAdmissible)
            → GuardedCommit (the Owner's Offer; CASE_MANAGER only)
            → CaseManagerGate[MakeOwnershipTransferOfferNode]

    - **At the CASE_MANAGER** the Offer is the Owner's proposal.  The guards
      refuse it while an earlier Offer for the case is open (CM-21-014), and
      when it names no transferee, or one that is the CASE_MANAGER, the
      Owner or not an active participant (CM-21-021, CM-21-026), so a
      refused Offer leaves no entry and makes no Offer.  An admitted one is
      committed as one entry; the effect then makes the CASE_MANAGER's own
      Offer, queues it and commits it as its own
      ``offer_case_ownership_transfer`` entry (CM-21-028, CM-21-029,
      SYNC-09-002).  An Owner's Offer the CASE_MANAGER already made its
      Offer from is a redelivery, ``SKIPPED`` (HP-01-014).
    - **At the transferee** the Offer is the CASE_MANAGER's.  Intake records
      it, which is the copy the transferee answers (CLP-10-017, DL-06-006);
      nothing is committed, since the CASE_MANAGER ledgered the Offer when
      it made it.

    The Offer names the case by reference (ADR-0165): a receiver that does
    not hold it is refused at the path stage (AKM-03-006).

    Args:
        case_id: URI of the case the Offer names as its ``object``;
            ``None`` for an Offer that names no case, which intake archives
            (CLP-10-018); nothing is committed or made.
        transferee_id: The Offer's ``target``, the proposed new owner.
        proposal_id: The received Offer's own id: at the CASE_MANAGER a
            redelivery is recognised by the Offer derived from it.
        answer_deadline: The Offer's ``end_time`` in UTC, if it carries one
            (CM-21-016); the Offer the CASE_MANAGER makes carries it
            (CM-21-041).
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (CM-21-019, HP-01-025).
        sender_id: The Offer's sender, which the guard checks
            (:func:`proposal_sender_context`).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    if case_id is None:
        # Intake records the Offer; there is no case to judge it against
        # (CLP-10-018).
        return create_incomplete_activity_received_tree(
            "OfferOwnershipTransferBT",
            "ownership-transfer Offer names no case",
        )
    guards = OnPaths.at_case_manager(
        "OwnershipProposalAdmissibleAtCaseManager",
        *case_manager_admits_ownership_proposal_guard(
            case_id=case_id,
            proposal_id=proposal_id,
            transferee_id=transferee_id,
            proposer_id=sender_id,
        ),
    )
    # The guards refuse an Offer naming no transferee before this runs, so
    # the effect is built only when there is an Offer to make.
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
        name="OfferOwnershipTransferBT",
        case_id=case_id,
        # The Offer names the case (ADR-0165): one the receiver does not
        # hold is refused at the path stage (AKM-03-006).
        held_case=CaseNamedByReference.OWNERSHIP_TRANSFER_OFFER,
        # The Case Owner sends its Offer to the CASE_MANAGER, which alone
        # adjudicates it and makes its own; the transferee takes that one on
        # its replica (CM-21-026, PCR-08-001, HP-01-038).
        paths={ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA},
        sender_rule=sender_rule,
        sender_context=proposal_sender_context(
            sender_id, case_id, proposal_id
        ),
        precondition_guards=[guards],
        manager_effects=effects,
        manager_case_id=case_id if effects else None,
        manager_gate_name=(
            "MakeOwnershipTransferOfferIfCaseManager" if effects else None
        ),
    )
    logger.debug(
        "Created OfferOwnershipTransferBT for case='%s' transferee='%s'"
        " sender='%s'",
        case_id,
        transferee_id,
        sender_id,
    )
    return tree
