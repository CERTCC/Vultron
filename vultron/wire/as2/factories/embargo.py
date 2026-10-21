#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""
Factory functions for outbound Vultron embargo-management activities.

These are the sole public construction API for activities involving
``as_EmbargoEvent`` objects. Internal activity subclasses are
imported here and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError

from vultron.core.models._helpers import as_utc, now_utc
from vultron.core.models.embargo_termination import TerminationCause
from vultron.core.models.rsvp_deadline import (
    DEFAULT_MIN_RSVP_WINDOW,
    RsvpDeadlineClamp,
    resolve_rsvp_deadline,
)
from vultron.core.states.embargo_register import TerminationReason
from vultron.wire.as2.errors import VultronParseError
from vultron.wire.as2.factories._context import (
    case_target_ref,
    with_case_context,
)
from vultron.wire.as2.factories._held import as_answered
from vultron.wire.as2.factories._inline import require_inline
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.activities.embargo import (
    _ActivateEmbargoActivity,
    _AnnounceEmbargoActivity,
    _CreateEmbargoConsentActivity,
    _EmAcceptEmbargoActivity,
    _EmProposeEmbargoActivity,
    _EmRejectEmbargoActivity,
    _IgnoreLateEmbargoAcceptActivity,
    _RejectEmbargoProposalActivity,
    _RemoveEmbargoFromCaseActivity,
    _UpdateEmbargoConsentActivity,
    _WithdrawFromEmbargoActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Announce,
    as_Create,
    as_Ignore,
    as_Invite,
    as_Leave,
    as_Reject,
    as_Remove,
    as_Update,
)
from vultron.wire.as2.vocab.objects.embargo_consent import (
    as_EmbargoConsent,
)
from vultron.wire.as2.vocab.objects.embargo_event import (
    as_EmbargoEvent,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseRef,
)

logger = logging.getLogger(__name__)


def _published_instant(published: object) -> datetime | None:
    """Read a caller-supplied ``published`` as an aware instant.

    This is the one input to the RSVP-deadline check not read from a
    validated object, so it is normalised at this edge (ADR-0032, CS-13-001)
    whether it arrived as an ISO 8601 string or a naive ``datetime``;
    ``resolve_rsvp_deadline`` expects aware inputs (#3784).  Anything else
    yields ``None``, which the deadline check measures from now.

    Raises:
        VultronActivityConstructionError: If a string is not ISO 8601.
    """
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published)
        except ValueError as exc:
            raise VultronActivityConstructionError(
                f"em_propose_embargo_activity: published {published!r}"
                " is not an ISO 8601 datetime"
            ) from exc
    return as_utc(published) if isinstance(published, datetime) else None


def em_propose_embargo_activity(
    embargo: as_EmbargoEvent,
    context: as_VulnerabilityCaseRef | None = None,
    rsvp_deadline: datetime | None = None,
    min_rsvp_window: timedelta = DEFAULT_MIN_RSVP_WINDOW,
    **kwargs,
) -> as_Invite:
    """Build an Invite(as_EmbargoEvent) — the EP/EV message.

    Proposes a new embargo for the case.

    Args:
        embargo: The ``as_EmbargoEvent`` being proposed.
        context: The ``VulnerabilityCase`` (or its URI) for which the
            embargo is being proposed.
        rsvp_deadline: Optional RSVP-by deadline set on the activity-level
            ``end_time`` (CM-27-001, ADR-0065). MUST be timezone-aware, no
            earlier than the applicable minimum — ``min_rsvp_window`` after
            ``published`` (or now), or the embargo's ``end_time`` if that is
            sooner (EP-07-002) — and no later than the embargo's
            ``end_time`` (EP-07-006).
        min_rsvp_window: Configured minimum RSVP window; defaults to 72 hours
            (EP-07-002). Pass ``ActorConfig.min_rsvp_window`` from the caller
            to apply the configured floor.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Invite`` whose ``object_`` is the embargo event, with
        ``end_time`` set to *rsvp_deadline* when provided.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails, or
            if *rsvp_deadline* is naive, below the applicable minimum, or
            after the embargo's end, or if *embargo* is not an
            ``as_EmbargoEvent``.
    """
    # The wire class takes the terms by URI for a received Invite (ADR-0123);
    # this codebase always sends them inline (VAM-01-010).
    embargo = require_inline(
        embargo, as_EmbargoEvent, factory="em_propose_embargo_activity"
    )
    if rsvp_deadline is not None:
        if rsvp_deadline.tzinfo is None:
            raise VultronActivityConstructionError(
                "em_propose_embargo_activity: rsvp_deadline must be"
                " timezone-aware (naive datetime rejected per EP-07-002)"
            )
        # Fix ``published`` before measuring from it, so the window the
        # sender checks is the one the receiver measures (EP-07-002).
        deadline = resolve_rsvp_deadline(
            requested=rsvp_deadline,
            published=_published_instant(
                kwargs.setdefault("published", now_utc())
            ),
            embargo_end=embargo.end_time,
            min_window=min_rsvp_window,
        )
        if deadline.clamp is RsvpDeadlineClamp.RAISED_TO_MINIMUM:
            raise VultronActivityConstructionError(
                f"em_propose_embargo_activity: rsvp_deadline"
                f" {rsvp_deadline.isoformat()} is below the minimum"
                f" window floor {deadline.minimum.isoformat()} (EP-07-002)"
            )
        if deadline.clamp is RsvpDeadlineClamp.LOWERED_TO_EMBARGO_END:
            raise VultronActivityConstructionError(
                f"em_propose_embargo_activity: rsvp_deadline"
                f" {rsvp_deadline.isoformat()} is after the embargo end"
                f" {deadline.effective.isoformat()} (EP-07-006)"
            )
        kwargs["end_time"] = rsvp_deadline
    try:
        return _EmProposeEmbargoActivity(
            object_=embargo, context=context, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "em_propose_embargo_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "em_propose_embargo_activity: invalid arguments"
        ) from exc


def em_accept_embargo_activity(
    proposal: as_Invite,
    context: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_EmProposeEmbargoActivity) — the EA/EC message.

    Per ActivityStreams convention the actor accepts the proposal
    activity itself, not the ``as_EmbargoEvent`` being proposed.
    The ``proposal`` MUST be the value returned by
    :func:`em_propose_embargo_activity`, or the Invite a receiver parsed
    from its archived body, which the answer embeds verbatim
    (:func:`as_answered`); a plain ``as_Invite`` will fail validation.

    Args:
        proposal: The ``_EmProposeEmbargoActivity`` being accepted.
        context: The ``VulnerabilityCase`` (or its URI) for which the
            embargo was proposed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the proposal.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _EmAcceptEmbargoActivity(
            object_=as_answered(_EmProposeEmbargoActivity, proposal),
            context=context,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "em_accept_embargo_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "em_accept_embargo_activity: invalid arguments"
        ) from exc


def em_reject_embargo_activity(
    proposal: as_Invite,
    context: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_EmProposeEmbargoActivity) — the ER/EJ message.

    Per ActivityStreams convention the actor rejects the proposal
    activity itself, not the ``as_EmbargoEvent`` being proposed.
    The ``proposal`` MUST be the value returned by
    :func:`em_propose_embargo_activity`, or the Invite a receiver parsed
    from its archived body, which the answer embeds verbatim
    (:func:`as_answered`); a plain ``as_Invite`` will fail validation.

    Args:
        proposal: The ``_EmProposeEmbargoActivity`` being rejected.
        context: The ``VulnerabilityCase`` (or its URI) for which the
            embargo was proposed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the proposal.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _EmRejectEmbargoActivity(
            object_=as_answered(_EmProposeEmbargoActivity, proposal),
            context=context,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "em_reject_embargo_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "em_reject_embargo_activity: invalid arguments"
        ) from exc


def ignore_late_embargo_accept_activity(
    late_accept: dict[str, Any],
    **kwargs,
) -> as_Ignore:
    """Build the CASE_MANAGER's ``Ignore(Accept(Invite(EmbargoEvent)))`` (EMB-17-004).

    The no-op acknowledgement of a late embargo ``Accept``: the Invite had
    expired and no embargo remains for the Accept to bind, so the
    CASE_MANAGER records the answer and changes nothing.  *late_accept* is
    the received ``Accept``'s body, as the receiver archived it, carried
    inline as it arrived (:func:`as_answered`);
    the ``Ignore`` is the CASE_MANAGER's own act (pass it as ``actor``).
    ``context`` defaults to the case the Accept names.

    Args:
        late_accept: The received ``Accept(Invite(EmbargoEvent))``, with its
            Invite inline.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``id_``, ``in_reply_to``, ``context``).

    Returns:
        An ``as_Ignore`` whose ``object_`` is the late Accept.

    Raises:
        VultronActivityConstructionError: If *late_accept* is not an embargo
            Accept or Pydantic validation fails.
    """
    try:
        # Parsed as the inbox parses a body, then embedded as it arrived
        # (DL-06-004, ADR-0149).
        accept = as_answered(
            _EmAcceptEmbargoActivity, parse_activity(late_accept)
        )
        return _IgnoreLateEmbargoAcceptActivity(
            object_=accept, **with_case_context(kwargs, accept.context)
        )
    except (ValidationError, VultronParseError) as exc:
        logger.warning(
            "ignore_late_embargo_accept_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "ignore_late_embargo_accept_activity: invalid arguments"
        ) from exc


def activate_embargo_activity(
    embargo: as_EmbargoEvent,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Accept:
    """Build an Accept(as_EmbargoEvent, target=VulnerabilityCase).

    The case owner's activation of a proposed embargo (ADR-0122): the
    receiver activates the embargo's register entry, superseding any entry
    in force, and records the owner's agreement.  Distinct from
    :func:`em_accept_embargo_activity`, the sender's own consent to an
    Invite.  Only the case owner sends it.

    Args:
        embargo: The ``as_EmbargoEvent`` being activated, carried inline.
        target: The ``VulnerabilityCase`` (or its URI) the embargo was
            proposed for.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``context``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _ActivateEmbargoActivity(
            object_=embargo, target=case_target_ref(target), **kwargs
        )
    except ValidationError as exc:
        logger.warning("activate_embargo_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "activate_embargo_activity: invalid arguments"
        ) from exc


def reject_embargo_proposal_activity(
    embargo: as_EmbargoEvent,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Reject:
    """Build a Reject(as_EmbargoEvent, target=VulnerabilityCase).

    The case owner's rejection of a proposed embargo (ADR-0122): the
    receiver rejects the embargo's register entry and writes no consent.
    Distinct from :func:`em_reject_embargo_activity`, the sender's own
    refusal of an Invite.  Only the case owner sends it.

    Args:
        embargo: The ``as_EmbargoEvent`` being rejected, carried inline.
        target: The ``VulnerabilityCase`` (or its URI) the embargo was
            proposed for.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``context``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RejectEmbargoProposalActivity(
            object_=embargo, target=case_target_ref(target), **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "reject_embargo_proposal_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "reject_embargo_proposal_activity: invalid arguments"
        ) from exc


def withdraw_from_embargo_activity(
    embargo: as_EmbargoEvent,
    context: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Leave:
    """Build a Leave(as_EmbargoEvent)[context=VulnerabilityCase].

    A signatory's withdrawal from the embargo in force (MSM-07-010,
    ADR-0122): the receiver declines the sender's ``AGREED`` row for the
    active embargo, and every open proposal's row it had agreed to, and
    changes no register entry.  Distinct from
    :func:`em_reject_embargo_activity`, which answers an Invite and never
    withdraws, and from ``Leave(VulnerabilityCase)``, which leaves the case.
    The case owner does not send it.

    Args:
        embargo: The ``as_EmbargoEvent`` in force, carried inline.
        context: The ``VulnerabilityCase`` (or its URI) the embargo is on.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Leave`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _WithdrawFromEmbargoActivity(
            object_=embargo, context=context, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "withdraw_from_embargo_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "withdraw_from_embargo_activity: invalid arguments"
        ) from exc


def announce_embargo_activity(
    embargo: as_EmbargoEvent,
    context: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Announce:
    """Build an Announce(as_EmbargoEvent) — announces an active embargo.

    Args:
        embargo: The ``as_EmbargoEvent`` being announced.
        context: The ``VulnerabilityCase`` (or its URI) for which the
            embargo is active.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Announce`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AnnounceEmbargoActivity(
            object_=embargo, context=context, **kwargs
        )
    except ValidationError as exc:
        logger.warning("announce_embargo_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "announce_embargo_activity: invalid arguments"
        ) from exc


#: The human-readable ``summary`` of a termination ``Remove``, by reason.
#: The protocol reads ``content``, never this (ADR-0122).
_TERMINATION_SUMMARY: dict[TerminationReason, str] = {
    TerminationReason.END_TIME_REACHED: "The embargo reached its end time.",
    TerminationReason.EARLY: "The embargo ended before its end time.",
}


def remove_embargo_from_case_activity(
    embargo: as_EmbargoEvent,
    origin: as_VulnerabilityCaseRef | None = None,
    *,
    reason: TerminationReason,
    cause: TerminationCause | None = None,
    **kwargs,
) -> as_Remove:
    """Build a Remove(as_EmbargoEvent, origin=VulnerabilityCase).

    Ends the embargo in force on a case (ET): the receiver terminates the
    case's ``ACTIVE`` embargo register entry and cancels every open proposal
    with it (MSM-07-006, ADR-0122).  This MUST only be performed by the case
    owner, or by the CASE_MANAGER.

    *reason* is the termination's what, carried as ``content``: exactly
    ``END_TIME_REACHED`` or ``EARLY`` (ADR-0122).  *cause* is its why, when
    the sender names one, carried as ``terminationCause`` (EMB-13-005); an
    ``END_TIME_REACHED`` termination has none.  ``summary`` defaults to a
    human-readable account the protocol does not read; pass ``summary`` to
    override it, as an ``OTHER`` cause does to give its account.

    Note: this activity uses ``origin`` (not ``target``) for the case
    reference, following the ActivityStreams convention for Remove.

    Args:
        embargo: The ``as_EmbargoEvent`` to remove.
        origin: The ``VulnerabilityCase`` (or its URI) from which
            the embargo is removed.
        reason: What ended the embargo; required.
        cause: Why it ended, or ``None`` when the sender names no cause.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Remove`` whose ``object_`` is the embargo event and
        ``origin`` is the case reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails,
            including a *cause* on an ``END_TIME_REACHED`` termination.
    """
    try:
        kwargs.setdefault("summary", _TERMINATION_SUMMARY[reason])
        return _RemoveEmbargoFromCaseActivity(
            object_=embargo,
            origin=origin,
            content=reason.value,
            termination_cause=cause,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "remove_embargo_from_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "remove_embargo_from_case_activity: invalid arguments"
        ) from exc


def create_embargo_consent_activity(
    row: as_EmbargoConsent,
    **kwargs,
) -> as_Create:
    """Build a Create(as_EmbargoConsent): the CASE_MANAGER created a row.

    The snapshot shape of a CASE_MANAGER-authored ledger entry carrying the
    new consent row in full (ADR-0122, CLP-07-013); never sent as a message.

    Args:
        row: The new consent row; it names its participant actor.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``context``, ``id_``).

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _CreateEmbargoConsentActivity(object_=row, **kwargs)
    except ValidationError as exc:
        logger.warning(
            "create_embargo_consent_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "create_embargo_consent_activity: invalid arguments"
        ) from exc


def update_embargo_consent_activity(
    row: as_EmbargoConsent,
    **kwargs,
) -> as_Update:
    """Build an Update(as_EmbargoConsent): the CASE_MANAGER changed a row.

    The snapshot shape of a CASE_MANAGER-authored ledger entry carrying the
    changed consent row in full (ADR-0122, CLP-07-013); never sent as a
    message.

    Args:
        row: The changed consent row; it names its participant actor.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``context``, ``id_``).

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _UpdateEmbargoConsentActivity(object_=row, **kwargs)
    except ValidationError as exc:
        logger.warning(
            "update_embargo_consent_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "update_embargo_consent_activity: invalid arguments"
        ) from exc
