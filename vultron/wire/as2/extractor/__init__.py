"""AS2 wire layer semantic extractor for the Vultron Protocol.

Maps AS2 activity structures to domain MessageSemantics. This is the sole
location where AS2 vocabulary is translated to domain concepts (ARCH-03-001).
This is stage 3 of the inbound pipeline: typed AS2 activity → MessageSemantics.

This package replaces the former single-file ``extractor.py``.  It is split
into focused submodules:

- ``_pattern`` — ``ActivityPattern`` class and ``_match_activity_field``
  helper
- ``_instances`` — all ``*Pattern`` module-level constants
- ``_builders`` — private field-extraction helpers and domain-object builders
- ``_extract`` — ``extract_intent`` (the sole AS2 → domain translation point)

Public re-exports below preserve the original import paths so all existing
callers continue to work without change (CS-18-003, AC-4).
"""

# Pattern class
from vultron.wire.as2.extractor._pattern import ActivityPattern  # noqa: F401

# Domain-event extractor
from vultron.wire.as2.extractor._extract import extract_intent  # noqa: F401

# Pattern instances — all exported so semantic_registry sub-modules and tests
# can continue to import directly from vultron.wire.as2.extractor.
from vultron.wire.as2.extractor._instances import (  # noqa: F401
    AcceptCaseManagerRolePattern,
    AcceptCaseOwnershipTransferActivityPattern,
    AcceptCaseProposalPattern,
    AcceptInviteActorToCasePattern,
    AcceptInviteToEmbargoOnCasePattern,
    AcceptSuggestActorToCasePattern,
    AckReportPattern,
    AddCaseParticipantToCasePattern,
    AddCaseStatusToCasePattern,
    AddEmbargoEventToCasePattern,
    AddNoteToCaseActivityPattern,
    AddParticipantStatusToParticipantPattern,
    AddReportToCaseActivityPattern,
    AnnounceEmbargoEventToCasePattern,
    AnnounceLogEntryPattern,
    AnnounceVulnerabilityCasePattern,
    CloseCasePattern,
    CloseReportPattern,
    CreateCaseActivityPattern,
    CreateCaseParticipantPattern,
    CreateCaseProposalPattern,
    CreateCaseStatusActivityPattern,
    CreateEmbargoEventPattern,
    CreateNotePattern,
    CreateParticipantStatusPattern,
    CreateReportPattern,
    DeferCasePattern,
    EngageCasePattern,
    InviteActorToCasePattern,
    InviteToEmbargoOnCasePattern,
    InvalidateReportPattern,
    OfferCaseManagerRolePattern,
    OfferCaseOwnershipTransferActivityPattern,
    RejectCaseManagerRolePattern,
    RejectCaseOwnershipTransferActivityPattern,
    RejectCaseProposalPattern,
    RejectInviteActorToCasePattern,
    RejectInviteToEmbargoOnCasePattern,
    RejectLogEntryPattern,
    RejectSuggestActorToCasePattern,
    RemoveCaseParticipantFromCasePattern,
    RemoveEmbargoEventFromCasePattern,
    RemoveNoteFromCasePattern,
    ReportSubmissionPattern,
    SuggestActorToCasePattern,
    UpdateCaseActivityPattern,
    ValidateReportPattern,
)

__all__ = [
    # Pattern class
    "ActivityPattern",
    # Extractor
    "extract_intent",
    # Pattern instances
    "AcceptCaseManagerRolePattern",
    "AcceptCaseOwnershipTransferActivityPattern",
    "AcceptCaseProposalPattern",
    "AcceptInviteActorToCasePattern",
    "AcceptInviteToEmbargoOnCasePattern",
    "AcceptSuggestActorToCasePattern",
    "AckReportPattern",
    "AddCaseParticipantToCasePattern",
    "AddCaseStatusToCasePattern",
    "AddEmbargoEventToCasePattern",
    "AddNoteToCaseActivityPattern",
    "AddParticipantStatusToParticipantPattern",
    "AddReportToCaseActivityPattern",
    "AnnounceEmbargoEventToCasePattern",
    "AnnounceLogEntryPattern",
    "AnnounceVulnerabilityCasePattern",
    "CloseCasePattern",
    "CloseReportPattern",
    "CreateCaseActivityPattern",
    "CreateCaseParticipantPattern",
    "CreateCaseProposalPattern",
    "CreateCaseStatusActivityPattern",
    "CreateEmbargoEventPattern",
    "CreateNotePattern",
    "CreateParticipantStatusPattern",
    "CreateReportPattern",
    "DeferCasePattern",
    "EngageCasePattern",
    "InviteActorToCasePattern",
    "InviteToEmbargoOnCasePattern",
    "InvalidateReportPattern",
    "OfferCaseManagerRolePattern",
    "OfferCaseOwnershipTransferActivityPattern",
    "RejectCaseManagerRolePattern",
    "RejectCaseOwnershipTransferActivityPattern",
    "RejectCaseProposalPattern",
    "RejectInviteActorToCasePattern",
    "RejectInviteToEmbargoOnCasePattern",
    "RejectLogEntryPattern",
    "RejectSuggestActorToCasePattern",
    "RemoveCaseParticipantFromCasePattern",
    "RemoveEmbargoEventFromCasePattern",
    "RemoveNoteFromCasePattern",
    "ReportSubmissionPattern",
    "SuggestActorToCasePattern",
    "UpdateCaseActivityPattern",
    "ValidateReportPattern",
]
