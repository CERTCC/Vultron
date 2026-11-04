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

"""Received-side BT factories for the suggest-actor workflow (ADR-0026, CM-16).

Three factories run on the CASE_MANAGER's inbox:

- :func:`create_recommend_actor_to_case_received_tree`  — the CASE_MANAGER
  handles ``Offer(Actor)[target=VulnerabilityCase]`` from a recommending participant
  (CM-16-001..004).
- :func:`create_accept_actor_recommendation_received_tree` — the CASE_MANAGER
  handles ``Accept(Offer(CaseParticipant))`` from the Case Owner (CM-16-006).
  Despite its name, it routes ``ACCEPT_OFFER_CASE_PARTICIPANT``, the Case
  Owner's decision, not ``ACCEPT_ACTOR_RECOMMENDATION``.
- :func:`create_reject_actor_recommendation_received_tree` — the CASE_MANAGER
  handles ``Reject(Offer(CaseParticipant))`` from the Case Owner (CM-16-007).
  Likewise, it routes ``REJECT_OFFER_CASE_PARTICIPANT``.

These three route through the CASE_MANAGER's inbox per ADR-0021/ADR-0026
and use
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
to enforce CLP-10-006 ordering (ledger commit before effect nodes).

A fourth, :func:`create_recommendation_answer_received_tree`, runs on the
recommender's inbox: it handles the CASE_MANAGER's ``Accept`` or
``Reject(Offer(Actor)[target=VulnerabilityCase])`` answer (``ACCEPT_ACTOR_RECOMMENDATION``,
``REJECT_ACTOR_RECOMMENDATION``; CM-16-006, CM-16-007, CM-16-009), and
records no entry and runs no effect.

Every effect in this workflow is the CASE_MANAGER's, so each tree's effect
section is passed as ``manager_effects``, which the factory wraps in the
CASE_MANAGER gate (BT-17-001, BT-17-008, BTND-07-005).  The same handler
runs on every participant that holds a copy of the message; the gate is
what keeps a participant that is *not* the case's CASE_MANAGER from
forwarding, accepting, or inviting as itself (#3752).  The handler then
reports the skip as a refusal (HP-01-005).

BT leaf nodes for this workflow are in the
:mod:`vultron.core.behaviors.case.nodes.suggest_actor` subpackage.

The factories live in submodules grouped by concern (CS-18-005):

- ``recommend``: the CASE_MANAGER's handling of a participant's
  recommendation.
- ``owner_offer``: the ``Offer(CaseParticipant)`` round trip with the Case
  Owner — its receipt on the Case Owner's inbox and the Case Owner's
  ``Accept`` or ``Reject`` on the CASE_MANAGER's.
- ``answer``: the recommender's receipt of the CASE_MANAGER's answer.
"""

from vultron.core.behaviors.case.nodes.suggest_actor import (
    ActorAlreadyParticipantNode,
    EmitAcceptActorRecommendationNode,
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
    EmitRejectActorRecommendationNode,
    InviteInFlightNode,
    PendingOfferCaseParticipantNode,
)
from vultron.core.behaviors.case.suggest_actor_tree.answer import (
    create_recommendation_answer_received_tree,
)
from vultron.core.behaviors.case.suggest_actor_tree.owner_offer import (
    create_accept_actor_recommendation_received_tree,
    create_receive_offer_case_participant_tree,
    create_reject_actor_recommendation_received_tree,
)
from vultron.core.behaviors.case.suggest_actor_tree.recommend import (
    create_recommend_actor_to_case_received_tree,
)

__all__ = [
    # node classes live in nodes.suggest_actor; re-exported here for backward compat
    "ActorAlreadyParticipantNode",
    "EmitAcceptActorRecommendationNode",
    "EmitNoteDuplicateRecommendationToOwnerNode",
    "EmitOfferCaseParticipantToOwnerNode",
    "EmitRejectActorRecommendationNode",
    "InviteInFlightNode",
    "PendingOfferCaseParticipantNode",
    "create_accept_actor_recommendation_received_tree",
    "create_receive_offer_case_participant_tree",
    "create_recommend_actor_to_case_received_tree",
    "create_recommendation_answer_received_tree",
    "create_reject_actor_recommendation_received_tree",
]
