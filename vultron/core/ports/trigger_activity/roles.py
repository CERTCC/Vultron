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


"""TriggerRolesPort: the roles part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Case Actor / CASE_MANAGER delegation: participant-role offers and answers.
"""

from datetime import datetime
from typing import Protocol

from vultron.enums.roles import CVDRole


class TriggerRolesPort(Protocol):
    """Case Actor / CASE_MANAGER delegation: participant-role offers and answers."""

    def offer_case_participant_role(
        self,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        in_reply_to: str | None = None,
        id_: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist ``Offer(CaseParticipantRole)[context=VulnerabilityCase]``.

        Canonical role-delegation wire format (ADR-0039).  ``role`` is the
        :class:`CVDRole` being offered; ``target_actor_id`` is the Actor URI
        receiving the offer; ``case_id`` supplies the VulnerabilityCase context.
        The Case Owner addresses its Offer to the CASE_MANAGER (CM-33-001).
        The CASE_MANAGER's forward to the target passes ``attributed_to`` (the
        Case Owner, CM-24-005), ``in_reply_to`` (the recorded Offer's id) and
        a derived ``id_``, so a retry rebuilds the same forward (OX-06-002).

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_case_participant_role(
        self,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(_OfferCaseParticipantRoleActivity)`` (ADR-0039).

        Ephemerally reconstructs the original Offer (using ``offer_id``,
        ``case_id``, ``role``, ``target_actor_id``, and ``vendor_id``)
        before building the Accept so that ``Accept.object_`` is a typed
        ``_OfferCaseParticipantRoleActivity``, not a bare string IRI.
        ``id_`` allows callers to supply a deterministic ID for idempotency.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def reject_case_participant_role(
        self,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(_OfferCaseParticipantRoleActivity)`` (ADR-0039).

        Ephemerally reconstructs the original Offer before building the
        Reject so that ``Reject.object_`` is a typed
        ``_OfferCaseParticipantRoleActivity``, not a bare string IRI.
        ``id_`` allows callers to supply a deterministic id for idempotency.

        Returns ``(activity_id, activity_json)``.
        """
        ...
