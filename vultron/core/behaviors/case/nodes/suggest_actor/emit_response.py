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

"""The CaseActor's answer back to a recommender (CM-16-006, CM-16-007).

Split out of ``emit`` to stay under the BTND-07-004 leaf-module ceiling, along
the seam the workflow already has: ``emit`` addresses the *Case Owner*, asking
it to decide on a recommendation, while these two nodes close the loop with the
*recommender* once that decision is in.  ``accept_offer`` was split off the same
module for the same reason.

Classes: EmitAcceptActorRecommendationNode (CM-16-006),
EmitRejectActorRecommendationNode (CM-16-007).
"""

from typing import ClassVar, cast

from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence


class _AnswerRecommenderNode(_EmitSingleActivityBase):
    """Queue the CASE_MANAGER's answer to a recommender, then commit it.

    The answer is sent before it is recorded: a ledger entry records a
    completed act (ADR-0119, CM-16-010).  Its id is derived from the
    recommendation it answers, so a retry for the same recommendation after
    a send whose commit failed rebuilds the same answer, which the outbox
    does not queue twice (OX-06-002) and the commit records once.
    """

    #: Ledger ``event_type`` of the answer, and the kind label of its id.
    _EVENT_TYPE: ClassVar[str]
    #: Activity name for the log line.
    _LABEL: ClassVar[str]

    def __init__(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommender_id = recommender_id
        self.recommendation_id = recommendation_id
        self.recommended_id = recommended_id
        self.case_id = case_id

    def _answer_id(self) -> str:
        assert self.actor_id is not None
        return derived_activity_id(
            self._EVENT_TYPE,
            self.actor_id,
            self.case_id,
            self.recommendation_id,
        )

    def _record_sent(self, activity_id: str, activity_blob: str) -> None:
        # Exact blob as snapshot (VM-08-003): the factory sets context.
        assert self.actor_id is not None
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=self.actor_id,
            case_id=self.case_id,
            activity_id=activity_id,
            activity_blob=activity_blob,
            event_type=self._EVENT_TYPE,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: queued %s to '%s' for case '%s'",
            self.name,
            self._LABEL,
            self.recommender_id,
            self.case_id,
        )


class EmitAcceptActorRecommendationNode(_AnswerRecommenderNode):
    """Queue AcceptActorRecommendation to the original recommender.

    Used after the Case Owner accepts Offer(CaseParticipant) (CM-16-006 step 3).
    The ``in_reply_to`` field is set to the original recommender's offer ID
    (carried in the Case Owner's Accept via the ``origin`` field of the
    transformed Offer) so the recommender can correlate the response.
    """

    _EVENT_TYPE = "accept_actor_recommendation"
    _LABEL = "AcceptActorRecommendation"

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.emit_accept_actor_recommendation(
            recommender_id=self.recommender_id,
            recommendation_id=self.recommendation_id,
            recommended_id=self.recommended_id,
            case_id=self.case_id,
            actor=self.actor_id,
            id_=self._answer_id(),
        )


class EmitRejectActorRecommendationNode(_AnswerRecommenderNode):
    """Queue RejectActorRecommendation to the original recommender.

    Used after the Case Owner rejects Offer(CaseParticipant) (CM-16-007 step 3).
    """

    _EVENT_TYPE = "reject_actor_recommendation"
    _LABEL = "RejectActorRecommendation"

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.emit_reject_actor_recommendation(
            recommender_id=self.recommender_id,
            recommendation_id=self.recommendation_id,
            recommended_id=self.recommended_id,
            case_id=self.case_id,
            actor=self.actor_id,
            id_=self._answer_id(),
        )


__all__ = [
    "EmitAcceptActorRecommendationNode",
    "EmitRejectActorRecommendationNode",
]
