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

"""Tree factories for the replies to an ownership-transfer Offer (ADR-0148).

The transferee's ``Accept`` or ``Reject`` of the CASE_MANAGER's
``Offer(VulnerabilityCase)`` (CM-21-012) and the Case Owner's ``Undo`` of the
proposal it was made from (CM-21-015).  Each judges the Offer against its own
``end_time`` at the CASE_MANAGER only (CM-21-014, CM-21-016, ADR-0152).
"""

import logging
from typing import NamedTuple

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
)
from vultron.core.behaviors.case.nodes.ownership_reply_guard import (
    OfferParty,
    case_manager_ownership_offer_open_guard,
)
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    AcceptRecordedOwnershipOfferNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
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
    precondition_guards: list[py_trees.behaviour.Behaviour]


def _reply_stages(
    case_id: str,
    offer_id: str | None,
    sender_id: str,
    reply_id: str,
    party: OfferParty,
    *,
    transferee_must_be_active: bool = False,
) -> _ReplyStages:
    """The sender context and guards of a reply to an Offer.

    The sender check reads the Offer the CASE_MANAGER recorded, so a sender
    that is not its party is refused first.  The reply trees run at the
    CASE_MANAGER alone: the path stage refuses a replica, and a receiver
    that does not hold the case, before the sender check (HP-01-005).  The
    open-Offer check runs next (CM-21-014, CM-21-016, HP-01-003): a reply
    to an Offer past its ``end_time`` is refused from that time alone, and
    nothing records the expiry (CM-21-043, ADR-0152).  With *transferee_must_be_active* (the
    Accept), the transferee must then still be an active participant
    (CM-21-022).
    """
    context = SenderCheckContext(
        sender_id=sender_id,
        case_id=case_id,
        request=OwnershipOfferRequest(offer_id=offer_id, reply_id=reply_id),
    )
    guards: list[py_trees.behaviour.Behaviour] = [
        case_manager_ownership_offer_open_guard(
            case_id=case_id,
            offer_id=offer_id,
            reply_id=reply_id,
            sender_id=sender_id,
            party=party,
            transferee_must_be_active=transferee_must_be_active,
        )
    ]
    return _ReplyStages(context, guards)


def create_accept_ownership_transfer_tree(
    case_id: str | None,
    offer_id: str | None,
    sender_id: str,
    answer_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``AcceptCaseOwnershipTransferReceivedUseCase``.

    Uses the standard ``create_receive_activity_tree`` factory to enforce the
    CLP-10-006 ordering: the sender guard runs before anything is committed
    (CM-21-011, HP-01-006), and the guarded commit (CaseLedgerEntry +
    Announce broadcast) fires before ``AcceptRecordedOwnershipOfferNode``
    applies the change (CM-21-007) to the transferee the recorded Offer
    names, never to the sender.  A transferee that is no longer an active
    participant is refused before the commit (CM-21-022).

    Args:
        case_id: URI of the case whose ownership is being transferred; ``None``
            builds the tree that archives the reply and refuses it
            (CLP-10-018).
        offer_id: The Offer the Accept names, the CASE_MANAGER's own.
        sender_id: The Accept's sender.  The sender guard checks it: at the
            CASE_MANAGER it must be the transferee of the Offer it recorded,
            which the open-Offer guard then requires to be open.
        answer_id: The Accept's own id, so a redelivery is recognised.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    if case_id is None:
        # Intake records the reply; there is no case to judge it
        # against (CLP-10-018).
        return create_incomplete_activity_received_tree(
            "AcceptOwnershipTransferBT",
            "Accept(ownership transfer) names no case",
        )
    stages = _reply_stages(
        case_id,
        offer_id,
        sender_id,
        answer_id,
        OfferParty.TRANSFEREE,
        transferee_must_be_active=True,
    )
    tree = create_receive_activity_tree(
        name="AcceptOwnershipTransferBT",
        case_id=case_id,
        # The transferee answers the CASE_MANAGER alone, which adjudicates
        # the answer (CM-21-013, TRIG-11-002/005); a participant replica takes
        # the ownership change from the ledger (RSH-08-003), so the path
        # stage refuses a copy there (HP-01-005, HP-01-038).
        paths={ReceivedPath.CASE_MANAGER},
        sender_rule=sender_rule,
        sender_context=stages.sender_context,
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
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``RejectCaseOwnershipTransferReceivedUseCase``.

    The Accept's tree with no effects: the sender guard admits only the
    transferee of an open Offer the CASE_MANAGER recorded (CM-21-013), and the
    guarded commit ledgers the Reject and broadcasts
    ``Announce(CaseLedgerEntry)`` (CM-21-032, CLP-02-016).  That entry closes
    the Offer (CM-21-014); ownership is unchanged, so nothing else is written.

    Args:
        case_id: URI of the case the declined Offer would have transferred; ``None``
            builds the tree that archives the reply and refuses it
            (CLP-10-018).
        offer_id: The Offer the Reject names, the CASE_MANAGER's own.
        sender_id: The Reject's sender, checked as for the Accept.
        answer_id: The Reject's own id, so a redelivery is recognised.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    if case_id is None:
        # Intake records the reply; there is no case to judge it
        # against (CLP-10-018).
        return create_incomplete_activity_received_tree(
            "RejectOwnershipTransferBT",
            "Reject(ownership transfer) names no case",
        )
    stages = _reply_stages(
        case_id, offer_id, sender_id, answer_id, OfferParty.TRANSFEREE
    )
    tree = create_receive_activity_tree(
        name="RejectOwnershipTransferBT",
        case_id=case_id,
        # The transferee answers the CASE_MANAGER alone, which adjudicates
        # the answer (CM-21-013, TRIG-11-002/005); a participant replica takes
        # the ownership change from the ledger (RSH-08-003), so the path
        # stage refuses a copy there (HP-01-005, HP-01-038).
        paths={ReceivedPath.CASE_MANAGER},
        # The Accept's sender rule (CM-21-013) and open-Offer guard, so a
        # closed Offer refuses either answer and a redelivery is recognised.
        sender_rule=sender_rule,
        sender_context=stages.sender_context,
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
            offerer, still the Case Owner.
        undo_id: The Undo's own id, so a redelivery is recognised.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    if case_id is None:
        # Intake records the reply; there is no case to judge it
        # against (CLP-10-018).
        return create_incomplete_activity_received_tree(
            "UndoOwnershipTransferBT", "Undo(ownership transfer) names no case"
        )
    stages = _reply_stages(
        case_id, offer_id, sender_id, undo_id, OfferParty.OFFERER
    )
    tree = create_receive_activity_tree(
        name="UndoOwnershipTransferBT",
        case_id=case_id,
        # The Case Owner withdraws to the CASE_MANAGER alone, which
        # adjudicates the withdrawal (CM-21-015); a participant replica takes
        # the change from the ledger (RSH-08-003), so the path stage refuses
        # a copy there (HP-01-005, HP-01-038).
        paths={ReceivedPath.CASE_MANAGER},
        sender_rule=sender_rule,
        sender_context=stages.sender_context,
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
