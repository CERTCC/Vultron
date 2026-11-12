"""The activity snapshot and the per-object dispatch of the extractor.

:func:`_build_object_kwargs` builds the domain-field kwargs for
``extract_intent``: the :class:`~vultron.core.models.activity.VultronActivity`
snapshot, then the fields the activity's object type contributes.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from vultron.core.models.activity import VultronActivity
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.wire.as2.enums import as_ObjectType as AOtype
from vultron.wire.as2.extractor._builders.fields import (
    _get_id,
    _get_id_list,
    _get_timestamp,
    _to_domain_obj,
)
from vultron.wire.as2.extractor._builders.objects import (
    _build_case_ledger_entry_object,
    _build_case_object,
    _build_embargo_event_object,
    _build_note_object,
    _build_participant_object,
    _build_report_object,
)
from vultron.wire.as2.extractor._builders.statuses import (
    _build_case_status_object,
    _build_participant_status_object,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Event
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseReference,
)

# ---------------------------------------------------------------------------
# Activity snapshot builder
# ---------------------------------------------------------------------------


def _build_activity_snapshot(
    activity: as_Activity,
    actor_id: str,
    obj: BaseModel | str | None,
    target: BaseModel | str | None,
    origin: object,
    context: object,
    end_time: datetime | None = None,
    proposed_embargo: EmbargoEvent | None = None,
) -> VultronActivity:
    """Build a VultronActivity snapshot from raw AS2 fields.

    ``proposed_embargo`` is carried when the caller passes it: an
    ``Offer(VulnerabilityReport)``'s proposed terms (EP-04-004) are part of
    the Offer the receiver archives (CLP-10-017) and later inlines whole in
    its case proposal (CP-01-008), so the archive must keep them.

    ``end_time`` is carried only when the caller passes it, with the offset
    it arrived with (CS-13-005): for the ownership-transfer Offer it is the
    binding deadline to answer, which the CASE_MANAGER reads back from the
    ledgered Offer (CM-21-016).  Other activities' ``endTime`` is not part of
    what their entries record.

    ``attributed_to`` is carried because it is the *only* record of who asked for
    a delegated message: under CM-24-001 the CaseActor is the `actor` of an
    Activity it sends on a participant's behalf, and CM-24-002 puts the
    requesting participant in ``attributed_to`` "so that receivers can recover
    the originating identity".  Dropping it here made that recovery impossible —
    a received-side use case saw only ``actor_id`` (the CaseActor), so the Offer
    the CaseActor forwarded to a transferee attributed the vendor's intent to the
    CaseActor itself.  See CM-24-002 and notes/ownership-transfer.md.

    ``published`` is carried for the same class of reason (ISSUE-3149).  It is
    the sender's *claimed* event time; omitting it once let
    ``VultronActivity.published`` fall back to a clock default, the receiver's
    own clock, so core read the receiver's clock as the sender's claim
    (CLP-15-004).  The field is now required (ADR-0176).

    This summary is what core reads and intake records, not what a received
    ledger entry records: the entry records the received body itself, which
    the event carries (``VultronEvent.received_evidence``, CLP-07-011).
    """
    activity_type = str(activity.type_) if activity.type_ else "Activity"
    return VultronActivity(
        id_=activity.id_,
        type_=activity_type,
        actor=actor_id,
        attributed_to=_get_id(getattr(activity, "attributed_to", None)),
        published=_get_timestamp(activity, "published"),
        updated=_get_timestamp(activity, "updated"),
        object_=obj,
        target=target,
        origin=_get_id(origin),
        context=_get_id(context),
        in_reply_to=_get_id(getattr(activity, "in_reply_to", None)),
        # `to` only: `cc` is AS2 vocabulary the wire model still parses, and
        # the inbox still counts for addressing (IE-11-003), but it has no
        # handler semantics, so it is not carried into core (HP-10-001,
        # ADR-0109).
        to=_get_id_list(getattr(activity, "to", None)),
        # Blank text is refused when the activity is built (CS-08-001), so
        # absence is the only empty form left to carry.
        summary=getattr(activity, "summary", None),
        content=getattr(activity, "content", None),
        # The sender's position (SYNC-18-001), so a reader of the received
        # activity (the full-case Invite's floor) gets it from core.
        ledger_position=getattr(activity, "ledger_position", None),
        # The sender's number (SYNC-21-001), and a refusal notice's next
        # expected one (SYNC-21-015), so core reads them from the activity.
        sender_sequence=getattr(activity, "sender_sequence", None),
        expected_sender_sequence=getattr(
            activity, "expected_sender_sequence", None
        ),
        suggested_roles=getattr(activity, "suggested_roles", None) or None,
        roles=getattr(activity, "roles", None) or None,
        termination_cause=getattr(activity, "termination_cause", None),
        end_time=end_time,
        proposed_embargo=proposed_embargo,
    )


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
    obj: BaseModel | str | None,
    _obj_type: str,
    context: object,
    target: BaseModel | str | None,
    include_activity: bool,
    activity: as_Activity,
    actor_id: str,
    origin: object,
    activity_end_time: datetime | None = None,
    activity_proposed_embargo: EmbargoEvent | None = None,
) -> dict[str, Any]:
    """Build the domain-field kwargs dict for ``extract_intent``.

    *activity_end_time* and *activity_proposed_embargo* are passed through to
    the activity snapshot (see :func:`_build_activity_snapshot`).

    Uses type_ string comparison because the wire parser returns ``as_Object``
    (base class) for nested objects; isinstance checks against Vultron subtypes
    would always fail.  The ``as_Event`` check is an exception and is placed
    after the VULNERABILITY_REPORT / VULNERABILITY_CASE type-string checks to
    preserve the original priority order.
    """
    kw: dict[str, Any] = {}
    if include_activity:
        kw["activity"] = _build_activity_snapshot(
            activity,
            actor_id,
            obj,
            target,
            origin,
            context,
            end_time=activity_end_time,
            proposed_embargo=activity_proposed_embargo,
        )
    if obj is None:
        return kw

    if _obj_type == str(VOtype.VULNERABILITY_REPORT):
        kw.update(_build_report_object(obj))
    elif isinstance(obj, as_VulnerabilityCaseReference):
        # A case named by typed reference reaches core as its id and type
        # only (ADR-0165); the receiver reads the case from its own store.
        kw["object_"] = _to_domain_obj(obj)
    elif _obj_type == str(VOtype.VULNERABILITY_CASE):
        kw.update(_build_case_object(obj))
    elif isinstance(obj, (as_Event, EmbargoEvent)):
        kw.update(_build_embargo_event_object(obj, context, target))
    elif builder := _OBJ_BUILDERS.get(_obj_type):
        kw.update(builder(obj))
    elif (domain_obj := _to_domain_obj(obj)) is not None:
        kw["object_"] = domain_obj
    return kw
