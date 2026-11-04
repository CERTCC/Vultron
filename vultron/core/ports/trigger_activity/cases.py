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


"""TriggerCasesPort: the cases part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

VulnerabilityCase creation, engagement, closure and announcement.
"""

from typing import Protocol

from vultron.core.models.events.base import MessageSemantics


class TriggerCasesPort(Protocol):
    """VulnerabilityCase creation, engagement, closure and announcement."""

    def create_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Create(VulnerabilityCase)`` activity.

        ``id_`` allows callers to supply a deterministic ID for idempotency.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def close_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Leave(VulnerabilityCase)`` close-case activity.

        Per ADR-0021 CLP-10-027: routes the activity to the Case Actor so the
        CaseActor can commit a canonical ledger entry.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def engage_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(VulnerabilityCase)`` engage activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def defer_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``TentativeReject(VulnerabilityCase)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def add_object_to_case_semantics(
        self,
        object_id: str,
        case_id: str,
    ) -> MessageSemantics:
        """Return what a receiver would read ``Add(object)[target=VulnerabilityCase]`` as.

        Classifies the ``Add`` that :meth:`add_object_to_case` would build
        for the stored object against the receive-side patterns, without
        persisting it.  The add-object trigger asks this
        before its tree runs so it can refuse an object the CASE_MANAGER
        could not route, and the answer names the ledger ``semantic_type`` the
        CASE_MANAGER's commit of the ``Add`` will carry (TRIG-10-001,
        SYNC-11-002).

        Raises:
            VultronNotFoundError: when the case or the object is not stored.
            VultronActivityConstructionError: when the object has no wire
                representation or cannot be carried in an ``Add``.
            VultronValidationError: when no receive-side pattern routes the
                ``Add`` as an addition to the case, or when the object is of
                a type whose addition the protocol carries by its own flow
                (``EmbargoEvent``, ``CaseParticipant``, ``CaseStatus``).
        """
        ...

    def add_object_to_case(
        self,
        actor: str,
        object_id: str,
        case_id: str,
        to: list[str],
    ) -> tuple[str, str]:
        """Create and persist an ``Add(object)[target=VulnerabilityCase]`` activity
        addressed to *to*.

        *to* is the CASE_MANAGER alone: the ``Add`` is a participant asking
        the case to take the object (PCR-08-005).

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def reject_close_case(
        self,
        case_id: str,
        actor: str,
        close_sender: str,
        in_reply_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Leave(VulnerabilityCase))`` activity.

        Emitted by the Case Actor to decline an owner's
        ``Leave(VulnerabilityCase)`` while an embargo is still active
        (CM-23-011).  ``actor`` is the Case Actor sending the decline;
        ``close_sender`` is the Case Owner who sent the Leave and is used as the
        sole ``to`` recipient so the decline is routable back to them.
        ``in_reply_to`` threads the decline to the received Leave activity.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def announce_vulnerability_case(
        self,
        case_id: str,
        actor: str,
        context_id: str,
        to: list[str],
    ) -> str:
        """Create and persist an ``Announce(VulnerabilityCase)`` activity.

        Sent by the case owner to a newly accepted participant after their
        embargo consent is resolved (MV-10-003).  The full case object is
        sent inline so the recipient can seed their local DataLayer.

        Returns the activity ID.
        """
        ...
