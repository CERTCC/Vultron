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
"""Factories for the EM negotiation messages: propose, accept, reject, withdraw.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from datetime import datetime, timedelta

from vultron.core.models._helpers import as_utc
from vultron.core.models.rsvp_deadline import (
    DEFAULT_MIN_RSVP_WINDOW,
    RsvpDeadlineClamp,
    resolve_rsvp_deadline,
)
from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.factories._held import as_answered
from vultron.wire.as2.factories._inline import require_inline
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.embargo import (
    _EmAcceptEmbargoActivity,
    _EmProposeEmbargoActivity,
    _EmRejectEmbargoActivity,
    _EmUndoEmbargoInviteActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Reject,
    as_Undo,
)
from vultron.wire.as2.vocab.objects.embargo_event import (
    as_EmbargoEvent,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseRef,
)


def em_propose_embargo_activity(
    embargo: as_EmbargoEvent,
    context: as_VulnerabilityCaseRef | None = None,
    rsvp_deadline: datetime | None = None,
    min_rsvp_window: timedelta = DEFAULT_MIN_RSVP_WINDOW,
    *,
    at: datetime,
    **kwargs,
) -> as_Invite:
    """Build an Invite(EmbargoEvent) — the EP/EV message.

    Proposes a new embargo for the case.

    Args:
        embargo: The ``as_EmbargoEvent`` being proposed.
        context: The ``VulnerabilityCase`` (or its URI) for which the
            embargo is being proposed.
        rsvp_deadline: Optional RSVP-by deadline set on the activity-level
            ``end_time`` (CM-27-001, ADR-0065). MUST be timezone-aware, no
            earlier than the applicable minimum — ``min_rsvp_window`` after
            ``published``, or the embargo's ``end_time`` if that is
            sooner (EP-07-002) — and no later than the embargo's
            ``end_time`` (EP-07-006).  The window is measured from *at*.
        min_rsvp_window: Configured minimum RSVP window; defaults to 72 hours
            (EP-07-002). Pass ``ActorConfig.min_rsvp_window`` from the caller
            to apply the configured floor.
        at: The authoring act's instant: the Invite's ``published``, which
            the RSVP window is measured from (ADR-0176).
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
    # this codebase always sends them inline (VAM-01-016).
    embargo = require_inline(
        embargo, as_EmbargoEvent, factory="em_propose_embargo_activity"
    )
    if rsvp_deadline is not None:
        if rsvp_deadline.tzinfo is None:
            raise VultronActivityConstructionError(
                "em_propose_embargo_activity: rsvp_deadline must be"
                " timezone-aware (naive datetime rejected per EP-07-002)"
            )
        # Measure from *at*, the Invite's ``published``, so the window the
        # sender checks is the one the receiver measures (EP-07-002).  A
        # naive *at* is read as UTC (CS-13-001, #3784).
        deadline = resolve_rsvp_deadline(
            requested=rsvp_deadline,
            published=as_utc(at),
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
    return build_activity(
        "em_propose_embargo_activity",
        _EmProposeEmbargoActivity,
        at,
        lambda: {"object_": embargo, "context": context, **kwargs},
    )


def em_accept_embargo_activity(
    proposal: as_Invite,
    context: as_VulnerabilityCaseRef | None = None,
    *,
    at: datetime,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_EmProposeEmbargoActivity) — a Participant's consent.

    The Accept is the sender's own consent to the proposed terms and carries
    no protocol shorthand; EA and EC are the Case Owner's decision, built by
    :func:`activate_embargo_activity` (MSM-02-010).

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
    return build_activity(
        "em_accept_embargo_activity",
        _EmAcceptEmbargoActivity,
        at,
        lambda: {
            "object_": as_answered(_EmProposeEmbargoActivity, proposal),
            "context": context,
            **kwargs,
        },
    )


def em_reject_embargo_activity(
    proposal: as_Invite,
    context: as_VulnerabilityCaseRef | None = None,
    *,
    at: datetime,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_EmProposeEmbargoActivity) — a refusal of the terms.

    A Participant's Reject is its own consent, declining the terms, and
    carries no protocol shorthand; ER and EJ are the Case Owner's decision,
    built by :func:`reject_embargo_proposal_activity` (MSM-02-010).  The
    CASE_MANAGER's own Reject abandons the proposal, and is ER (MSM-02-006,
    EMB-16-001).

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
    return build_activity(
        "em_reject_embargo_activity",
        _EmRejectEmbargoActivity,
        at,
        lambda: {
            "object_": as_answered(_EmProposeEmbargoActivity, proposal),
            "context": context,
            **kwargs,
        },
    )


def em_undo_embargo_invite_activity(
    invite: as_Invite,
    context: as_VulnerabilityCaseRef | None = None,
    *,
    at: datetime,
    **kwargs,
) -> as_Undo:
    """Build an Undo(_EmProposeEmbargoActivity): withdraw an Invite one sent.

    The CASE_MANAGER's withdrawal of an embargo Invite it sent, when it
    abandons an open proposal (EMB-16-001, ADR-0152).  An actor undoes only
    an activity it performed; declining an Invite one received is
    :func:`em_reject_embargo_activity`.  The ``invite`` is embedded verbatim
    (:func:`as_answered`), as the Invite the sender holds; a plain
    ``as_Invite`` will fail validation.

    Args:
        invite: The ``_EmProposeEmbargoActivity`` being withdrawn.
        context: The ``VulnerabilityCase`` (or its URI) the embargo was
            proposed for.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Undo`` whose ``object_`` is the Invite.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "em_undo_embargo_invite_activity",
        _EmUndoEmbargoInviteActivity,
        at,
        lambda: {
            "object_": as_answered(_EmProposeEmbargoActivity, invite),
            "context": context,
            **kwargs,
        },
    )
