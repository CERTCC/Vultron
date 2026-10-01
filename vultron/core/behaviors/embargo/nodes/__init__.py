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

from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.conditions import (
    HasActiveEmbargoNode,
    HasCaseStatusesNode,
    IsActiveEmbargoNode,
    IsCloseBlockedByActiveEmbargoNode,
    IsProposedEmbargoNode,
    LookupParticipantNode,
    ValidateCaseExistsNode,
)
from vultron.core.behaviors.embargo.nodes.em_state import ReadEmStateNode
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
    ValidateEmbargoRevisionStateNode,
)
from vultron.core.behaviors.embargo.nodes.proposal import (
    CreateAndStoreInviteNode,
    RecordParticipantAcceptanceNode,
    RecordParticipantRejectionNode,
)
from vultron.core.behaviors.embargo.nodes.reject_proposed import (
    DecideRejectedEmbargoProposalNode,
    ReadProposedEmbargoIdNode,
    RejectProposedEmbargoLifecycleNode,
    SendRejectEmbargoActivityNode,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    EMBARGO_INVITE_EVENT_TYPE,
    CollectEmbargoInviteRecipientsNode,
    EmbargoProposalNotYetRecordedNode,
    EmStateAdmitsProposalNode,
    RelayEmbargoInviteToEachNode,
    case_manager_admits_proposal_guard,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    ApplyEmbargoTeardownNode,
    ClearActiveEmbargoNode,
    HasEmbargoActiveNode,
    RemoveFromProposedEmbargoesNode,
    ResetParticipantConsentNode,
    SendAnnounceEmbargoEventNode,
)

__all__ = [
    # Invite answer (EP-09-003)
    "CanAnswerEmbargoInviteNode",
    "SendEmbargoInviteAnswerNode",
    # Conditions
    "ValidateCaseExistsNode",
    "IsActiveEmbargoNode",
    "IsCloseBlockedByActiveEmbargoNode",
    "IsProposedEmbargoNode",
    "HasActiveEmbargoNode",
    "HasCaseStatusesNode",
    "LookupParticipantNode",
    # EM state read
    "ReadEmStateNode",
    # Teardown
    "HasEmbargoActiveNode",
    "ClearActiveEmbargoNode",
    "ResetParticipantConsentNode",
    "ApplyEmbargoTeardownNode",
    "RemoveFromProposedEmbargoesNode",
    "SendAnnounceEmbargoEventNode",
    # Relay (EP-09)
    "EMBARGO_INVITE_EVENT_TYPE",
    "CollectEmbargoInviteRecipientsNode",
    "EmStateAdmitsProposalNode",
    "EmbargoProposalNotYetRecordedNode",
    "RelayEmbargoInviteToEachNode",
    "case_manager_admits_proposal_guard",
    # Proposal
    "CreateAndStoreInviteNode",
    "RecordParticipantAcceptanceNode",
    "RecordParticipantRejectionNode",
    # Lifecycle
    "PersistEmbargoEventNode",
    "ValidateEmbargoRevisionStateNode",
    "ProposeEmbargoLifecycleNode",
    "AcceptEmbargoLifecycleNode",
    "RejectEmbargoLifecycleNode",
    "TerminateEmbargoLifecycleNode",
    "ReadEmbargoIdNode",
    "DecideRejectedEmbargoProposalNode",
    "ReadProposedEmbargoIdNode",
    "RejectProposedEmbargoLifecycleNode",
    "SendTerminateEmbargoActivityNode",
    "SendRejectEmbargoActivityNode",
    "SetEmbargoActiveNode",
]
