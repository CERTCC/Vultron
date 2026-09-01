"""Domain event vocabulary for the Vultron Protocol.

Defines the authoritative vocabulary of semantic intents that can occur
in the system, as understood by the domain layer.

Public surface:
- MessageSemantics — enum of all recognised semantic types
- VultronEvent — base class for all per-semantic inbound domain events
- AnyReceivedEvent — Union of all concrete VultronEvent subclasses (discriminated
  by ``semantic_type``); use as the return annotation for extract_intent /
  extract_event so callers can narrow to a concrete type via isinstance.
- Per-semantic *ReceivedEvent classes imported from category submodules
- Case-context resolution helpers used by the inbox deferral/replay path
"""

from typing import Union

from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptCaseParticipantRoleReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptOfferCaseParticipantReceivedEvent,
    AnnounceVulnerabilityCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    OfferActorToCaseReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    OfferCaseParticipantRoleReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectCaseParticipantRoleReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
)
from vultron.core.models.events.case_proposal import (
    AcceptCaseProposalReceivedEvent,
    CreateCaseProposalReceivedEvent,
    RejectCaseProposalReceivedEvent,
)
from vultron.core.models.events.base import (
    MessageSemantics,
    VultronEvent,
)
from vultron.core.models.events.case_context import (
    CASE_BOOTSTRAP_SEMANTICS,
    is_case_bootstrap,
    resolve_case_context_id,
)
from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CloseCaseReceivedEvent,
    CreateCaseReceivedEvent,
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
    UpdateCaseReceivedEvent,
)
from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
)
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    AddEmbargoEventToCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.models.events.note import (
    AddNoteToCaseReceivedEvent,
    CreateNoteReceivedEvent,
    RemoveNoteFromCaseReceivedEvent,
)
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
    SubmitReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.models.events.status import (
    AddCaseStatusToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
    CreateCaseStatusReceivedEvent,
    CreateParticipantStatusReceivedEvent,
)
from vultron.core.models.events.sync import (
    AnnounceLogEntryReceivedEvent,
    RejectLogEntryReceivedEvent,
)
from vultron.core.models.events.fault import (
    CreateProcessingFaultReceivedEvent,
)
from vultron.core.models.events.unknown import (
    UnknownReceivedEvent,
    UnresolvableObjectReceivedEvent,
)

AnyReceivedEvent = Union[
    # report
    CreateReportReceivedEvent,
    SubmitReportReceivedEvent,
    ValidateReportReceivedEvent,
    InvalidateReportReceivedEvent,
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    # case
    CreateCaseReceivedEvent,
    UpdateCaseReceivedEvent,
    EngageCaseReceivedEvent,
    DeferCaseReceivedEvent,
    AddReportToCaseReceivedEvent,
    CloseCaseReceivedEvent,
    # actor
    OfferActorToCaseReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    AcceptOfferCaseParticipantReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
    OfferCaseParticipantRoleReceivedEvent,
    AcceptCaseParticipantRoleReceivedEvent,
    RejectCaseParticipantRoleReceivedEvent,
    AnnounceVulnerabilityCaseReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    AcceptCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    InviteActorToCaseReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    # case_proposal
    CreateCaseProposalReceivedEvent,
    AcceptCaseProposalReceivedEvent,
    RejectCaseProposalReceivedEvent,
    # case_participant
    CreateCaseParticipantReceivedEvent,
    AddCaseParticipantToCaseReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
    # embargo
    CreateEmbargoEventReceivedEvent,
    AddEmbargoEventToCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    # note
    CreateNoteReceivedEvent,
    AddNoteToCaseReceivedEvent,
    RemoveNoteFromCaseReceivedEvent,
    # status
    CreateCaseStatusReceivedEvent,
    AddCaseStatusToCaseReceivedEvent,
    CreateParticipantStatusReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
    # sync
    AnnounceLogEntryReceivedEvent,
    RejectLogEntryReceivedEvent,
    # fault
    CreateProcessingFaultReceivedEvent,
    # unknown
    UnknownReceivedEvent,
    UnresolvableObjectReceivedEvent,
]

__all__ = [
    "MessageSemantics",
    "VultronEvent",
    "AnyReceivedEvent",
    # case-context resolution
    "CASE_BOOTSTRAP_SEMANTICS",
    "is_case_bootstrap",
    "resolve_case_context_id",
    # report
    "CreateReportReceivedEvent",
    "SubmitReportReceivedEvent",
    "ValidateReportReceivedEvent",
    "InvalidateReportReceivedEvent",
    "AckReportReceivedEvent",
    "CloseReportReceivedEvent",
    # case
    "CreateCaseReceivedEvent",
    "UpdateCaseReceivedEvent",
    "EngageCaseReceivedEvent",
    "DeferCaseReceivedEvent",
    "AddReportToCaseReceivedEvent",
    "CloseCaseReceivedEvent",
    # actor
    "OfferActorToCaseReceivedEvent",
    "OfferCaseParticipantReceivedEvent",
    "AcceptOfferCaseParticipantReceivedEvent",
    "RejectOfferCaseParticipantReceivedEvent",
    "OfferCaseParticipantRoleReceivedEvent",
    "AcceptCaseParticipantRoleReceivedEvent",
    "RejectCaseParticipantRoleReceivedEvent",
    "AnnounceVulnerabilityCaseReceivedEvent",
    "OfferCaseOwnershipTransferReceivedEvent",
    "AcceptCaseOwnershipTransferReceivedEvent",
    "RejectCaseOwnershipTransferReceivedEvent",
    "InviteActorToCaseReceivedEvent",
    "AcceptInviteActorToCaseReceivedEvent",
    "RejectInviteActorToCaseReceivedEvent",
    # case_proposal
    "CreateCaseProposalReceivedEvent",
    "AcceptCaseProposalReceivedEvent",
    "RejectCaseProposalReceivedEvent",
    # case_participant
    "CreateCaseParticipantReceivedEvent",
    "AddCaseParticipantToCaseReceivedEvent",
    "RemoveCaseParticipantFromCaseReceivedEvent",
    # embargo
    "CreateEmbargoEventReceivedEvent",
    "AddEmbargoEventToCaseReceivedEvent",
    "RemoveEmbargoEventFromCaseReceivedEvent",
    "AnnounceEmbargoEventToCaseReceivedEvent",
    "InviteToEmbargoOnCaseReceivedEvent",
    "AcceptInviteToEmbargoOnCaseReceivedEvent",
    "RejectInviteToEmbargoOnCaseReceivedEvent",
    # note
    "CreateNoteReceivedEvent",
    "AddNoteToCaseReceivedEvent",
    "RemoveNoteFromCaseReceivedEvent",
    # status
    "CreateCaseStatusReceivedEvent",
    "AddCaseStatusToCaseReceivedEvent",
    "CreateParticipantStatusReceivedEvent",
    "AddParticipantStatusToParticipantReceivedEvent",
    # unknown
    "UnknownReceivedEvent",
    "UnresolvableObjectReceivedEvent",
    # sync
    "AnnounceLogEntryReceivedEvent",
    "RejectLogEntryReceivedEvent",
    # fault
    "CreateProcessingFaultReceivedEvent",
]
