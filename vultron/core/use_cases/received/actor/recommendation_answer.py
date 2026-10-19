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
"""Use cases for the CASE_MANAGER's answer to a recommender (ADR-0026).

- :class:`AcceptActorRecommendationReceivedUseCase` — the recommender received
  ``Accept(Offer(Actor, Case))`` (CM-16-006, CM-16-009).
- :class:`RejectActorRecommendationReceivedUseCase` — the recommender received
  ``Reject(Offer(Actor, Case))`` (CM-16-007).

Both archive the answer and change nothing else: the CASE_MANAGER ledgered the
answer when it sent it (CM-16-010), and the recommender takes the change from
that entry.  Only the CASE_MANAGER sends either answer (PCR-03-001), so the
tree's sender guard refuses one from any other actor.
"""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.suggest_actor_tree import (
    create_recommendation_answer_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
    any_of,
)
from vultron.core.models.events.actor import (
    AcceptActorRecommendationReceivedEvent,
    RejectActorRecommendationReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import intake_verdict

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)

type RecommendationAnswerEvent = (
    AcceptActorRecommendationReceivedEvent
    | RejectActorRecommendationReceivedEvent
)


class _RecommendationAnswerReceivedUseCase:
    """Archive the CASE_MANAGER's answer to this actor's recommendation.

    The answer is addressed to the recommender, a participant, so the rule
    states only the participant side: the CASE_MANAGER never receives its
    own answer, and one addressed to it is refused.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_participant=any_of(SenderEntitlementKind.CASE_MANAGER)
    )

    #: Name of the received tree, and the verdict label.
    _TREE_NAME: ClassVar[str]
    #: What the answer says, for the log line.
    _ANSWER: ClassVar[str]

    def __init__(
        self,
        dl: CasePersistence,
        request: RecommendationAnswerEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        # The received baseline supplies the trigger port to every use case;
        # this one runs no tree that builds an activity, so it is unused.
        del trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request = request

    def execute(self) -> HandlerResult:
        request = self._request
        case_id = request.target_id
        tree = create_recommendation_answer_received_tree(
            name=self._TREE_NAME,
            case_id=case_id,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = intake_verdict(tree, result, label=self._TREE_NAME)
        if verdict.disposition is HandlerDisposition.APPLIED:
            logger.info(
                "%s: the case manager '%s' %s recommendation '%s' for case"
                " '%s' (activity '%s')",
                self._TREE_NAME,
                request.actor_id,
                self._ANSWER,
                request.object_id,
                case_id,
                request.activity_id,
            )
        return verdict


class AcceptActorRecommendationReceivedUseCase(
    _RecommendationAnswerReceivedUseCase
):
    """The recommender received ``AcceptActorRecommendation``.

    Sent once the Case Owner accepted the suggestion (CM-16-006 step 3) or
    when the suggested actor was already invited or joined (CM-16-009).
    """

    _TREE_NAME = "AcceptActorRecommendationReceivedBT"
    _ANSWER = "accepted"

    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptActorRecommendationReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        # Restated so ``request`` names the event this handler's row routes
        # (HP-02-002); the base class does the work.
        super().__init__(
            dl, request, sync_port, wire_render_port, trigger_activity
        )


class RejectActorRecommendationReceivedUseCase(
    _RecommendationAnswerReceivedUseCase
):
    """The recommender received ``RejectActorRecommendation`` (CM-16-007)."""

    _TREE_NAME = "RejectActorRecommendationReceivedBT"
    _ANSWER = "declined"

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectActorRecommendationReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        # Restated so ``request`` names the event this handler's row routes
        # (HP-02-002); the base class does the work.
        super().__init__(
            dl, request, sync_port, wire_render_port, trigger_activity
        )
