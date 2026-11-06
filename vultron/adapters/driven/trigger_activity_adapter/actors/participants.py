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


"""Trigger activity methods for participant offers, actor recommendations, and
participant membership and status.
"""

import logging
from collections.abc import Callable
from typing import cast

from vultron.adapters.received_archive import (
    read_received_as_received,
)
from vultron.core.models._helpers import _as_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    accept_case_participant_offer_activity,
    add_participant_to_case_activity,
    add_status_to_participant_activity,
    offer_case_participant_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
    reject_case_participant_offer_activity,
    remove_participant_from_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus

from .._base import (
    _addressing,
    _already_sealed,
    _create_and_seal,
    _to_wire,
)
from ._helpers import (
    _held_actor,
)

logger = logging.getLogger(__name__)


class _ParticipantsMixin:
    """Trigger activity methods for participant offers, actor recommendations,
    and participant membership and status.
    """

    _dl: CaseOutboxPersistence

    def _answer_case_participant_offer(
        self,
        build: Callable[..., as_Accept | as_Reject],
        label: str,
        cp_offer_id: str,
        actor: str,
        to: list[str] | None,
    ) -> tuple[str, str]:
        """Build, persist and seal the Case Owner's answer to a forwarded Offer.

        Shared by the Accept (CM-16-006) and the Reject (CM-16-007).  The
        Offer is read as received: parsed from the body intake recorded,
        which holds the participant inline (#3763).  The answer embeds it
        verbatim, and addresses the case as the Offer did (AKM-02-002).
        """
        cp_offer = cast(
            as_Offer,
            read_received_as_received(
                self._dl, cp_offer_id, "Offer(CaseParticipant)"
            ),
        )
        target = _as_id(getattr(cp_offer, "target", None))
        activity = build(offer=cp_offer, actor=actor, to=to, target=target)
        return _create_and_seal(self._dl, activity, label)

    def accept_case_participant_offer(
        self,
        cp_offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Offer(CaseParticipant))`` activity.

        Sent by the Case Owner to the CaseActor after reviewing the
        Offer(CaseParticipant) forwarded per ADR-0026 (CM-16-006).
        The ``to:`` list should contain the CaseActor URI so the Accept routes
        back to CaseActor for processing.
        """
        return self._answer_case_participant_offer(
            accept_case_participant_offer_activity,
            "accept_case_participant_offer",
            cp_offer_id,
            actor,
            to,
        )

    def reject_case_participant_offer(
        self,
        cp_offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Offer(CaseParticipant))`` activity.

        Sent by the Case Owner to the CASE_MANAGER after reviewing the
        Offer(CaseParticipant) forwarded per ADR-0026 (CM-16-007).
        The ``to:`` list should contain the CASE_MANAGER URI so the Reject
        routes back to it for processing.
        """
        return self._answer_case_participant_offer(
            reject_case_participant_offer_activity,
            "reject_case_participant_offer",
            cp_offer_id,
            actor,
            to,
        )

    def suggest_actor_to_case(
        self,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
        roles: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Offer(Actor)[target=VulnerabilityCase]``
        recommendation activity."""
        extra = _addressing(actor, to, id_)
        # The factory accepts a string for target (case ID).
        activity = recommend_actor_activity(
            recommended=_held_actor(self._dl, recommended_id),
            target=case_id,
            suggested_roles=roles,
            **extra,
        )
        return _create_and_seal(self._dl, activity, "suggest_actor_to_case")

    def offer_actor_to_case(
        self,
        recommender_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        origin: str | None = None,
        to: list[str] | None = None,
        id_: str | None = None,
        roles: list | None = None,
    ) -> tuple[str, str]:
        """Create and persist an Offer(CaseParticipant)[target=VulnerabilityCase].

        Transforms the original Offer(Actor)[target=VulnerabilityCase] from a recommending
        participant into an Offer(CaseParticipant) naming the actor and its roles,
        addressed to the Case Owner.
        ``roles`` defaults to ``[CVDRole.VENDOR]`` when ``None`` (CM-16-003).
        ``origin`` carries the original Offer ID for causal traceability
        (CM-16-004).  An Offer already built under *id_* is returned as
        sealed, without storing a second inline participant.
        """
        if (built := _already_sealed(self._dl, id_)) is not None:
            return built
        extra = _addressing(actor, to, id_)
        if origin is not None:
            extra["origin"] = origin
        activity = offer_case_participant_activity(
            recommended=recommended_id,
            target=case_id,
            roles=roles,
            **extra,
        )
        # Save the inline CaseParticipant so dl.read() can expand it during
        # outbox delivery (AKM-03-003: dehydration stores object_ as a bare ID).
        if isinstance(activity.object_, as_CaseParticipant):
            try:
                self._dl.create(activity.object_)
            except ValueError:
                pass
        return _create_and_seal(self._dl, activity, "offer_actor_to_case")

    def _rebuilt_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
    ) -> as_Offer:
        """The recommender's ``Offer(Actor)``, rebuilt for the answer to embed.

        Built only from what this actor knows: the recommended actor as held
        (:func:`_held_actor`), and no ``published`` or ``updated``, which the
        recommender stated and this actor would otherwise read from its own
        clock (AKM-02-006).  So every rebuild under the same ids produces the
        same body (OX-06-002).
        """
        return recommend_actor_activity(
            recommended=_held_actor(self._dl, recommended_id),
            target=case_id,
            id_=recommendation_id,
            actor=recommender_id,
            published=None,
            updated=None,
        )

    def emit_accept_actor_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an AcceptActorRecommendation activity.

        Sent by the CaseActor to the recommender after the Case Owner accepts
        the Offer(CaseParticipant) (CM-16-006 step 3), or at once for an
        actor already invited or joined (CM-16-009).  ``inReplyTo`` names
        the recommendation it answers.
        """
        recommendation = self._rebuilt_recommendation(
            recommender_id, recommendation_id, recommended_id, case_id
        )
        extra = _addressing(actor, to or [recommender_id], id_)
        activity = accept_actor_recommendation_activity(
            offer=recommendation,
            target=case_id,
            in_reply_to=recommendation_id,
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "emit_accept_actor_recommendation"
        )

    def emit_reject_actor_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a RejectActorRecommendation activity.

        Sent by the CaseActor to the recommender after the Case Owner rejects
        the Offer(CaseParticipant) (CM-16-007 step 3).  ``inReplyTo``
        names the recommendation it answers.
        """
        recommendation = self._rebuilt_recommendation(
            recommender_id, recommendation_id, recommended_id, case_id
        )
        extra = _addressing(actor, to or [recommender_id], id_)
        activity = reject_actor_recommendation_activity(
            offer=recommendation,
            target=case_id,
            in_reply_to=recommendation_id,
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "emit_reject_actor_recommendation"
        )

    def add_participant_to_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Add(CaseParticipant)[target=VulnerabilityCase]``.

        The participant goes inline as the store holds it, removal fact
        cleared.  Returns ``(activity_id, activity_blob)`` (CM-31-011).
        """
        participant = _to_wire(
            self._dl.read(participant_id), as_CaseParticipant
        )
        activity = add_participant_to_case_activity(
            participant=participant,
            target=case_id,
            actor=actor,
            to=to,
            attributed_to=attributed_to,
        )
        return _create_and_seal(self._dl, activity, "add_participant_to_case")

    def remove_participant_from_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        attributed_to: str,
        to: list[str],
    ) -> tuple[str, str]:
        """Create and persist a ``Remove(CaseParticipant)[target=VulnerabilityCase]``.

        The ``Remove`` is the removal notice.

        The participant goes inline as the store holds it, removal fact
        included.  Returns ``(activity_id, activity_blob)`` (CM-31-006).
        """
        participant = _to_wire(
            self._dl.read(participant_id), as_CaseParticipant
        )
        activity = remove_participant_from_case_activity(
            participant=participant,
            target=case_id,
            actor=actor,
            attributed_to=attributed_to,
            to=to,
        )
        return _create_and_seal(
            self._dl, activity, "remove_participant_from_case"
        )

    def add_participant_status_to_participant(
        self,
        status_id: str,
        participant_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Add(ParticipantStatus)[target=CaseParticipant]``."""
        raw = self._dl.read(status_id)
        if raw is None:
            raise VultronNotFoundError(
                "ParticipantStatus",
                f"status '{status_id}' not found",
            )
        # No conversion step: ``as_ParticipantStatus`` *is* ``ParticipantStatus``
        # (ARCH-25-003, ADR-0099), so the object read from the DataLayer is already the
        # class the activity slot wants.  This previously called
        # ``as_ParticipantStatus.from_core(raw)`` to make nested fields survive a
        # boundary that no longer exists; once the pair collapsed, that call raised
        # ``AttributeError: from_core`` and the use case reported "Activity
        # construction failed".
        activity = add_status_to_participant_activity(
            status=cast(as_ParticipantStatus, raw),
            target=participant_id,
            actor=actor,
            to=to,
        )
        return _create_and_seal(
            self._dl, activity, "add_participant_status_to_participant"
        )[0]
