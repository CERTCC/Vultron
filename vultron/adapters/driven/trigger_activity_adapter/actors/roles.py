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


"""Trigger activity methods for CASE_MANAGER delegation: participant-role offers
and their answers.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories.case import (
    accept_case_participant_role_activity,
    offer_case_participant_role_activity,
    reject_case_participant_role_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Reject,
)

from .._base import (
    _addressing,
    _case_for_wire,
    _create_and_seal,
)
from ._helpers import (
    _held_actor,
)


class _RolesMixin:
    """Trigger activity methods for CASE_MANAGER delegation: participant-role
    offers and their answers.
    """

    _dl: CaseOutboxPersistence

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

        The canonical role-delegation wire format introduced by ADR-0039.
        *attributed_to* and *in_reply_to*, when given, make it the
        CASE_MANAGER's forward of a recorded Offer (CM-33-008); a given *id_*
        is kept so a retry rebuilds the same activity (OX-06-002).

        Returns ``(activity_id, activity_dict)``.
        """
        case = _case_for_wire(self._dl, case_id)
        target = _held_actor(self._dl, target_actor_id)
        extra: dict[str, Any] = _addressing(actor, to, id_)
        if attributed_to is not None:
            extra["attributed_to"] = attributed_to
        if in_reply_to is not None:
            extra["in_reply_to"] = in_reply_to
        activity = offer_case_participant_role_activity(
            role=role,
            target_actor=target,
            case=case,
            **extra,
            at=at,
        )
        return _create_and_seal(
            self._dl, activity, "offer_case_participant_role"
        )

    def _answer_case_participant_role(
        self,
        build: Callable[..., as_Accept | as_Reject],
        label: str,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None,
        id_: str | None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Build, persist and seal one answer to an ``Offer(CaseParticipantRole)``.

        Shared by the Accept and the Reject (ADR-0039): the Offer is rebuilt
        ephemerally so the answer's ``object_`` is a typed
        ``_OfferCaseParticipantRoleActivity``, and a caller-supplied ``id_``
        is kept so a retry rebuilds the same answer (OX-06-002).
        """
        target = _held_actor(self._dl, target_actor_id)
        case = _case_for_wire(self._dl, case_id)
        offer = offer_case_participant_role_activity(
            role=role,
            target_actor=target,
            case=case,
            id_=offer_id,
            actor=vendor_id,
            at=at,
        )
        activity = build(offer=offer, **_addressing(actor, to, id_), at=at)
        return _create_and_seal(self._dl, activity, label)

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
        """Create and persist an ``Accept(_OfferCaseParticipantRoleActivity)`` (ADR-0039)."""
        return self._answer_case_participant_role(
            accept_case_participant_role_activity,
            "accept_case_participant_role",
            offer_id=offer_id,
            case_id=case_id,
            role=role,
            target_actor_id=target_actor_id,
            vendor_id=vendor_id,
            actor=actor,
            to=to,
            id_=id_,
            at=at,
        )

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
        """Create and persist a ``Reject(_OfferCaseParticipantRoleActivity)`` (ADR-0039)."""
        return self._answer_case_participant_role(
            reject_case_participant_role_activity,
            "reject_case_participant_role",
            offer_id=offer_id,
            case_id=case_id,
            role=role,
            target_actor_id=target_actor_id,
            vendor_id=vendor_id,
            actor=actor,
            to=to,
            id_=id_,
            at=at,
        )
