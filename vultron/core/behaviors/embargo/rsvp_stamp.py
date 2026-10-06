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

"""The CASE_MANAGER's RSVP-deadline stamp on an embargo Invite it sends.

Every embargo Invite the CASE_MANAGER sends — each relayed revision
(EP-09-002) and the EMB-17-003 re-invite of a stale signatory — carries the
deadline its addressee must answer by, so the ask carries its own deadline
(ASK-03-004).  The manager sets it as the Invite's ``published`` plus its
configured ``default_rsvp_window``, floored at ``min_rsvp_window`` (EP-07-002)
and capped at the embargo's own end (EP-07-006): CM-28-012.  The same value
is what the manager records against the invitee at commit and what each
replica records from the committed entry (CM-28-013), so nothing downstream
re-derives it.
"""

from datetime import datetime, timedelta

from pydantic import ConfigDict

from vultron.config.actor import ActorConfig
from vultron.core.models._helpers import now_utc
from vultron.core.models.base import ValidatedAssignmentMixin
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.rsvp_deadline import resolve_rsvp_deadline
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronNotFoundError


class InviteRsvpStamp(ValidatedAssignmentMixin):
    """The instants an outgoing embargo Invite is stamped with.

    Attributes:
        published: The Invite's ``published`` — the instant every RSVP window
            is measured from (EP-07-001, EP-07-002).
        rsvp_deadline: The Invite's ``endTime`` (CM-28-012).
        min_rsvp_window: The configured floor the activity factory checks
            ``rsvp_deadline`` against, so sender and receiver measure the
            same window (EP-07-002).
    """

    model_config = ConfigDict(frozen=True)

    published: datetime
    rsvp_deadline: datetime
    min_rsvp_window: timedelta


def stamp_invite_rsvp_deadline(
    dl: CasePersistence,
    embargo_id: str,
    actor_config: ActorConfig | None = None,
) -> InviteRsvpStamp:
    """Compute the RSVP deadline for an Invite to *embargo_id* sent now.

    Args:
        dl: The sender's store; the invited embargo is read from it.
        embargo_id: The embargo the Invite proposes.
        actor_config: The sender's configuration; ``None`` applies the
            ``ActorConfig`` defaults.

    Raises:
        VultronNotFoundError: If the store holds no ``EmbargoEvent`` for
            *embargo_id* — the Invite would have nothing to stamp against.
    """
    embargo = dl.read(embargo_id)
    if not isinstance(embargo, EmbargoEvent):
        raise VultronNotFoundError("EmbargoEvent", embargo_id)
    config = actor_config if actor_config is not None else ActorConfig()
    published = now_utc()
    deadline = resolve_rsvp_deadline(
        requested=None,
        published=published,
        embargo_end=embargo.end_time,
        min_window=config.min_rsvp_window,
        default_window=config.default_rsvp_window,
    )
    return InviteRsvpStamp(
        published=published,
        rsvp_deadline=deadline.effective,
        min_rsvp_window=config.min_rsvp_window,
    )


__all__ = ["InviteRsvpStamp", "stamp_invite_rsvp_deadline"]
