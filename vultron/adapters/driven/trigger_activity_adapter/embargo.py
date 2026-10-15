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

from vultron.adapters.outbox_sealed_body import requeue_if_sealed
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import (
    VultronActivityConstructionError,
)
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    announce_embargo_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    ignore_late_embargo_accept_activity,
    reject_embargo_proposal_activity,
    remove_embargo_from_case_activity,
    withdraw_from_embargo_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._base import (
    _create_and_seal,
    _seal_record,
    _to_wire,
)

logger = logging.getLogger(__name__)


def _attribution(attributed_to: str | None) -> dict[str, str]:
    """``attributed_to`` as a factory keyword, only when given (CM-24-002).

    Absent, the factory keeps its default of no attribution, so an activity
    the CASE_MANAGER decides on its own names nobody else.
    """
    return {} if attributed_to is None else {"attributed_to": attributed_to}


def _reject_id(actor: str, proposal_id: str) -> str:
    """The id of *actor*'s ``Reject`` of the Invite *proposal_id*."""
    return derived_activity_id("embargo-reject", actor, proposal_id)


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
        return _create_and_seal(self._dl, activity, "propose_embargo")

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
        return _create_and_seal(self._dl, activity, "accept_embargo")

    def reject_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Invite)`` embargo-reject activity.

        The id is derived from the rejecting actor and the Invite, so an
        actor's rejection of one Invite is one activity (ID-04-004) and
        :meth:`requeue_embargo_refusal` can tell it was sent.
        """
        proposal = cast(Any, self._dl.read(proposal_id))
        activity = em_reject_embargo_activity(
            proposal=proposal,
            context=case_id,
            actor=actor,
            to=to,
            id_=_reject_id(actor, proposal_id),
        )
        return _create_and_seal(self._dl, activity, "reject_embargo")

    def ignore_late_embargo_accept(
        self,
        case_id: str,
        actor: str,
        late_accept: dict[str, Any],
    ) -> tuple[str, str]:
        """Build and seal the CASE_MANAGER's ``Ignore`` of a late embargo ``Accept``.

        The EMB-17-004 no-op acknowledgement.  *late_accept* is carried
        inline; *actor* (the CASE_MANAGER) is the ``Ignore``'s
        only author, and the ``Ignore`` is threaded to the Accept by
        ``inReplyTo``.  The id is derived from the CASE_MANAGER and the
        Accept, so a redelivered Accept hands back the body its first
        delivery sealed (ID-04-004, VM-08-003).  Not addressed to anyone: the
        ledger fan-out delivers it.
        """
        accept_id = late_accept.get("id")
        if not isinstance(accept_id, str) or not accept_id:
            raise VultronActivityConstructionError(
                "ignore_late_embargo_accept: the late Accept has no id"
            )
        activity = ignore_late_embargo_accept_activity(
            late_accept,
            actor=actor,
            context=case_id,
            in_reply_to=accept_id,
            id_=derived_activity_id("late-accept-ignore", actor, accept_id),
        )
        return _seal_record(self._dl, activity)

    def activate_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist the owner's ``Accept(as_EmbargoEvent, target=case)``.

        ``context`` names the case as well, so the snapshot the CASE_MANAGER
        commits carries the case URI there (VM-08-003, #4085).
        """
        embargo = _to_wire(self._dl.read(embargo_id), as_EmbargoEvent)
        activity = activate_embargo_activity(
            embargo=embargo,
            target=case_id,
            context=case_id,
            actor=actor,
            to=to,
        )
        return _create_and_seal(self._dl, activity, "activate_embargo")

    def reject_embargo_proposal(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist the owner's ``Reject(as_EmbargoEvent, target=case)``.

        ``context`` names the case as well, so the snapshot the CASE_MANAGER
        commits carries the case URI there (VM-08-003, #4085).
        """
        embargo = _to_wire(self._dl.read(embargo_id), as_EmbargoEvent)
        activity = reject_embargo_proposal_activity(
            embargo=embargo,
            target=case_id,
            context=case_id,
            actor=actor,
            to=to,
        )
        return _create_and_seal(self._dl, activity, "reject_embargo_proposal")

    def withdraw_from_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Leave(as_EmbargoEvent)[context=case]``.

        A signatory's withdrawal from the embargo in force (MSM-07-010).  The
        case is the activity's ``context``, which is also where the snapshot
        the CASE_MANAGER commits carries the case URI (VM-08-003).
        """
        embargo = _to_wire(self._dl.read(embargo_id), as_EmbargoEvent)
        activity = withdraw_from_embargo_activity(
            embargo=embargo,
            context=case_id,
            actor=actor,
            to=to,
        )
        return _create_and_seal(self._dl, activity, "withdraw_from_embargo")

    def requeue_embargo_refusal(self, actor: str, proposal_id: str) -> bool:
        """Whether *actor* already rejected the Invite *proposal_id*.

        The sealed body is written before the caller queues the ``Reject``, so
        a sealed ``Reject`` that is no longer pending may have been delivered
        or may never have been queued; the queue cannot say which.  It is
        queued again under the same id and body, which the receiver
        deduplicates, so a failure between the two writes never loses the ER
        (ID-04-005).  A ``Reject`` still pending is left alone.
        """
        return requeue_if_sealed(self._dl, _reject_id(actor, proposal_id))

    def announce_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Announce(as_EmbargoEvent)`` activity."""
        embargo = _to_wire(self._dl.read(embargo_id), as_EmbargoEvent)
        activity = announce_embargo_activity(
            embargo=embargo,
            context=case_id,
            actor=actor,
            to=to,
            **_attribution(attributed_to),
        )
        return _create_and_seal(self._dl, activity, "announce_embargo")

    def terminate_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Remove(as_EmbargoEvent, origin=case)`` ET activity.

        ``context`` names the case as well: the CASE_MANAGER commits its own
        teardown as a canonical entry, whose snapshot must carry the case URI
        in ``context`` (VM-08-003, #4085).
        """
        embargo = _to_wire(self._dl.read(embargo_id), as_EmbargoEvent)
        activity = remove_embargo_from_case_activity(
            embargo=embargo,
            origin=case_id,
            context=case_id,
            actor=actor,
            to=to,
            **_attribution(attributed_to),
        )
        return _create_and_seal(self._dl, activity, "terminate_embargo")
