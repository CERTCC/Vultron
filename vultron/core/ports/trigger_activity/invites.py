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


"""TriggerInvitesPort: the invites part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Case and full-case invitations and their answers.
"""

from datetime import datetime
from typing import Protocol

from vultron.core.models.case import VulnerabilityCase


class TriggerInvitesPort(Protocol):
    """Case and full-case invitations and their answers."""

    def invite_actor_to_case(
        self,
        invitee_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
        attributed_to: str | None = None,
        roles: list[str] | None = None,
        target: VulnerabilityCase | None = None,
        rsvp_deadline: datetime | None = None,
        published: datetime | None = None,
        in_reply_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Invite(Actor)[target=VulnerabilityCaseStub]`` activity.

        ``actor`` MUST be the CASE_MANAGER's ID (PCR-08-007); ``attributed_to``
        MAY carry the case owner's ID for attribution.  There is no ``cc``:
        the CASE_MANAGER commits the Invite in the tree that emits it and
        never addresses a copy to itself (CM-17-015, ADR-0109).
        ``id_`` allows callers to supply a deterministic ID for idempotency.
        ``roles`` carries the intended CVD roles for the invitee (CM-17-003).
        ``target`` may be a core ``VulnerabilityCase`` (the adapter projects it
        to an enriched stub carrying the embargo in force, EM ``ACTIVE`` or
        ``REVISE``),
        a pre-built stub, or a bare URI string.  When ``None``, the adapter reads
        the case from the DataLayer by ``case_id`` (CM-17-002).
        ``rsvp_deadline`` becomes the Invite's ``endTime``, the reply deadline
        the CASE_MANAGER stamps as it does on an embargo Invite (CM-11-014,
        CM-28-012, ASK-03-004); ``published`` is the instant it was measured
        from.  ``in_reply_to`` names the stub Invite this one replaces, in the
        standard AS2 ``inReplyTo`` property, after an embargo change or a
        re-invite (CM-11-015, CM-11-016).  Each is forwarded only when given.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def invite_actor_to_full_case(
        self,
        invitee_id: str,
        case_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist the full-case ``Invite(Actor)[target=VulnerabilityCase]``.

        ``actor`` MUST be the CASE_MANAGER's ID.  The Invite references the
        case by ID and carries the CASE_MANAGER's ledger tail
        (``ledger_log_index``, ``ledger_entry_hash``) as the floor the
        invitee's reply must reach (CM-11-010, VAM-04-011).
        Returns ``(activity_id, activity_blob)``.
        """
        ...

    def accept_full_case_invite(
        self,
        invite_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
    ) -> tuple[str, str]:
        """Create and persist ``Accept(full-case Invite)`` — RV (VAM-04-012).

        The reply carries the replier's own ledger position
        (``ledger_log_index``, ``ledger_entry_hash``).  The ``to:`` field is
        the Invite's sender.  Returns ``(activity_id, activity_blob)``.
        """
        ...

    def tentative_reject_full_case_invite(
        self,
        invite_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
    ) -> tuple[str, str]:
        """Create and persist ``TentativeReject(full-case Invite)`` — RI (VAM-04-013).

        Returns ``(activity_id, activity_blob)``.
        """
        ...

    def reject_full_case_invite(
        self,
        invite_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
    ) -> tuple[str, str]:
        """Create and persist ``Reject(full-case Invite)`` — RC (VAM-04-014).

        Returns ``(activity_id, activity_blob)``.
        """
        ...

    def accept_case_invite(
        self,
        invite_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Invite)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def reject_case_invite(
        self,
        invite_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Invite)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...
