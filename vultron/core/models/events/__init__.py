"""Domain event vocabulary for the Vultron Protocol.

Defines the authoritative vocabulary of semantic intents that can occur
in the system, as understood by the domain layer.

Public surface:
- MessageSemantics — enum of all recognised semantic types
- VultronEvent — base class for all per-semantic inbound domain events
- EVENT_CLASS_MAP — mapping from MessageSemantics to its concrete event class
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
from vultron.core.models.events.unknown import UnknownReceivedEvent

# Maps each MessageSemantics value to its concrete VultronEvent subclass.
# Used by extract_intent() in the wire layer to construct the right domain event.
EVENT_CLASS_MAP: dict[MessageSemantics, type[VultronEvent]] = {
    MessageSemantics.CREATE_REPORT: CreateReportReceivedEvent,
    MessageSemantics.SUBMIT_REPORT: SubmitReportReceivedEvent,
    MessageSemantics.VALIDATE_REPORT: ValidateReportReceivedEvent,
    MessageSemantics.INVALIDATE_REPORT: InvalidateReportReceivedEvent,
    MessageSemantics.ACK_REPORT: AckReportReceivedEvent,
    MessageSemantics.CLOSE_REPORT: CloseReportReceivedEvent,
    MessageSemantics.CREATE_CASE: CreateCaseReceivedEvent,
    MessageSemantics.UPDATE_CASE: UpdateCaseReceivedEvent,
    MessageSemantics.ENGAGE_CASE: EngageCaseReceivedEvent,
    MessageSemantics.DEFER_CASE: DeferCaseReceivedEvent,
    MessageSemantics.ADD_REPORT_TO_CASE: AddReportToCaseReceivedEvent,
    MessageSemantics.SUGGEST_ACTOR_TO_CASE: SuggestActorToCaseReceivedEvent,
    MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE: AcceptSuggestActorToCaseReceivedEvent,
    MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE: RejectSuggestActorToCaseReceivedEvent,
    MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER: OfferCaseOwnershipTransferReceivedEvent,
    MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER: AcceptCaseOwnershipTransferReceivedEvent,
    MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER: RejectCaseOwnershipTransferReceivedEvent,
    MessageSemantics.INVITE_ACTOR_TO_CASE: InviteActorToCaseReceivedEvent,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: AcceptInviteActorToCaseReceivedEvent,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: RejectInviteActorToCaseReceivedEvent,
    MessageSemantics.CREATE_EMBARGO_EVENT: CreateEmbargoEventReceivedEvent,
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE: AddEmbargoEventToCaseReceivedEvent,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: RemoveEmbargoEventFromCaseReceivedEvent,
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE: AnnounceEmbargoEventToCaseReceivedEvent,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: InviteToEmbargoOnCaseReceivedEvent,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: AcceptInviteToEmbargoOnCaseReceivedEvent,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: RejectInviteToEmbargoOnCaseReceivedEvent,
    MessageSemantics.CLOSE_CASE: CloseCaseReceivedEvent,
    MessageSemantics.CREATE_CASE_PARTICIPANT: CreateCaseParticipantReceivedEvent,
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE: AddCaseParticipantToCaseReceivedEvent,
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE: RemoveCaseParticipantFromCaseReceivedEvent,
    MessageSemantics.CREATE_NOTE: CreateNoteReceivedEvent,
    MessageSemantics.ADD_NOTE_TO_CASE: AddNoteToCaseReceivedEvent,
    MessageSemantics.REMOVE_NOTE_FROM_CASE: RemoveNoteFromCaseReceivedEvent,
    MessageSemantics.CREATE_CASE_STATUS: CreateCaseStatusReceivedEvent,
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: AddCaseStatusToCaseReceivedEvent,
    MessageSemantics.CREATE_PARTICIPANT_STATUS: CreateParticipantStatusReceivedEvent,
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: AddParticipantStatusToParticipantReceivedEvent,
    MessageSemantics.UNKNOWN: UnknownReceivedEvent,
}

__all__ = [
    "MessageSemantics",
    "VultronEvent",
    "EVENT_CLASS_MAP",
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
]
