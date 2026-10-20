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

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.refusal_notice import (
    EMBARGO_REFUSAL_ANSWERS,
)
from vultron.core.behaviors.case.nodes.stub_reissue import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.embargo_clock_decisions import (
    embargo_clock_decisions,
)
from vultron.core.behaviors.embargo.nodes import (
    ActivationAppliesNode,
    CommitAndApplyEmbargoActivationNode,
    DecideRejectedEmbargoProposalNode,
    IsOpenEmbargoProposalNode,
    OwnerMayActivateEmbargoNode,
    OwnerRejectionAppliesNode,
    embargo_ending_notice_nodes,
)
from vultron.core.behaviors.embargo.trigger_tree import (
    end_embargo_outliving_disclosure_bt,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)

logger = logging.getLogger(__name__)


def activate_embargo_on_case_tree(
    case_id: str,
    embargo_id: str,
    sender_actor_id: str,
    actor_config: ActorConfig | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the case owner's activation of a proposal (EA / EC).

    Handles receipt of an ``Accept(EmbargoEvent, target=Case)``::

        ActivateEmbargoOnCaseBT (Sequence)
        ├─ IntakeReceivedActivityNode
        ├─ SenderIsCaseOwnerNode             # sender guard (ADR-0115)
        ├─ ClockDecisionsIfCaseManager       # overdue invites (CM-28-015)
        ├─ IsOpenEmbargoProposalNode         # read-only guards (CLP-10-009)
        ├─ OwnerMayActivateEmbargoNode       # P/X/A clear (EMB-02-002)
        ├─ ActivationAppliesNode             # decide + trial apply (ADR-0124)
        └─ ActivateEmbargoOnCaseBTAct (ActTransaction)  # one act (ADR-0151)
           ├─ GuardedCommitCaseLedgerEntryBT    # the Accept: ACTIVATE (+ SUPERSEDE)
           └─ ActivateEmbargoOnCaseBTIfCaseManager (CASE_MANAGER gate)
              ├─ CaptureActiveEmbargoNode       # snapshot signatories before
              ├─ CommitAndApplyEmbargoActivationNode  # CARRY_OVER entries, apply
              ├─ SendEmbargoEndingNoticesNode   # tell dropped signatories (CM-31-009)
              ├─ BackfillAdmittedParticipantsNode  # CM-10-006
              └─ ReissueStubInvitesNode         # CM-11-016

    The guards refuse the activation before the commit when P/X/A is set
    (EMB-02-002) or the owner had declined the proposal (ADR-0122), so a
    refused activation is never ledgered; the activation itself runs
    ``STRICT``.  The CASE_MANAGER decides the activation and trial-applies it
    among the guards, so a step the register refuses commits nothing; once
    the guarded commit has committed the ``Accept`` (the whole register step and the
    owner's agreement), each ``CARRY_OVER`` row is committed as its own
    ``Update(EmbargoConsent)`` entry and only then is the case file written
    (ADR-0124, CLP-07-013).
    Activating a revision can admit a participant that had already accepted
    it after the entry was fanned out, so the CASE_MANAGER then sends what
    the gate withheld (CM-10-006), tells any signatory a shorter revision
    dropped and the ledger no longer reaches (CM-31-009), and re-issues each
    outstanding stub Invite against the now-active embargo (CM-11-016).

    Args:
        case_id: ID of the VulnerabilityCase.
        embargo_id: ID of the proposed EmbargoEvent being activated.
        sender_actor_id: Sender of the ``Accept``; must be the case owner.
        actor_config: The CASE_MANAGER's configuration; its RSVP windows set
            the deadline of a stub Invite the activation re-issues.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        Root node of the ``ActivateEmbargoOnCaseBT`` Sequence.
    """
    # The owner's activation of a shorter revision drops bound signatories the
    # ledger no longer reaches; capture them before the write, tell them after
    # (CM-31-009).
    capture, notices = embargo_ending_notice_nodes(
        case_id, requested_by=sender_actor_id
    )
    root = create_receive_activity_tree(
        name="ActivateEmbargoOnCaseBT",
        refusal_notice_exemption=EMBARGO_REFUSAL_ANSWERS,
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_actor_id, case_id=case_id
        ),
        # The owner decides knowing of every timeout (CM-28-015).
        clock_decisions=embargo_clock_decisions(case_id),
        precondition_guards=[
            IsOpenEmbargoProposalNode(case_id=case_id, embargo_id=embargo_id),
            OwnerMayActivateEmbargoNode(
                case_id=case_id, embargo_id=embargo_id
            ),
            ActivationAppliesNode(case_id=case_id, embargo_id=embargo_id),
        ],
        manager_effects=[
            capture,
            CommitAndApplyEmbargoActivationNode(
                case_id=case_id, embargo_id=embargo_id, result_out={}
            ),
            notices,
            BackfillAdmittedParticipantsNode(case_id=case_id),
            # The owner's activation of a revision changes the active embargo
            # under any stub Invite still outstanding (CM-11-016).
            ReissueStubInvitesNode(case_id=case_id, actor_config=actor_config),
        ],
        manager_case_id=case_id,
        # The Accept's own entry, the activation's rows, the backfill and the
        # stub re-issue are one act (CLP-07-015, ADR-0146, ADR-0151).
        as_one_act=True,
    )
    logger.info(
        "Created ActivateEmbargoOnCaseBT for case=%s embargo=%s sender=%s",
        case_id,
        embargo_id,
        sender_actor_id,
    )
    return root


def reject_embargo_proposal_on_case_tree(
    case_id: str,
    embargo_id: str,
    sender_actor_id: str,
    actor_config: ActorConfig | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the case owner's rejection of a proposal (ER / EJ).

    Handles receipt of a ``Reject(EmbargoEvent, target=Case)``::

        RejectEmbargoProposalOnCaseBT (Sequence)
        ├─ IntakeReceivedActivityNode
        ├─ SenderIsCaseOwnerNode             # sender guard (ADR-0115)
        ├─ ClockDecisionsIfCaseManager       # overdue invites (CM-28-015)
        ├─ IsOpenEmbargoProposalNode         # read-only guard (CLP-10-009)
        ├─ OwnerRejectionAppliesNode         # trial REJECT (+ TERMINATE)
        └─ RejectEmbargoProposalOnCaseBTAct (ActTransaction)  # one act (ADR-0151)
           ├─ GuardedCommitCaseLedgerEntryBT    # the Reject: REJECT
           └─ RejectEmbargoProposalOnCaseBTIfCaseManager (CASE_MANAGER gate)
              ├─ DecideRejectedEmbargoProposalNode  # REJECT; no consent
              └─ EndEmbargoOutlivingDisclosure (Selector)
                 ├─ TerminateOutlivingEmbargo   # P/X/A set → ET (Remove)
                 └─ PriorTermsAllowed

    ``PROPOSED → NONE`` or ``REVISE → ACTIVE`` when it was the last open
    proposal, and EM unchanged while another is open (EP-08-001).  No
    participant's consent changes, the owner's included (ADR-0122).

    When the owner rejects the last open revision while CS is public,
    exploited or attacked, the prior terms may not stand (EMB-04-002): the
    CASE_MANAGER records the ``REJECT`` step as decided and then commits
    its own ``Remove(EmbargoEvent)`` carrying the ``TERMINATE`` step and the
    threat signals as its cause (EMB-13-005), through the shared
    ``terminate_embargo_bt`` (BT-19-002), which announces the end to every
    other participant.  The guard trial-applies both steps before the
    commit, and the act is one transaction, so a refused termination
    commits neither entry (MSM-07-009).  A replica copies both entries in
    order and decides nothing (CM-23-016).

    Args:
        case_id: ID of the VulnerabilityCase.
        embargo_id: ID of the proposed EmbargoEvent being rejected.
        sender_actor_id: Sender of the ``Reject``; must be the case owner.
        actor_config: The CASE_MANAGER's configuration; its RSVP windows set
            the deadline of a stub Invite a termination re-issues.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        Root node of the ``RejectEmbargoProposalOnCaseBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="RejectEmbargoProposalOnCaseBT",
        refusal_notice_exemption=EMBARGO_REFUSAL_ANSWERS,
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_actor_id, case_id=case_id
        ),
        # The owner decides knowing of every timeout (CM-28-015).
        clock_decisions=embargo_clock_decisions(case_id),
        precondition_guards=[
            IsOpenEmbargoProposalNode(case_id=case_id, embargo_id=embargo_id),
            OwnerRejectionAppliesNode(case_id=case_id, embargo_id=embargo_id),
        ],
        manager_effects=[
            DecideRejectedEmbargoProposalNode(
                case_id=case_id, embargo_id=embargo_id
            ),
            end_embargo_outliving_disclosure_bt(
                case_id=case_id,
                otherwise=[],
                requested_by=sender_actor_id,
                actor_config=actor_config,
            ),
        ],
        manager_case_id=case_id,
        # The rejection's own entry, a termination it causes and that
        # termination's stub re-issue are one act (CLP-07-015, ADR-0146,
        # ADR-0151).
        as_one_act=True,
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
