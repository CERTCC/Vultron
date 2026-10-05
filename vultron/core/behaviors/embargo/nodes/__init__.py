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
    CommitEmbargoAbandonmentNode,
    LeaveAbandonmentToCaseManagerNode,
    ReadOpenEmbargoProposalsNode,
)
from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.conditions import (
    HasActiveEmbargoNode,
    HasCaseStatusesNode,
    IsActiveEmbargoNode,
    IsCloseBlockedByActiveEmbargoNode,
    IsProposedEmbargoNode,
    IsRejectableEmbargoNode,
    LookupParticipantNode,
    ValidateCaseExistsNode,
)
from vultron.core.behaviors.embargo.nodes.em_state import (
    ReadEmStateNode,
    read_case_em_state,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    ApplyHonourLateAcceptFromLedgerNode,
    ApplyInviteExpiryFromLedgerNode,
    ApplyInviteExpiryNoopFromLedgerNode,
    EvaluateInviteExpiryNode,
    HonourLateAcceptNode,
    InviteExpiryChangedConsentNode,
    InviteExpiryNeedsApplyNode,
    RecordInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.invite_answer import (
    CanAnswerEmbargoInviteNode,
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    AcceptEmbargoLifecycleNode,
    ProposeEmbargoLifecycleNode,
    ReadEmbargoIdNode,
    RejectEmbargoLifecycleNode,
    SendTerminateEmbargoActivityNode,
    SetEmbargoActiveNode,
    TerminateEmbargoLifecycleNode,
    ValidateEmbargoProposalStateNode,
    ValidateEmbargoRevisionStateNode,
)
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    COMMITTED_ACTIVITY_KEY,
    EMBARGO_TEARDOWN_EVENT_TYPE,
    CommitEmbargoDecisionNode,
    CommitEmbargoTeardownNode,
    EmbargoActivityBuilder,
    IndexOwnEmbargoProposalNode,
)
from vultron.core.behaviors.embargo.nodes.proposal import (
    CreateAndStoreInviteNode,
    RecordParticipantAcceptanceNode,
    RecordParticipantRejectionNode,
)
from vultron.core.behaviors.embargo.nodes.reject_proposed import (
    DecideRejectedEmbargoProposalNode,
    OwnerRejectsRevisionAfterDisclosureNode,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    EMBARGO_INVITE_EVENT_TYPE,
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
    ApplyEmbargoRejectionFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    ApplyEmbargoTeardownNode,
    ClearActiveEmbargoNode,
    ExitParticipantConsentNode,
    HasEmbargoActiveNode,
    RemoveFromProposedEmbargoesNode,
    SendAnnounceEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.terminate import (
    TeardownAskPendingNode,
    ask_case_manager_to_terminate_once,
)

__all__ = [
    # Invite answer (EP-09-003)
    "CanAnswerEmbargoInviteNode",
    "SendEmbargoInviteAnswerNode",
    # Conditions
    "ValidateCaseExistsNode",
    "IsActiveEmbargoNode",
    "IsRejectableEmbargoNode",
    "OwnerRejectsRevisionAfterDisclosureNode",
    "IsCloseBlockedByActiveEmbargoNode",
    "IsProposedEmbargoNode",
    "HasActiveEmbargoNode",
    "HasCaseStatusesNode",
    "LookupParticipantNode",
    # EM state read
    "ReadEmStateNode",
    "read_case_em_state",
    # Teardown
    "HasEmbargoActiveNode",
    "ClearActiveEmbargoNode",
    "ExitParticipantConsentNode",
    "ApplyEmbargoTeardownNode",
    "RemoveFromProposedEmbargoesNode",
    "SendAnnounceEmbargoEventNode",
    # Relay (EP-09)
    "EMBARGO_INVITE_EVENT_TYPE",
    "CollectEmbargoInviteRecipientsNode",
    "EmStateAdmitsProposalNode",
    "EmbargoProposalNotYetRecordedNode",
    "RelayEmbargoInviteToEachNode",
    # CASE_MANAGER decision commit (EP-09-008, #4085)
    "EMBARGO_TEARDOWN_EVENT_TYPE",
    "CommitEmbargoDecisionNode",
    "CommitEmbargoTeardownNode",
    "COMMITTED_ACTIVITY_KEY",
    "IndexOwnEmbargoProposalNode",
    "EmbargoActivityBuilder",
    # Relay ledger replay (EP-09-007)
    "ApplyEmbargoProposalFromLedgerNode",
    "ApplyEmbargoInviteFromLedgerNode",
    "ApplyEmbargoAcceptanceFromLedgerNode",
    "ApplyEmbargoRejectionFromLedgerNode",
    # P/X/A abandonment of open proposals (EMB-16-001, #4131)
    "ABANDONED_PROPOSALS_KEY",
    "ReadOpenEmbargoProposalsNode",
    "AbandonEmbargoProposalsLifecycleNode",
    "CommitEmbargoAbandonmentNode",
    "LeaveAbandonmentToCaseManagerNode",
    "ApplyEmbargoAbandonmentFromLedgerNode",
    "case_manager_admits_proposal_guard",
    # Invite expiry: evaluation (CM-28-014, BT-17-001) and replay (ADR-0118)
    "ApplyHonourLateAcceptFromLedgerNode",
    "ApplyInviteExpiryFromLedgerNode",
    "ApplyInviteExpiryNoopFromLedgerNode",
    "EvaluateInviteExpiryNode",
    "HonourLateAcceptNode",
    "InviteExpiryChangedConsentNode",
    "InviteExpiryNeedsApplyNode",
    "RecordInviteExpiryNode",
    # Proposal
    "CreateAndStoreInviteNode",
    "RecordParticipantAcceptanceNode",
    "RecordParticipantRejectionNode",
    # Lifecycle
    "PersistEmbargoEventNode",
    "ValidateEmbargoProposalStateNode",
    "ValidateEmbargoRevisionStateNode",
    "ProposeEmbargoLifecycleNode",
    "AcceptEmbargoLifecycleNode",
    "RejectEmbargoLifecycleNode",
    "TerminateEmbargoLifecycleNode",
    "ReadEmbargoIdNode",
    "DecideRejectedEmbargoProposalNode",
    "SendTerminateEmbargoActivityNode",
    "SetEmbargoActiveNode",
    "TeardownAskPendingNode",
    "ask_case_manager_to_terminate_once",
]
