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

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.behaviors.case.nodes.suggest_actor._snapshot import (
    _snapshot_with_context,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence


class EmitAcceptActorRecommendationNode(DataLayerActionWithPorts):
    """Queue AcceptActorRecommendation to the original recommender.

    Used after the Case Owner accepts Offer(CaseParticipant) (CM-16-006 step 3).
    The ``in_reply_to`` field is set to the original recommender's offer ID
    (carried in the Case Owner's Accept via the ``origin`` field of the
    transformed Offer) so the recommender can correlate the response.
    """

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

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        if (f := self._require_factory()) is not None:
            self.logger.error(self.feedback_message)
            return f
        assert self.trigger_activity_factory is not None

        factory = self.trigger_activity_factory  # guaranteed non-None
        try:
            activity_id, activity_dict = (
                factory.emit_accept_actor_recommendation(
                    recommender_id=self.recommender_id,
                    recommendation_id=self.recommendation_id,
                    recommended_id=self.recommended_id,
                    case_id=self.case_id,
                    actor=self.actor_id,
                )
            )
            snapshot = _snapshot_with_context(activity_dict, self.case_id)
            commit_tree = create_commit_log_entry_tree(
                case_id=self.case_id,
                object_id=activity_id,
                event_type="accept_actor_recommendation",
                payload_snapshot=snapshot,
                disposition="recorded",
            )
            result = BTBridge(
                datalayer=cast(CaseOutboxPersistence, self.datalayer)
            ).execute_with_setup(
                tree=commit_tree,
                actor_id=self.actor_id,
            )
            if result.status != Status.SUCCESS:
                raise RuntimeError(
                    f"ledger commit failed for "
                    f"accept_actor_recommendation/{self.recommended_id}"
                )
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
            self.logger.info(
                "%s: queued AcceptActorRecommendation to '%s' for case '%s'",
                self.name,
                self.recommender_id,
                self.case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.feedback_message = (
                f"EmitAcceptActorRecommendation failed: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE


class EmitRejectActorRecommendationNode(DataLayerActionWithPorts):
    """Queue RejectActorRecommendation to the original recommender.

    Used after the Case Owner rejects Offer(CaseParticipant) (CM-16-007 step 3).
    """

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

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        if (f := self._require_factory()) is not None:
            self.logger.error(self.feedback_message)
            return f
        assert self.trigger_activity_factory is not None

        factory = self.trigger_activity_factory  # guaranteed non-None
        try:
            activity_id, activity_dict = (
                factory.emit_reject_actor_recommendation(
                    recommender_id=self.recommender_id,
                    recommendation_id=self.recommendation_id,
                    recommended_id=self.recommended_id,
                    case_id=self.case_id,
                    actor=self.actor_id,
                )
            )
            snapshot = _snapshot_with_context(activity_dict, self.case_id)
            commit_tree = create_commit_log_entry_tree(
                case_id=self.case_id,
                object_id=activity_id,
                event_type="reject_actor_recommendation",
                payload_snapshot=snapshot,
                disposition="recorded",
            )
            result = BTBridge(
                datalayer=cast(CaseOutboxPersistence, self.datalayer)
            ).execute_with_setup(
                tree=commit_tree,
                actor_id=self.actor_id,
            )
            if result.status != Status.SUCCESS:
                raise RuntimeError(
                    f"ledger commit failed for "
                    f"reject_actor_recommendation/{self.recommended_id}"
                )
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
            self.logger.info(
                "%s: queued RejectActorRecommendation to '%s' for case '%s'",
                self.name,
                self.recommender_id,
                self.case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.feedback_message = (
                f"EmitRejectActorRecommendation failed: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE


__all__ = [
    "EmitAcceptActorRecommendationNode",
    "EmitRejectActorRecommendationNode",
]
