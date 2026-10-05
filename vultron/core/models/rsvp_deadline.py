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

"""Effective RSVP deadline for an embargo invitation (EP-07, CM-28-011).

One computation serves both sides of an ``Invite(EmbargoEvent)``: the sender
refuses a deadline this would move (EP-07-002, EP-07-006), and the receiver
applies the moved value (EP-07-003, EP-07-006).  Keeping the two rules in one
function is what makes them agree: the minimum is capped at the embargo's end,
so raising a deadline to the minimum can never carry it past that end.

Layer-neutral, so the wire extractor can call it (ADR-0099).  Inputs are
timezone-aware by contract: they are read from ``as_Object`` or ``CoreObject``
fields, both of which normalise a naive timestamp to UTC at construction
(CS-13-001, #3784), so no guard is repeated here.
"""

from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import ConfigDict

from vultron.core.models._helpers import now_utc
from vultron.core.models.base import ValidatedAssignmentMixin

DEFAULT_MIN_RSVP_WINDOW = timedelta(hours=72)
"""Default minimum RSVP window (EP-07-002)."""

DEFAULT_RSVP_WINDOW = timedelta(days=7)
"""Default policy RSVP window when an invite names no deadline (EP-07-001)."""

INVITE_EXPIRED_EVENT_TYPE = "invite_to_embargo_on_case_expired"
"""Ledger ``event_type`` of the CASE_MANAGER's invite-expiry entry (CM-28-009).

The entry records ``PEC_Trigger.EXPIRE`` (``INVITED → EXPIRED``), distinct from
the ``Reject(Invite)`` entry of an explicit refusal (CM-28-005, ADR-0118).
"""

INVITE_EXPIRED_SNAPSHOT_TYPE = "Expire"
"""``payloadSnapshot.type`` of the invite-expiry entry; its object is the Invite."""


class RsvpDeadlineClamp(StrEnum):
    """Which rule, if any, moved the requested deadline."""

    NONE = "none"
    RAISED_TO_MINIMUM = "raised_to_minimum"  # EP-07-003
    LOWERED_TO_EMBARGO_END = "lowered_to_embargo_end"  # EP-07-006


class RsvpDeadline(ValidatedAssignmentMixin):
    """An effective RSVP deadline and how it was derived from the request.

    Attributes:
        requested: The invite's explicit ``end_time``, or ``None`` when the
            policy window supplied the deadline (EP-07-001).
        computed: The deadline before any clamp — ``requested``, or the
            policy window measured from ``published``.
        minimum: The applicable minimum: the configured window from
            ``published`` or the embargo's end, whichever is earlier
            (EP-07-002).
        effective: The deadline after clamping.
        clamp: The clamp that produced ``effective`` from ``computed``.
    """

    model_config = ConfigDict(frozen=True)

    requested: datetime | None
    computed: datetime
    minimum: datetime
    effective: datetime
    clamp: RsvpDeadlineClamp


def resolve_rsvp_deadline(
    *,
    requested: datetime | None,
    published: datetime | None,
    embargo_end: datetime | None,
    min_window: timedelta = DEFAULT_MIN_RSVP_WINDOW,
    default_window: timedelta = DEFAULT_RSVP_WINDOW,
) -> RsvpDeadline:
    """Compute the effective RSVP deadline for an embargo invitation.

    Args:
        requested: The invite's explicit ``end_time``, if any.
        published: The invitation's ``published`` time; every window is
            measured from it (EP-07-001, EP-07-002).  ``None`` measures from
            now.
        embargo_end: The invited embargo's ``end_time``; ``None`` when the
            embargo has no end, in which case no down-clamp applies.
        min_window: Configured minimum RSVP window (EP-07-002).
        default_window: Configured policy window used when *requested* is
            ``None`` (EP-07-001, CM-18-002).

    Every datetime argument MUST be timezone-aware (CS-13-001); the objects
    they are read from guarantee it.  Results are correct instants and carry
    the inputs' offsets; the wire serializer, not this function, decides how
    an instant is rendered (CS-13-005).

    Returns:
        The resolved deadline.  ``effective`` never falls after
        *embargo_end* (EP-07-006, CM-28-011) and never before ``minimum``.
    """
    if published is None:
        published = now_utc()
    computed = (
        requested if requested is not None else published + default_window
    )
    minimum = published + min_window
    if embargo_end is not None:
        minimum = min(minimum, embargo_end)

    effective, clamp = computed, RsvpDeadlineClamp.NONE
    if effective < minimum:
        effective, clamp = minimum, RsvpDeadlineClamp.RAISED_TO_MINIMUM
    if embargo_end is not None and effective > embargo_end:
        effective, clamp = (
            embargo_end,
            RsvpDeadlineClamp.LOWERED_TO_EMBARGO_END,
        )
    return RsvpDeadline(
        requested=requested,
        computed=computed,
        minimum=minimum,
        effective=effective,
        clamp=clamp,
    )


__all__ = [
    "DEFAULT_MIN_RSVP_WINDOW",
    "DEFAULT_RSVP_WINDOW",
    "RsvpDeadline",
    "RsvpDeadlineClamp",
    "resolve_rsvp_deadline",
]
