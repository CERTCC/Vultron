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

"""The reviewed seeding declaration of every received event and trigger request.

``seeding_declaration`` seeds a vocabulary key from any attribute of the same
name (BT-25-007), so a new property on an event, or a new key in the
vocabulary, can add a seed nobody chose.  This table is the reviewed record:
each type's seeded keys, as ``key`` (from the same-named attribute) or
``key<-attribute``.  ``test_act_key_vocabulary`` fails when a type's
declaration differs from its row, so a new seed is a diff a reviewer reads.

Before adding a row, check that each attribute means what the key's
``meaning`` says; withhold one that does not with ``declare_seeds`` (as the
actor-recommendation answers withhold ``case_actor_id``).
"""

#: Each act type's seeded keys, by type name.
SEEDING_TABLE: dict[str, str] = {
    "AcceptActorRecommendationReceivedEvent": "object_id sender_id<-actor_id",
    "AcceptActorRecommendationTriggerRequest": "",
    "AcceptCaseInviteTriggerRequest": "invite_id",
    "AcceptCaseOwnershipTransferReceivedEvent": "case_id object_id sender_id<-actor_id",
    "AcceptCaseOwnershipTransferTriggerRequest": "offer_id",
    "AcceptCaseParticipantRoleReceivedEvent": "object_id offer_id sender_id<-actor_id",
    "AcceptCaseProposalReceivedEvent": "object_id proposal_id report_id sender_id<-actor_id",
    "AcceptEmbargoTriggerRequest": "case_id proposal_id",
    "AcceptFullCaseInviteTriggerRequest": "invite_id",
    "AcceptInviteActorToCaseReceivedEvent": "case_id invite_id invitee_id object_id sender_id<-actor_id",
    "AcceptInviteActorToFullCaseReceivedEvent": "case_id invite_id invitee_id object_id sender_id<-actor_id",
    "AcceptInviteToEmbargoOnCaseReceivedEvent": "case_id embargo embargo_id invite_id object_id sender_id<-actor_id",
    "AcceptOfferCaseParticipantReceivedEvent": "case_id object_id sender_id<-actor_id",
    "AckReportReceivedEvent": "object_id offer_id report_id sender_id<-actor_id",
    "AckReportTriggerRequest": "offer_id",
    "ActivateEmbargoOnCaseReceivedEvent": "case_id embargo embargo_id object_id sender_id<-actor_id",
    "AddCaseParticipantToCaseReceivedEvent": "case_id object_id participant_id sender_id<-actor_id",
    "AddCaseReferenceToCaseReceivedEvent": "case_id object_id sender_id<-actor_id",
    "AddCaseStatusToCaseReceivedEvent": "case_id object_id sender_id<-actor_id",
    "AddNoteToCaseReceivedEvent": "case_id note_id object_id sender_id<-actor_id",
    "AddNoteToCaseTriggerRequest": "case_id",
    "AddObjectToCaseTriggerRequest": "case_id object_id",
    "AddOnBehalfStatusTriggerRequest": "case_id",
    "AddParticipantStatusToParticipantReceivedEvent": "object_id participant_id sender_id<-actor_id",
    "AddParticipantStatusTriggerRequest": "case_id",
    "AddReportToCaseReceivedEvent": "case_id object_id report_id sender_id<-actor_id",
    "AddReportToCaseTriggerRequest": "case_id report_id",
    "AddVulnerabilityItemToCaseReceivedEvent": "case_id object_id sender_id<-actor_id",
    "AnnounceEmbargoEventToCaseReceivedEvent": "case_id embargo embargo_id object_id sender_id<-actor_id",
    "AddLogEntryReceivedEvent": "object_id sender_id<-actor_id",
    "AnnounceVulnerabilityCaseReceivedEvent": "object_id sender_id<-actor_id",
    "CloseCaseReceivedEvent": "case_id object_id sender_id<-actor_id",
    "CloseReportReceivedEvent": "object_id offer_id report_id sender_id<-actor_id",
    "CreateCaseParticipantReceivedEvent": "case_id object_id participant_id sender_id<-actor_id",
    "CreateCaseProposalReceivedEvent": "object_id proposal_id sender_id<-actor_id",
    "CreateCaseReceivedEvent": "case_id object_id sender_id<-actor_id",
    "CreateCaseTriggerRequest": "report_id",
    "CreateEmbargoConsentReceivedEvent": "case_id object_id sender_id<-actor_id",
    "CreateEmbargoEventReceivedEvent": "case_id embargo_id object_id sender_id<-actor_id",
    "CreateProcessingFaultReceivedEvent": "object_id sender_id<-actor_id",
    "CreateReportReceivedEvent": "object_id report_id sender_id<-actor_id",
    "DeferCaseReceivedEvent": "case_id object_id sender_id<-actor_id",
    "DeferCaseTriggerRequest": "case_id",
    "EngageCaseReceivedEvent": "case_id object_id sender_id<-actor_id",
    "EngageCaseTriggerRequest": "case_id",
    "InvalidateReportReceivedEvent": "object_id offer_id report_id sender_id<-actor_id",
    "InvalidateReportTriggerRequest": "offer_id",
    "InviteActorToCaseReceivedEvent": "case_id invitee_id object_id sender_id<-actor_id",
    "InviteActorToCaseTriggerRequest": "case_id invitee_id",
    "InviteActorToFullCaseReceivedEvent": "case_id invitee_id object_id sender_id<-actor_id",
    "InviteToEmbargoOnCaseReceivedEvent": "case_id invitee_id object_id sender_id<-actor_id",
    "LeaveCaseTriggerRequest": "case_id",
    "LedgerPositionedEvent": "object_id sender_id<-actor_id",
    "OfferActorToCaseReceivedEvent": "case_id object_id sender_id<-actor_id",
    "OfferCaseOwnershipTransferReceivedEvent": "object_id sender_id<-actor_id",
    "OfferCaseOwnershipTransferTriggerRequest": "case_id",
    "OfferCaseParticipantReceivedEvent": "case_id object_id sender_id<-actor_id",
    "OfferCaseParticipantRoleReceivedEvent": "object_id sender_id<-actor_id",
    "OfferCaseParticipantRoleTriggerRequest": "case_id",
    "OfferTriggerRequest": "offer_id",
    "ProposeCaseOwnershipTransferReceivedEvent": "case_id object_id sender_id<-actor_id",
    "ProposeEmbargoRevisionTriggerRequest": "case_id",
    "ProposeEmbargoTriggerRequest": "case_id",
    "ReadLogEntryReceivedEvent": "object_id sender_id<-actor_id",
    "RefusalNoticeReceivedEvent": "case_id object_id refused_activity_id sender_id<-actor_id",
    "RejectActorRecommendationReceivedEvent": "object_id sender_id<-actor_id",
    "RejectActorRecommendationTriggerRequest": "",
    "RejectCaseInviteTriggerRequest": "invite_id",
    "RejectCaseOwnershipTransferReceivedEvent": "case_id object_id offer_id sender_id<-actor_id",
    "RejectCaseOwnershipTransferTriggerRequest": "offer_id",
    "RejectCaseParticipantRoleReceivedEvent": "object_id offer_id sender_id<-actor_id",
    "RejectCaseProposalReceivedEvent": "object_id proposal_id report_id sender_id<-actor_id",
    "RejectEmbargoProposalOnCaseReceivedEvent": "case_id embargo embargo_id object_id sender_id<-actor_id",
    "RejectEmbargoTriggerRequest": "case_id proposal_id",
    "RejectFullCaseInviteTriggerRequest": "invite_id",
    "RejectInviteActorToCaseReceivedEvent": "case_id invite_id object_id sender_id<-actor_id",
    "RejectInviteActorToFullCaseReceivedEvent": "case_id invite_id invitee_id object_id sender_id<-actor_id",
    "RejectInviteToEmbargoOnCaseReceivedEvent": "case_id embargo embargo_id invite_id object_id sender_id<-actor_id",
    "RejectLogEntryReceivedEvent": "object_id sender_id<-actor_id",
    "RejectOfferCaseParticipantReceivedEvent": "case_id object_id sender_id<-actor_id",
    "RejectReportTriggerRequest": "offer_id",
    "RemoveCaseParticipantFromCaseReceivedEvent": "case_id object_id participant_id sender_id<-actor_id",
    "RemoveEmbargoEventFromCaseReceivedEvent": "case_id embargo embargo_id object_id sender_id<-actor_id",
    "RemoveNoteFromCaseReceivedEvent": "case_id note_id object_id sender_id<-actor_id",
    "SetStubSummaryTriggerRequest": "case_id",
    "SubmitReportReceivedEvent": "object_id report_id sender_id<-actor_id",
    "SubmitReportTriggerRequest": "",
    "SuggestActorToCaseTriggerRequest": "case_id",
    "SyncLogEntryTriggerRequest": "case_id object_id",
    "TentativeRejectFullCaseInviteTriggerRequest": "invite_id",
    "TentativeRejectInviteActorToFullCaseReceivedEvent": "case_id invite_id invitee_id object_id sender_id<-actor_id",
    "TerminateEmbargoTriggerRequest": "case_id",
    "UndoCaseOwnershipTransferReceivedEvent": "case_id object_id proposal_id sender_id<-actor_id",
    "UndoInviteToEmbargoOnCaseReceivedEvent": "case_id embargo_id invite_id object_id sender_id<-actor_id",
    "UnknownReceivedEvent": "object_id sender_id<-actor_id",
    "UnresolvableObjectReceivedEvent": "object_id sender_id<-actor_id",
    "UpdateCaseOwnerReceivedEvent": "case_id object_id sender_id<-actor_id",
    "UpdateCaseParticipantReceivedEvent": "case_id object_id participant_id sender_id<-actor_id",
    "UpdateEmbargoConsentReceivedEvent": "case_id object_id sender_id<-actor_id",
    "ValidateReportReceivedEvent": "object_id offer_id report_id sender_id<-actor_id",
    "ValidateReportTriggerRequest": "offer_id",
    "WithdrawCaseOwnershipTransferTriggerRequest": "offer_id",
    "WithdrawEmbargoTriggerRequest": "case_id",
    "WithdrawFromEmbargoOnCaseReceivedEvent": "case_id embargo embargo_id object_id sender_id<-actor_id",
    "_FullCaseInviteReplyEvent": "case_id invite_id invitee_id object_id sender_id<-actor_id",
    "_OwnerEmbargoDecisionEvent": "case_id embargo embargo_id object_id sender_id<-actor_id",
}
