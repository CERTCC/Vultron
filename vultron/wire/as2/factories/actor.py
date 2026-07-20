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
"""
Factory functions for outbound Vultron actor-recommendation activities.

These are the sole public construction API for activities involving
actor recommendations. Internal activity subclasses are
imported here and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

import logging
from typing import cast

from pydantic import ValidationError

from vultron.core.models.actor import CoreActor
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.actor import (
    _AcceptActorRecommendationActivity,
    _AcceptCaseParticipantOfferActivity,
    _OfferCaseParticipantActivity,
    _RecommendActorActivity,
    _RejectActorRecommendationActivity,
    _RejectCaseParticipantOfferActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseRef,
)

logger = logging.getLogger(__name__)


def recommend_actor_activity(
    recommended: CoreActor | as_Actor,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Offer:
    """Build an Offer(Actor, target=VulnerabilityCase) — actor recommendation.

    Recommends another actor for participation in a case. The case
    owner may then accept or reject the recommendation via
    :func:`accept_actor_recommendation_activity` or
    :func:`reject_actor_recommendation_activity`.

    Args:
        recommended: The ``as_Actor`` being recommended.
        target: The ``VulnerabilityCase`` (or its URI) for which the
            actor is being recommended.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor`` for the recommending party).

    Returns:
        An ``as_Offer`` whose ``object_`` is the recommended actor.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RecommendActorActivity(
            object_=recommended, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning("recommend_actor_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "recommend_actor_activity: invalid arguments"
        ) from exc


def accept_actor_recommendation_activity(
    offer: as_Offer,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_RecommendActorActivity).

    Accepts a recommendation to add an actor to the case.  The
    ``offer`` MUST be the value returned by
    :func:`recommend_actor_activity`; a plain ``as_Offer`` will fail
    validation.  This MUST be followed by an
    :func:`vultron.wire.as2.factories.case.rm_invite_to_case_activity`
    targeted at the recommended actor.

    Args:
        offer: The ``_RecommendActorActivity`` being accepted.
        target: The ``VulnerabilityCase`` (or its URI) for which the
            recommendation was made.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the recommendation offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AcceptActorRecommendationActivity(
            object_=cast(_RecommendActorActivity, offer),
            target=target,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "accept_actor_recommendation_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "accept_actor_recommendation_activity: invalid arguments"
        ) from exc


def reject_actor_recommendation_activity(
    offer: as_Offer,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_RecommendActorActivity).

    Rejects a recommendation to add an actor to the case.  The
    ``offer`` MUST be the value returned by
    :func:`recommend_actor_activity`; a plain ``as_Offer`` will fail
    validation.

    Args:
        offer: The ``_RecommendActorActivity`` being rejected.
        target: The ``VulnerabilityCase`` (or its URI) for which the
            recommendation was made.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the recommendation offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RejectActorRecommendationActivity(
            object_=cast(_RecommendActorActivity, offer),
            target=target,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "reject_actor_recommendation_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "reject_actor_recommendation_activity: invalid arguments"
        ) from exc


def offer_case_participant_activity(
    recommended: CoreActor | as_Actor,
    target: as_VulnerabilityCaseRef | None = None,
    roles: list[CVDRole] | None = None,
    **kwargs,
) -> as_Offer:
    """Build an Offer(as_CaseParticipant{actor, roles}, Case) for the Case Owner.

    Transforms the original ``Offer(Actor, Case)`` recommendation into a
    typed ``Offer(as_CaseParticipant{actor, roles=[VENDOR]}, Case)`` addressed
    to the Case Owner.  ``origin`` in ``kwargs`` SHOULD carry the ID of the
    original ``Offer(Actor, Case)`` for causal traceability (CM-16-004).

    Args:
        recommended: The actor being recommended as a participant.
        target: The ``VulnerabilityCase`` (or its URI).
        roles: Roles to assign; defaults to ``[CVDRole.VENDOR]`` (CM-16-003).
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``origin``).

    Returns:
        An ``as_Offer`` whose ``object_`` is a ``as_CaseParticipant``.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    effective_roles = roles if roles is not None else [CVDRole.VENDOR]
    actor_id = getattr(recommended, "id_", None) or str(recommended)
    participant = as_CaseParticipant(
        id_=f"{actor_id}#participant",
        attributed_to=recommended,
        case_roles=effective_roles,
    )
    try:
        return _OfferCaseParticipantActivity(
            object_=participant, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "offer_case_participant_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "offer_case_participant_activity: invalid arguments"
        ) from exc


def accept_case_participant_offer_activity(
    offer: as_Offer,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_OfferCaseParticipantActivity) from the Case Owner.

    Args:
        offer: The ``_OfferCaseParticipantActivity`` being accepted.
        target: The ``VulnerabilityCase`` (or its URI).
        **kwargs: Optional AS2 fields forwarded to the constructor.

    Returns:
        An ``as_Accept`` whose ``object_`` is the as_CaseParticipant offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    # dl.read() returns the base as_Offer; coerce to the typed subclass so
    # Pydantic accepts it (the subclass requires object_ to be as_CaseParticipant).
    typed_offer = (
        _OfferCaseParticipantActivity.model_validate(
            offer.model_dump(by_alias=True)
        )
        if not isinstance(offer, _OfferCaseParticipantActivity)
        else offer
    )
    try:
        return _AcceptCaseParticipantOfferActivity(
            object_=typed_offer,
            target=target,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "accept_case_participant_offer_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "accept_case_participant_offer_activity: invalid arguments"
        ) from exc


def reject_case_participant_offer_activity(
    offer: as_Offer,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_OfferCaseParticipantActivity) from the Case Owner.

    Args:
        offer: The ``_OfferCaseParticipantActivity`` being rejected.
        target: The ``VulnerabilityCase`` (or its URI).
        **kwargs: Optional AS2 fields forwarded to the constructor.

    Returns:
        An ``as_Reject`` whose ``object_`` is the as_CaseParticipant offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RejectCaseParticipantOfferActivity(
            object_=cast(_OfferCaseParticipantActivity, offer),
            target=target,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "reject_case_participant_offer_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "reject_case_participant_offer_activity: invalid arguments"
        ) from exc
