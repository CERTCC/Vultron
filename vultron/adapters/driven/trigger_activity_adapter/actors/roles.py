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

from vultron.adapters.received_archive import read_received_as_received
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.wire.as2.factories.case import (
    accept_case_participant_role_activity,
    offer_case_participant_role_activity,
    reject_case_participant_role_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)

from .._base import (
    _addressing,
    _case_for_wire,
    _create_and_seal,
    _delegation,
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
        extra.update(_delegation(attributed_to, in_reply_to))
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

    def _held_role_offer(self, offer_id: str) -> as_Offer:
        """The role Offer as this actor received it.

        The answer embeds the Offer as its sender sent it, parsed from the
        body intake recorded on arrival (:func:`read_received_as_received`),
        with its ``published`` and every other field as sent.  Nothing is
        rebuilt: a rebuild carries only what this actor knows, stamped with
        the answer's own time, so the answer would quote an Offer nobody sent
        (AKM-02-006, DL-06-004).  Every build under the same ids embeds the
        same Offer (OX-06-002).

        Raises:
            VultronNotFoundError: when no activity with *offer_id* was
                received.
            VultronValidationError: when the activity received under
                *offer_id* is not an Offer.
        """
        held = read_received_as_received(
            self._dl, offer_id, "Offer(CaseParticipantRole)"
        )
        if not isinstance(held, as_Offer):
            raise VultronValidationError(
                f"role offer '{offer_id}' is held as {type(held).__name__},"
                " not as an Offer"
            )
        return held

    def _answer_case_participant_role(
        self,
        build: Callable[..., as_Accept | as_Reject],
        label: str,
        offer_id: str,
        actor: str,
        to: list[str] | None,
        id_: str | None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Build, persist and seal one answer to an ``Offer(CaseParticipantRole)``.

        Shared by the Accept and the Reject (ADR-0039): the answer embeds the
        Offer as received (:meth:`_held_role_offer`), and a caller-supplied
        ``id_`` is kept so a retry rebuilds the same answer (OX-06-002).

        Raises:
            VultronNotFoundError: when the Offer was not received.
            VultronValidationError: when the activity received under
                *offer_id* is not an Offer.
        """
        offer = self._held_role_offer(offer_id)
        activity = build(offer=offer, **_addressing(actor, to, id_), at=at)
        return _create_and_seal(self._dl, activity, label)

    def accept_case_participant_role(
        self,
        offer_id: str,
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
            actor=actor,
            to=to,
            id_=id_,
            at=at,
        )

    def reject_case_participant_role(
        self,
        offer_id: str,
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
            actor=actor,
            to=to,
            id_=id_,
            at=at,
        )
