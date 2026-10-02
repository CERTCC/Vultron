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

"""Embargo-domain trigger activity construction for TriggerActivityAdapter."""

import logging
from datetime import datetime, timedelta
from typing import Any, cast

from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronAlreadyExistsError
from vultron.wire.as2.factories import (
    announce_embargo_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._base import _seal, _to_wire

logger = logging.getLogger(__name__)


class _EmbargoMixin:
    """Trigger activity methods for embargo negotiation and lifecycle."""

    _dl: CaseOutboxPersistence

    def propose_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        activity_id: str | None = None,
        rsvp_deadline: datetime | None = None,
        published: datetime | None = None,
        min_rsvp_window: timedelta | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Invite(as_EmbargoEvent, Case)`` proposal.

        ``attributed_to`` names the proposer of a relayed proposal (CM-24-002);
        it is forwarded only when given so a participant's own proposal keeps
        the factory's default of no attribution.  ``activity_id`` likewise:
        given, it is the Invite's id (EP-04-011); absent, the factory mints one.
        So are ``rsvp_deadline`` (the Invite's ``endTime``, CM-28-012) and the
        ``published`` instant and ``min_rsvp_window`` floor the factory
        validates it against (EP-07-002, EP-07-006).
        """
        embargo = _to_wire(self._dl.read(embargo_id), as_EmbargoEvent)
        optional: dict[str, Any] = {
            key: value
            for key, value in (
                ("attributed_to", attributed_to),
                ("id_", activity_id),
                ("rsvp_deadline", rsvp_deadline),
                ("published", published),
                ("min_rsvp_window", min_rsvp_window),
            )
            if value is not None
        }
        activity = em_propose_embargo_activity(
            embargo=embargo, context=case_id, actor=actor, to=to, **optional
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "propose_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def accept_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Invite)`` embargo-accept activity."""
        proposal = cast(Any, self._dl.read(proposal_id))
        activity = em_accept_embargo_activity(
            proposal=proposal, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "accept_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def reject_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Invite)`` embargo-reject activity."""
        proposal = cast(Any, self._dl.read(proposal_id))
        activity = em_reject_embargo_activity(
            proposal=proposal, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "reject_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def announce_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Announce(as_EmbargoEvent)`` activity."""
        embargo = _to_wire(self._dl.read(embargo_id), as_EmbargoEvent)
        activity = announce_embargo_activity(
            embargo=embargo, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "announce_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def terminate_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Remove(as_EmbargoEvent, origin=case)`` ET activity."""
        embargo = _to_wire(self._dl.read(embargo_id), as_EmbargoEvent)
        activity = remove_embargo_from_case_activity(
            embargo=embargo, origin=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "terminate_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)
