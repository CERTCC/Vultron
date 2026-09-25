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
from typing import cast

from vultron.core.models.events import (
    AnyReceivedEvent,
    MessageSemantics,
    VultronEvent,
)
from vultron.core.models.rsvp_deadline import (
    DEFAULT_MIN_RSVP_WINDOW,
    DEFAULT_RSVP_WINDOW,
    RsvpDeadlineClamp,
    resolve_rsvp_deadline,
)
from vultron.wire.as2.extractor._builders import (
    _build_object_kwargs,
    _get_id,
    _to_domain_obj,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


def extract_intent(
    activity: as_Activity,
    semantics: MessageSemantics,
    event_class: type[VultronEvent],
    include_activity: bool = False,
    min_rsvp_window: timedelta = DEFAULT_MIN_RSVP_WINDOW,
    default_rsvp_window: timedelta = DEFAULT_RSVP_WINDOW,
) -> AnyReceivedEvent:
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
        min_rsvp_window: Minimum RSVP window for an inbound embargo invite
            (EP-07-002, EP-07-003); 72 h by default.  Pass
            ``ActorConfig.min_rsvp_window`` to apply the configured floor.
        default_rsvp_window: Policy window used when an inbound embargo
            invite names no deadline (EP-07-001, CM-18-002); 7 days by
            default.  Pass ``ActorConfig.default_rsvp_window``.

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

    if "rsvp_deadline" in event_class.model_fields:
        extra_kwargs["rsvp_deadline"] = _effective_rsvp_deadline(
            activity, obj, min_rsvp_window, default_rsvp_window
        )

    return cast(
        AnyReceivedEvent,
        event_class(
            semantic_type=semantics,
            activity_id=activity.id_,
            activity_type=str(activity.type_) if activity.type_ else None,
            actor_id=actor_id,
            # object_ comes from extra_kwargs if a typed domain object was built;
            # otherwise fall back to a minimal CoreObject wrapper.
            object_=extra_kwargs.pop("object_", None) or _to_domain_obj(obj),
            target=_to_domain_obj(target),
            context=_to_domain_obj(context),
            origin=_to_domain_obj(origin),
            inner_object=_to_domain_obj(inner_obj),
            inner_target=_to_domain_obj(inner_target),
            inner_context=_to_domain_obj(inner_context),
            in_reply_to=_get_id(getattr(activity, "in_reply_to", None)),
            **extra_kwargs,
        ),
    )


def _effective_rsvp_deadline(
    activity: as_Activity,
    embargo: object,
    min_window: timedelta,
    default_window: timedelta,
) -> datetime:
    """Return the deadline an inbound embargo invite is held to.

    Clamps are applied, never refused (EP-07-004), and each one is logged
    (EP-07-005).  Windows are measured from the invite's ``published`` time;
    an activity without one is measured from now.

    ``resolve_rsvp_deadline`` normalises every input to UTC, including the
    nested embargo's ``end_time``, which the wire edge does not.
    """
    raw_end_time = getattr(activity, "end_time", None)
    requested = raw_end_time if isinstance(raw_end_time, datetime) else None
    raw_published = getattr(activity, "published", None)
    published = raw_published if isinstance(raw_published, datetime) else None
    raw_embargo_end = getattr(embargo, "end_time", None)
    embargo_end = (
        raw_embargo_end if isinstance(raw_embargo_end, datetime) else None
    )
    deadline = resolve_rsvp_deadline(
        requested=requested,
        published=published,
        embargo_end=embargo_end,
        min_window=min_window,
        default_window=default_window,
    )
    source = "Invite.end_time" if requested is not None else "policy window"
    if deadline.clamp is RsvpDeadlineClamp.RAISED_TO_MINIMUM:
        logger.info(
            "extract_intent: activity '%s' rsvp_deadline %s (%s) is below the"
            " applicable minimum; clamped up to %s (EP-07-003)",
            activity.id_,
            deadline.computed.isoformat(),
            source,
            deadline.effective.isoformat(),
        )
    elif deadline.clamp is RsvpDeadlineClamp.LOWERED_TO_EMBARGO_END:
        logger.info(
            "extract_intent: activity '%s' rsvp_deadline %s (%s) is after the"
            " embargo end; clamped down to %s (EP-07-006)",
            activity.id_,
            deadline.computed.isoformat(),
            source,
            deadline.effective.isoformat(),
        )
    if deadline.effective <= datetime.now(tz=timezone.utc):
        logger.warning(
            "extract_intent: activity '%s' rsvp_deadline %s is already past"
            " (published %s); the invitation lapses on the next check",
            activity.id_,
            deadline.effective.isoformat(),
            published.isoformat() if published is not None else "absent",
        )
    return deadline.effective
