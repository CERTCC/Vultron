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

from vultron.wire.as2.vocab.activities.actor import (
    AcceptActorRecommendation,
    RecommendActor,
    RejectActorRecommendation,
)
from vultron.wire.as2.vocab.examples._base import (
    _CASE,
    _COORDINATOR,
    _FINDER,
    _VENDOR,
    case,
    finder,
    vendor,
)


def recommend_actor() -> RecommendActor:
    _case = case()
    _finder = finder()
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _activity = RecommendActor(
        actor=_finder.as_id,
        object=_coordinator.as_id,
        context=_case.as_id,
        target=_case.as_id,
        to=_vendor.as_id,
        content=f"I'm recommending we add {_coordinator.name} to the case.",
    )
    return _activity


def accept_actor_recommendation() -> AcceptActorRecommendation:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _finder = finder()
    _case = case()
    _recommendation = recommend_actor()
    _activity = AcceptActorRecommendation(
        actor=_vendor.as_id,
        object=_recommendation,
        context=_case.as_id,
        target=_case.as_id,
        to=_finder.as_id,
        content=f"We're accepting your recommendation to add {_coordinator.name} to the case. "
        "We'll reach out to them shortly.",
    )
    return _activity


def reject_actor_recommendation() -> RejectActorRecommendation:
    _vendor = vendor()
    _coordinator = _COORDINATOR
    _finder = finder()
    _case = case()
    _recommendation = recommend_actor()
    _activity = RejectActorRecommendation(
        actor=_vendor.as_id,
        object=_recommendation,
        context=_case.as_id,
        target=_case.as_id,
        to=_finder.as_id,
        content=f"We're declining your recommendation to add {_coordinator.name} to the case. Thanks anyway.",
    )
    return _activity
