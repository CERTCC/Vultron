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


"""TriggerEmbargoPort: the embargo part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Embargo proposal, answers, activation, withdrawal and termination.
"""

from datetime import datetime, timedelta
from typing import Protocol

from vultron.core.models.embargo_termination import TerminationCause
from vultron.core.states.embargo_register import TerminationReason


class TriggerEmbargoPort(Protocol):
    """Embargo proposal, answers, activation, withdrawal and termination."""

    def propose_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        activity_id: str | None = None,
        rsvp_deadline: datetime | None = None,
        min_rsvp_window: timedelta | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Invite(EmbargoEvent)[context=VulnerabilityCase]``.

        The Invite is the embargo proposal.

        ``attributed_to`` carries the proposer when the CASE_MANAGER relays a
        proposal on a participant's behalf (CM-24-002, EP-09-002): ``actor`` is
        then the CASE_MANAGER and ``attributed_to`` the participant whose terms
        these are.
        ``activity_id`` is the Invite's id when the caller recorded it before
        the emission — the creation-time revision is indexed under its
        Invite's id at registration and relayed only after the initialization
        sequence completes (EP-04-011, CM-14-014).  ``None`` mints a fresh id.
        ``rsvp_deadline`` becomes the Invite's ``endTime`` (CM-28-012,
        ASK-03-004), measured from *at*, the act's instant and the Invite's
        ``published``; ``min_rsvp_window`` is the configured floor the factory
        checks it against (EP-07-002).  Each is forwarded only when given.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        derived_id: bool = False,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Invite)`` embargo-accept activity.

        With *derived_id* the id is derived from *actor* and the Invite: the
        automatic answer to a received Invite is one activity however often
        the Invite is delivered (ID-04-004), and a second build returns the
        first one's id and body.  Without it the id is fresh, so a deliberate
        ``Accept`` after the actor's own ``Reject`` is a new activity, a
        changed answer (CM-18-003).  Returns ``(activity_id, activity_dict)``.
        """
        ...

    def reject_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        derived_id: bool = False,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Invite)`` embargo-reject activity.

        With *derived_id* the id is derived from *actor* and the Invite: the
        automatic rejection of a received Invite is one activity however
        often the Invite is delivered (ID-04-004), and a second build returns
        the first one's id and body.  Without it the id is fresh, so a
        deliberate ``Reject`` after the actor's own ``Accept`` (or a second
        ``Reject`` after a first one) is a new activity, a changed answer
        (CM-18-003).  Returns ``(activity_id, activity_dict)``.
        """
        ...

    def undo_embargo_invite(
        self,
        invite_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Undo(Invite)`` of an embargo Invite *actor* sent.

        The CASE_MANAGER's withdrawal of an Invite it sent, when it abandons
        an open proposal (EMB-16-001, ADR-0152).  The id is derived from
        *actor* and the Invite, so one Invite is withdrawn by one activity
        (ID-04-004).  Returns ``(activity_id, activity_dict)``.
        """
        ...

    def activate_embargo(
        self,
        embargo_id: str,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist the case owner's ``Add(EmbargoEvent)[target=VulnerabilityCase]``.

        The owner's activation of a proposed embargo (ADR-0180), distinct
        from :meth:`accept_embargo`, the sender's own consent to an Invite.
        *proposal_id* is the ``Invite(EmbargoEvent)`` that proposed the
        embargo, as the owner's store records it for the open proposal; the
        activity names it in ``inReplyTo`` (RF-08-001).
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def reject_embargo_proposal(
        self,
        embargo_id: str,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist the case owner's ``Reject(EmbargoEvent)[target=VulnerabilityCase]``.

        The owner's rejection of a proposed embargo (ADR-0122), distinct
        from :meth:`reject_embargo`, the sender's own refusal of an Invite.
        *proposal_id* is named in ``inReplyTo`` as for
        :meth:`activate_embargo` (ADR-0180).
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def withdraw_from_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Leave(EmbargoEvent)[context=VulnerabilityCase]``
        activity.

        A signatory's withdrawal from the embargo in force (MSM-07-010,
        ADR-0122), distinct from :meth:`reject_embargo`, which answers an
        Invite and never withdraws.  Returns ``(activity_id, activity_dict)``.
        """
        ...

    def requeue_embargo_refusal(self, actor: str, proposal_id: str) -> bool:
        """Whether *actor* already rejected the Invite *proposal_id*.

        A ``Reject`` of one Invite by one actor is a single activity, so a
        repeat refusal of a re-delivered Invite can be told from the first.
        A ``Reject`` that was sealed but is no longer pending is queued again
        under the same id, so a refusal whose queue write failed is not lost
        (ID-04-005).
        """
        ...

    def answered_embargo_invite(self, actor: str, proposal_id: str) -> bool:
        """Whether *actor* already sent its automatic answer to *proposal_id*.

        Read-only.  True when *actor* built a derived ``Accept``
        (:meth:`accept_embargo` with ``derived_id=True``) or a derived
        ``Reject`` (:meth:`reject_embargo` with ``derived_id=True``) of the
        Invite: the latch that keeps a re-delivered Invite from being
        answered twice (ID-04-004).  A deliberate (fresh-id) answer is not
        detected here, because each deliberate answer is a new activity and
        the guard is not appropriate for it.
        """
        ...

    def announce_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Announce(EmbargoEvent)`` activity.

        *attributed_to*, when given, names the actor whose request the
        CASE_MANAGER is carrying out (CM-24-002), as on the CM-31-009 notice
        of a shorter revision.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def terminate_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        *,
        reason: TerminationReason,
        cause: TerminationCause | None = None,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Remove(EmbargoEvent)`` ET activity.

        Corresponds to the ET (Embargo Termination) protocol message.
        *reason* is the termination's what, carried as ``content``
        (ADR-0122); *cause* is its why, carried as ``terminationCause``
        when given (EMB-13-005).  The CASE_MANAGER passes the cause it
        records on its own ``TERMINATED`` entry.
        *attributed_to*, when given, names the actor whose request the
        CASE_MANAGER is carrying out (CM-24-002), as on the CM-31-009 notice
        to a bound signatory the ledger no longer reaches.
        Returns ``(activity_id, activity_dict)``.
        """
        ...
