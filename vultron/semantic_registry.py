"""Consolidated semantic dispatch registry for the Vultron Protocol.

``SEMANTIC_REGISTRY`` is the single source of truth that maps each
``MessageSemantics`` value to the five components needed to process an
inbound ActivityStreams activity:

- ``pattern`` — wire-layer ``ActivityPattern`` for recognising the activity
- ``event_class`` — core domain ``VultronEvent`` subclass to construct
- ``use_case_class`` — core use-case class to execute
- ``wire_activity_class`` — wire-layer ``as_Activity`` subclass for
  DataLayer coercion (may be ``None`` for types without a specific wire class)
- ``include_activity`` — whether to populate ``VultronEvent.activity``
  during extraction (replaces the old ``_ACTIVITY_SEMANTICS`` set)

Ordering of entries in ``SEMANTIC_REGISTRY`` matches the previously-defined
``SEMANTICS_ACTIVITY_PATTERNS`` ordering — more specific patterns before
general ones, ``UNKNOWN`` last.

This module is a neutral layer importable by wire, core, adapter, and test
code.  ``extractor.py`` must NOT import from this module (it provides the
``ActivityPattern`` instances imported here).

Public API
----------
``SEMANTIC_REGISTRY`` — ordered list of ``SemanticEntry`` values
``find_matching_semantics(activity)`` — iterates ``SEMANTIC_REGISTRY`` directly
``extract_event(activity)`` — convenience wrapper: pattern-match + extract
``lookup_entry(semantics)`` — O(1) entry lookup by ``MessageSemantics``
"""

from dataclasses import dataclass, field

from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptSuggestActorToCaseReceivedEvent,
    AnnounceVulnerabilityCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectSuggestActorToCaseReceivedEvent,
    SuggestActorToCaseReceivedEvent,
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
from vultron.core.models.events.unknown import (
    UnknownReceivedEvent,
    UnresolvableObjectReceivedEvent,
)
from vultron.core.use_cases.received.actor import (
    AcceptCaseOwnershipTransferReceivedUseCase,
    AcceptInviteActorToCaseReceivedUseCase,
    AcceptSuggestActorToCaseReceivedUseCase,
    AnnounceVulnerabilityCaseReceivedUseCase,
    InviteActorToCaseReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    RejectInviteActorToCaseReceivedUseCase,
    RejectSuggestActorToCaseReceivedUseCase,
    SuggestActorToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case import (
    AddReportToCaseReceivedUseCase,
    CloseCaseReceivedUseCase,
    CreateCaseReceivedUseCase,
    DeferCaseReceivedUseCase,
    EngageCaseReceivedUseCase,
    UpdateCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case_participant import (
    AddCaseParticipantToCaseReceivedUseCase,
    CreateCaseParticipantReceivedUseCase,
    RemoveCaseParticipantFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    AddEmbargoEventToCaseReceivedUseCase,
    AnnounceEmbargoEventToCaseReceivedUseCase,
    CreateEmbargoEventReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.note import (
    AddNoteToCaseReceivedUseCase,
    CreateNoteReceivedUseCase,
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.report import (
    AckReportReceivedUseCase,
    CloseReportReceivedUseCase,
    CreateReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
    SubmitReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
    AddParticipantStatusToParticipantReceivedUseCase,
    CreateCaseStatusReceivedUseCase,
    CreateParticipantStatusReceivedUseCase,
)
from vultron.core.use_cases.received.sync import (
    AnnounceLogEntryReceivedUseCase,
    RejectLogEntryReceivedUseCase,
)
from vultron.core.use_cases.received.unknown import (
    UnknownUseCase,
    UnresolvableObjectUseCase,
)
from vultron.wire.as2.extractor import (
    AcceptCaseOwnershipTransferActivityPattern,
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
    ActivityPattern,
    AnnounceEmbargoEventToCasePattern,
    AnnounceLogEntryPattern,
    CloseCasePattern,
    CloseReportPattern,
    CreateCaseActivityPattern,
    CreateCaseParticipantPattern,
    CreateCaseStatusActivityPattern,
    CreateEmbargoEventPattern,
    CreateNotePattern,
    CreateParticipantStatusPattern,
    CreateReportPattern,
    DeferCasePattern,
    EngageCasePattern,
    InvalidateReportPattern,
    InviteActorToCasePattern,
    InviteToEmbargoOnCasePattern,
    AnnounceVulnerabilityCasePattern,
    OfferCaseOwnershipTransferActivityPattern,
    RejectCaseOwnershipTransferActivityPattern,
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
from vultron.wire.as2.vocab.activities.actor import (
    AcceptActorRecommendationActivity,
    RecommendActorActivity,
    RejectActorRecommendationActivity,
)
from vultron.wire.as2.vocab.activities.case import (
    AcceptCaseOwnershipTransferActivity,
    AddNoteToCaseActivity,
    AddReportToCaseActivity,
    AddStatusToCaseActivity,
    CreateCaseActivity,
    CreateCaseStatusActivity,
    OfferCaseOwnershipTransferActivity,
    RejectCaseOwnershipTransferActivity,
    RmAcceptInviteToCaseActivity,
    RmCloseCaseActivity,
    RmDeferCaseActivity,
    RmEngageCaseActivity,
    RmInviteToCaseActivity,
    RmRejectInviteToCaseActivity,
    UpdateCaseActivity,
    AnnounceVulnerabilityCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
    AddStatusToParticipantActivity,
    CreateParticipantActivity,
    CreateStatusForParticipantActivity,
    RemoveParticipantFromCaseActivity,
)
from vultron.wire.as2.vocab.activities.embargo import (
    AddEmbargoToCaseActivity,
    AnnounceEmbargoActivity,
    EmAcceptEmbargoActivity,
    EmProposeEmbargoActivity,
    EmRejectEmbargoActivity,
    RemoveEmbargoFromCaseActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmCloseReportActivity,
    RmCreateReportActivity,
    RmInvalidateReportActivity,
    RmReadReportActivity,
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.activities.sync import (
    AnnounceLogEntryActivity,
    RejectLogEntryActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity


@dataclass(frozen=True)
class SemanticEntry:
    """All dispatch components for a single ``MessageSemantics`` value.

    Attributes:
        semantics: The semantic intent this entry describes.
        pattern: Wire-layer pattern for matching the incoming activity.
            ``None`` for the ``UNKNOWN`` fallback entry.
        event_class: Domain event class to construct from the matched activity.
        use_case_class: Use-case class to execute for this semantic type.
        wire_activity_class: Specific wire ``as_Activity`` subclass for
            DataLayer coercion. ``None`` when no specific wire class exists.
        include_activity: When ``True``, ``extract_intent()`` populates
            ``VultronEvent.activity`` for this semantic type.
    """

    semantics: MessageSemantics
    pattern: ActivityPattern | None
    event_class: type[VultronEvent]
    use_case_class: type
    wire_activity_class: type[as_Activity] | None = field(default=None)
    include_activity: bool = field(default=False)


# ---------------------------------------------------------------------------
# The registry.  Order matters: find_matching_semantics() returns the first
# pattern that matches, so more specific patterns must appear before general
# ones.  The UNKNOWN fallback (pattern=None) must be last.
# ---------------------------------------------------------------------------

SEMANTIC_REGISTRY: list[SemanticEntry] = [
    # Order matches the previous SEMANTICS_ACTIVITY_PATTERNS dict — do not
    # reorder without verifying pattern-matching correctness.
    # --- Report ---
    SemanticEntry(
        semantics=MessageSemantics.CREATE_REPORT,
        pattern=CreateReportPattern,
        event_class=CreateReportReceivedEvent,
        use_case_class=CreateReportReceivedUseCase,
        wire_activity_class=RmCreateReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.SUBMIT_REPORT,
        pattern=ReportSubmissionPattern,
        event_class=SubmitReportReceivedEvent,
        use_case_class=SubmitReportReceivedUseCase,
        wire_activity_class=RmSubmitReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACK_REPORT,
        pattern=AckReportPattern,
        event_class=AckReportReceivedEvent,
        use_case_class=AckReportReceivedUseCase,
        wire_activity_class=RmReadReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.VALIDATE_REPORT,
        pattern=ValidateReportPattern,
        event_class=ValidateReportReceivedEvent,
        use_case_class=ValidateReportReceivedUseCase,
        wire_activity_class=RmValidateReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVALIDATE_REPORT,
        pattern=InvalidateReportPattern,
        event_class=InvalidateReportReceivedEvent,
        use_case_class=InvalidateReportReceivedUseCase,
        wire_activity_class=RmInvalidateReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.CLOSE_REPORT,
        pattern=CloseReportPattern,
        event_class=CloseReportReceivedEvent,
        use_case_class=CloseReportReceivedUseCase,
        wire_activity_class=RmCloseReportActivity,
        include_activity=True,
    ),
    # --- Case ---
    SemanticEntry(
        semantics=MessageSemantics.CREATE_CASE,
        pattern=CreateCaseActivityPattern,
        event_class=CreateCaseReceivedEvent,
        use_case_class=CreateCaseReceivedUseCase,
        wire_activity_class=CreateCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.UPDATE_CASE,
        pattern=UpdateCaseActivityPattern,
        event_class=UpdateCaseReceivedEvent,
        use_case_class=UpdateCaseReceivedUseCase,
        wire_activity_class=UpdateCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ENGAGE_CASE,
        pattern=EngageCasePattern,
        event_class=EngageCaseReceivedEvent,
        use_case_class=EngageCaseReceivedUseCase,
        wire_activity_class=RmEngageCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.DEFER_CASE,
        pattern=DeferCasePattern,
        event_class=DeferCaseReceivedEvent,
        use_case_class=DeferCaseReceivedUseCase,
        wire_activity_class=RmDeferCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_REPORT_TO_CASE,
        pattern=AddReportToCaseActivityPattern,
        event_class=AddReportToCaseReceivedEvent,
        use_case_class=AddReportToCaseReceivedUseCase,
        wire_activity_class=AddReportToCaseActivity,
    ),
    # --- Actor / participant management ---
    SemanticEntry(
        semantics=MessageSemantics.SUGGEST_ACTOR_TO_CASE,
        pattern=SuggestActorToCasePattern,
        event_class=SuggestActorToCaseReceivedEvent,
        use_case_class=SuggestActorToCaseReceivedUseCase,
        wire_activity_class=RecommendActorActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE,
        pattern=AcceptSuggestActorToCasePattern,
        event_class=AcceptSuggestActorToCaseReceivedEvent,
        use_case_class=AcceptSuggestActorToCaseReceivedUseCase,
        wire_activity_class=AcceptActorRecommendationActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE,
        pattern=RejectSuggestActorToCasePattern,
        event_class=RejectSuggestActorToCaseReceivedEvent,
        use_case_class=RejectSuggestActorToCaseReceivedUseCase,
        wire_activity_class=RejectActorRecommendationActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
        pattern=OfferCaseOwnershipTransferActivityPattern,
        event_class=OfferCaseOwnershipTransferReceivedEvent,
        use_case_class=OfferCaseOwnershipTransferReceivedUseCase,
        wire_activity_class=OfferCaseOwnershipTransferActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        pattern=AcceptCaseOwnershipTransferActivityPattern,
        event_class=AcceptCaseOwnershipTransferReceivedEvent,
        use_case_class=AcceptCaseOwnershipTransferReceivedUseCase,
        wire_activity_class=AcceptCaseOwnershipTransferActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
        pattern=RejectCaseOwnershipTransferActivityPattern,
        event_class=RejectCaseOwnershipTransferReceivedEvent,
        use_case_class=RejectCaseOwnershipTransferReceivedUseCase,
        wire_activity_class=RejectCaseOwnershipTransferActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVITE_ACTOR_TO_CASE,
        pattern=InviteActorToCasePattern,
        event_class=InviteActorToCaseReceivedEvent,
        use_case_class=InviteActorToCaseReceivedUseCase,
        wire_activity_class=RmInviteToCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        pattern=AcceptInviteActorToCasePattern,
        event_class=AcceptInviteActorToCaseReceivedEvent,
        use_case_class=AcceptInviteActorToCaseReceivedUseCase,
        wire_activity_class=RmAcceptInviteToCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE,
        pattern=RejectInviteActorToCasePattern,
        event_class=RejectInviteActorToCaseReceivedEvent,
        use_case_class=RejectInviteActorToCaseReceivedUseCase,
        wire_activity_class=RmRejectInviteToCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ANNOUNCE_VULNERABILITY_CASE,
        pattern=AnnounceVulnerabilityCasePattern,
        event_class=AnnounceVulnerabilityCaseReceivedEvent,
        use_case_class=AnnounceVulnerabilityCaseReceivedUseCase,
        wire_activity_class=AnnounceVulnerabilityCaseActivity,
        include_activity=True,
    ),
    # --- Embargo ---
    SemanticEntry(
        semantics=MessageSemantics.CREATE_EMBARGO_EVENT,
        pattern=CreateEmbargoEventPattern,
        event_class=CreateEmbargoEventReceivedEvent,
        use_case_class=CreateEmbargoEventReceivedUseCase,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE,
        pattern=AddEmbargoEventToCasePattern,
        event_class=AddEmbargoEventToCaseReceivedEvent,
        use_case_class=AddEmbargoEventToCaseReceivedUseCase,
        wire_activity_class=AddEmbargoToCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
        pattern=RemoveEmbargoEventFromCasePattern,
        event_class=RemoveEmbargoEventFromCaseReceivedEvent,
        use_case_class=RemoveEmbargoEventFromCaseReceivedUseCase,
        wire_activity_class=RemoveEmbargoFromCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE,
        pattern=AnnounceEmbargoEventToCasePattern,
        event_class=AnnounceEmbargoEventToCaseReceivedEvent,
        use_case_class=AnnounceEmbargoEventToCaseReceivedUseCase,
        wire_activity_class=AnnounceEmbargoActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        pattern=InviteToEmbargoOnCasePattern,
        event_class=InviteToEmbargoOnCaseReceivedEvent,
        use_case_class=InviteToEmbargoOnCaseReceivedUseCase,
        wire_activity_class=EmProposeEmbargoActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        pattern=AcceptInviteToEmbargoOnCasePattern,
        event_class=AcceptInviteToEmbargoOnCaseReceivedEvent,
        use_case_class=AcceptInviteToEmbargoOnCaseReceivedUseCase,
        wire_activity_class=EmAcceptEmbargoActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        pattern=RejectInviteToEmbargoOnCasePattern,
        event_class=RejectInviteToEmbargoOnCaseReceivedEvent,
        use_case_class=RejectInviteToEmbargoOnCaseReceivedUseCase,
        wire_activity_class=EmRejectEmbargoActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.CLOSE_CASE,
        pattern=CloseCasePattern,
        event_class=CloseCaseReceivedEvent,
        use_case_class=CloseCaseReceivedUseCase,
        wire_activity_class=RmCloseCaseActivity,
    ),
    # --- Sync / log ---
    SemanticEntry(
        semantics=MessageSemantics.ANNOUNCE_CASE_LOG_ENTRY,
        pattern=AnnounceLogEntryPattern,
        event_class=AnnounceLogEntryReceivedEvent,
        use_case_class=AnnounceLogEntryReceivedUseCase,
        wire_activity_class=AnnounceLogEntryActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_CASE_LOG_ENTRY,
        pattern=RejectLogEntryPattern,
        event_class=RejectLogEntryReceivedEvent,
        use_case_class=RejectLogEntryReceivedUseCase,
        wire_activity_class=RejectLogEntryActivity,
    ),
    # --- Case participant ---
    SemanticEntry(
        semantics=MessageSemantics.CREATE_CASE_PARTICIPANT,
        pattern=CreateCaseParticipantPattern,
        event_class=CreateCaseParticipantReceivedEvent,
        use_case_class=CreateCaseParticipantReceivedUseCase,
        wire_activity_class=CreateParticipantActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE,
        pattern=AddCaseParticipantToCasePattern,
        event_class=AddCaseParticipantToCaseReceivedEvent,
        use_case_class=AddCaseParticipantToCaseReceivedUseCase,
        wire_activity_class=AddParticipantToCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
        pattern=RemoveCaseParticipantFromCasePattern,
        event_class=RemoveCaseParticipantFromCaseReceivedEvent,
        use_case_class=RemoveCaseParticipantFromCaseReceivedUseCase,
        wire_activity_class=RemoveParticipantFromCaseActivity,
    ),
    # --- Note ---
    SemanticEntry(
        semantics=MessageSemantics.CREATE_NOTE,
        pattern=CreateNotePattern,
        event_class=CreateNoteReceivedEvent,
        use_case_class=CreateNoteReceivedUseCase,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_NOTE_TO_CASE,
        pattern=AddNoteToCaseActivityPattern,
        event_class=AddNoteToCaseReceivedEvent,
        use_case_class=AddNoteToCaseReceivedUseCase,
        wire_activity_class=AddNoteToCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_NOTE_FROM_CASE,
        pattern=RemoveNoteFromCasePattern,
        event_class=RemoveNoteFromCaseReceivedEvent,
        use_case_class=RemoveNoteFromCaseReceivedUseCase,
    ),
    # --- Case status ---
    SemanticEntry(
        semantics=MessageSemantics.CREATE_CASE_STATUS,
        pattern=CreateCaseStatusActivityPattern,
        event_class=CreateCaseStatusReceivedEvent,
        use_case_class=CreateCaseStatusReceivedUseCase,
        wire_activity_class=CreateCaseStatusActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_CASE_STATUS_TO_CASE,
        pattern=AddCaseStatusToCasePattern,
        event_class=AddCaseStatusToCaseReceivedEvent,
        use_case_class=AddCaseStatusToCaseReceivedUseCase,
        wire_activity_class=AddStatusToCaseActivity,
    ),
    # --- Participant status ---
    SemanticEntry(
        semantics=MessageSemantics.CREATE_PARTICIPANT_STATUS,
        pattern=CreateParticipantStatusPattern,
        event_class=CreateParticipantStatusReceivedEvent,
        use_case_class=CreateParticipantStatusReceivedUseCase,
        wire_activity_class=CreateStatusForParticipantActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        pattern=AddParticipantStatusToParticipantPattern,
        event_class=AddParticipantStatusToParticipantReceivedEvent,
        use_case_class=AddParticipantStatusToParticipantReceivedUseCase,
        wire_activity_class=AddStatusToParticipantActivity,
    ),
    # --- Unresolvable object_ (before UNKNOWN fallback) ---
    SemanticEntry(
        semantics=MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
        pattern=None,
        event_class=UnresolvableObjectReceivedEvent,
        use_case_class=UnresolvableObjectUseCase,
        wire_activity_class=None,
        include_activity=True,
    ),
    # --- Unknown (fallback, must be last) ---
    SemanticEntry(
        semantics=MessageSemantics.UNKNOWN,
        pattern=None,
        event_class=UnknownReceivedEvent,
        use_case_class=UnknownUseCase,
        wire_activity_class=None,
    ),
]

# ---------------------------------------------------------------------------
# Fast-lookup index: O(1) entry access by MessageSemantics value.
# ---------------------------------------------------------------------------

_ENTRY_MAP: dict[MessageSemantics, SemanticEntry] = {
    e.semantics: e for e in SEMANTIC_REGISTRY
}

# Frozenset of activity type strings that have at least one registered pattern.
# Used by find_matching_semantics() to distinguish "known type with unresolvable
# object_" from "genuinely unknown activity type".
_ACTIVITY_TYPES_WITH_PATTERNS: frozenset[str] = frozenset(
    str(e.pattern.activity_)
    for e in SEMANTIC_REGISTRY
    if e.pattern is not None
)


def lookup_entry(semantics: MessageSemantics) -> SemanticEntry:
    """Return the ``SemanticEntry`` for *semantics*.

    Falls back to the ``UNKNOWN`` entry when *semantics* is not registered
    (which should not happen in practice).
    """
    return _ENTRY_MAP.get(semantics, _ENTRY_MAP[MessageSemantics.UNKNOWN])


from vultron.wire.as2.extractor import (  # noqa: E402
    extract_intent as _extract_intent,
)

__all__ = [
    "SemanticEntry",
    "SEMANTIC_REGISTRY",
    "lookup_entry",
    "find_matching_semantics",
    "matches_semantics",
    "extract_event",
    "use_case_map",
    "semantics_to_activity_class",
]


def extract_event(
    activity: as_Activity,
) -> VultronEvent:
    """Extract a typed ``VultronEvent`` from an AS2 activity.

    This is the public entry point for the inbound activity pipeline.  It
    combines pattern matching (``find_matching_semantics``) with field
    extraction (``extract_intent``) using the registry entry for the matched
    semantics.

    Args:
        activity: The rehydrated AS2 activity to process.

    Returns:
        A concrete ``VultronEvent`` subclass populated with domain fields.
    """
    semantics = find_matching_semantics(activity)
    entry = lookup_entry(semantics)
    return _extract_intent(
        activity,
        semantics=semantics,
        event_class=entry.event_class,
        include_activity=entry.include_activity,
    )


def use_case_map() -> dict[MessageSemantics, type]:
    """Return a mapping of ``MessageSemantics`` → use-case class.

    Equivalent to the old ``USE_CASE_MAP`` dict.  Used by the dispatcher
    initializer to build its routing table.
    """
    return {e.semantics: e.use_case_class for e in SEMANTIC_REGISTRY}


def semantics_to_activity_class() -> dict[MessageSemantics, type[as_Activity]]:
    """Return a mapping of ``MessageSemantics`` → wire activity class.

    Equivalent to the old ``SEMANTICS_TO_ACTIVITY_CLASS`` dict.  Used by the
    DataLayer adapter to coerce stored rows back to typed AS2 activities.
    Only entries with a non-``None`` ``wire_activity_class`` are included.
    """
    return {
        e.semantics: e.wire_activity_class
        for e in SEMANTIC_REGISTRY
        if e.wire_activity_class is not None
    }


def find_matching_semantics(activity: as_Activity) -> MessageSemantics:
    """Find the MessageSemantics for the given AS2 activity.

    Iterates ``SEMANTIC_REGISTRY`` in order and returns the first match.
    Returns ``MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT`` when no pattern
    matches, the activity type is registered (has patterns), and ``object_``
    is still a bare string URI (rehydration did not resolve it).
    Returns ``MessageSemantics.UNKNOWN`` when the activity type is not
    registered at all.

    ``SEMANTIC_REGISTRY`` is the single source of truth for pattern-match order;
    more specific patterns must appear before general ones.

    Args:
        activity: The AS2 activity to classify.

    Returns:
        The matching MessageSemantics value, or MessageSemantics.UNKNOWN.
    """
    for entry in SEMANTIC_REGISTRY:
        if entry.pattern is not None and entry.pattern.match(activity):
            return entry.semantics
    obj = getattr(activity, "object_", None)
    activity_type = str(activity.type_) if activity.type_ else ""
    if isinstance(obj, str) and activity_type in _ACTIVITY_TYPES_WITH_PATTERNS:
        return MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    return MessageSemantics.UNKNOWN


def matches_semantics(
    activity: as_Activity,
    expected: MessageSemantics,
) -> bool:
    """Return True if *activity* matches the *expected* MessageSemantics.

    Convenience predicate for test authors — eliminates the need to import
    named ``*Pattern`` constants just to assert semantic identity.

    Args:
        activity: The AS2 activity to classify.
        expected: The expected ``MessageSemantics`` value.

    Returns:
        True when ``find_matching_semantics(activity) == expected``.
    """
    return find_matching_semantics(activity) == expected
