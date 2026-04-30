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

from vultron.wire.as2.vocab.examples._base import (
    _COORDINATOR,
    case,
    finder,
    vendor,
)
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
)
from vultron.core.models.vultron_types import VultronActivity


def recommend_actor() -> VultronActivity:
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


def accept_actor_recommendation() -> VultronActivity:
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


def reject_actor_recommendation() -> VultronActivity:
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
