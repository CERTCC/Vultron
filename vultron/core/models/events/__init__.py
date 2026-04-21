"""Domain event vocabulary for the Vultron Protocol.

Defines the authoritative vocabulary of semantic intents that can occur
in the system, as understood by the domain layer.

Public surface:
- MessageSemantics — enum of all recognised semantic types
- VultronEvent — base class for all per-semantic inbound domain events
- Per-semantic *ReceivedEvent classes imported from category submodules
"""

from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptSuggestActorToCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectSuggestActorToCaseReceivedEvent,
    SuggestActorToCaseReceivedEvent,
)
from vultron.core.models.events.base import (
    MessageSemantics,
    VultronEvent,
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
from vultron.core.models.events.unknown import UnknownReceivedEvent

__all__ = [
    "MessageSemantics",
    "VultronEvent",
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
    "SuggestActorToCaseReceivedEvent",
    "AcceptSuggestActorToCaseReceivedEvent",
    "RejectSuggestActorToCaseReceivedEvent",
    "OfferCaseOwnershipTransferReceivedEvent",
    "AcceptCaseOwnershipTransferReceivedEvent",
    "RejectCaseOwnershipTransferReceivedEvent",
    "InviteActorToCaseReceivedEvent",
    "AcceptInviteActorToCaseReceivedEvent",
    "RejectInviteActorToCaseReceivedEvent",
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
    # sync
    "AnnounceLogEntryReceivedEvent",
    "RejectLogEntryReceivedEvent",
]
