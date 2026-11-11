"""The kwargs ``extract_intent`` adds for particular semantics.

A fault's unresolved object, a proposal's proposer profile, an Offer's answer
deadline, a ``content`` the semantics reads, a sender's ledger position and an
embargo Invite's effective RSVP deadline are each read here, at the parse
edge, so core receives validated values (ADR-0032).
"""

import logging
from datetime import UTC, datetime, timedelta

from vultron.core.models.actor import CoreActor
from vultron.core.models.events import (
    VultronEvent,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.rsvp_deadline import (
    RsvpDeadlineClamp,
    resolve_rsvp_deadline,
)
from vultron.primitives import normalise_actor_id
from vultron.wire.as2.errors import (
    VultronParseMissingPublishedError,
    VultronParseValidationError,
)
from vultron.wire.as2.extractor._builders import (
    termination_of,
)
from vultron.wire.as2.extractor._builders.fields import (
    _get_id,
)
from vultron.wire.as2.extractor._pattern import bare_object_id
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault

logger = logging.getLogger(__name__)


def _unresolved_object_id(activity: as_Activity) -> str:
    """The bare id ending the ``object`` chain of an unresolvable activity.

    Classified ``UNKNOWN_UNRESOLVABLE_OBJECT`` only because the chain ends in
    a bare id, so one is always there; the fetch names it at any depth
    (VAM-01-009, AKM-05-007).

    Raises:
        VultronParseValidationError: When the chain ends in no bare id.
    """
    object_id = bare_object_id(activity)
    if object_id is None:
        raise VultronParseValidationError(
            f"Activity {activity.id_!r} is unresolvable but its object chain"
            " ends in no bare id (VAM-01-009)"
        )
    return object_id


def _proposer_profile(activity: as_Activity) -> CoreActor | str:
    """The proposer's profile a ``Create(CaseProposal)`` carries, or its id.

    The ``actor`` is the proposer's inline profile, or the proposer's id,
    which the inbox dereferences before dispatch (CP-01-009, CP-01-010).  The
    parse edge refuses any other shape; an activity that reached here some
    other way is refused the same way, so core always receives one of the
    two (ADR-0032).

    Raises:
        VultronParseValidationError: When the ``actor`` is neither.
    """
    actor = getattr(activity, "actor", None)
    if isinstance(actor, str) and actor:
        return normalise_actor_id(actor)
    if isinstance(actor, CoreActor):
        return actor
    raise VultronParseValidationError(
        f"Create(CaseProposal) {activity.id_!r} carries neither an"
        " inline actor profile nor the proposer's id (got"
        f" {type(actor).__name__}); the proposer's profile is the"
        " only source of the CASE_OWNER's actor default (CP-01-016)"
    )


def _fault_kwargs(
    activity: as_Activity, obj: object, event_class: type[VultronEvent]
) -> dict[str, object]:
    """The fault fields a ``Create(ProcessingFault)`` event carries.

    Empty for every other event class.
    """
    fields = event_class.model_fields
    extra_kwargs: dict[str, object] = {}
    if "failed_activity_id" in fields:
        # Create(ProcessingFault): the fault object's inReplyTo names the
        # activity that failed (ASK-07-004).  Extracted here at the parse edge
        # so core never reads the wire object for it (ADR-0032, ADR-0035).
        extra_kwargs["failed_activity_id"] = _get_id(
            getattr(obj, "in_reply_to", None)
        )
    if "failure_class" in fields:
        # The receiver's response depends on the fault's class (ASK-07-005,
        # SYNC-16-003), so it is carried to core here.  The pattern matches
        # only an inline ProcessingFault, whose failureClass is required; any
        # other object is refused rather than read as a fault of no class
        # (ADR-0032).
        if not isinstance(obj, as_ProcessingFault):
            raise VultronParseValidationError(
                f"Create(ProcessingFault) {activity.id_!r} carries no parsed"
                f" ProcessingFault (got {type(obj).__name__}); its"
                " failureClass cannot be read (ASK-07-005)"
            )
        extra_kwargs["failure_class"] = obj.failure_class
    return extra_kwargs


def _activity_end_time(activity: object) -> datetime | None:
    """The activity-level ``end_time`` as received, or ``None``.

    ``as_Object.validate_datetime`` already read a naive value as UTC, so
    the value is aware; its offset is the sender's.
    """
    raw_end_time = getattr(activity, "end_time", None)
    return raw_end_time if isinstance(raw_end_time, datetime) else None


def _answer_deadline(activity: object) -> datetime | None:
    """The ownership-transfer Offer's deadline to answer, in UTC (CM-21-042).

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

    Also the sender's ``ledgerPosition`` (SYNC-18-001), which the activity
    carries as a Vultron property rather than in ``content``.

    Core receives the parsed value (ADR-0032); an absent or malformed one is
    refused with a reason (``VultronParseValidationError``).
    """
    kwargs: dict[str, object] = {}
    if "ledger_position" in event_class.model_fields:
        kwargs["ledger_position"] = _ledger_position(activity, event_class)
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


def _ledger_position(
    activity: as_Activity, event_class: type[VultronEvent]
) -> LedgerPosition | None:
    """The sender's ledger position the activity states (SYNC-18-001).

    ``as_Activity`` already parsed ``ledgerPosition`` as a
    ``LedgerPosition``, so a malformed one never reaches here.  An event
    class that requires the position (a ``LedgerPositionedEvent``) refuses
    an activity that carries none, naming it, before anything is written
    (SYNC-18-015); one that admits its absence (``Reject(CaseLedgerEntry)``
    from a peer that holds no ledger yet) gets ``None`` (SYNC-18-016).

    Raises:
        VultronParseValidationError: when the event class requires the
            position and the activity states none.
    """
    position = getattr(activity, "ledger_position", None)
    if isinstance(position, LedgerPosition):
        return position
    if event_class.model_fields["ledger_position"].is_required():
        raise VultronParseValidationError(
            f"activity {activity.id_!r} states no ledgerPosition: a case"
            " activity must carry its sender's ledger tail (SYNC-18-015)"
        )
    return None


def _effective_rsvp_deadline(
    activity: as_Activity,
    actor_id: str,
    embargo: object,
    min_window: timedelta,
    default_window: timedelta,
) -> datetime:
    """Return the deadline an inbound embargo invite is held to.

    Clamps are applied, never refused (EP-07-004), and each one is logged
    (EP-07-005).  Windows are measured from the invite's ``published`` time,
    which ``parse_activity`` already requires (CLP-15-008).  No clock is
    read here: whether the deadline has already passed is the handler's
    question, asked at the act's instant (ADR-0176).

    Every input is already UTC-aware: the activity's fields by
    ``as_Object.validate_datetime`` and the nested embargo's ``end_time`` by
    ``CoreObject`` (CS-13-001, #3784).

    Raises:
        VultronParseMissingPublishedError: When *activity* carries no
            ``published``; never measured from a clock instead.
    """
    raw_end_time = getattr(activity, "end_time", None)
    requested = raw_end_time if isinstance(raw_end_time, datetime) else None
    published = getattr(activity, "published", None)
    if not isinstance(published, datetime):
        raise VultronParseMissingPublishedError(
            f"Invite(EmbargoEvent) {activity.id_!r} carries no 'published'"
            " to measure its RSVP deadline from (CLP-15-008)"
        )
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
    return deadline.effective
