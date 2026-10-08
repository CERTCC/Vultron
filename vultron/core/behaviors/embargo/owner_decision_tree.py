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

"""Received-side trees for the case owner's decision on an embargo proposal.

``activate_embargo_on_case_tree`` handles ``Accept(EmbargoEvent,
target=Case)`` and ``reject_embargo_proposal_on_case_tree`` handles
``Reject(EmbargoEvent, target=Case)`` (ADR-0122).  Only the case owner sends
either (EP-09-005); the sender guard refuses anyone else (HP-01-006).  The
owner addresses its decision to the CASE_MANAGER (PCR-08-001), so the
effects write shared case state behind the factory's CASE_MANAGER gate
(BT-17-008); a participant replica learns the decision from the
``Announce(CaseLedgerEntry)`` broadcast (EP-09-007), never from the activity
itself.
"""

import logging

import py_trees

from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    ActivateEmbargoLifecycleNode,
    DecideRejectedEmbargoProposalNode,
    IsOpenEmbargoProposalNode,
    OwnerMayActivateEmbargoNode,
    OwnerRejectsRevisionAfterDisclosureNode,
)
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.sender_entitlement import SenderIsCaseOwnerNode
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)
from vultron.core.states.embargo_register import TerminationReason

logger = logging.getLogger(__name__)


def activate_embargo_on_case_tree(
    case_id: str,
    embargo_id: str,
    sender_actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the case owner's activation of a proposal (EA / EC).

    Handles receipt of an ``Accept(EmbargoEvent, target=Case)``::

        ActivateEmbargoOnCaseBT (Sequence)
        ├─ IntakeReceivedActivityNode
        ├─ SenderIsCaseOwnerNode             # sender guard (ADR-0115)
        ├─ IsOpenEmbargoProposalNode         # read-only guards (CLP-10-009)
        ├─ OwnerMayActivateEmbargoNode       # P/X/A clear, owner not DECLINED
        ├─ GuardedCommitCaseLedgerEntryBT
        └─ ActivateEmbargoOnCaseBTIfCaseManager (CASE_MANAGER gate)
           ├─ ActivateEmbargoLifecycleNode   # ACTIVATE (+ SUPERSEDE), owner AGREE
           └─ BackfillAdmittedParticipantsNode  # CM-10-006

    The guards refuse the activation before the commit when P/X/A is set
    (EMB-02-002) or the owner had declined the proposal (ADR-0122), so a
    refused activation is never ledgered; the activation itself runs
    ``STRICT``.
    Activating a revision can admit a participant that had already accepted
    it after the entry was fanned out, so the CASE_MANAGER then sends what
    the gate withheld (CM-10-006).

    Args:
        case_id: ID of the VulnerabilityCase.
        embargo_id: ID of the proposed EmbargoEvent being activated.
        sender_actor_id: Sender of the ``Accept``; must be the case owner.

    Returns:
        Root node of the ``ActivateEmbargoOnCaseBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="ActivateEmbargoOnCaseBT",
        case_id=case_id,
        sender_guard=SenderIsCaseOwnerNode(
            sender_actor_id=sender_actor_id, case_id=case_id
        ),
        precondition_guards=[
            IsOpenEmbargoProposalNode(case_id=case_id, embargo_id=embargo_id),
            OwnerMayActivateEmbargoNode(
                case_id=case_id, embargo_id=embargo_id
            ),
        ],
        manager_effects=[
            ActivateEmbargoLifecycleNode(
                case_id=case_id, embargo_id=embargo_id, result_out={}
            ),
            BackfillAdmittedParticipantsNode(case_id=case_id),
        ],
        manager_case_id=case_id,
    )
    logger.info(
        "Created ActivateEmbargoOnCaseBT for case=%s embargo=%s sender=%s",
        case_id,
        embargo_id,
        sender_actor_id,
    )
    return root


def _decide_owner_rejection(
    case_id: str,
    embargo_id: str,
    rejecting_actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """The owner's Reject decides the proposal; with P/X/A set it ends the embargo.

    ``Selector``: when the owner rejects the last open revision after CS has
    gone public, exploited or attacked, returning to the prior terms is not
    allowed (EMB-04-002), so the CASE_MANAGER terminates the embargo through
    the shared ``terminate_embargo_bt`` and announces ET to every other
    participant — the same path the public-disclosure cascade takes.  Any
    other Reject is decided by the :class:`DecideRejectedEmbargoProposalNode`
    that follows.  Once the condition holds, a termination failure fails the
    tree: it is not a reason to revert to the prior terms instead.

    The whole decision sits behind the CASE_MANAGER gate, so the
    non-manager ask arm inside ``terminate_embargo_bt`` never runs here.  It
    stays rather than a manager-only variant: every path ends an embargo
    through the one shared composition (BT-19-002).
    """
    return py_trees.composites.Selector(
        name="DecideRejectedProposal",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="TerminateOnRejectedRevision",
                memory=False,
                children=[
                    OwnerRejectsRevisionAfterDisclosureNode(
                        case_id=case_id,
                        embargo_id=embargo_id,
                        rejecting_actor_id=rejecting_actor_id,
                    ),
                    terminate_embargo_bt(
                        case_id=case_id,
                        result_out={},
                        reason=TerminationReason.THREAT_SIGNAL,
                    ),
                ],
            ),
            py_trees.decorators.Inverter(
                name="UnlessTerminating",
                child=OwnerRejectsRevisionAfterDisclosureNode(
                    case_id=case_id,
                    embargo_id=embargo_id,
                    rejecting_actor_id=rejecting_actor_id,
                    name="CheckOwnerRejectsRevisionAfterDisclosure",
                ),
            ),
        ],
    )


def reject_embargo_proposal_on_case_tree(
    case_id: str,
    embargo_id: str,
    sender_actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the case owner's rejection of a proposal (ER / EJ).

    Handles receipt of a ``Reject(EmbargoEvent, target=Case)``::

        RejectEmbargoProposalOnCaseBT (Sequence)
        ├─ IntakeReceivedActivityNode
        ├─ SenderIsCaseOwnerNode             # sender guard (ADR-0115)
        ├─ IsOpenEmbargoProposalNode         # read-only guard (CLP-10-009)
        ├─ GuardedCommitCaseLedgerEntryBT
        └─ RejectEmbargoProposalOnCaseBTIfCaseManager (CASE_MANAGER gate)
           ├─ DecideRejectedProposal (Selector)
           │  ├─ TerminateOnRejectedRevision  # EJ with P/X/A → ET
           │  └─ UnlessTerminating (Inverter)
           └─ DecideRejectedEmbargoProposalNode  # REJECT; no consent

    ``PROPOSED → NONE`` or ``REVISE → ACTIVE`` when it was the last open
    proposal, EM unchanged while another is open (EP-08-001), or ET when
    P/X/A is set (EMB-04-002).  No participant's consent changes, the
    owner's included (ADR-0122).

    Args:
        case_id: ID of the VulnerabilityCase.
        embargo_id: ID of the proposed EmbargoEvent being rejected.
        sender_actor_id: Sender of the ``Reject``; must be the case owner.

    Returns:
        Root node of the ``RejectEmbargoProposalOnCaseBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="RejectEmbargoProposalOnCaseBT",
        case_id=case_id,
        sender_guard=SenderIsCaseOwnerNode(
            sender_actor_id=sender_actor_id, case_id=case_id
        ),
        precondition_guards=[
            IsOpenEmbargoProposalNode(case_id=case_id, embargo_id=embargo_id),
        ],
        manager_effects=[
            _decide_owner_rejection(case_id, embargo_id, sender_actor_id),
            # After an ET the proposal is already cancelled, so this is a
            # no-op.
            DecideRejectedEmbargoProposalNode(
                case_id=case_id, embargo_id=embargo_id
            ),
        ],
        manager_case_id=case_id,
    )
    logger.info(
        "Created RejectEmbargoProposalOnCaseBT for case=%s embargo=%s"
        " sender=%s",
        case_id,
        embargo_id,
        sender_actor_id,
    )
    return root


__all__ = [
    "activate_embargo_on_case_tree",
    "reject_embargo_proposal_on_case_tree",
]
