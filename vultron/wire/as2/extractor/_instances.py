"""ActivityPattern instances for all Vultron semantic dispatch entries.

Each constant named ``<TypeName>Pattern`` corresponds to one
``MessageSemantics`` value and is imported by the
``vultron.semantic_registry`` sub-modules to build ``SEMANTIC_REGISTRY``.

Pattern ordering does **not** matter here — ordering is enforced by the
registry in ``vultron/semantic_registry/``.
"""

from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.wire.as2.enums import (
    as_ObjectType as AOtype,
    as_TransitiveActivityType as TAtype,
)
from vultron.wire.as2.extractor._pattern import ActivityPattern

# ---------------------------------------------------------------------------
# Embargo patterns
# ---------------------------------------------------------------------------

CreateEmbargoEventPattern = ActivityPattern(
    description=(
        "Create an embargo event. This is the initial step in the embargo "
        "management process, where a coordinator creates an embargo event to "
        "manage the embargo on a vulnerability case."
    ),
    activity_=TAtype.CREATE,
    object_=AOtype.EVENT,
    context_=VOtype.VULNERABILITY_CASE,
)
AddEmbargoEventToCasePattern = ActivityPattern(
    description=(
        "Add an embargo event to a vulnerability case. This is typically "
        "observed as an ADD activity where the object is an EVENT and the "
        "target is a VULNERABILITY_CASE."
    ),
    activity_=TAtype.ADD,
    object_=AOtype.EVENT,
    target_=VOtype.VULNERABILITY_CASE,
)
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
        "EmbargoEvent and the context is the VulnerabilityCase. "
        "Corresponds to EmProposeEmbargoActivity."
    ),
    activity_=TAtype.INVITE,
    object_=AOtype.EVENT,
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
UpdateCaseActivityPattern = ActivityPattern(
    activity_=TAtype.UPDATE, object_=VOtype.VULNERABILITY_CASE
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
        "Vendor actor requests case initialization at a case-actor service "
        "by creating a CaseProposal object. "
        "Corresponds to Create(as_CaseProposal) — CP-03-001."
    ),
    activity_=TAtype.CREATE,
    object_=VOtype.CASE_PROPOSAL,
)
AcceptCaseProposalPattern = ActivityPattern(
    description=(
        "Case-actor service accepts a vendor's CaseProposal. "
        "Corresponds to Accept(as_CaseProposal) — CP-03-002."
    ),
    activity_=TAtype.ACCEPT,
    object_=VOtype.CASE_PROPOSAL,
)
RejectCaseProposalPattern = ActivityPattern(
    description=(
        "Case-actor service rejects a vendor's CaseProposal. "
        "Corresponds to Reject(as_CaseProposal) — CP-03-003."
    ),
    activity_=TAtype.REJECT,
    object_=VOtype.CASE_PROPOSAL,
)

# ---------------------------------------------------------------------------
# Actor-suggestion and case-manager-role patterns
# ---------------------------------------------------------------------------

SuggestActorToCasePattern = ActivityPattern(
    activity_=TAtype.OFFER,
    object_=AOtype.ACTOR,
    target_=VOtype.VULNERABILITY_CASE,
)
AcceptSuggestActorToCasePattern = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=SuggestActorToCasePattern
)
RejectSuggestActorToCasePattern = ActivityPattern(
    activity_=TAtype.REJECT, object_=SuggestActorToCasePattern
)
OfferCaseManagerRolePattern = ActivityPattern(
    description=(
        "Vendor offers the CASE_MANAGER role to a Case Actor participant. "
        "Distinct from OFFER_CASE_OWNERSHIP_TRANSFER: the offering actor "
        "retains CASE_OWNER; only operational management authority is "
        "delegated. Identified by target being a CASE_PARTICIPANT record. "
        "See DEMOMA-08-002, DEMOMA-08-003."
    ),
    activity_=TAtype.OFFER,
    object_=VOtype.VULNERABILITY_CASE,
    target_=VOtype.CASE_PARTICIPANT,
)
AcceptCaseManagerRolePattern = ActivityPattern(
    description="Case Actor accepted the CASE_MANAGER role delegation offer.",
    activity_=TAtype.ACCEPT,
    object_=OfferCaseManagerRolePattern,
)
RejectCaseManagerRolePattern = ActivityPattern(
    description="Case Actor rejected the CASE_MANAGER role delegation offer.",
    activity_=TAtype.REJECT,
    object_=OfferCaseManagerRolePattern,
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

# ---------------------------------------------------------------------------
# Case membership / invite patterns
# ---------------------------------------------------------------------------

InviteActorToCasePattern = ActivityPattern(
    activity_=TAtype.INVITE,
    object_=AOtype.ACTOR,
    target_=VOtype.VULNERABILITY_CASE,
)
AcceptInviteActorToCasePattern = ActivityPattern(
    activity_=TAtype.ACCEPT,
    object_=InviteActorToCasePattern,
)
RejectInviteActorToCasePattern = ActivityPattern(
    activity_=TAtype.REJECT,
    object_=InviteActorToCasePattern,
)
CloseCasePattern = ActivityPattern(
    activity_=TAtype.LEAVE, object_=VOtype.VULNERABILITY_CASE
)

# ---------------------------------------------------------------------------
# Case log / announcement patterns
# ---------------------------------------------------------------------------

AnnounceLogEntryPattern = ActivityPattern(
    description=(
        "Announce a canonical CaseLedgerEntry to a participant for log "
        "replication. The object is a CaseLedgerEntry object."
    ),
    activity_=TAtype.ANNOUNCE,
    object_=VOtype.CASE_LEDGER_ENTRY,
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
        "hash-chain mismatch. The object is the rejected CaseLedgerEntry."
    ),
    activity_=TAtype.REJECT,
    object_=VOtype.CASE_LEDGER_ENTRY,
)

# ---------------------------------------------------------------------------
# Note patterns
# ---------------------------------------------------------------------------

CreateNotePattern = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=AOtype.NOTE,
)
AddNoteToCaseActivityPattern = ActivityPattern(
    activity_=TAtype.ADD,
    object_=AOtype.NOTE,
    target_=VOtype.VULNERABILITY_CASE,
)
RemoveNoteFromCasePattern = ActivityPattern(
    activity_=TAtype.REMOVE,
    object_=AOtype.NOTE,
    target_=VOtype.VULNERABILITY_CASE,
)

# ---------------------------------------------------------------------------
# Case participant patterns
# ---------------------------------------------------------------------------

CreateCaseParticipantPattern = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=VOtype.CASE_PARTICIPANT,
    context_=VOtype.VULNERABILITY_CASE,
)
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

# ---------------------------------------------------------------------------
# Case status / participant status patterns
# ---------------------------------------------------------------------------

CreateCaseStatusActivityPattern = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=VOtype.CASE_STATUS,
    context_=VOtype.VULNERABILITY_CASE,
)
AddCaseStatusToCasePattern = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.CASE_STATUS,
    target_=VOtype.VULNERABILITY_CASE,
)
CreateParticipantStatusPattern = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=VOtype.PARTICIPANT_STATUS,
)
AddParticipantStatusToParticipantPattern = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.PARTICIPANT_STATUS,
    target_=VOtype.CASE_PARTICIPANT,
)
