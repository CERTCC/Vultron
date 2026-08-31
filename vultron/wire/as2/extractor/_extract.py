"""Domain-event extraction from AS2 activities.

This module provides ``extract_intent``, the sole AS2 → domain translation
point for inbound activities.  It is called after pattern matching has
determined the ``MessageSemantics``; the caller supplies the matching
``event_class`` and ``include_activity`` flag from the registry entry.

For a single-call convenience wrapper that performs pattern matching and
registry lookup automatically, use ``vultron.semantic_registry.extract_event``.
"""

import logging
from datetime import datetime, timedelta, timezone

from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.wire.as2.extractor._builders import (
    _build_object_kwargs,
    _get_id,
    _to_domain_obj,
)
from vultron.wire.as2.factories.embargo import _DEFAULT_MIN_RSVP_WINDOW
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


def extract_intent(
    activity: as_Activity,
    semantics: MessageSemantics,
    event_class: type[VultronEvent],
    include_activity: bool = False,
    min_rsvp_window: timedelta = _DEFAULT_MIN_RSVP_WINDOW,
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
        min_rsvp_window: Floor applied when clamping a sub-floor inbound
            ``end_time`` (EP-07-003). Defaults to ``_DEFAULT_MIN_RSVP_WINDOW``
            (72 h). Pass ``ActorConfig.min_rsvp_window`` from the caller to
            apply the actor-configured floor.

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

    # AC-2/AC-3/AC-5 (issue #2211): extract activity-level end_time as
    # rsvp_deadline for event classes that carry it.  Applies UTC normalization
    # and clamps sub-floor values up to the configured minimum window (EP-07-003).
    if "rsvp_deadline" in event_class.model_fields:
        raw_end_time = getattr(activity, "end_time", None)
        if isinstance(raw_end_time, datetime) and raw_end_time.tzinfo is None:
            # CM-28-006: naive end_time MUST be rejected as malformed.
            logger.warning(
                "extract_intent: inbound end_time %r on activity %s is"
                " naive (no timezone); rejected as malformed (CM-28-006)",
                raw_end_time.isoformat(),
                getattr(activity, "id_", "<unknown>"),
            )
        elif isinstance(raw_end_time, datetime):
            floor = datetime.now(tz=timezone.utc) + min_rsvp_window
            if raw_end_time < floor:
                logger.info(
                    "extract_intent: inbound rsvp_deadline %s is below floor"
                    " %s; clamped to floor (EP-07-003)",
                    raw_end_time.isoformat(),
                    floor.isoformat(),
                )
                raw_end_time = floor
            extra_kwargs["rsvp_deadline"] = raw_end_time.astimezone(
                timezone.utc
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
