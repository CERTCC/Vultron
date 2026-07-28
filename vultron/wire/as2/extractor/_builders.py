"""Private domain-object builder helpers for the Vultron extractor.

Converts raw AS2 wire objects to core domain model instances.  All
functions here are internal implementation details of
``vultron.wire.as2.extractor``; callers should use ``extract_intent``
from ``_extract.py`` (or the ``vultron.semantic_registry.extract_event``
convenience wrapper) rather than calling these builders directly.
"""

from datetime import datetime
from typing import Any, Callable

from vultron.core.models._helpers import _now_utc as _core_now_utc
from vultron.core.models.base import VultronObject
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.dimensions import (
    EmDimension,
    PecDimension,
    PxaDimension,
    RmDimension,
    VfdDimension,
)
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.core.models.participant_status import coerce_cvd_roles
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.core.models.vultron_types import (
    CaseStatus,
    EmbargoEvent,
    ParticipantStatus,
    VultronActivity,
    VultronCase,
    VultronNote,
    VultronParticipant,
    VultronReport,
)
from vultron.wire.as2.enums import as_ObjectType as AOtype
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Event

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
        summary=getattr(activity, "summary", None) or None,
        content=getattr(activity, "content", None) or None,
    )


# ---------------------------------------------------------------------------
# Per-type domain-object builders
# ---------------------------------------------------------------------------


def _get_timestamp(obj: object, field: str) -> datetime:
    """Return a wire object's ``published`` or ``updated`` datetime.

    Falls back to ``_core_now_utc()`` if the attribute is absent or not a
    ``datetime``, so callers always receive a typed, non-optional value.
    """
    val = getattr(obj, field, None)
    return val if isinstance(val, datetime) else _core_now_utc()


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
                published=_get_timestamp(obj, "published"),
                updated=_get_timestamp(obj, "updated"),
            )
        }
    return {}


def _participant_ref_to_domain(ref: object) -> str | VultronParticipant | None:
    """Convert a wire-layer participant ref to a core domain object or ID string.

    Returns a ``VultronParticipant`` if ``ref`` has ``case_roles`` (duck-type),
    a plain string if it is a URI reference, or ``None`` if the ref is
    unusable.  This preserves participant metadata — including role lists —
    across the wire→domain extraction boundary so bootstrap trust logic can
    inspect ``CVDRole.CASE_MANAGER`` on the extracted case (CBT-01-003).
    """
    if isinstance(ref, str):
        return ref if ref else None

    participant_id = _get_id(ref)
    if not participant_id:
        return None

    roles = getattr(ref, "case_roles", [])
    attributed = getattr(ref, "attributed_to", None)
    context_id = _get_id(getattr(ref, "context", None))
    if roles is not None and attributed is not None and context_id:
        return VultronParticipant(
            id_=participant_id,
            attributed_to=str(attributed),
            context=context_id,
            name=getattr(ref, "name", None),
            case_roles=list(roles),
        )

    # Fallback: return as ID string only
    return participant_id


def _build_case_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    if object_id:
        raw_participants = getattr(obj, "case_participants", []) or []
        participants: list[str | VultronParticipant] = []
        for ref in raw_participants:
            converted = _participant_ref_to_domain(ref)
            if converted is not None:
                participants.append(converted)
        raw_index = getattr(obj, "actor_participant_index", None)
        actor_participant_index: dict[str, str] = (
            {str(k): str(v) for k, v in raw_index.items()}
            if isinstance(raw_index, dict)
            else {}
        )
        active_embargo = _get_id(getattr(obj, "active_embargo", None))
        raw_statuses = getattr(obj, "case_statuses", []) or []
        case_statuses: list[str | CaseStatus] = []
        for cs in raw_statuses:
            if hasattr(cs, "to_core"):
                case_statuses.append(cs.to_core())
            else:
                cs_id = _get_id(cs)
                if cs_id:
                    case_statuses.append(cs_id)
        return {
            "object_": VultronCase(
                id_=object_id,
                name=getattr(obj, "name", None),
                summary=getattr(obj, "summary", None),
                content=getattr(obj, "content", None),
                url=_get_id(getattr(obj, "url", None)),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                published=_get_timestamp(obj, "published"),
                updated=_get_timestamp(obj, "updated"),
                case_participants=participants,
                actor_participant_index=actor_participant_index,
                active_embargo=active_embargo,
                case_statuses=case_statuses if case_statuses else [],
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
        raw_start = getattr(obj, "start_time", None)
        kwargs: dict[str, Any] = {
            "id_": object_id,
            "name": getattr(obj, "name", None),
            "end_time": end_time,
            "published": getattr(obj, "published", None),
            "updated": getattr(obj, "updated", None),
            "context": embargo_context,
        }
        if isinstance(raw_start, datetime):
            kwargs["start_time"] = raw_start
        return {"object_": EmbargoEvent(**kwargs)}
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


def _build_case_ledger_entry_object(obj: object) -> dict[str, Any]:
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
            "object_": VultronCaseLedgerEntry(
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


def _coerce_em(raw: object) -> EM:
    if isinstance(raw, EM):
        return raw
    if isinstance(raw, str):
        return EM[raw] if raw in EM.__members__ else EM(raw)
    return EM.NO_EMBARGO


def _coerce_pxa(raw: object) -> CS_pxa:
    if isinstance(raw, CS_pxa):
        return raw
    if isinstance(raw, str):
        return CS_pxa[raw]
    return CS_pxa.pxa


def _coerce_rm(raw: object) -> RM:
    if isinstance(raw, RM):
        return raw
    if isinstance(raw, str):
        return RM[raw]
    return RM.START


def _coerce_vfd(raw: object) -> CS_vfd:
    if isinstance(raw, CS_vfd):
        return raw
    if isinstance(raw, str):
        return CS_vfd[raw]
    return CS_vfd.vfd


def _coerce_pec_or_none(raw: object) -> PEC | None:
    if raw is None:
        return None
    if isinstance(raw, PEC):
        return raw
    if isinstance(raw, str):
        return PEC[raw]
    return None


def _build_case_status_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    case_context = _get_id(getattr(obj, "context", None))
    attributed_to = _get_id(getattr(obj, "attributed_to", None))
    if object_id and case_context:
        return {
            "object_": CaseStatus(
                id_=object_id,
                name=getattr(obj, "name", None),
                context=case_context,
                attributed_to=attributed_to,
                em=EmDimension(
                    state=_coerce_em(getattr(obj, "em_state", None))
                ),
                pxa=PxaDimension(
                    state=_coerce_pxa(getattr(obj, "pxa_state", None))
                ),
            )
        }
    return {}


def _build_participant_status_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    ctx = _get_id(getattr(obj, "context", None)) or ""
    wire_case_status = getattr(obj, "case_status", None)
    if object_id:
        # Extract embedded CaseStatus into a CaseStatus core object so
        # that pxa and em are propagated across the wire boundary.
        core_case_status: CaseStatus | None = None
        if wire_case_status is not None:
            cs_id = _get_id(wire_case_status)
            cs_context = (
                _get_id(getattr(wire_case_status, "context", None)) or ctx
            )
            cs_attributed_to = _get_id(
                getattr(wire_case_status, "attributed_to", None)
            )
            if cs_id and cs_context:
                core_case_status = CaseStatus(
                    id_=cs_id,
                    context=cs_context,
                    attributed_to=cs_attributed_to,
                    em=EmDimension(
                        state=_coerce_em(
                            getattr(wire_case_status, "em_state", None)
                        )
                    ),
                    pxa=PxaDimension(
                        state=_coerce_pxa(
                            getattr(wire_case_status, "pxa_state", None)
                        )
                    ),
                )
        raw_pec = getattr(obj, "em_consent_state", None)
        pec_val = _coerce_pec_or_none(
            PEC[raw_pec] if isinstance(raw_pec, str) else raw_pec
        )
        return {
            "object_": ParticipantStatus(
                id_=object_id,
                name=getattr(obj, "name", None),
                context=ctx,
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                rm=RmDimension(
                    state=_coerce_rm(getattr(obj, "rm_state", None))
                ),
                vfd=VfdDimension(
                    state=_coerce_vfd(getattr(obj, "vfd_state", None))
                ),
                consent=(
                    PecDimension(state=pec_val)
                    if pec_val is not None
                    else None
                ),
                cvd_role=coerce_cvd_roles(
                    getattr(obj, "cvd_role", getattr(obj, "cvd_roles", None))
                ),
                case_status=core_case_status,
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
    str(VOtype.CASE_LEDGER_ENTRY): _build_case_ledger_entry_object,
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
