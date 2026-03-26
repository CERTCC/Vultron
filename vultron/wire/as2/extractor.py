"""AS2 wire layer semantic extractor for the Vultron Protocol.

Maps AS2 activity structures to domain MessageSemantics. This is the sole
location where AS2 vocabulary is translated to domain concepts (ARCH-03-001).
This is stage 3 of the inbound pipeline: typed AS2 activity → MessageSemantics.

Consolidates ActivityPattern definitions (formerly in vultron/activity_patterns.py)
and the SEMANTICS_ACTIVITY_PATTERNS mapping + find_matching_semantics function
(formerly in vultron/semantic_map.py) into a single extractor module.
"""

from datetime import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel

from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.core.models.base import VultronObject
from vultron.core.models.events import (
    EVENT_CLASS_MAP,
    MessageSemantics,
    VultronEvent,
)
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.core.models.vultron_types import (
    VultronActivity,
    VultronCase,
    VultronCaseStatus,
    VultronEmbargoEvent,
    VultronNote,
    VultronParticipant,
    VultronParticipantStatus,
    VultronReport,
)
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

        def _match_field(
            pattern_field: AOtype | VOtype | ActivityPattern | None,
            activity_field: object,
        ) -> bool:
            if pattern_field is None:
                return True
            # URI/ID string reference: can't type-check, conservatively allow
            if isinstance(activity_field, str):
                return True
            if isinstance(pattern_field, ActivityPattern):
                return isinstance(
                    activity_field, as_Activity
                ) and pattern_field.match(activity_field)
            if activity_field is None:
                return False
            return bool(
                pattern_field == getattr(activity_field, "as_type", None)
            )

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
OfferCaseOwnershipTransferActivityPattern = ActivityPattern(
    activity_=TAtype.OFFER, object_=VOtype.VULNERABILITY_CASE
)
AcceptCaseOwnershipTransferActivityPattern = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=OfferCaseOwnershipTransferActivityPattern
)
RejectCaseOwnershipTransferActivityPattern = ActivityPattern(
    activity_=TAtype.REJECT, object_=OfferCaseOwnershipTransferActivityPattern
)
InviteActorToCasePattern = ActivityPattern(
    activity_=TAtype.INVITE,
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


# ---------------------------------------------------------------------------
# Semantics → pattern mapping (formerly in vultron/semantic_map.py)
# The order of entries matters: find_matching_semantics returns the first match.
# ---------------------------------------------------------------------------

SEMANTICS_ACTIVITY_PATTERNS: dict[MessageSemantics, ActivityPattern] = {
    MessageSemantics.CREATE_REPORT: CreateReportPattern,
    MessageSemantics.SUBMIT_REPORT: ReportSubmissionPattern,
    MessageSemantics.ACK_REPORT: AckReportPattern,
    MessageSemantics.VALIDATE_REPORT: ValidateReportPattern,
    MessageSemantics.INVALIDATE_REPORT: InvalidateReportPattern,
    MessageSemantics.CLOSE_REPORT: CloseReportPattern,
    MessageSemantics.CREATE_CASE: CreateCaseActivityPattern,
    MessageSemantics.UPDATE_CASE: UpdateCaseActivityPattern,
    MessageSemantics.ENGAGE_CASE: EngageCasePattern,
    MessageSemantics.DEFER_CASE: DeferCasePattern,
    MessageSemantics.ADD_REPORT_TO_CASE: AddReportToCaseActivityPattern,
    MessageSemantics.SUGGEST_ACTOR_TO_CASE: SuggestActorToCasePattern,
    MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE: AcceptSuggestActorToCasePattern,
    MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE: RejectSuggestActorToCasePattern,
    MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER: OfferCaseOwnershipTransferActivityPattern,
    MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER: AcceptCaseOwnershipTransferActivityPattern,
    MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER: RejectCaseOwnershipTransferActivityPattern,
    MessageSemantics.INVITE_ACTOR_TO_CASE: InviteActorToCasePattern,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: AcceptInviteActorToCasePattern,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: RejectInviteActorToCasePattern,
    MessageSemantics.CREATE_EMBARGO_EVENT: CreateEmbargoEventPattern,
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE: AddEmbargoEventToCasePattern,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: RemoveEmbargoEventFromCasePattern,
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE: AnnounceEmbargoEventToCasePattern,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: InviteToEmbargoOnCasePattern,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: AcceptInviteToEmbargoOnCasePattern,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: RejectInviteToEmbargoOnCasePattern,
    MessageSemantics.CLOSE_CASE: CloseCasePattern,
    MessageSemantics.CREATE_CASE_PARTICIPANT: CreateCaseParticipantPattern,
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE: AddCaseParticipantToCasePattern,
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE: RemoveCaseParticipantFromCasePattern,
    MessageSemantics.CREATE_NOTE: CreateNotePattern,
    MessageSemantics.ADD_NOTE_TO_CASE: AddNoteToCaseActivityPattern,
    MessageSemantics.REMOVE_NOTE_FROM_CASE: RemoveNoteFromCasePattern,
    MessageSemantics.CREATE_CASE_STATUS: CreateCaseStatusActivityPattern,
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: AddCaseStatusToCasePattern,
    MessageSemantics.CREATE_PARTICIPANT_STATUS: CreateParticipantStatusPattern,
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: AddParticipantStatusToParticipantPattern,
}


def extract_intent(
    activity: as_Activity,
) -> VultronEvent:
    """Extract semantic intent and domain fields from an AS2 activity.

    Returns a fully-populated per-semantic VultronEvent subclass with all
    relevant IDs and types extracted from the AS2 object graph.
    This is the sole point where AS2 wire types are translated to domain concepts.

    Args:
        activity: The AS2 activity to classify and extract from.

    Returns:
        A concrete VultronEvent subclass discriminated by MessageSemantics.
    """

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

    def _build_domain_kwargs() -> dict[str, Any]:
        # Use as_type string comparison because the wire parser returns
        # as_Object (base class) for nested objects; isinstance checks against
        # Vultron subtypes (EmbargoEvent, CaseParticipant, etc.) would always
        # fail. Match on as_type string, consistent with ActivityPattern._match_field.
        _obj_type = str(getattr(obj, "as_type", "")) if obj is not None else ""

        kw: dict[str, Any] = {}
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

        if _obj_type == str(VOtype.VULNERABILITY_REPORT) and obj is not None:
            content = getattr(obj, "content", None)
            object_id = _get_id(obj)
            if isinstance(content, str) and content and object_id:
                kw["object_"] = VultronReport(
                    as_id=object_id,
                    name=getattr(obj, "name", None),
                    summary=getattr(obj, "summary", None),
                    content=content,
                    url=_get_id(getattr(obj, "url", None)),
                    media_type=getattr(obj, "media_type", None),
                    attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                    context=_get_id(getattr(obj, "context", None)),
                    published=getattr(obj, "published", None),
                    updated=getattr(obj, "updated", None),
                )
        elif _obj_type == str(VOtype.VULNERABILITY_CASE) and obj is not None:
            object_id = _get_id(obj)
            if object_id:
                kw["object_"] = VultronCase(
                    as_id=object_id,
                    name=getattr(obj, "name", None),
                    summary=getattr(obj, "summary", None),
                    content=getattr(obj, "content", None),
                    url=_get_id(getattr(obj, "url", None)),
                    attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                    published=getattr(obj, "published", None),
                    updated=getattr(obj, "updated", None),
                )
        elif _obj_type == str(AOtype.EVENT) and obj is not None:
            end_time = getattr(obj, "end_time", None)
            object_id = _get_id(obj)
            embargo_context = (
                _get_id(getattr(obj, "context", None))
                or _get_id(context)
                or _get_id(target)
            )
            if (
                isinstance(end_time, datetime)
                and embargo_context
                and object_id
            ):
                kw["object_"] = VultronEmbargoEvent(
                    as_id=object_id,
                    name=getattr(obj, "name", None),
                    start_time=getattr(obj, "start_time", None),
                    end_time=end_time,
                    published=getattr(obj, "published", None),
                    updated=getattr(obj, "updated", None),
                    context=embargo_context,
                )
        elif _obj_type == str(VOtype.CASE_PARTICIPANT) and obj is not None:
            object_id = _get_id(obj)
            attributed_to = _get_id(getattr(obj, "attributed_to", None))
            participant_context = _get_id(getattr(obj, "context", None))
            if object_id and attributed_to and participant_context:
                kw["object_"] = VultronParticipant(
                    as_id=object_id,
                    name=getattr(obj, "name", None),
                    attributed_to=attributed_to,
                    context=participant_context,
                    case_roles=list(getattr(obj, "case_roles", []) or []),
                    participant_case_name=getattr(
                        obj, "participant_case_name", None
                    ),
                )
        elif _obj_type == str(AOtype.NOTE) and obj is not None:
            content = getattr(obj, "content", None)
            object_id = _get_id(obj)
            if isinstance(content, str) and content and object_id:
                kw["object_"] = VultronNote(
                    as_id=object_id,
                    name=getattr(obj, "name", None),
                    summary=getattr(obj, "summary", None),
                    content=content,
                    url=_get_id(getattr(obj, "url", None)),
                    attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                    context=_get_id(getattr(obj, "context", None)),
                )
        elif _obj_type == str(VOtype.CASE_STATUS) and obj is not None:
            object_id = _get_id(obj)
            case_context = _get_id(getattr(obj, "context", None))
            if object_id and case_context:
                kw["object_"] = VultronCaseStatus(
                    as_id=object_id,
                    name=getattr(obj, "name", None),
                    context=case_context,
                    attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                    em_state=getattr(obj, "em_state", None)
                    or VultronCaseStatus.model_fields["em_state"].default,
                    pxa_state=getattr(obj, "pxa_state", None)
                    or VultronCaseStatus.model_fields["pxa_state"].default,
                )
        elif _obj_type == str(VOtype.PARTICIPANT_STATUS) and obj is not None:
            object_id = _get_id(obj)
            ctx = _get_id(getattr(obj, "context", None)) or ""
            wire_case_status = getattr(obj, "case_status", None)
            if object_id:
                kw["object_"] = VultronParticipantStatus(
                    as_id=object_id,
                    name=getattr(obj, "name", None),
                    context=ctx,
                    attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                    rm_state=getattr(obj, "rm_state", None)
                    or VultronParticipantStatus.model_fields[
                        "rm_state"
                    ].default,
                    vfd_state=getattr(obj, "vfd_state", None)
                    or VultronParticipantStatus.model_fields[
                        "vfd_state"
                    ].default,
                    case_status=(
                        _get_id(wire_case_status)
                        if wire_case_status is not None
                        else None
                    ),
                )
        elif obj is not None:
            obj_id = _get_id(obj)
            if obj_id:
                obj_type = _get_type(obj)
                kw["object_"] = VultronObject(as_id=obj_id, as_type=obj_type)
        return kw

    def _to_domain_obj(as_obj: object) -> VultronObject | None:
        """Wrap a bare AS2 object reference as a minimal VultronObject."""
        if as_obj is None:
            return None
        obj_id = _get_id(as_obj)
        if not obj_id:
            return None
        obj_type = _get_type(as_obj)
        return VultronObject(as_id=obj_id, as_type=obj_type)

    extra_kwargs = _build_domain_kwargs()
    return event_class(
        semantic_type=semantics,
        activity_id=activity.as_id,
        activity_type=str(activity.as_type) if activity.as_type else None,
        actor_id=actor_id,
        # object_ comes from extra_kwargs if a typed domain object was built;
        # otherwise fall back to a minimal VultronObject wrapper.
        object_=extra_kwargs.pop("object_", None) or _to_domain_obj(obj),
        target=_to_domain_obj(target),
        context=_to_domain_obj(context),
        origin=_to_domain_obj(origin),
        inner_object=_to_domain_obj(inner_obj),
        inner_target=_to_domain_obj(inner_target),
        inner_context=_to_domain_obj(inner_context),
        in_reply_to=_get_id(getattr(activity, "in_reply_to", None)),
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
