"""AS2 wire layer semantic extractor for the Vultron Protocol.

Maps AS2 activity structures to domain MessageSemantics. This is the sole
location where AS2 vocabulary is translated to domain concepts (ARCH-03-001).
This is stage 3 of the inbound pipeline: typed AS2 activity → MessageSemantics.

Consolidates ActivityPattern definitions (formerly in vultron/activity_patterns.py)
and the SEMANTICS_ACTIVITY_PATTERNS mapping + find_matching_semantics function
(formerly in vultron/semantic_map.py) into a single extractor module.
"""

from typing import Optional, Union

from pydantic import BaseModel

from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.wire.as2.enums import (
    as_IntransitiveActivityType as IAtype,
    as_ObjectType as AOtype,
    as_TransitiveActivityType as TAtype,
)


class ActivityPattern(BaseModel):
    """Represents a pattern to match against an AS2 activity for semantic dispatch.

    Supports nested patterns for activities whose object is itself an activity.
    """

    description: Optional[str] = None
    activity_: TAtype | IAtype

    to_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    object_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    target_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    context_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    in_reply_to_: Optional["ActivityPattern"] = None

    def match(self, activity: as_Activity) -> bool:
        """Return True if the given activity matches this pattern."""
        if self.activity_ != activity.as_type:
            return False

        def _match_field(pattern_field, activity_field) -> bool:
            if pattern_field is None:
                return True
            # URI/ID string reference: can't type-check, conservatively allow
            if isinstance(activity_field, str):
                return True
            if isinstance(pattern_field, ActivityPattern):
                return pattern_field.match(activity_field)
            return pattern_field == getattr(activity_field, "as_type", None)

        if not _match_field(
            self.object_, getattr(activity, "as_object", None)
        ):
            return False
        if not _match_field(self.target_, getattr(activity, "target", None)):
            return False
        if not _match_field(self.context_, getattr(activity, "context", None)):
            return False
        if not _match_field(self.to_, getattr(activity, "to", None)):
            return False
        if not _match_field(
            self.in_reply_to_, getattr(activity, "in_reply_to", None)
        ):
            return False

        return True


# ---------------------------------------------------------------------------
# Pattern instances (formerly in vultron/activity_patterns.py)
# ---------------------------------------------------------------------------

CreateEmbargoEvent = ActivityPattern(
    description=(
        "Create an embargo event. This is the initial step in the embargo "
        "management process, where a coordinator creates an embargo event to "
        "manage the embargo on a vulnerability case."
    ),
    activity_=TAtype.CREATE,
    object_=AOtype.EVENT,
    context_=VOtype.VULNERABILITY_CASE,
)
AddEmbargoEventToCase = ActivityPattern(
    description=(
        "Add an embargo event to a vulnerability case. This is typically "
        "observed as an ADD activity where the object is an EVENT and the "
        "target is a VULNERABILITY_CASE."
    ),
    activity_=TAtype.ADD,
    object_=AOtype.EVENT,
    target_=VOtype.VULNERABILITY_CASE,
)
RemoveEmbargoEventFromCase = ActivityPattern(
    description=(
        "Remove an embargo event from a vulnerability case. This is typically "
        "observed as a REMOVE activity where the object is an EVENT. The "
        "origin field of the activity contains the VulnerabilityCase from "
        "which the embargo is removed."
    ),
    activity_=TAtype.REMOVE,
    object_=AOtype.EVENT,
)
AnnounceEmbargoEventToCase = ActivityPattern(
    description=(
        "Announce an embargo event to a vulnerability case. This is typically "
        "observed as an ANNOUNCE activity where the object is an EVENT and the "
        "context is a VULNERABILITY_CASE."
    ),
    activity_=TAtype.ANNOUNCE,
    object_=AOtype.EVENT,
    context_=VOtype.VULNERABILITY_CASE,
)
InviteToEmbargoOnCase = ActivityPattern(
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
AcceptInviteToEmbargoOnCase = ActivityPattern(
    description="Accept an invitation to an embargo on a vulnerability case.",
    activity_=TAtype.ACCEPT,
    object_=InviteToEmbargoOnCase,
)
RejectInviteToEmbargoOnCase = ActivityPattern(
    description="Reject an invitation to an embargo on a vulnerability case.",
    activity_=TAtype.REJECT,
    object_=InviteToEmbargoOnCase,
)
CreateReport = ActivityPattern(
    description=(
        "Create a vulnerability report. This is the initial step in the "
        "vulnerability disclosure process, where a finder creates a report to "
        "disclose a vulnerability. It may not always be observed directly, as "
        "it could be implicit in the OFFER of the report."
    ),
    activity_=TAtype.CREATE,
    object_=VOtype.VULNERABILITY_REPORT,
)
ReportSubmission = ActivityPattern(
    description=(
        "Submit a vulnerability report for validation. This is typically "
        "observed as an OFFER of a VULNERABILITY_REPORT, which represents the "
        "submission of the report to a coordinator or vendor for validation."
    ),
    activity_=TAtype.OFFER,
    object_=VOtype.VULNERABILITY_REPORT,
)
AckReport = ActivityPattern(activity_=TAtype.READ, object_=ReportSubmission)
ValidateReport = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=ReportSubmission
)
InvalidateReport = ActivityPattern(
    activity_=TAtype.TENTATIVE_REJECT, object_=ReportSubmission
)
CloseReport = ActivityPattern(
    activity_=TAtype.REJECT, object_=ReportSubmission
)
CreateCaseActivity = ActivityPattern(
    activity_=TAtype.CREATE, object_=VOtype.VULNERABILITY_CASE
)
UpdateCaseActivity = ActivityPattern(
    activity_=TAtype.UPDATE, object_=VOtype.VULNERABILITY_CASE
)
EngageCase = ActivityPattern(
    description=(
        "Actor engages (joins) a VulnerabilityCase, transitioning their RM "
        "state to ACCEPTED."
    ),
    activity_=TAtype.JOIN,
    object_=VOtype.VULNERABILITY_CASE,
)
DeferCase = ActivityPattern(
    description=(
        "Actor defers (ignores) a VulnerabilityCase, transitioning their RM "
        "state to DEFERRED."
    ),
    activity_=TAtype.IGNORE,
    object_=VOtype.VULNERABILITY_CASE,
)
AddReportToCaseActivity = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.VULNERABILITY_REPORT,
    target_=VOtype.VULNERABILITY_CASE,
)
SuggestActorToCase = ActivityPattern(
    activity_=TAtype.OFFER,
    object_=AOtype.ACTOR,
    target_=VOtype.VULNERABILITY_CASE,
)
AcceptSuggestActorToCase = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=SuggestActorToCase
)
RejectSuggestActorToCase = ActivityPattern(
    activity_=TAtype.REJECT, object_=SuggestActorToCase
)
OfferCaseOwnershipTransferActivity = ActivityPattern(
    activity_=TAtype.OFFER, object_=VOtype.VULNERABILITY_CASE
)
AcceptCaseOwnershipTransferActivity = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=OfferCaseOwnershipTransferActivity
)
RejectCaseOwnershipTransferActivity = ActivityPattern(
    activity_=TAtype.REJECT, object_=OfferCaseOwnershipTransferActivity
)
InviteActorToCase = ActivityPattern(
    activity_=TAtype.INVITE,
    target_=VOtype.VULNERABILITY_CASE,
)
AcceptInviteActorToCase = ActivityPattern(
    activity_=TAtype.ACCEPT,
    object_=InviteActorToCase,
)
RejectInviteActorToCase = ActivityPattern(
    activity_=TAtype.REJECT,
    object_=InviteActorToCase,
)
CloseCase = ActivityPattern(
    activity_=TAtype.LEAVE, object_=VOtype.VULNERABILITY_CASE
)
CreateNote = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=AOtype.NOTE,
)
AddNoteToCaseActivity = ActivityPattern(
    activity_=TAtype.ADD,
    object_=AOtype.NOTE,
    target_=VOtype.VULNERABILITY_CASE,
)
RemoveNoteFromCase = ActivityPattern(
    activity_=TAtype.REMOVE,
    object_=AOtype.NOTE,
    target_=VOtype.VULNERABILITY_CASE,
)
CreateCaseParticipant = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=VOtype.CASE_PARTICIPANT,
    context_=VOtype.VULNERABILITY_CASE,
)
AddCaseParticipantToCase = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.CASE_PARTICIPANT,
    target_=VOtype.VULNERABILITY_CASE,
)
RemoveCaseParticipantFromCase = ActivityPattern(
    activity_=TAtype.REMOVE,
    object_=VOtype.CASE_PARTICIPANT,
    target_=VOtype.VULNERABILITY_CASE,
)
CreateCaseStatusActivity = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=VOtype.CASE_STATUS,
    context_=VOtype.VULNERABILITY_CASE,
)
AddCaseStatusToCase = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.CASE_STATUS,
    target_=VOtype.VULNERABILITY_CASE,
)
CreateParticipantStatus = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=VOtype.PARTICIPANT_STATUS,
)
AddParticipantStatusToParticipant = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.PARTICIPANT_STATUS,
    target_=VOtype.CASE_PARTICIPANT,
)


# ---------------------------------------------------------------------------
# Semantics → pattern mapping (formerly in vultron/semantic_map.py)
# The order of entries matters: find_matching_semantics returns the first match.
# ---------------------------------------------------------------------------

SEMANTICS_ACTIVITY_PATTERNS: dict[MessageSemantics, ActivityPattern] = {
    MessageSemantics.CREATE_REPORT: CreateReport,
    MessageSemantics.SUBMIT_REPORT: ReportSubmission,
    MessageSemantics.ACK_REPORT: AckReport,
    MessageSemantics.VALIDATE_REPORT: ValidateReport,
    MessageSemantics.INVALIDATE_REPORT: InvalidateReport,
    MessageSemantics.CLOSE_REPORT: CloseReport,
    MessageSemantics.CREATE_CASE: CreateCaseActivity,
    MessageSemantics.UPDATE_CASE: UpdateCaseActivity,
    MessageSemantics.ENGAGE_CASE: EngageCase,
    MessageSemantics.DEFER_CASE: DeferCase,
    MessageSemantics.ADD_REPORT_TO_CASE: AddReportToCaseActivity,
    MessageSemantics.SUGGEST_ACTOR_TO_CASE: SuggestActorToCase,
    MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE: AcceptSuggestActorToCase,
    MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE: RejectSuggestActorToCase,
    MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER: OfferCaseOwnershipTransferActivity,
    MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER: AcceptCaseOwnershipTransferActivity,
    MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER: RejectCaseOwnershipTransferActivity,
    MessageSemantics.INVITE_ACTOR_TO_CASE: InviteActorToCase,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: AcceptInviteActorToCase,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: RejectInviteActorToCase,
    MessageSemantics.CREATE_EMBARGO_EVENT: CreateEmbargoEvent,
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE: AddEmbargoEventToCase,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: RemoveEmbargoEventFromCase,
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE: AnnounceEmbargoEventToCase,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: InviteToEmbargoOnCase,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: AcceptInviteToEmbargoOnCase,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: RejectInviteToEmbargoOnCase,
    MessageSemantics.CLOSE_CASE: CloseCase,
    MessageSemantics.CREATE_CASE_PARTICIPANT: CreateCaseParticipant,
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE: AddCaseParticipantToCase,
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE: RemoveCaseParticipantFromCase,
    MessageSemantics.CREATE_NOTE: CreateNote,
    MessageSemantics.ADD_NOTE_TO_CASE: AddNoteToCaseActivity,
    MessageSemantics.REMOVE_NOTE_FROM_CASE: RemoveNoteFromCase,
    MessageSemantics.CREATE_CASE_STATUS: CreateCaseStatusActivity,
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: AddCaseStatusToCase,
    MessageSemantics.CREATE_PARTICIPANT_STATUS: CreateParticipantStatus,
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: AddParticipantStatusToParticipant,
}


def extract_intent(
    activity: as_Activity,
) -> "VultronEvent":
    """Extract semantic intent and domain fields from an AS2 activity.

    Returns a fully-populated per-semantic VultronEvent subclass with all
    relevant IDs and types extracted from the AS2 object graph.
    This is the sole point where AS2 wire types are translated to domain concepts.

    Args:
        activity: The AS2 activity to classify and extract from.

    Returns:
        A concrete VultronEvent subclass discriminated by MessageSemantics.
    """
    from vultron.core.models.events import EVENT_CLASS_MAP, VultronEvent

    semantics = find_matching_semantics(activity)

    def _get_id(field) -> str | None:
        if field is None:
            return None
        if isinstance(field, str):
            return field
        return getattr(field, "as_id", str(field)) or None

    def _get_type(field) -> str | None:
        if field is None or isinstance(field, str):
            return None
        t = getattr(field, "as_type", None)
        return str(t) if t is not None else None

    actor_id = _get_id(getattr(activity, "actor", None)) or ""
    obj = getattr(activity, "as_object", None)
    target = getattr(activity, "target", None)
    context = getattr(activity, "context", None)
    origin = getattr(activity, "origin", None)

    # Nested fields from activity.as_object (for Accept/Reject wrapping another activity)
    inner_obj = None
    inner_target = None
    inner_context = None
    if obj is not None and not isinstance(obj, str):
        inner_obj = getattr(obj, "as_object", None)
        inner_target = getattr(obj, "target", None)
        inner_context = getattr(obj, "context", None)

    event_class: type[VultronEvent] = EVENT_CLASS_MAP.get(
        semantics, EVENT_CLASS_MAP[MessageSemantics.UNKNOWN]
    )

    def _build_domain_kwargs() -> dict:
        from vultron.core.models.vultron_types import (
            VultronActivity,
            VultronCase,
            VultronEmbargoEvent,
            VultronNote,
            VultronParticipant,
            VultronParticipantStatus,
            VultronCaseStatus,
            VultronReport,
        )

        # Use as_type string comparison because the wire parser returns
        # as_Object (base class) for nested objects; isinstance checks against
        # Vultron subtypes (EmbargoEvent, CaseParticipant, etc.) would always
        # fail. Match on as_type string, consistent with ActivityPattern._match_field.
        _obj_type = str(getattr(obj, "as_type", "")) if obj is not None else ""

        kw: dict = {}
        activity_type = (
            str(activity.as_type) if activity.as_type else "Activity"
        )

        _ACTIVITY_SEMANTICS = {
            MessageSemantics.CREATE_REPORT,
            MessageSemantics.SUBMIT_REPORT,
            MessageSemantics.VALIDATE_REPORT,
            MessageSemantics.INVALIDATE_REPORT,
            MessageSemantics.ACK_REPORT,
            MessageSemantics.CLOSE_REPORT,
            MessageSemantics.SUGGEST_ACTOR_TO_CASE,
            MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE,
            MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
            MessageSemantics.INVITE_ACTOR_TO_CASE,
            MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
            MessageSemantics.CREATE_CASE,
        }
        if semantics in _ACTIVITY_SEMANTICS:
            kw["activity"] = VultronActivity(
                as_id=activity.as_id,
                as_type=activity_type,
                actor=actor_id,
                as_object=_get_id(obj),
                target=_get_id(target),
                origin=_get_id(origin),
                context=_get_id(context),
                in_reply_to=_get_id(getattr(activity, "in_reply_to", None)),
            )

        if _obj_type == str(VOtype.VULNERABILITY_REPORT):
            kw["report"] = VultronReport(
                as_id=obj.as_id,
                as_type=str(obj.as_type),
                name=obj.name,
                summary=getattr(obj, "summary", None),
                content=obj.content,
                url=_get_id(getattr(obj, "url", None)),
                media_type=getattr(obj, "media_type", None),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                context=_get_id(getattr(obj, "context", None)),
                published=getattr(obj, "published", None),
                updated=getattr(obj, "updated", None),
            )
        elif _obj_type == str(VOtype.VULNERABILITY_CASE):
            kw["case"] = VultronCase(
                as_id=obj.as_id,
                as_type=str(obj.as_type),
                name=getattr(obj, "name", None),
                summary=getattr(obj, "summary", None),
                content=getattr(obj, "content", None),
                url=_get_id(getattr(obj, "url", None)),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                published=getattr(obj, "published", None),
                updated=getattr(obj, "updated", None),
            )
        elif _obj_type == str(AOtype.EVENT):
            kw["embargo"] = VultronEmbargoEvent(
                as_id=obj.as_id,
                as_type=str(obj.as_type),
                name=getattr(obj, "name", None),
                start_time=getattr(obj, "start_time", None),
                end_time=getattr(obj, "end_time", None),
                published=getattr(obj, "published", None),
                updated=getattr(obj, "updated", None),
                context=_get_id(getattr(obj, "context", None)),
            )
        elif _obj_type == str(VOtype.CASE_PARTICIPANT):
            kw["participant"] = VultronParticipant(
                as_id=obj.as_id,
                as_type=str(obj.as_type),
                name=getattr(obj, "name", None),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                context=_get_id(getattr(obj, "context", None)),
                case_roles=list(getattr(obj, "case_roles", []) or []),
                participant_case_name=getattr(
                    obj, "participant_case_name", None
                ),
            )
        elif _obj_type == str(AOtype.NOTE):
            kw["note"] = VultronNote(
                as_id=obj.as_id,
                name=getattr(obj, "name", None),
                summary=getattr(obj, "summary", None),
                content=getattr(obj, "content", None),
                url=_get_id(getattr(obj, "url", None)),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                context=_get_id(getattr(obj, "context", None)),
            )
        elif _obj_type == str(VOtype.CASE_STATUS):
            kw["status"] = VultronCaseStatus(
                as_id=obj.as_id,
                name=getattr(obj, "name", None),
                context=_get_id(getattr(obj, "context", None)),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                em_state=getattr(obj, "em_state", None)
                or VultronCaseStatus.model_fields["em_state"].default,
                pxa_state=getattr(obj, "pxa_state", None)
                or VultronCaseStatus.model_fields["pxa_state"].default,
            )
        elif _obj_type == str(VOtype.PARTICIPANT_STATUS):
            ctx = _get_id(getattr(obj, "context", None)) or ""
            wire_case_status = getattr(obj, "case_status", None)
            kw["status"] = VultronParticipantStatus(
                as_id=obj.as_id,
                name=getattr(obj, "name", None),
                context=ctx,
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                rm_state=getattr(obj, "rm_state", None)
                or VultronParticipantStatus.model_fields["rm_state"].default,
                vfd_state=getattr(obj, "vfd_state", None)
                or VultronParticipantStatus.model_fields["vfd_state"].default,
                case_status=(
                    _get_id(wire_case_status)
                    if wire_case_status is not None
                    else None
                ),
            )
        return kw

    extra_kwargs = _build_domain_kwargs()
    return event_class(
        semantic_type=semantics,
        activity_id=activity.as_id,
        activity_type=str(activity.as_type) if activity.as_type else None,
        actor_id=actor_id,
        object_id=_get_id(obj),
        object_type=_get_type(obj),
        target_id=_get_id(target),
        target_type=_get_type(target),
        context_id=_get_id(context),
        context_type=_get_type(context),
        origin_id=_get_id(origin),
        origin_type=_get_type(origin),
        inner_object_id=_get_id(inner_obj),
        inner_object_type=_get_type(inner_obj),
        inner_target_id=_get_id(inner_target),
        inner_target_type=_get_type(inner_target),
        inner_context_id=_get_id(inner_context),
        inner_context_type=_get_type(inner_context),
        **extra_kwargs,
    )


def find_matching_semantics(activity: as_Activity) -> MessageSemantics:
    """Find the MessageSemantics for the given AS2 activity.

    Iterates SEMANTICS_ACTIVITY_PATTERNS in order and returns the first match.
    Returns MessageSemantics.UNKNOWN if no pattern matches.

    Note:
        Pattern ordering matters when patterns overlap. More specific patterns
        must appear before more general ones.

    Args:
        activity: The AS2 activity to classify.

    Returns:
        The matching MessageSemantics value, or MessageSemantics.UNKNOWN.
    """
    for semantics, pattern in SEMANTICS_ACTIVITY_PATTERNS.items():
        if pattern.match(activity):
            return semantics
    return MessageSemantics.UNKNOWN
