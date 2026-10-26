"""Domain-event extraction from AS2 activities.

This module provides ``extract_intent``, the sole AS2 → domain translation
point for inbound activities.  It is called after pattern matching has
determined the ``MessageSemantics``; the caller supplies the matching
``event_class`` and ``include_activity`` flag from the registry entry.

For a single-call convenience wrapper that performs pattern matching and
registry lookup automatically, use ``vultron.semantic_registry.extract_event``.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import cast

from vultron.core.models._helpers import now_utc
from vultron.core.models.actor import CoreActor
from vultron.core.models.events import (
    AnyReceivedEvent,
    MessageSemantics,
    VultronEvent,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.rsvp_deadline import (
    DEFAULT_MIN_RSVP_WINDOW,
    DEFAULT_RSVP_WINDOW,
    RsvpDeadlineClamp,
    resolve_rsvp_deadline,
)
from vultron.enums.object_types import VultronObjectType as VOtype
from vultron.primitives import normalise_actor_id
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.extractor._builders import (
    _build_object_kwargs,
    _get_id,
    _to_domain_obj,
    ledger_position_from_content,
    proposed_embargo_from,
    termination_of,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

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
    # The sender id as written, for the activity snapshot: the stored
    # activity and the ledger postmark keep the sender's spelling.  The event
    # gets the normalised id (OID-01-006, OID-01-007).
    actor_id = _get_id(getattr(activity, "actor", None)) or ""
    sender_id = normalise_actor_id(actor_id)
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
    carries_deadline = "answer_deadline" in event_class.model_fields
    proposed_embargo = None
    carries_terms = "proposed_embargo" in event_class.model_fields
    terms_on_activity = _obj_type != str(VOtype.CASE_PROPOSAL)
    if carries_terms:
        # Offer(VulnerabilityReport) carries it itself; Create(CaseProposal)
        # carries it on the Offer inlined in the proposal (EP-04-004,
        # CP-01-008).  Surfaced here so no use case re-reads the wire
        # activity for it (ADR-0035).
        proposed_embargo = proposed_embargo_from(
            activity if terms_on_activity else obj, activity_id=activity.id_
        )
    extra_kwargs = _build_object_kwargs(
        obj,
        _obj_type,
        context,
        target,
        include_activity,
        activity,
        actor_id,
        origin,
        # Carried as received on the activity the entry records (CS-13-005,
        # CLP-07-011); core reads it back through ``parse_published``.
        activity_end_time=(
            _activity_end_time(activity) if carries_deadline else None
        ),
        # Terms the activity carries itself are part of the Offer the
        # receiver archives and inlines in its case proposal (CP-01-008).
        activity_proposed_embargo=(
            proposed_embargo if terms_on_activity else None
        ),
    )

    if "rsvp_deadline" in event_class.model_fields:
        extra_kwargs["rsvp_deadline"] = _effective_rsvp_deadline(
            activity, actor_id, obj, min_rsvp_window, default_rsvp_window
        )
    extra_kwargs.update(_deadline_kwargs(activity, obj, event_class))
    if carries_terms:
        extra_kwargs["proposed_embargo"] = proposed_embargo

    extra_kwargs.update(_content_kwargs(activity, event_class))

    if "proposer_profile" in event_class.model_fields:
        # Create(CaseProposal)'s actor is the proposer's inline profile
        # (CP-01-010).  The parse edge refuses any other shape; an activity
        # that reached here some other way is refused the same way, so core
        # always receives the profile (ADR-0032).
        actor = getattr(activity, "actor", None)
        if not isinstance(actor, CoreActor):
            raise VultronParseValidationError(
                f"Create(CaseProposal) {activity.id_!r} carries no inline"
                f" actor profile (got {type(actor).__name__}); the"
                " proposer's profile is the only source of the CASE_OWNER's"
                " actor default (CP-01-010)"
            )
        extra_kwargs["proposer_profile"] = actor

    if "proposer_case_roles" in event_class.model_fields:
        # The proposer's own roles ride on the proposal (CP-01-011, ADR-0133):
        # the CASE_MANAGER has no other way to learn them.  as_CaseProposal
        # refused a CASE_MANAGER claim when it was parsed (CP-01-012).  Any
        # other object is refused rather than read as "no roles", which would
        # seat the owner as CASE_OWNER alone without a sound.
        if not isinstance(obj, as_CaseProposal):
            raise VultronParseValidationError(
                f"Create(CaseProposal) {activity.id_!r} carries no parsed"
                f" CaseProposal (got {type(obj).__name__}); its"
                " proposerCaseRoles cannot be read (CP-01-011)"
            )
        extra_kwargs["proposer_case_roles"] = list(obj.proposer_case_roles)

    return cast(
        AnyReceivedEvent,
        event_class(
            semantic_type=semantics,
            activity_id=activity.id_,
            activity_type=str(activity.type_) if activity.type_ else None,
            actor_id=sender_id,
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
            # Carried, never re-derived: core records it in the ledger as
            # received (VM-08-002, CLP-07-011, ADR-0107).
            received_evidence=activity.received_evidence_json,
            **extra_kwargs,
        ),
    )


def _activity_end_time(activity: object) -> datetime | None:
    """The activity-level ``end_time`` as received, or ``None``.

    ``as_Object.validate_datetime`` already read a naive value as UTC, so
    the value is aware; its offset is the sender's.
    """
    raw_end_time = getattr(activity, "end_time", None)
    return raw_end_time if isinstance(raw_end_time, datetime) else None


def _answer_deadline(activity: object) -> datetime | None:
    """The ownership-transfer Offer's deadline to answer, in UTC (CM-21-016).

    The activity-level ``end_time``, normalised to UTC here, at the edge
    (ADR-0032), so core compares and reports one zone (CS-13-001).  ``None``
    when the Offer names no deadline.
    """
    end_time = _activity_end_time(activity)
    return end_time.astimezone(UTC) if end_time is not None else None


def _deadline_kwargs(
    activity: as_Activity, obj: object, event_class: type[VultronEvent]
) -> dict[str, datetime | None]:
    """The ownership-transfer answer deadlines the event carries, in UTC.

    An Offer carries its own as ``answer_deadline``; the owner's proposal
    carries it on the inner Offer it asks the CASE_MANAGER to make, as
    ``proposed_answer_deadline`` (ADR-0148, CM-21-016).
    """
    kwargs: dict[str, datetime | None] = {}
    if "answer_deadline" in event_class.model_fields:
        kwargs["answer_deadline"] = _answer_deadline(activity)
    if "proposed_answer_deadline" in event_class.model_fields:
        kwargs["proposed_answer_deadline"] = _answer_deadline(obj)
    return kwargs


def _content_kwargs(
    activity: as_Activity, event_class: type[VultronEvent]
) -> dict[str, object]:
    """The event fields parsed from the activity's ``content`` at the edge.

    Also the ``ledgerPosition`` a ``Read(CaseLedgerEntry)`` states, the one
    such field the activity carries as a Vultron property (SYNC-17-001).

    Core receives the parsed value (ADR-0032); an absent or malformed one is
    refused with a reason (``VultronParseValidationError``).
    """
    kwargs: dict[str, object] = {}
    if "ledger_tail" in event_class.model_fields:
        # The full-case Invite and its replies each carry a ledger position as
        # the JSON dump of a LedgerPosition in ``content`` (VAM-04-019).
        kwargs["ledger_tail"] = ledger_position_from_content(activity)
    if "ledger_position" in event_class.model_fields:
        # A Read(CaseLedgerEntry) states its position as the Vultron
        # property ``ledgerPosition``, which as_Read already parsed as a
        # LedgerPosition (SYNC-17-001).  The pattern admits only a Read that
        # carries one, so its absence here is refused, never defaulted.
        position = getattr(activity, "ledger_position", None)
        if not isinstance(position, LedgerPosition):
            raise VultronParseValidationError(
                f"activity {activity.id_!r} states no ledgerPosition; a"
                " Read(CaseLedgerEntry) must carry the position of the entry"
                " it names (SYNC-17-001)"
            )
        kwargs["ledger_position"] = position
    if "termination_reason" in event_class.model_fields:
        # A termination Remove carries its what in ``content``: exactly
        # END_TIME_REACHED or EARLY, refused otherwise (ADR-0122); and its
        # why, when named, as ``terminationCause`` (EMB-13-005).
        termination = termination_of(activity)
        kwargs["termination_reason"] = termination.reason
        kwargs["termination_cause"] = termination.cause
    elif getattr(activity, "termination_cause", None) is not None:
        # Only a termination Remove(EmbargoEvent) has a why (EMB-13-005).
        # Any other Remove naming one is refused here, so the cause never
        # reaches a ledger snapshot through an activity that cannot carry it.
        raise VultronParseValidationError(
            f"activity {activity.id_!r} carries a terminationCause, but only"
            " a termination Remove(EmbargoEvent) may name one (EMB-13-005)"
        )
    return kwargs


def _effective_rsvp_deadline(
    activity: as_Activity,
    actor_id: str,
    embargo: object,
    min_window: timedelta,
    default_window: timedelta,
) -> datetime:
    """Return the deadline an inbound embargo invite is held to.

    Clamps are applied, never refused (EP-07-004), and each one is logged
    (EP-07-005).  Windows are measured from the invite's ``published`` time;
    an activity without one is measured from now.

    Every input is already UTC-aware: the activity's fields by
    ``as_Object.validate_datetime`` and the nested embargo's ``end_time`` by
    ``CoreObject`` (CS-13-001, #3784).
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
            "extract_intent: activity '%s' from actor '%s' rsvp_deadline %s"
            " (%s) is below the applicable minimum; clamped up to %s"
            " (EP-07-003)",
            activity.id_,
            actor_id,
            deadline.computed.isoformat(),
            source,
            deadline.effective.isoformat(),
        )
    elif deadline.clamp is RsvpDeadlineClamp.LOWERED_TO_EMBARGO_END:
        logger.info(
            "extract_intent: activity '%s' from actor '%s' rsvp_deadline %s"
            " (%s) is after the embargo end; clamped down to %s (EP-07-006)",
            activity.id_,
            actor_id,
            deadline.computed.isoformat(),
            source,
            deadline.effective.isoformat(),
        )
    if deadline.effective <= now_utc():
        logger.warning(
            "extract_intent: activity '%s' from actor '%s' rsvp_deadline %s"
            " is already past (published %s); the invitation lapses on the"
            " next check",
            activity.id_,
            actor_id,
            deadline.effective.isoformat(),
            published.isoformat() if published is not None else "absent",
        )
    return deadline.effective
