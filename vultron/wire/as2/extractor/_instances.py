"""ActivityPattern instances for all Vultron semantic dispatch entries.

Each constant named ``<TypeName>Pattern`` corresponds to one
``MessageSemantics`` value and is imported by the
``vultron.semantic_registry`` sub-modules to build ``SEMANTIC_REGISTRY``.

Pattern ordering does **not** matter here — ordering is enforced by the
registry in ``vultron/semantic_registry/``.
"""

from vultron.enums.object_types import VultronObjectType as VOtype
from vultron.wire.as2.enums import (
    as_ObjectType as AOtype,
    as_TransitiveActivityType as TAtype,
)
from vultron.wire.as2.extractor._pattern import (
    ActivityPattern,
    InlineActivityObjectPattern,
    LedgerPositionReadPattern,
    ObjectForm,
)

# ---------------------------------------------------------------------------
# Embargo patterns
# ---------------------------------------------------------------------------

RemoveEmbargoEventFromCasePattern = ActivityPattern(
    description=(
        "Remove an embargo event from a vulnerability case. This is typically "
        "observed as a REMOVE activity where the object is an EVENT. The "
        "origin field of the activity contains the VulnerabilityCase from "
        "which the embargo is removed."
    ),
    activity_=TAtype.REMOVE,
    object_=AOtype.EVENT,
)
AnnounceEmbargoEventToCasePattern = ActivityPattern(
    description=(
        "Announce an embargo event to a vulnerability case. This is typically "
        "observed as an ANNOUNCE activity where the object is an EVENT and the "
        "context is a VULNERABILITY_CASE."
    ),
    activity_=TAtype.ANNOUNCE,
    object_=AOtype.EVENT,
    context_=VOtype.VULNERABILITY_CASE,
)
InviteToEmbargoOnCasePattern = ActivityPattern(
    description=(
        "Propose an embargo on a vulnerability case. "
        "This is observed as an INVITE activity where the object is an "
        "EmbargoEvent, the target is the invited Actor (ADR-0205) and the "
        "context is the VulnerabilityCase. "
        "Corresponds to EmProposeEmbargoActivity."
    ),
    activity_=TAtype.INVITE,
    object_=AOtype.EVENT,
    target_=AOtype.ACTOR,
    context_=VOtype.VULNERABILITY_CASE,
)
AcceptInviteToEmbargoOnCasePattern = ActivityPattern(
    description="Accept an invitation to an embargo on a vulnerability case.",
    activity_=TAtype.ACCEPT,
    object_=InviteToEmbargoOnCasePattern,
)
RejectInviteToEmbargoOnCasePattern = ActivityPattern(
    description="Reject an invitation to an embargo on a vulnerability case.",
    activity_=TAtype.REJECT,
    object_=InviteToEmbargoOnCasePattern,
)
CreateEmbargoEventPattern = ActivityPattern(
    description=(
        "The CASE_MANAGER records an embargo its case's creation wrote, such "
        "as the default embargo: a CREATE of the EmbargoEvent carrying it in "
        "full, right after the genesis entry (CLP-07-013).  The object must "
        "be an EmbargoEvent; a Create of any other Event is unrecognized."
    ),
    activity_=TAtype.CREATE,
    object_=VOtype.EMBARGO_EVENT,
)
CreateEmbargoConsentPattern = ActivityPattern(
    description=(
        "The CASE_MANAGER creates a participant's embargo consent row: a "
        "CREATE of the EmbargoConsent carrying the row in full (ADR-0122, "
        "CLP-07-013)."
    ),
    activity_=TAtype.CREATE,
    object_=VOtype.EMBARGO_CONSENT,
)
UpdateEmbargoConsentPattern = ActivityPattern(
    description=(
        "The CASE_MANAGER changes a participant's embargo consent row: an "
        "UPDATE of the EmbargoConsent carrying the row in full (ADR-0122, "
        "MSM-07-004)."
    ),
    activity_=TAtype.UPDATE,
    object_=VOtype.EMBARGO_CONSENT,
)
UndoInviteToEmbargoOnCasePattern = ActivityPattern(
    description=(
        "Withdraw an invitation to an embargo on a vulnerability case: an "
        "UNDO of the Invite the sender itself sent (ADR-0152).  The "
        "CASE_MANAGER sends it when it abandons an open proposal "
        "(EMB-16-001)."
    ),
    activity_=TAtype.UNDO,
    object_=InviteToEmbargoOnCasePattern,
)
ActivateEmbargoOnCasePattern = ActivityPattern(
    description=(
        "The case owner activates a proposed embargo on a vulnerability "
        "case: an ADD whose object is the EmbargoEvent itself and whose "
        "target is the VulnerabilityCase, the pair of the REMOVE that ends "
        "an embargo (ADR-0180)."
    ),
    activity_=TAtype.ADD,
    object_=AOtype.EVENT,
    target_=VOtype.VULNERABILITY_CASE,
    # target_ is lenient: the case target is a bare URI by design (the
    # recipient holds the case, so ``case_target_ref`` reduces it,
    # MV-10-001).  The ADD verb tells this activity from a participant's
    # ``Accept(Invite(EmbargoEvent))`` by type alone (ADR-0180); an embargo
    # the receiver cannot resolve is left a bare URI, which no object_ type
    # accepts (SE-01-006).
)
RejectEmbargoProposalOnCasePattern = ActivityPattern(
    description=(
        "The case owner rejects a proposed embargo on a vulnerability case: "
        "a REJECT whose object is the EmbargoEvent itself (not the Invite "
        "that proposed it, which it names in inReplyTo) and whose target "
        "is the VulnerabilityCase (ADR-0122, ADR-0180)."
    ),
    activity_=TAtype.REJECT,
    object_=AOtype.EVENT,
    target_=VOtype.VULNERABILITY_CASE,
    # target_ lenient, for the same reason as the activation pattern above.
)

WithdrawFromEmbargoOnCasePattern = ActivityPattern(
    description=(
        "A signatory withdraws from the embargo in force on a vulnerability "
        "case: a LEAVE whose object is the EmbargoEvent and whose context is "
        "the VulnerabilityCase (MSM-07-010, ADR-0122).  Distinct from "
        "Leave(VulnerabilityCase), which leaves the case."
    ),
    activity_=TAtype.LEAVE,
    object_=AOtype.EVENT,
    context_=VOtype.VULNERABILITY_CASE,
)

# ---------------------------------------------------------------------------
# Report patterns
# ---------------------------------------------------------------------------

CreateReportPattern = ActivityPattern(
    description=(
        "Create a vulnerability report. This is the initial step in the "
        "vulnerability disclosure process, where a finder creates a report to "
        "disclose a vulnerability. It may not always be observed directly, as "
        "it could be implicit in the OFFER of the report."
    ),
    activity_=TAtype.CREATE,
    object_=VOtype.VULNERABILITY_REPORT,
)
ReportSubmissionPattern = ActivityPattern(
    description=(
        "Submit a vulnerability report for validation. This is typically "
        "observed as an OFFER of a VULNERABILITY_REPORT, which represents the "
        "submission of the report to a coordinator or vendor for validation."
    ),
    activity_=TAtype.OFFER,
    object_=VOtype.VULNERABILITY_REPORT,
)
AckReportPattern = ActivityPattern(
    activity_=TAtype.READ, object_=ReportSubmissionPattern
)
ValidateReportPattern = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=ReportSubmissionPattern
)
InvalidateReportPattern = ActivityPattern(
    activity_=TAtype.TENTATIVE_REJECT, object_=ReportSubmissionPattern
)
CloseReportPattern = ActivityPattern(
    activity_=TAtype.REJECT, object_=ReportSubmissionPattern
)

# ---------------------------------------------------------------------------
# Case patterns
# ---------------------------------------------------------------------------

CreateCaseActivityPattern = ActivityPattern(
    activity_=TAtype.CREATE, object_=VOtype.VULNERABILITY_CASE
)
UpdateCaseOwnerPattern = ActivityPattern(
    description=(
        "The CASE_MANAGER names a new Case Owner on a vulnerability case: an "
        "UPDATE of the case carrying its new attributedTo, its own act on an "
        "ownership transfer (CM-21-024, CLP-07-013)."
    ),
    activity_=TAtype.UPDATE,
    object_=VOtype.VULNERABILITY_CASE,
)
EngageCasePattern = ActivityPattern(
    description=(
        "Actor engages (joins) a VulnerabilityCase, transitioning their RM "
        "state to ACCEPTED."
    ),
    activity_=TAtype.JOIN,
    object_=VOtype.VULNERABILITY_CASE,
)
DeferCasePattern = ActivityPattern(
    description=(
        "Actor defers (ignores) a VulnerabilityCase, transitioning their RM "
        "state to DEFERRED."
    ),
    activity_=TAtype.IGNORE,
    object_=VOtype.VULNERABILITY_CASE,
)
AddReportToCaseActivityPattern = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.VULNERABILITY_REPORT,
    target_=VOtype.VULNERABILITY_CASE,
)

# ---------------------------------------------------------------------------
# CaseProposal patterns (CP-03-001 through CP-03-004)
# ---------------------------------------------------------------------------

CreateCaseProposalPattern = ActivityPattern(
    description=(
        "Report receiver requests case initialization at a case-actor service "
        "by creating a CaseProposal object. "
        "Corresponds to Create(CaseProposal) — CP-03-001."
    ),
    activity_=TAtype.CREATE,
    object_=VOtype.CASE_PROPOSAL,
)
AcceptCaseProposalPattern = ActivityPattern(
    description=(
        "Case-actor service accepts a report receiver's CaseProposal. "
        "Corresponds to Accept(CaseProposal) — CP-03-002."
    ),
    activity_=TAtype.ACCEPT,
    object_=VOtype.CASE_PROPOSAL,
)
RejectCaseProposalPattern = ActivityPattern(
    description=(
        "Case-actor service rejects a report receiver's CaseProposal. "
        "Corresponds to Reject(CaseProposal) — CP-03-003."
    ),
    activity_=TAtype.REJECT,
    object_=VOtype.CASE_PROPOSAL,
)

# ---------------------------------------------------------------------------
# Actor-suggestion and role-offer patterns
# ---------------------------------------------------------------------------

SuggestActorToCasePattern = ActivityPattern(
    activity_=TAtype.OFFER,
    object_=AOtype.ACTOR,
    target_=VOtype.VULNERABILITY_CASE,
)
AcceptSuggestActorToCasePattern = ActivityPattern(
    description=(
        "CASE_MANAGER Accept(Offer(Actor)[target=VulnerabilityCase])"
        " answering a recommender, "
        "received on the recommender's inbox (ACCEPT_ACTOR_RECOMMENDATION; "
        "CM-16-006, CM-16-009)."
    ),
    activity_=TAtype.ACCEPT,
    object_=SuggestActorToCasePattern,
)
RejectSuggestActorToCasePattern = ActivityPattern(
    description=(
        "CASE_MANAGER Reject(Offer(Actor)[target=VulnerabilityCase])"
        " answering a recommender, "
        "received on the recommender's inbox (REJECT_ACTOR_RECOMMENDATION; "
        "CM-16-007)."
    ),
    activity_=TAtype.REJECT,
    object_=SuggestActorToCasePattern,
)

# CaseActor-routed ADR-0026 patterns (CM-16)
OfferActorToCasePattern = ActivityPattern(
    description=(
        "Offer(CaseParticipant)[target=VulnerabilityCase], naming the "
        "actor and its roles, sent by the CaseActor to the Case Owner "
        "(CM-16-003/CM-16-004, ADR-0026). Used as the "
        "nested sub-pattern inside AcceptActorRecommendationPattern and "
        "RejectActorRecommendationPattern. Identified by object being "
        "CASE_PARTICIPANT."
    ),
    activity_=TAtype.OFFER,
    object_=VOtype.CASE_PARTICIPANT,
    target_=VOtype.VULNERABILITY_CASE,
)
AcceptActorRecommendationPattern = ActivityPattern(
    description=(
        "Case Owner Accept(Offer(CaseParticipant)) routed to CaseActor "
        "inbox per ADR-0026/CM-16-006. Routes ACCEPT_OFFER_CASE_PARTICIPANT; "
        "the CASE_MANAGER's answer to the recommender "
        "(ACCEPT_ACTOR_RECOMMENDATION) is AcceptSuggestActorToCasePattern."
    ),
    activity_=TAtype.ACCEPT,
    object_=OfferActorToCasePattern,
)
RejectActorRecommendationPattern = ActivityPattern(
    description=(
        "Case Owner Reject(Offer(CaseParticipant)) routed to CaseActor "
        "inbox per ADR-0026/CM-16-007. Routes REJECT_OFFER_CASE_PARTICIPANT; "
        "the CASE_MANAGER's answer to the recommender "
        "(REJECT_ACTOR_RECOMMENDATION) is RejectSuggestActorToCasePattern."
    ),
    activity_=TAtype.REJECT,
    object_=OfferActorToCasePattern,
)
OfferCaseParticipantRolePattern = ActivityPattern(
    description=(
        "Offer(CaseParticipantRole)[context=VulnerabilityCase], whose target "
        "is the actor offered the role — the canonical role-delegation "
        "wire format introduced in ADR-0039. "
        "Replaces the deprecated Offer(VulnerabilityCase)[target=CaseParticipant] "
        "format. Self-describing: the object type unambiguously identifies this "
        "as a role offer. See SE-08-003."
    ),
    activity_=TAtype.OFFER,
    object_=VOtype.CASE_PARTICIPANT_ROLE,
    context_=VOtype.VULNERABILITY_CASE,
)
AcceptCaseParticipantRolePattern = ActivityPattern(
    description=(
        "Accept(Offer(CaseParticipantRole)[context=VulnerabilityCase])"
        " — acceptance of the canonical "
        "role-delegation wire format (ADR-0039). Received by the case's "
        "CASE_MANAGER when the target actor accepts the role (CM-33-015). "
        "See SE-08-003."
    ),
    activity_=TAtype.ACCEPT,
    object_=OfferCaseParticipantRolePattern,
)
RejectCaseParticipantRolePattern = ActivityPattern(
    description=(
        "Reject(Offer(CaseParticipantRole)[context=VulnerabilityCase])"
        " — rejection of the canonical "
        "role-delegation wire format (ADR-0039). Received by the case's "
        "CASE_MANAGER when the target actor declines the role (CM-33-015). "
        "See SE-08-003."
    ),
    activity_=TAtype.REJECT,
    object_=OfferCaseParticipantRolePattern,
)

# ---------------------------------------------------------------------------
# Case ownership transfer patterns
# ---------------------------------------------------------------------------

OfferCaseOwnershipTransferActivityPattern = ActivityPattern(
    activity_=TAtype.OFFER, object_=VOtype.VULNERABILITY_CASE
)
AcceptCaseOwnershipTransferActivityPattern = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=OfferCaseOwnershipTransferActivityPattern
)
RejectCaseOwnershipTransferActivityPattern = ActivityPattern(
    activity_=TAtype.REJECT, object_=OfferCaseOwnershipTransferActivityPattern
)
ProposeCaseOwnershipTransferActivityPattern = ActivityPattern(
    description=(
        "Offer(Offer(VulnerabilityCase)) — the Case Owner proposes an "
        "ownership transfer to the CASE_MANAGER, which makes the one "
        "Offer(VulnerabilityCase) the transferee answers (ADR-0148, "
        "CM-21-005).  Told apart from that Offer by its shape: its object "
        "is an Offer, not a case."
    ),
    activity_=TAtype.OFFER,
    object_=OfferCaseOwnershipTransferActivityPattern,
)
UndoCaseOwnershipTransferActivityPattern = ActivityPattern(
    description=(
        "Undo(Offer(Offer(VulnerabilityCase))) — the Case Owner withdraws "
        "its ownership-transfer proposal, and with it the Offer the "
        "CASE_MANAGER made from it (CM-21-015, ADR-0148)."
    ),
    activity_=TAtype.UNDO,
    object_=ProposeCaseOwnershipTransferActivityPattern,
)

# ---------------------------------------------------------------------------
# Case membership / invite patterns
# ---------------------------------------------------------------------------

InviteActorToCasePattern = ActivityPattern(
    description=(
        "The stub Invite: Invite(VulnerabilityCase preview)[target=Actor]"
        " (VAM-04-004, ADR-0205).  Its object is the case's typed reference"
        " carrying the case's preview, the case stub (CM-17-010), which"
        " object_form requires (SE-01-009): the form, not the type, tells it"
        " from the full-case Invite."
    ),
    activity_=TAtype.INVITE,
    object_=VOtype.VULNERABILITY_CASE,
    object_form=ObjectForm.PREVIEWED_REFERENCE,
    target_=AOtype.ACTOR,
)
AcceptInviteActorToCasePattern = ActivityPattern(
    description=(
        "Accept(Invite(VulnerabilityCase preview)[target=Actor])"
        " (VAM-04-005): the nested stub Invite's form tells it from the RV"
        " reply to the full-case Invite."
    ),
    activity_=TAtype.ACCEPT,
    object_=InviteActorToCasePattern,
)
RejectInviteActorToCasePattern = ActivityPattern(
    description=(
        "Reject(Invite(VulnerabilityCase preview)[target=Actor])"
        " (VAM-04-006): the nested stub Invite's form tells it from the RC"
        " reply to the full-case Invite."
    ),
    activity_=TAtype.REJECT,
    object_=InviteActorToCasePattern,
)
InviteActorToFullCasePattern = ActivityPattern(
    description=(
        "The full-case Invite: Invite(whole VulnerabilityCase)[target=Actor]"
        " (VAM-04-011, CM-11-010, ADR-0205).  Its object is the whole case,"
        " which object_form requires (SE-01-009), so the stub Invite's"
        " previewed reference does not match."
    ),
    activity_=TAtype.INVITE,
    object_=VOtype.VULNERABILITY_CASE,
    object_form=ObjectForm.WHOLE_OBJECT,
    target_=AOtype.ACTOR,
)
AcceptInviteActorToFullCasePattern = ActivityPattern(
    description=(
        "RV: Accept(Invite(whole VulnerabilityCase)[target=Actor])"
        " (VAM-04-012)."
    ),
    activity_=TAtype.ACCEPT,
    object_=InviteActorToFullCasePattern,
)
TentativeRejectInviteActorToFullCasePattern = ActivityPattern(
    description=(
        "RI: TentativeReject(Invite(whole VulnerabilityCase)[target=Actor])"
        " (VAM-04-013).  The stub Invite has no TentativeReject (CM-11-028)."
    ),
    activity_=TAtype.TENTATIVE_REJECT,
    object_=InviteActorToFullCasePattern,
)
RejectInviteActorToFullCasePattern = ActivityPattern(
    description=(
        "RC: Reject(Invite(whole VulnerabilityCase)[target=Actor])"
        " (VAM-04-014)."
    ),
    activity_=TAtype.REJECT,
    object_=InviteActorToFullCasePattern,
)
CloseCasePattern = ActivityPattern(
    activity_=TAtype.LEAVE, object_=VOtype.VULNERABILITY_CASE
)

# ---------------------------------------------------------------------------
# Case log / announcement patterns
# ---------------------------------------------------------------------------

AddLogEntryToLedgerPattern = ActivityPattern(
    description=(
        "The CASE_MANAGER adds a committed CaseLedgerEntry to the case's "
        "ledger, <case>/ledger, for log replication (ADR-0204). The object is "
        "a CaseLedgerEntry object; the target is the ledger's id."
    ),
    activity_=TAtype.ADD,
    object_=VOtype.CASE_LEDGER_ENTRY,
    # No target_ constraint: the ledger is an identity only, a bare IRI no
    # vocabulary type describes, and no other Add carries a CaseLedgerEntry.
    # The event checks the target names the entry's own ledger (SYNC-02-006).
)
AnnounceVulnerabilityCasePattern = ActivityPattern(
    description=(
        "Case owner announces full VulnerabilityCase details to a newly "
        "accepted invitee (MV-10-003). The object is a VulnerabilityCase."
    ),
    activity_=TAtype.ANNOUNCE,
    object_=VOtype.VULNERABILITY_CASE,
)
RejectLogEntryPattern = ActivityPattern(
    description=(
        "Participant rejects a CaseLedgerEntry announcement due to "
        "hash-chain mismatch: the object is the rejected CaseLedgerEntry, and "
        "inReplyTo names the Add that carried it (SYNC-03-001, ADR-0204)."
    ),
    activity_=TAtype.REJECT,
    object_=VOtype.CASE_LEDGER_ENTRY,
)
ReadLedgerPattern = LedgerPositionReadPattern(
    description=(
        "Participant states its ledger position: a Read whose object is the "
        "case's ledger, the OrderedCollection <case>/ledger, whose context is "
        "the case and whose ledgerPosition is the sender's tail, at index -1 "
        "when it holds no entry (SYNC-17-001, ADR-0204)."
    ),
    activity_=TAtype.READ,
    object_=AOtype.ORDERED_COLLECTION,
    context_=VOtype.VULNERABILITY_CASE,
)
RefusalNoticePattern = InlineActivityObjectPattern(
    description=(
        "The CASE_MANAGER's refusal notice: a Refuse whose object is the "
        "refused activity, inline (CLP-05-001, ADR-0196).  Any verb: a "
        "Refuse is never a decline, so a Refuse of an Invite or an Offer is "
        "a refusal notice too, and a Reject matches no part of it."
    ),
    activity_=TAtype.REFUSE,
)

# ---------------------------------------------------------------------------
# Note patterns
# ---------------------------------------------------------------------------

AddNoteToCaseActivityPattern = ActivityPattern(
    activity_=TAtype.ADD,
    object_=AOtype.NOTE,
    target_=VOtype.VULNERABILITY_CASE,
)
RemoveNoteFromCasePattern = ActivityPattern(
    description=(
        "Remove a note from a vulnerability case. A Remove names the "
        "collection it takes its object from in origin, so the case is the "
        "activity's origin, not its target."
    ),
    activity_=TAtype.REMOVE,
    object_=AOtype.NOTE,
    origin_=VOtype.VULNERABILITY_CASE,
)

# ---------------------------------------------------------------------------
# Case participant patterns
# ---------------------------------------------------------------------------

AddCaseParticipantToCasePattern = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.CASE_PARTICIPANT,
    target_=VOtype.VULNERABILITY_CASE,
)
RemoveCaseParticipantFromCasePattern = ActivityPattern(
    activity_=TAtype.REMOVE,
    object_=VOtype.CASE_PARTICIPANT,
    target_=VOtype.VULNERABILITY_CASE,
)
CreateCaseParticipantPattern = ActivityPattern(
    description=(
        "The CASE_MANAGER creates a participant record: a CREATE of the "
        "CaseParticipant carrying the record in full (ADR-0114, CLP-07-021)."
    ),
    activity_=TAtype.CREATE,
    object_=VOtype.CASE_PARTICIPANT,
)
UpdateCaseParticipantPattern = ActivityPattern(
    description=(
        "The CASE_MANAGER changes a participant record: an UPDATE of the "
        "CaseParticipant carrying the record in full (CLP-07-021)."
    ),
    activity_=TAtype.UPDATE,
    object_=VOtype.CASE_PARTICIPANT,
)

# ---------------------------------------------------------------------------
# ProcessingFault patterns (ASK-07-001, ADR-0080)
# ---------------------------------------------------------------------------

CreateProcessingFaultPattern = ActivityPattern(
    description=(
        "Receiver notifies an authenticated sender that their status assertion "
        "could not be processed. "
        "Corresponds to Create(ProcessingFault) — ASK-07-001, ADR-0080."
    ),
    activity_=TAtype.CREATE,
    object_=VOtype.PROCESSING_FAULT,
)

# ---------------------------------------------------------------------------
# Case status / participant status patterns
# ---------------------------------------------------------------------------

AddCaseStatusToCasePattern = ActivityPattern(
    description=(
        "The CASE_MANAGER adds a case status to the case's status history: "
        "an ADD whose target is <case>/statuses, an ordered collection whose "
        "newest item is the current status, and whose context is the case "
        "(ADR-0204)."
    ),
    activity_=TAtype.ADD,
    object_=VOtype.CASE_STATUS,
    target_=AOtype.ORDERED_COLLECTION,
    context_=VOtype.VULNERABILITY_CASE,
)
AddVulnerabilityItemToCasePattern = ActivityPattern(
    description=(
        "The CASE_MANAGER adds a vulnerability item to a vulnerability case: "
        "an ADD carrying the item in full, its own record of an item it "
        "brought into the case (CLP-07-021)."
    ),
    activity_=TAtype.ADD,
    object_=VOtype.VULNERABILITY_ITEM,
    target_=VOtype.VULNERABILITY_CASE,
)
AddCaseReferenceToCasePattern = ActivityPattern(
    description=(
        "The CASE_MANAGER adds a case reference to a vulnerability case: an "
        "ADD carrying the reference in full, its own record of a reference it "
        "brought into the case (CLP-07-021)."
    ),
    activity_=TAtype.ADD,
    object_=VOtype.CASE_REFERENCE,
    target_=VOtype.VULNERABILITY_CASE,
)
AddParticipantStatusToParticipantPattern = ActivityPattern(
    description=(
        "A participant status is added to the participant's status history: "
        "an ADD whose target is <participant>/statuses, an ordered collection "
        "whose newest item is the current status, and whose context is the "
        "case (ADR-0204)."
    ),
    activity_=TAtype.ADD,
    object_=VOtype.PARTICIPANT_STATUS,
    target_=AOtype.ORDERED_COLLECTION,
    context_=VOtype.VULNERABILITY_CASE,
)
