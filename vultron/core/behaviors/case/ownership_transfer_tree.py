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

"""Tree factories for ownership-transfer received activities.

Provides:

- :func:`create_accept_ownership_transfer_tree` — BT for
  ``AcceptCaseOwnershipTransferReceivedUseCase``.
- :func:`create_reject_ownership_transfer_tree` — BT for
  ``RejectCaseOwnershipTransferReceivedUseCase``: the Accept's tree with no
  effects, so the declined Offer is ledgered and closed (CM-21-012).
- :func:`create_undo_ownership_transfer_tree` — BT for
  ``UndoCaseOwnershipTransferReceivedUseCase``: the offerer's withdrawal,
  ledgered like the Reject so it closes the Offer (CM-21-015).
- :func:`create_offer_ownership_transfer_tree` — BT for
  ``OfferCaseOwnershipTransferReceivedUseCase``; passes
  ``ForwardOfferToTransfereeNode`` as ``manager_effects`` so the factory's
  CASE_MANAGER gate lets only the CaseActor forward the offer (CM-21-005,
  ADR-0053, BT-17-008), and refuses the Offer at the CASE_MANAGER while an
  earlier one for the case is open (CM-21-014).  Its sender guard is
  composed from the use case's declared rule: the Case Owner at the
  CASE_MANAGER, the CASE_MANAGER at the transferee (CM-21-019).
"""

import logging
from datetime import datetime

import py_trees

from vultron.core.behaviors.case.nodes.ownership_offer_expiry import (
    OfferParty,
)
from vultron.core.behaviors.case.nodes.ownership_offer_guard import (
    case_manager_admits_ownership_offer_guard,
    case_manager_ownership_offer_open_guard,
)
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    AcceptRecordedOwnershipOfferNode,
    ForwardOfferToTransfereeNode,
)
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
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


def _reply_guards(
    case_id: str,
    offer_id: str | None,
    sender_id: str,
    reply_id: str,
    party: OfferParty,
    now: datetime | None,
) -> tuple[SenderCheckContext, list[py_trees.behaviour.Behaviour]]:
    """The sender context and precondition guards of a reply to an Offer.

    The sender check reads the Offer the CASE_MANAGER recorded, so a sender
    that is not its party is refused first; at a replica the sender must be
    the CASE_MANAGER, and a case this store does not hold refuses
    (PCR-03-001).  The open-Offer check runs right after it, at the
    CASE_MANAGER only (CM-21-014, CM-21-016, HP-01-003).
    """
    context = SenderCheckContext(
        sender_id=sender_id,
        case_id=case_id,
        request=OwnershipOfferRequest(offer_id=offer_id, reply_id=reply_id),
        case_manager_required=True,
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
    return context, guards


def create_accept_ownership_transfer_tree(
    case_id: str,
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
        case_id: URI of the case whose ownership is being transferred.
        offer_id: The Offer the Accept names (the recorded Offer or the
            CASE_MANAGER's forward of it).
        sender_id: The Accept's sender.  The sender guard checks it: at the
            CASE_MANAGER it must be the transferee of the Offer it recorded,
            which the open-Offer guard then requires to be open; at a
            replica it must be the CASE_MANAGER.
        answer_id: The Accept's own id, so a redelivery is recognised.
        now: The instant the Offer's ``end_time`` is compared against; an
            Accept at or after it is refused (CM-21-016).  ``None`` reads the
            clock when the guard runs.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    sender_context, precondition_guards = _reply_guards(
        case_id, offer_id, sender_id, answer_id, OfferParty.TRANSFEREE, now
    )
    tree = create_receive_activity_tree(
        name="AcceptOwnershipTransferBT",
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=sender_context,
        precondition_guards=precondition_guards,
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
    case_id: str,
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
        case_id: URI of the case the declined Offer would have transferred.
        offer_id: The Offer the Reject names (the recorded Offer or the
            CASE_MANAGER's forward of it).
        sender_id: The Reject's sender, checked as for the Accept.
        answer_id: The Reject's own id, so a redelivery is recognised.
        now: As for the Accept: a Reject after the deadline is refused.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    sender_context, precondition_guards = _reply_guards(
        case_id, offer_id, sender_id, answer_id, OfferParty.TRANSFEREE, now
    )
    tree = create_receive_activity_tree(
        name="RejectOwnershipTransferBT",
        case_id=case_id,
        # The Accept's sender rule (CM-21-013) and open-Offer guard, so a
        # closed Offer refuses either answer and a redelivery is recognised.
        sender_rule=sender_rule,
        sender_context=sender_context,
        precondition_guards=precondition_guards,
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
    case_id: str,
    offer_id: str | None,
    sender_id: str,
    undo_id: str,
    now: datetime | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``UndoCaseOwnershipTransferReceivedUseCase``.

    The offerer withdraws an open Offer (CM-21-015).  The sender guard admits
    only the Case Owner that made an open Offer the CASE_MANAGER recorded;
    the guarded commit ledgers the withdrawal and broadcasts
    ``Announce(CaseLedgerEntry)``.  That entry closes the Offer (CM-21-014),
    so a later Accept or Reject of it is refused and the case may be offered
    again.  Ownership is unchanged.

    Args:
        case_id: URI of the case the withdrawn Offer would have transferred.
        offer_id: The Offer the Undo names.
        sender_id: The Undo's sender: at the CASE_MANAGER it must be the
            offerer, still the Case Owner; at a replica, the CASE_MANAGER.
        undo_id: The Undo's own id, so a redelivery is recognised.
        now: As for the Accept: an expired Offer cannot be withdrawn.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    sender_context, precondition_guards = _reply_guards(
        case_id, offer_id, sender_id, undo_id, OfferParty.OFFERER, now
    )
    tree = create_receive_activity_tree(
        name="UndoOwnershipTransferBT",
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=sender_context,
        precondition_guards=precondition_guards,
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


def offer_sender_context(
    sender_id: str, case_id: str, offer_id: str | None
) -> SenderCheckContext:
    """The context a new ownership-transfer Offer's sender is checked in.

    At the CASE_MANAGER the sender must be the Case Owner, unless it
    redelivers an Offer recorded from it (*offer_id*, HP-01-003); at a
    replica it must be the CASE_MANAGER, and a case the replica does not
    hold refuses (CM-21-019, PCR-03-001).  The handler's pre-flight and the
    received tree's guard read the same context.
    """
    return SenderCheckContext(
        sender_id=sender_id,
        case_id=case_id,
        offered_ownership_id=offer_id,
        case_manager_required=True,
    )


def create_offer_ownership_transfer_tree(
    case_id: str | None,
    transferee_id: str | None,
    original_actor_id: str | None,
    store_offer: StoreReceivedObjectNode | None = None,
    offer_id: str | None = None,
    answer_deadline: datetime | None = None,
    *,
    sender_rule: SenderRule,
    sender_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for ``OfferCaseOwnershipTransferReceivedUseCase``.

    Builds a ``create_receive_activity_tree`` whose ``manager_effects`` hold
    ``ForwardOfferToTransfereeNode``, so the factory's CASE_MANAGER gate
    ensures only the CaseActor forwards the offer to the transferee
    (CM-21-005, ADR-0053, CLP-10-006, BT-17-008).

    When ``transferee_id`` or ``original_actor_id`` is ``None`` the forwarding
    node is omitted: the ledger-commit gate still fires but no outbox write
    occurs.

    Args:
        case_id: URI of the case whose ownership is being offered; ``None``
            for an Offer that names no case, which intake archives
            (CLP-10-018); its handler passes no ``store_offer`` for it, and
            nothing is committed or forwarded.
        transferee_id: URI of the intended new owner; ``None`` skips forwarding.
        original_actor_id: URI of the actor who originated the offer (vendor).
        store_offer: Effect node that writes the Offer activity the accept
            trigger reads back by id (DL-06); it runs before the gated
            forward, after the guards and the commit (CLP-10-017,
            CLP-10-019).
        offer_id: The received Offer's id.  With a case, the CASE_MANAGER
            refuses it while an earlier ownership-transfer Offer for the case
            is open (CM-21-014); a redelivery of the same Offer is not an
            earlier one.
        answer_deadline: The Offer's ``end_time`` in UTC, if it carries one
            (CM-21-016); the forward carries it, so the transferee knows
            when it may no longer answer.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (CM-21-019, HP-01-008).
            Composed only with a case: an Offer naming no case is kept and
            refused by its handler (CLP-10-018).
        sender_id: The Offer's sender, which the guard checks
            (:func:`offer_sender_context`).

    Returns:
        A ``py_trees`` ``Behaviour`` ready for ``BTBridge.execute_with_setup()``.
    """
    replica_effects: list[py_trees.behaviour.Behaviour] = []
    if store_offer is not None:
        replica_effects.append(store_offer)
    manager_effects: list[py_trees.behaviour.Behaviour] = []
    if (
        case_id is not None
        and transferee_id is not None
        and original_actor_id is not None
    ):
        manager_effects.append(
            ForwardOfferToTransfereeNode(
                case_id=case_id,
                transferee_id=transferee_id,
                original_actor_id=original_actor_id,
                end_time=answer_deadline,
            )
        )
    precondition_guards: list[py_trees.behaviour.Behaviour] = []
    if case_id is not None and offer_id is not None:
        precondition_guards.append(
            case_manager_admits_ownership_offer_guard(
                case_id=case_id, offer_id=offer_id
            )
        )
    tree = create_receive_activity_tree(
        name="OfferOwnershipTransferBT",
        case_id=case_id,
        sender_rule=sender_rule if case_id is not None else None,
        sender_context=(
            offer_sender_context(sender_id, case_id, offer_id)
            if case_id is not None
            else None
        ),
        precondition_guards=precondition_guards,
        replica_effects=replica_effects,
        manager_effects=manager_effects,
        manager_case_id=case_id if manager_effects else None,
        manager_gate_name=(
            "ForwardOfferToTransfereeCMGated" if manager_effects else None
        ),
    )
    logger.debug(
        "Created OfferOwnershipTransferBT for case='%s'"
        " transferee='%s' original_actor='%s'",
        case_id,
        transferee_id,
        original_actor_id,
    )
    return tree
