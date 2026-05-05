"""AS2 wire layer semantic extractor for the Vultron Protocol.

Maps AS2 activity structures to domain MessageSemantics. This is the sole
location where AS2 vocabulary is translated to domain concepts (ARCH-03-001).
This is stage 3 of the inbound pipeline: typed AS2 activity → MessageSemantics.

Consolidates ActivityPattern definitions (formerly in vultron/activity_patterns.py)
into a single module.  Pattern-to-semantics matching lives in
``vultron.semantic_registry``, which iterates ``SEMANTIC_REGISTRY`` directly.
"""

from datetime import datetime
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel

from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Event
from vultron.core.models.base import VultronObject
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.events import (
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
        if self.activity_ != activity.type_:
            return False

        def _match_field(
            pattern_field: AOtype | VOtype | ActivityPattern | None,
            activity_field: object,
        ) -> bool:
            if pattern_field is None:
                return True
            # Nested pattern: bare-string references cannot satisfy a typed
            # nested-activity constraint — rehydration is required first.
            if isinstance(pattern_field, ActivityPattern):
                return isinstance(
                    activity_field, as_Activity
                ) and pattern_field.match(activity_field)
            # URI/ID string reference: can't type-check AOtype/VOtype, allow
            if isinstance(activity_field, str):
                return True
            if activity_field is None:
                return False
            # Subtype-aware matching: AOtype.ACTOR matches any as_Actor subclass
            # (Person, Organization, Service, etc.) whose type_ differs from "Actor".
            # AOtype.EVENT matches any as_Event subclass (e.g., EmbargoEvent).
            if pattern_field == AOtype.ACTOR and isinstance(
                activity_field, as_Actor
            ):
                return True
            if pattern_field == AOtype.EVENT and isinstance(
                activity_field, as_Event
            ):
                return True
            return bool(
                pattern_field == getattr(activity_field, "type_", None)
            )

        if not _match_field(self.object_, getattr(activity, "object_", None)):
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
AnnounceLogEntryPattern = ActivityPattern(
    description=(
        "Announce a canonical CaseLogEntry to a participant for log "
        "replication. The object is a CaseLogEntry object."
    ),
    activity_=TAtype.ANNOUNCE,
    object_=VOtype.CASE_LOG_ENTRY,
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
        "Participant rejects a CaseLogEntry announcement due to "
        "hash-chain mismatch. The object is the rejected CaseLogEntry."
    ),
    activity_=TAtype.REJECT,
    object_=VOtype.CASE_LOG_ENTRY,
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
# Private field-extraction helpers
# ---------------------------------------------------------------------------


def _get_id(field: object) -> str | None:
    if field is None:
        return None
    if isinstance(field, str):
        return field
    return getattr(field, "id_", str(field)) or None


def _get_id_list(field: object) -> list[str] | None:
    """Convert an AS2 to/cc field (Any | None) to a list of ID strings."""
    if field is None:
        return None
    if isinstance(field, str):
        return [field] if field else None
    if isinstance(field, list):
        ids = [_get_id(x) for x in field]
        result = [r for r in ids if r]
        return result or None
    single = _get_id(field)
    return [single] if single else None


def _get_type(field: object) -> str | None:
    if field is None or isinstance(field, str):
        return None
    t = getattr(field, "type_", None)
    return str(t) if t is not None else None


def _to_domain_obj(as_obj: object) -> VultronObject | None:
    """Wrap a bare AS2 object reference as a minimal VultronObject."""
    if as_obj is None:
        return None
    obj_id = _get_id(as_obj)
    if not obj_id:
        return None
    obj_type = _get_type(as_obj)
    return VultronObject(id_=obj_id, type_=obj_type)


# ---------------------------------------------------------------------------
# Activity snapshot builder
# ---------------------------------------------------------------------------


def _build_activity_snapshot(
    activity: as_Activity,
    actor_id: str,
    obj: object,
    target: object,
    origin: object,
    context: object,
) -> VultronActivity:
    """Build a VultronActivity snapshot from raw AS2 fields."""
    activity_type = str(activity.type_) if activity.type_ else "Activity"
    return VultronActivity(
        id_=activity.id_,
        type_=activity_type,
        actor=actor_id,
        object_=obj,
        target=target,
        origin=_get_id(origin),
        context=_get_id(context),
        in_reply_to=_get_id(getattr(activity, "in_reply_to", None)),
        to=_get_id_list(getattr(activity, "to", None)),
        cc=_get_id_list(getattr(activity, "cc", None)),
    )


# ---------------------------------------------------------------------------
# Per-type domain-object builders
# ---------------------------------------------------------------------------


def _build_report_object(obj: object) -> dict[str, Any]:
    content = getattr(obj, "content", None)
    object_id = _get_id(obj)
    if isinstance(content, str) and content and object_id:
        return {
            "object_": VultronReport(
                id_=object_id,
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
        }
    return {}


def _build_case_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    if object_id:
        return {
            "object_": VultronCase(
                id_=object_id,
                name=getattr(obj, "name", None),
                summary=getattr(obj, "summary", None),
                content=getattr(obj, "content", None),
                url=_get_id(getattr(obj, "url", None)),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                published=getattr(obj, "published", None),
                updated=getattr(obj, "updated", None),
            )
        }
    return {}


def _build_embargo_event_object(
    obj: as_Event, context: object, target: object
) -> dict[str, Any]:
    end_time = getattr(obj, "end_time", None)
    object_id = _get_id(obj)
    embargo_context = (
        _get_id(getattr(obj, "context", None))
        or _get_id(context)
        or _get_id(target)
    )
    if isinstance(end_time, datetime) and embargo_context and object_id:
        return {
            "object_": VultronEmbargoEvent(
                id_=object_id,
                name=getattr(obj, "name", None),
                start_time=getattr(obj, "start_time", None),
                end_time=end_time,
                published=getattr(obj, "published", None),
                updated=getattr(obj, "updated", None),
                context=embargo_context,
            )
        }
    return {}


def _build_participant_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    attributed_to = _get_id(getattr(obj, "attributed_to", None))
    participant_context = _get_id(getattr(obj, "context", None))
    if object_id and attributed_to and participant_context:
        return {
            "object_": VultronParticipant(
                id_=object_id,
                name=getattr(obj, "name", None),
                attributed_to=attributed_to,
                context=participant_context,
                case_roles=list(getattr(obj, "case_roles", []) or []),
                participant_case_name=getattr(
                    obj, "participant_case_name", None
                ),
            )
        }
    return {}


def _build_note_object(obj: object) -> dict[str, Any]:
    content = getattr(obj, "content", None)
    object_id = _get_id(obj)
    if isinstance(content, str) and content and object_id:
        return {
            "object_": VultronNote(
                id_=object_id,
                name=getattr(obj, "name", None),
                summary=getattr(obj, "summary", None),
                content=content,
                url=_get_id(getattr(obj, "url", None)),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                context=_get_id(getattr(obj, "context", None)),
            )
        }
    return {}


def _build_case_log_entry_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    case_id = getattr(obj, "case_id", None)
    log_index = getattr(obj, "log_index", -1)
    log_object_id = getattr(obj, "log_object_id", None) or getattr(
        obj, "logObjectId", None
    )
    event_type = getattr(obj, "event_type", None) or getattr(
        obj, "eventType", None
    )
    if object_id and case_id and log_object_id and event_type:
        return {
            "object_": VultronCaseLogEntry(
                id_=object_id,
                case_id=case_id,
                log_index=log_index,
                disposition=getattr(obj, "disposition", "recorded"),
                term=getattr(obj, "term", None),
                log_object_id=log_object_id,
                event_type=event_type,
                payload_snapshot=getattr(obj, "payload_snapshot", {})
                or getattr(obj, "payloadSnapshot", {}),
                prev_log_hash=getattr(obj, "prev_log_hash", None)
                or getattr(obj, "prevLogHash", None)
                or "",
                entry_hash=getattr(obj, "entry_hash", None)
                or getattr(obj, "entryHash", None)
                or "",
                reason_code=getattr(obj, "reason_code", None)
                or getattr(obj, "reasonCode", None),
                reason_detail=getattr(obj, "reason_detail", None)
                or getattr(obj, "reasonDetail", None),
            )
        }
    return {}


def _build_case_status_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    case_context = _get_id(getattr(obj, "context", None))
    if object_id and case_context:
        return {
            "object_": VultronCaseStatus(
                id_=object_id,
                name=getattr(obj, "name", None),
                context=case_context,
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                em_state=getattr(obj, "em_state", None)
                or VultronCaseStatus.model_fields["em_state"].default,
                pxa_state=getattr(obj, "pxa_state", None)
                or VultronCaseStatus.model_fields["pxa_state"].default,
            )
        }
    return {}


def _build_participant_status_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    ctx = _get_id(getattr(obj, "context", None)) or ""
    wire_case_status = getattr(obj, "case_status", None)
    if object_id:
        return {
            "object_": VultronParticipantStatus(
                id_=object_id,
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
        }
    return {}


# Dispatch table: obj type_ string → builder function.
# VULNERABILITY_REPORT and VULNERABILITY_CASE are handled explicitly in
# _build_object_kwargs (before the as_Event isinstance check) to preserve
# the original priority order.
_OBJ_BUILDERS: dict[str, Callable[[object], dict[str, Any]]] = {
    str(VOtype.CASE_PARTICIPANT): _build_participant_object,
    str(AOtype.NOTE): _build_note_object,
    str(VOtype.CASE_LOG_ENTRY): _build_case_log_entry_object,
    str(VOtype.CASE_STATUS): _build_case_status_object,
    str(VOtype.PARTICIPANT_STATUS): _build_participant_status_object,
}


def _build_object_kwargs(
    obj: object,
    _obj_type: str,
    context: object,
    target: object,
    include_activity: bool,
    activity: as_Activity,
    actor_id: str,
    origin: object,
) -> dict[str, Any]:
    """Build the domain-field kwargs dict for ``extract_intent``.

    Uses type_ string comparison because the wire parser returns ``as_Object``
    (base class) for nested objects; isinstance checks against Vultron subtypes
    would always fail.  The ``as_Event`` check is an exception and is placed
    after the VULNERABILITY_REPORT / VULNERABILITY_CASE type-string checks to
    preserve the original priority order.
    """
    kw: dict[str, Any] = {}
    if include_activity:
        kw["activity"] = _build_activity_snapshot(
            activity, actor_id, obj, target, origin, context
        )
    if obj is None:
        return kw

    if _obj_type == str(VOtype.VULNERABILITY_REPORT):
        kw.update(_build_report_object(obj))
    elif _obj_type == str(VOtype.VULNERABILITY_CASE):
        kw.update(_build_case_object(obj))
    elif isinstance(obj, as_Event):
        kw.update(_build_embargo_event_object(obj, context, target))
    elif builder := _OBJ_BUILDERS.get(_obj_type):
        kw.update(builder(obj))
    else:
        obj_id = _get_id(obj)
        if obj_id:
            kw["object_"] = VultronObject(id_=obj_id, type_=_get_type(obj))
    return kw


def extract_intent(
    activity: as_Activity,
    semantics: MessageSemantics,
    event_class: type[VultronEvent],
    include_activity: bool = False,
) -> VultronEvent:
    """Extract domain fields from an AS2 activity given pre-computed semantics.

    This function is the sole AS2 → domain translation point.  It is called
    after pattern matching has already determined the ``semantics``; the
    caller must supply the matching ``event_class`` and ``include_activity``
    flag from the registry entry.

    For a single-call convenience wrapper that performs pattern matching and
    registry lookup automatically, use ``vultron.semantic_registry.extract_event``.

    Args:
        activity: The AS2 activity to extract fields from.
        semantics: Pre-matched ``MessageSemantics`` value.
        event_class: Concrete ``VultronEvent`` subclass to instantiate.
        include_activity: When ``True``, populate ``event.activity`` with a
            summarised ``VultronActivity`` snapshot of the outer activity.

    Returns:
        A concrete VultronEvent subclass discriminated by MessageSemantics.
    """
    actor_id = _get_id(getattr(activity, "actor", None)) or ""
    obj = getattr(activity, "object_", None)
    target = getattr(activity, "target", None)
    context = getattr(activity, "context", None)
    origin = getattr(activity, "origin", None)

    # Nested fields from activity.object_ (for Accept/Reject wrapping another activity)
    inner_obj = inner_target = inner_context = None
    if obj is not None and not isinstance(obj, str):
        inner_obj = getattr(obj, "object_", None)
        inner_target = getattr(obj, "target", None)
        inner_context = getattr(obj, "context", None)

    _obj_type = str(getattr(obj, "type_", "")) if obj is not None else ""
    extra_kwargs = _build_object_kwargs(
        obj,
        _obj_type,
        context,
        target,
        include_activity,
        activity,
        actor_id,
        origin,
    )
    return event_class(
        semantic_type=semantics,
        activity_id=activity.id_,
        activity_type=str(activity.type_) if activity.type_ else None,
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
