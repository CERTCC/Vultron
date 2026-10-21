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

"""Embargo BT nodes subpackage.

Re-exports all public node classes from submodules for backward compatibility.
"""

from vultron.core.behaviors.embargo.nodes.abandon import (
    ABANDONED_PROPOSALS_KEY,
    AbandonEmbargoProposalsLifecycleNode,
    ApplyEmbargoAbandonmentFromLedgerNode,
    LeaveAbandonmentToCaseManagerNode,
    ReadOpenEmbargoProposalsNode,
)
from vultron.core.behaviors.embargo.nodes.activation_commit import (
    ActivationAppliesNode,
    CommitAndApplyEmbargoActivationNode,
)
from vultron.core.behaviors.embargo.nodes.activation_effect import (
    EMBARGO_ACTIVATION_SEMANTIC_TYPE,
    EMBARGO_PROPOSAL_REJECTION_SEMANTIC_TYPE,
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
    IsActivateEmbargoEventNode,
    IsRejectEmbargoProposalEventNode,
)
from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.chosen_cause import (
    ChooseTerminationCauseNode,
    ChosenTermination,
)
from vultron.core.behaviors.embargo.nodes.conditions import (
    HasActiveEmbargoNode,
    IsActiveEmbargoNode,
    IsAnswerableEmbargoNode,
    IsCloseBlockedByActiveEmbargoNode,
    IsProposedEmbargoNode,
    LookupParticipantNode,
    ValidateCaseExistsNode,
)
from vultron.core.behaviors.embargo.nodes.em_state import (
    ReadEmbargoIdNode,
    ReadEmStateNode,
    ValidateEmbargoProposalStateNode,
    ValidateEmbargoRevisionStateNode,
    read_case_em_state,
)
from vultron.core.behaviors.embargo.nodes.ending_notice import (
    CaptureActiveEmbargoNode,
    SendEmbargoEndingNoticesNode,
    embargo_ending_notice_nodes,
)
from vultron.core.behaviors.embargo.nodes.ending_notice_replica import (
    ApplyAnnouncedEmbargoRevisionNode,
    AwaitsEmbargoEndingNoticeNode,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    ApplyInviteExpiryNoopFromLedgerNode,
    EvaluateInviteExpiryNode,
    InviteExpiryChangedConsentNode,
    InviteExpiryNeedsApplyNode,
)
from vultron.core.behaviors.embargo.nodes.expiry_commit import (
    CommitAndApplyHonourLateAcceptNode,
    CommitAndApplyInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.invite_answer import (
    CanAnswerEmbargoInviteNode,
    OwnerMayAutoAcceptEmbargoNode,
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    AcceptEmbargoLifecycleNode,
    ProposeEmbargoLifecycleNode,
    RejectEmbargoLifecycleNode,
    SendTerminateEmbargoActivityNode,
)
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    COMMITTED_ACTIVITY_KEY,
    EMBARGO_TEARDOWN_SEMANTIC_TYPE,
    CommitEmbargoDecisionNode,
    CommitEmbargoProposalNode,
    EmbargoActivityBuilder,
    IndexOwnEmbargoProposalNode,
)
from vultron.core.behaviors.embargo.nodes.manager_consent import (
    ManagerHoldsUndecidedEmbargoStakeNode,
    RecordManagerEmbargoConsentNode,
    record_manager_embargo_consent_tree,
)
from vultron.core.behaviors.embargo.nodes.owner_decision import (
    IsOpenEmbargoProposalNode,
    OwnerMayActivateEmbargoNode,
    RejectEmbargoProposalLifecycleNode,
    SendOwnerEmbargoDecisionNode,
)
from vultron.core.behaviors.embargo.nodes.proposal import (
    IndexReceivedEmbargoProposalNode,
    RecordParticipantAcceptanceNode,
    RecordParticipantRejectionNode,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteStaleAccepterNode,
)
from vultron.core.behaviors.embargo.nodes.reject_proposed import (
    DecideRejectedEmbargoProposalNode,
    EmbargoOutlivesDisclosureNode,
    OwnerRejectionAppliesNode,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    EMBARGO_INVITE_SEMANTIC_TYPE,
    CollectEmbargoInviteRecipientsNode,
    EmbargoProposalNotYetRecordedNode,
    EmStateAdmitsProposalNode,
    RelayEmbargoInviteToEachNode,
    case_manager_admits_proposal_guard,
)
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoReinviteFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    ApplyEmbargoTeardownNode,
    ClearActiveEmbargoNode,
    HasEmbargoActiveNode,
    SendAnnounceEmbargoEventNode,
    TerminationIsTimelyNode,
)
from vultron.core.behaviors.embargo.nodes.terminate import (
    TeardownAskPendingNode,
    ask_case_manager_to_terminate_once,
)
from vultron.core.behaviors.embargo.nodes.termination_cause_guard import (
    TerminationCauseIsAdmissibleNode,
)
from vultron.core.behaviors.embargo.nodes.termination_commit import (
    CommitAndApplyEmbargoTerminationNode,
)
from vultron.core.behaviors.embargo.nodes.withdrawal import (
    ApplyEmbargoWithdrawalFromLedgerNode,
    IsWithdrawableEmbargoNode,
    RecordParticipantWithdrawalNode,
    RejectIsNotWithdrawalNode,
    WithdrawEmbargoLifecycleNode,
)

__all__ = [
    # Invite answer (EP-09-003)
    "CanAnswerEmbargoInviteNode",
    "OwnerMayAutoAcceptEmbargoNode",
    "SendEmbargoInviteAnswerNode",
    # Conditions
    "ValidateCaseExistsNode",
    "IsActiveEmbargoNode",
    "IsAnswerableEmbargoNode",
    "EmbargoOutlivesDisclosureNode",
    "OwnerRejectionAppliesNode",
    "IsCloseBlockedByActiveEmbargoNode",
    "IsProposedEmbargoNode",
    "HasActiveEmbargoNode",
    "LookupParticipantNode",
    # EM state read
    "ReadEmStateNode",
    "read_case_em_state",
    # Teardown
    "HasEmbargoActiveNode",
    "ClearActiveEmbargoNode",
    "TerminationIsTimelyNode",
    "TerminationCauseIsAdmissibleNode",
    "ApplyEmbargoTeardownNode",
    "SendAnnounceEmbargoEventNode",
    # The case owner's decision on a proposal (ADR-0122) and its replay
    "ActivationAppliesNode",
    "CommitAndApplyEmbargoActivationNode",
    "IsOpenEmbargoProposalNode",
    "OwnerMayActivateEmbargoNode",
    "RejectEmbargoProposalLifecycleNode",
    "SendOwnerEmbargoDecisionNode",
    # Embargo-ending notices to unreached signatories (CM-31-009, CM-31-010)
    "ApplyAnnouncedEmbargoRevisionNode",
    "CaptureActiveEmbargoNode",
    "AwaitsEmbargoEndingNoticeNode",
    "SendEmbargoEndingNoticesNode",
    "embargo_ending_notice_nodes",
    # The case owner's decision replayed from the ledger (RSH-08-004)
    "EMBARGO_ACTIVATION_SEMANTIC_TYPE",
    "EMBARGO_PROPOSAL_REJECTION_SEMANTIC_TYPE",
    "ApplyEmbargoActivationFromLedgerNode",
    "ApplyEmbargoProposalRejectionFromLedgerNode",
    "IsActivateEmbargoEventNode",
    "IsRejectEmbargoProposalEventNode",
    # Relay (EP-09)
    "EMBARGO_INVITE_SEMANTIC_TYPE",
    "CollectEmbargoInviteRecipientsNode",
    "EmStateAdmitsProposalNode",
    "EmbargoProposalNotYetRecordedNode",
    "ReinviteStaleAccepterNode",
    "RelayEmbargoInviteToEachNode",
    # CASE_MANAGER decision commit (EP-09-008, #4085)
    "EMBARGO_TEARDOWN_SEMANTIC_TYPE",
    "CommitEmbargoDecisionNode",
    "CommitEmbargoProposalNode",
    "CommitAndApplyEmbargoTerminationNode",
    "COMMITTED_ACTIVITY_KEY",
    "IndexOwnEmbargoProposalNode",
    "IndexReceivedEmbargoProposalNode",
    # The manager's own consent row (EP-09-002, #4180)
    "ManagerHoldsUndecidedEmbargoStakeNode",
    "RecordManagerEmbargoConsentNode",
    "record_manager_embargo_consent_tree",
    "EmbargoActivityBuilder",
    # Relay ledger replay (EP-09-007)
    "ApplyEmbargoProposalFromLedgerNode",
    "ApplyEmbargoInviteFromLedgerNode",
    "ApplyEmbargoReinviteFromLedgerNode",
    "ApplyEmbargoAcceptanceFromLedgerNode",
    "ApplyEmbargoRejectionFromLedgerNode",
    # P/X/A abandonment of open proposals (EMB-16-001, #4131)
    "ABANDONED_PROPOSALS_KEY",
    "ReadOpenEmbargoProposalsNode",
    "AbandonEmbargoProposalsLifecycleNode",
    "LeaveAbandonmentToCaseManagerNode",
    "ApplyEmbargoAbandonmentFromLedgerNode",
    "case_manager_admits_proposal_guard",
    # Invite expiry: evaluation (CM-28-014, BT-17-001) and replay (ADR-0118)
    "ApplyInviteExpiryNoopFromLedgerNode",
    "EvaluateInviteExpiryNode",
    "CommitAndApplyHonourLateAcceptNode",
    "CommitAndApplyInviteExpiryNode",
    "InviteExpiryChangedConsentNode",
    "InviteExpiryNeedsApplyNode",
    # Proposal
    "RecordParticipantAcceptanceNode",
    "RecordParticipantRejectionNode",
    # Lifecycle
    "PersistEmbargoEventNode",
    "ValidateEmbargoProposalStateNode",
    "ValidateEmbargoRevisionStateNode",
    "ProposeEmbargoLifecycleNode",
    "AcceptEmbargoLifecycleNode",
    "RejectEmbargoLifecycleNode",
    "ReadEmbargoIdNode",
    "DecideRejectedEmbargoProposalNode",
    "SendTerminateEmbargoActivityNode",
    "TeardownAskPendingNode",
    "ask_case_manager_to_terminate_once",
    # Withdrawal from the embargo in force (MSM-07-010)
    "ApplyEmbargoWithdrawalFromLedgerNode",
    "IsWithdrawableEmbargoNode",
    "RecordParticipantWithdrawalNode",
    "RejectIsNotWithdrawalNode",
    "WithdrawEmbargoLifecycleNode",
    # The cause a voluntary termination chose (EMB-14-001)
    "ChooseTerminationCauseNode",
    "ChosenTermination",
]
