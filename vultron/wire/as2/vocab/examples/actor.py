#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.examples._base import (
    _CASE_ACTOR,
    _COORDINATOR,
    case,
    finder,
    vendor,
)
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    accept_case_participant_offer_activity,
    offer_case_participant_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
    reject_case_participant_offer_activity,
)


def recommend_actor() -> as_Offer:
    _case = case()
    _finder = finder()
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _activity = recommend_actor_activity(
        _coordinator,
        actor=_finder.id_,
        context=_case.id_,
        target=_case.id_,
        to=_vendor.id_,
        content=f"I'm recommending we add {_coordinator.name} to the case.",
    )
    return _activity


def accept_actor_recommendation() -> as_Accept:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _finder = finder()
    _case = case()
    _recommendation = recommend_actor()
    _activity = accept_actor_recommendation_activity(
        _recommendation,
        actor=_vendor.id_,
        context=_case.id_,
        target=_case.id_,
        to=_finder.id_,
        content=f"We're accepting your recommendation to add {_coordinator.name} to the case. "
        "We'll reach out to them shortly.",
    )
    return _activity


def reject_actor_recommendation() -> as_Reject:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _finder = finder()
    _case = case()
    _recommendation = recommend_actor()
    _activity = reject_actor_recommendation_activity(
        _recommendation,
        actor=_vendor.id_,
        context=_case.id_,
        target=_case.id_,
        to=_finder.id_,
        content=f"We're declining your recommendation to add {_coordinator.name} to the case. Thanks anyway.",
    )
    return _activity


def offer_case_participant() -> as_Offer:
    """CaseActor transforms Offer(Actor) → Offer(CaseParticipant) for Case Owner."""
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _recommendation = recommend_actor()
    _activity = offer_case_participant_activity(
        _coordinator,
        target=_case.id_,
        actor=_CASE_ACTOR.id_,
        to=[_vendor.id_],
        context=_case.id_,
        origin=_recommendation.id_,
        content=(
            f"Recommending {_coordinator.name} for case participation "
            f"(roles: VENDOR). Origin: {_recommendation.id_}"
        ),
    )
    return _activity


def accept_case_participant_offer() -> as_Accept:
    """Case Owner accepts Offer(CaseParticipant) and sends to CaseActor."""
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _cp_offer = offer_case_participant()
    _activity = accept_case_participant_offer_activity(
        _cp_offer,
        target=_case.id_,
        actor=_vendor.id_,
        to=[_CASE_ACTOR.id_],
        context=_case.id_,
        content=(
            f"Accepting recommendation to add {_coordinator.name} to the case."
        ),
    )
    return _activity


def reject_case_participant_offer() -> as_Reject:
    """Case Owner rejects Offer(CaseParticipant) and sends to CaseActor."""
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _case = case()
    _cp_offer = offer_case_participant()
    _activity = reject_case_participant_offer_activity(
        _cp_offer,
        target=_case.id_,
        actor=_vendor.id_,
        to=[_CASE_ACTOR.id_],
        context=_case.id_,
        content=(
            f"Declining recommendation to add {_coordinator.name} to the case."
        ),
    )
    return _activity
