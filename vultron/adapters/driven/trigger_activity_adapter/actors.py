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

"""Actor-domain trigger activity construction for TriggerActivityAdapter.

Covers actor invitations, recommendations, participant management, and
Case Actor / CASE_MANAGER delegation activities.
"""

import logging
from datetime import datetime
from typing import Any, cast

from vultron.core.models.actor import CoreActor
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import _as_id
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    add_participant_to_case_activity,
    add_status_to_participant_activity,
    offer_case_participant_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.factories.case import (
    accept_case_manager_role_activity,
    offer_case_manager_role_activity,
    reject_case_manager_role_activity,
)
from vultron.core.states.em import EM
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseStub,
)

from ._base import _DUMP_KWARGS

logger = logging.getLogger(__name__)


class _ActorsMixin:
    """Trigger activity methods for actor invitations, recommendations,
    participant management, and CASE_MANAGER delegation.
    """

    _dl: CaseOutboxPersistence

    def invite_actor_to_case(
        self,
        invitee_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        cc: list[str] | None = None,
        id_: str | None = None,
        attributed_to: str | None = None,
        roles: list | None = None,
        active_embargo_id: str | None = None,
        em_state: str | None = None,
        embargo_end_time: datetime | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Invite(Actor, Case)`` activity.

        ``actor`` SHOULD be the Case Actor ID (PCR-08-007); ``attributed_to``
        MAY carry the case owner's ID for attribution.  ``cc`` MAY carry the
        Case Actor's own ID for self-archival (CLP-10-001).

        When ``active_embargo_id`` and ``em_state`` are provided and the
        embargo is active, an enriched ``VulnerabilityCaseStub`` is built
        with ``active_embargo`` and ``case_status`` so the invitee can check
        embargo terms before accepting (CM-16-002).  ``roles`` is embedded in
        the Invite activity (CM-16-003).
        """
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if cc is not None:
            extra["cc"] = cc
        if id_ is not None:
            extra["id_"] = id_
        if attributed_to is not None:
            extra["attributed_to"] = attributed_to
        if roles is not None:
            extra["roles"] = [str(r) for r in roles]

        stub_kwargs: dict[str, Any] = {}
        if (
            active_embargo_id
            and em_state == "ACTIVE"
            and embargo_end_time is not None
        ):
            stub_kwargs["active_embargo"] = EmbargoEvent(
                id_=active_embargo_id, end_time=embargo_end_time
            )
            stub_kwargs["case_status"] = CaseStatus(em_state=EM.ACTIVE)

        activity = rm_invite_to_case_activity(
            invitee=CoreActor(id_=invitee_id),
            target=VulnerabilityCaseStub(id_=case_id, **stub_kwargs),
            **extra,
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "invite_actor_to_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def accept_case_invite(
        self,
        invite_id: str,
        actor: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Invite)`` activity.

        The ``to:`` field is derived from ``invite.actor`` (the original
        sender of the invitation) so that OX-08-001 is satisfied and the
        Accept is routable via the outbox handler.  ``_as_id`` is used to
        extract the URI whether the stored actor field is a plain string or a
        hydrated AS2 object; a ``VultronValidationError`` is raised if the
        invite carries no routable actor reference.
        """
        invite = cast(Any, self._dl.read(invite_id))
        invite_actor_id = _as_id(getattr(invite, "actor", None))
        if not invite_actor_id:
            raise VultronValidationError(
                f"accept_case_invite: invite '{invite_id}' has no routable"
                " actor field; cannot derive Accept recipient"
            )
        activity = rm_accept_invite_to_case_activity(
            invite=invite, actor=actor, to=[invite_actor_id]
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "accept_case_invite: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def suggest_actor_to_case(
        self,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Offer(Actor, Case)`` recommendation activity."""
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if id_ is not None:
            extra["id_"] = id_
        # The factory accepts a string for target (case ID).
        activity = recommend_actor_activity(
            recommended=CoreActor(id_=recommended_id),
            target=case_id,
            **extra,
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "suggest_actor_to_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

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
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an Offer(CaseParticipant{actor, roles}, Case).

        Transforms the original Offer(Actor, Case) from a recommending
        participant into an Offer(CaseParticipant) addressed to the Case Owner.
        ``roles`` defaults to ``[CVDRole.VENDOR]`` when ``None`` (CM-16-003).
        ``origin`` carries the original Offer ID for causal traceability
        (CM-16-004).
        """
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if id_ is not None:
            extra["id_"] = id_
        if origin is not None:
            extra["origin"] = origin
        activity = offer_case_participant_activity(
            recommended=CoreActor(id_=recommended_id),
            target=case_id,
            roles=roles,
            **extra,
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "offer_actor_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def emit_accept_actor_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an AcceptActorRecommendation activity.

        Sent by the CaseActor to the recommender after the Case Owner accepts
        the Offer(CaseParticipant) (CM-16-006 step 3).
        """
        recommendation = recommend_actor_activity(
            recommended=CoreActor(id_=recommended_id),
            target=case_id,
            id_=recommendation_id,
            actor=recommender_id,
        )
        extra: dict[str, Any] = {"actor": actor, "to": to or [recommender_id]}
        if id_ is not None:
            extra["id_"] = id_
        activity = accept_actor_recommendation_activity(
            offer=recommendation, target=case_id, **extra
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "emit_accept_actor_recommendation: activity '%s' already"
                " exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def emit_reject_actor_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a RejectActorRecommendation activity.

        Sent by the CaseActor to the recommender after the Case Owner rejects
        the Offer(CaseParticipant) (CM-16-007 step 3).
        """
        recommendation = recommend_actor_activity(
            recommended=CoreActor(id_=recommended_id),
            target=case_id,
            id_=recommendation_id,
            actor=recommender_id,
        )
        extra: dict[str, Any] = {"actor": actor, "to": to or [recommender_id]}
        if id_ is not None:
            extra["id_"] = id_
        activity = reject_actor_recommendation_activity(
            offer=recommendation, target=case_id, **extra
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "emit_reject_actor_recommendation: activity '%s' already"
                " exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def accept_actor_recommendation(
        self,
        recommended_id: str,
        recommender_id: str,
        recommendation_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Offer)`` actor-recommendation activity.

        The recommendation offer is reconstructed ephemerally (not read from
        DataLayer) to allow callers that never stored the offer to still
        accept it, provided they know its deterministic ID.
        """
        recommendation = recommend_actor_activity(
            recommended=CoreActor(id_=recommended_id),
            target=case_id,
            id_=recommendation_id,
            actor=recommender_id,
        )
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if id_ is not None:
            extra["id_"] = id_
        activity = accept_actor_recommendation_activity(
            offer=recommendation, target=case_id, **extra
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "accept_actor_recommendation: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def add_participant_to_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Add(CaseParticipant, Case)`` activity."""
        participant = cast(CaseParticipant, self._dl.read(participant_id))
        activity = add_participant_to_case_activity(
            participant=participant, target=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "add_participant_to_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_

    def add_participant_status_to_participant(
        self,
        status_id: str,
        participant_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Add(ParticipantStatus, CaseParticipant)`` activity."""
        raw = self._dl.read(status_id)
        if raw is None:
            raise VultronNotFoundError(
                "ParticipantStatus",
                f"status '{status_id}' not found",
            )
        # Convert from core ParticipantStatus to wire ParticipantStatus
        # so that nested fields (case_status, pxa_state) survive the boundary.
        from vultron.core.models.participant_status import (
            ParticipantStatus as CorePS,
        )

        if isinstance(raw, CorePS):
            wire_status: ParticipantStatus = ParticipantStatus.from_core(raw)
        else:
            wire_status = cast(ParticipantStatus, raw)
        activity = add_status_to_participant_activity(
            status=wire_status, target=participant_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "add_participant_status_to_participant: activity '%s' already"
                " exists — skipping",
                activity.id_,
            )
        return activity.id_

    def offer_case_manager_role(
        self,
        case_id: str,
        participant_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Offer(VulnerabilityCase, target=CaseParticipant)``
        CASE_MANAGER delegation activity.
        """
        case = cast(VulnerabilityCase, self._dl.read(case_id))
        participant = cast(CaseParticipant, self._dl.read(participant_id))
        activity = offer_case_manager_role_activity(
            case=case, target=participant, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "offer_case_manager_role: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_

    def accept_case_manager_role(
        self,
        offer_id: str,
        case_id: str,
        participant_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Accept(_OfferCaseManagerRoleActivity)``.

        Ephemerally reconstructs the original Offer from ``offer_id``,
        ``case_id``, ``participant_id``, and ``vendor_id`` so that
        ``Accept.object_`` is a typed ``_OfferCaseManagerRoleActivity``.
        """
        case = cast(VulnerabilityCase, self._dl.read(case_id))
        participant = cast(CaseParticipant, self._dl.read(participant_id))
        offer = offer_case_manager_role_activity(
            case=case,
            target=participant,
            id_=offer_id,
            actor=vendor_id,
        )
        activity = accept_case_manager_role_activity(
            offer=offer, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "accept_case_manager_role: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_

    def reject_case_manager_role(
        self,
        offer_id: str,
        case_id: str,
        participant_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist a ``Reject(_OfferCaseManagerRoleActivity)``.

        Ephemerally reconstructs the original Offer from ``offer_id``,
        ``case_id``, ``participant_id``, and ``vendor_id`` so that
        ``Reject.object_`` is a typed ``_OfferCaseManagerRoleActivity``.
        """
        case = cast(VulnerabilityCase, self._dl.read(case_id))
        participant = cast(CaseParticipant, self._dl.read(participant_id))
        offer = offer_case_manager_role_activity(
            case=case,
            target=participant,
            id_=offer_id,
            actor=vendor_id,
        )
        activity = reject_case_manager_role_activity(
            offer=offer, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "reject_case_manager_role: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_
