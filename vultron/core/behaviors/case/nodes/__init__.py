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

"""
Case management behavior tree nodes subpackage.

Re-exports all public node classes from domain-specific submodules so that
existing import paths (``from vultron.core.behaviors.case.nodes import ...``)
continue to work without modification.

Submodules:
- ``actor``: Actor-participation invite/accept emit nodes
- ``conditions``: Idempotency guard condition nodes
- ``case_setup``: Case persistence, CaseActor identity and CaseActor
  provisioning leaf action nodes
- ``participant``: Participant creation and attachment leaf action nodes
- ``embargo``: Default embargo initialization action nodes
- ``close_case_effect``: Ledger-apply of a ``close_case`` entry on a replica
  (ApplyCloseCaseFromLedgerNode; composes the participant-status writer)
- ``communication``: Outbound activity emission action nodes
- ``intake``: Intake node — archives the received activity as received,
  first in every received tree (ADR-0111)
- ``lifecycle``: Case log entry commit action node
- ``proposal``: CaseProposal send nodes (ADR-0041 receiver-side slimmed tree)
- ``proposal_admission_conditions``: case-actor-side admission guards (CP-05-002)
- ``proposal_admission_actions``: case-actor-side admission writes and the
  ``Reject`` emit (CP-05-002, CP-05-004)
- ``suggest_actor``: Suggest-actor workflow emit and duplicate-detection nodes

Composite subtrees (``Sequence``/``Selector`` subclasses) are defined in
sibling ``*_tree.py`` modules at the process-area root per BTND-07-003.
They are not re-exported here: the tree modules import leaf nodes from
this package, so a re-export would close an import cycle (CS-05-003).
Import each composite from the ``*_tree.py`` module that defines it.
"""

from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
    EvaluateDefaultRolesNode,
    ProposeCaseToActorNode,
)
from vultron.core.behaviors.case.nodes.case_lookup import (
    RequireCaseForReport,
)
from vultron.core.behaviors.case.nodes.case_setup import (
    EnsureCaseActorHostedNode,
    PersistCase,
    RecordCaseCreatedEventNode,
    RecordOfferReceivedEventNode,
    SetCaseAttributedTo,
)
from vultron.core.behaviors.case.nodes.close_case_effect import (
    ApplyCloseCaseFromLedgerNode,
)
from vultron.core.behaviors.case.nodes.communication import (
    CollectCaseAddresseesNode,
    CreateAndPersistCaseActivityNode,
)
from vultron.core.behaviors.case.nodes.conditions import (
    CheckAutoCaseCreationEnabledNode,
    CheckCaseAlreadyExists,
    CheckCaseExistsForReport,
    CheckIsCaseManagerNode,
    CheckProposalAlreadySentForReport,
    WritePendingReportCaseLinkNode,
)
from vultron.core.behaviors.case.nodes.delegation import (
    AutoAcceptCaseParticipantRoleNode,
    EmitRejectCaseParticipantRoleNode,
)
from vultron.core.behaviors.case.nodes.embargo import (
    AdvanceEMStateToActiveNode,
    CreateEmbargoEventNode,
    SeedOwnerAsSignatoryNode,
)
from vultron.core.behaviors.case.nodes.embargo_resolution import (
    CaseEmbargoAlreadyInitializedNode,
    CaseNotEmbargoEligibleNode,
    ResolveEmbargoDurationNode,
)

# RelayCreationTimeRevisionNode is imported from its own module,
# ``embargo_revision_relay``: re-exporting it here closes an import cycle
# through the embargo relay emit, which imports the case role gates.
from vultron.core.behaviors.case.nodes.embargo_revision import (
    RegisterLongerProposalAsRevisionNode,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.invite_ledger_backfill import (
    BackfillCanonicalLedgerToInviteeNode,
    CapturePreCommitBackfillTargetNode,
    EmitAnnounceCaseToInviteeNode,
)
from vultron.core.behaviors.case.nodes.invite_participant import (
    CheckInviteeNotAlreadyParticipantNode,
    CreateInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.invite_participant_persist import (
    AdvanceInviteeToReceivedNode,
    PersistInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.invite_response import (
    EmitAcceptCaseInviteNode,
    EmitRejectCaseInviteNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.case.nodes.on_behalf_guards import (
    CheckOnBehalfAuthorizedNode,
    CheckOnBehalfTargetIsParticipantNode,
)
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    EmitAcceptCaseOwnershipTransferNode,
    EmitOfferCaseOwnershipTransferNode,
    ForwardOfferToTransfereeNode,
)
from vultron.core.behaviors.case.nodes.participant import (
    CreateParticipantStatusNode,
    RecordOwnerJoinedEventNode,
    _create_and_attach_participant,
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.proposal import (
    ProposeReportCaseToActorNode,
)
from vultron.core.behaviors.case.nodes.proposal_admission_actions import (
    EmitRejectCaseProposalNode,
    RecordProposalAdmissionNode,
    RecordProposalDeclineNode,
)
from vultron.core.behaviors.case.nodes.proposal_admission_conditions import (
    CheckDeclineRecordExistsNode,
    CheckNoDeclineRecordNode,
    CheckProposalAlreadyAnsweredNode,
    CheckRejectAlreadyAnsweredNode,
    activity_names_proposal,
    find_activity_for_proposal,
)
from vultron.core.behaviors.case.nodes.proposal_case_resolution import (
    CreateCaseFromProposalNode,
    LoadExistingCaseNode,
    StoreProposalReportNode,
)
from vultron.core.behaviors.case.nodes.proposal_consent import (
    SeedReporterSignatoryNode,
)
from vultron.core.behaviors.case.nodes.proposal_emits import (
    EmitAcceptCaseProposalNode,
    EmitCreateVulnerabilityCaseNode,
)
from vultron.core.behaviors.case.nodes.proposal_ledger import (
    CommitNativeLedgerEntriesNode,
)
from vultron.core.behaviors.case.nodes.proposal_participants import (
    AddCaseActorParticipantNode,
    AddOwnerParticipantNode,
)
from vultron.core.behaviors.case.nodes.proposal_reporter import (
    AddReporterParticipantNode,
)
from vultron.core.behaviors.case.nodes.proposal_retry_marker import (
    CheckMarkerExistsNode,
    ClearCreateCaseMarkerNode,
    WriteCreateCaseMarkerNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.nodes.suggest_actor import (
    ActorAlreadyParticipantNode,
    EmitAcceptActorRecommendationNode,
    EmitAcceptCaseParticipantOfferNode,
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
    EmitRejectActorRecommendationNode,
    InviteInFlightNode,
    PendingOfferCaseParticipantNode,
)
from vultron.core.behaviors.case.nodes.update import (
    ApplyCaseUpdateNode,
    BroadcastCaseUpdateNode,
    CaptureCaseUpdateBroadcastExclusionsNode,
    CheckCaseUpdateOwnerNode,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckIsCaseOwnerNode,
    CheckNotSoleObserverVfdNode,
)
from vultron.core.behaviors.helpers import UpdateActorOutbox

__all__ = [
    "CheckDeclineRecordExistsNode",
    "CheckNoDeclineRecordNode",
    "CheckProposalAlreadyAnsweredNode",
    "CheckRejectAlreadyAnsweredNode",
    "EmitRejectCaseProposalNode",
    "RecordProposalAdmissionNode",
    "RecordProposalDeclineNode",
    "activity_names_proposal",
    "find_activity_for_proposal",
    # actor (leaf nodes)
    "EmitInviteActorToCaseNode",
    "EmitAcceptCaseInviteNode",
    "EvaluateDefaultRolesNode",
    "ProposeCaseToActorNode",
    "ProposeReportCaseToActorNode",
    # conditions
    "CheckAutoCaseCreationEnabledNode",
    "CheckCaseAlreadyExists",
    "CheckCaseExistsForReport",
    "CheckIsCaseManagerNode",
    "CheckIsCaseOwnerNode",
    "CheckProposalAlreadySentForReport",
    "RequireCaseForReport",
    "WritePendingReportCaseLinkNode",
    # case_setup (leaf nodes)
    "EnsureCaseActorHostedNode",
    "PersistCase",
    "SetCaseAttributedTo",
    "RecordOfferReceivedEventNode",
    "RecordCaseCreatedEventNode",
    # participant (leaf nodes)
    "CreateParticipantStatusNode",
    "RecordOwnerJoinedEventNode",
    "_create_and_attach_participant",
    "resolve_participant_state_from_dl",
    # embargo (leaf nodes)
    "AdvanceEMStateToActiveNode",
    "CaseEmbargoAlreadyInitializedNode",
    "CaseNotEmbargoEligibleNode",
    "CreateEmbargoEventNode",
    "RegisterLongerProposalAsRevisionNode",
    "ResolveEmbargoDurationNode",
    "SeedOwnerAsSignatoryNode",
    # delegation (leaf nodes)
    "AutoAcceptCaseParticipantRoleNode",
    "EmitRejectCaseParticipantRoleNode",
    # close_case_effect (ledger-apply leaf node)
    "ApplyCloseCaseFromLedgerNode",
    # communication (leaf nodes)
    "CollectCaseAddresseesNode",
    "CreateAndPersistCaseActivityNode",
    # lifecycle
    "CommitCaseLedgerEntryNode",
    # update
    "CheckCaseUpdateOwnerNode",
    "CaptureCaseUpdateBroadcastExclusionsNode",
    "ApplyCaseUpdateNode",
    "BroadcastCaseUpdateNode",
    # ownership_transfer (leaf nodes)
    "EmitOfferCaseOwnershipTransferNode",
    "EmitAcceptCaseOwnershipTransferNode",
    "ForwardOfferToTransfereeNode",
    # role_gates (gated composites)
    "create_case_manager_gated_tree",
    "create_participant_replica_gated_tree",
    # vfd_role_guards (condition nodes)
    "CheckNotSoleObserverVfdNode",
    # on_behalf_guards (ADR-0084)
    "CheckOnBehalfAuthorizedNode",
    "CheckOnBehalfTargetIsParticipantNode",
    # suggest_actor (leaf nodes)
    "ActorAlreadyParticipantNode",
    "EmitAcceptActorRecommendationNode",
    "EmitAcceptCaseParticipantOfferNode",
    "EmitNoteDuplicateRecommendationToOwnerNode",
    "EmitOfferCaseParticipantToOwnerNode",
    "EmitRejectActorRecommendationNode",
    "InviteInFlightNode",
    "PendingOfferCaseParticipantNode",
    # re-exported from helpers (backward compat)
    "UpdateActorOutbox",
    # proposal_case_resolution (leaf nodes, #3457 BTND-07-003)
    "LoadExistingCaseNode",
    "CreateCaseFromProposalNode",
    "StoreProposalReportNode",
    # proposal_participants (leaf nodes)
    "AddCaseActorParticipantNode",
    "AddOwnerParticipantNode",
    # proposal_reporter (leaf node)
    "AddReporterParticipantNode",
    # proposal_consent (leaf node)
    "SeedReporterSignatoryNode",
    # proposal_ledger (leaf node)
    "CommitNativeLedgerEntriesNode",
    # proposal_retry_marker (leaf nodes)
    "CheckMarkerExistsNode",
    "WriteCreateCaseMarkerNode",
    "ClearCreateCaseMarkerNode",
    # proposal_emits (leaf nodes)
    "EmitAcceptCaseProposalNode",
    "EmitCreateVulnerabilityCaseNode",
    # invite_participant (leaf nodes)
    "CheckInviteeNotAlreadyParticipantNode",
    "CreateInviteeParticipantNode",
    # invite_participant_persist (leaf nodes)
    "PersistInviteeParticipantNode",
    "AdvanceInviteeToReceivedNode",
    # invite_ledger_backfill (leaf nodes)
    "CapturePreCommitBackfillTargetNode",
    "BackfillCanonicalLedgerToInviteeNode",
    "EmitAnnounceCaseToInviteeNode",
]
