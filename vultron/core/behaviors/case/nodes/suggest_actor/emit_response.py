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
it to decide on a recommendation, while these nodes close the loop with the
*recommender* once that decision is in.  ``accept_offer`` was split off the same
module for the same reason.

Classes: EmitAcceptActorRecommendationNode (CM-16-009),
EmitAcceptRecordedRecommendationNode (CM-16-006),
EmitRejectActorRecommendationNode (CM-16-007).
"""

from typing import ClassVar, NamedTuple, cast

from vultron.core.behaviors.case.nodes.suggest_actor.recorded_offer import (
    RecordedOfferAnswerInputMixin,
)
from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence


class RecommendationAnswerSubject(NamedTuple):
    """Who an answer to a recommendation goes to, and what it is about."""

    recommender_id: str
    recommendation_id: str
    recommended_id: str


class _AnswerRecommenderNode(_EmitSingleActivityBase):
    """Queue the CASE_MANAGER's answer to a recommender, then commit it.

    The answer is sent before it is recorded: a ledger entry records a
    completed act (ADR-0119, CM-16-010).  Its id is derived from the
    recommendation it answers, so a retry for the same recommendation after
    a send whose commit failed rebuilds the same answer, which the outbox
    does not queue twice (OX-06-002) and the commit records once.

    A subclass names the answer's subject (:meth:`_subject`): fixed at
    construction, or read from the recorded Offer the Case Owner answered.
    """

    #: Ledger ``event_type`` of the answer, and the kind label of its id.
    _EVENT_TYPE: ClassVar[str]
    #: Activity name for the log line.
    _LABEL: ClassVar[str]
    #: Whether the answer accepts (``True``) or rejects the recommendation.
    _ACCEPTS: ClassVar[bool]

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def _subject(self) -> RecommendationAnswerSubject:
        """Who the answer goes to and what it is about."""
        raise NotImplementedError

    def _answer_id(self) -> str:
        assert self.actor_id is not None
        return derived_activity_id(
            self._EVENT_TYPE,
            self.actor_id,
            self.case_id,
            self._subject().recommendation_id,
        )

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        factory = self.trigger_activity_factory
        emit = (
            factory.emit_accept_actor_recommendation
            if self._ACCEPTS
            else factory.emit_reject_actor_recommendation
        )
        subject = self._subject()
        return emit(
            recommender_id=subject.recommender_id,
            recommendation_id=subject.recommendation_id,
            recommended_id=subject.recommended_id,
            case_id=self.case_id,
            actor=self.actor_id,
            id_=self._answer_id(),
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
            self._subject().recommender_id,
            self.case_id,
        )


class _AnswerOnRecordNode(
    RecordedOfferAnswerInputMixin, _AnswerRecommenderNode
):
    """An answer whose subject is the recorded Offer the Case Owner answered.

    Reads the :class:`RecordedOfferAnswer` that
    ``RequireRecordedOfferAnswerNode`` published for *answer_id*, so the
    recommender and the recommended actor are the CASE_MANAGER's records,
    never the Case Owner's copy of the Offer (CM-16-019).
    """

    def __init__(
        self, answer_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self._read_answer_of(answer_id)

    def _subject(self) -> RecommendationAnswerSubject:
        answer = self._recorded_answer()
        return RecommendationAnswerSubject(
            recommender_id=answer.recommender_id,
            recommendation_id=answer.recommendation_id,
            recommended_id=answer.invitee_id,
        )


class EmitAcceptActorRecommendationNode(_AnswerRecommenderNode):
    """Queue AcceptActorRecommendation to the original recommender.

    The CASE_MANAGER's own answer when the recommended actor has already
    joined or been invited (CM-16-009), with the subject fixed at
    construction.  The answer after the Case Owner accepts
    Offer(CaseParticipant) is :class:`EmitAcceptRecordedRecommendationNode`.
    The ``in_reply_to`` field is set to the original recommender's offer ID
    so the recommender can correlate the response.
    """

    _EVENT_TYPE = "accept_actor_recommendation"
    _LABEL = "AcceptActorRecommendation"
    _ACCEPTS = True

    def __init__(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self.recommender_id = recommender_id
        self.recommendation_id = recommendation_id
        self.recommended_id = recommended_id

    def _subject(self) -> RecommendationAnswerSubject:
        return RecommendationAnswerSubject(
            recommender_id=self.recommender_id,
            recommendation_id=self.recommendation_id,
            recommended_id=self.recommended_id,
        )


class EmitAcceptRecordedRecommendationNode(_AnswerOnRecordNode):
    """Queue AcceptActorRecommendation after the Case Owner's Accept.

    CM-16-006 step 3: the recommender and the recommended actor are the
    recorded Offer's.  ``in_reply_to`` is the original recommender's offer
    ID, carried as the recorded Offer's ``origin``.
    """

    _EVENT_TYPE = EmitAcceptActorRecommendationNode._EVENT_TYPE
    _LABEL = EmitAcceptActorRecommendationNode._LABEL
    _ACCEPTS = True


class EmitRejectActorRecommendationNode(_AnswerOnRecordNode):
    """Queue RejectActorRecommendation after the Case Owner's Reject.

    CM-16-007 step 3: the recommender and the recommended actor are the
    recorded Offer's.
    """

    _EVENT_TYPE = "reject_actor_recommendation"
    _LABEL = "RejectActorRecommendation"
    _ACCEPTS = False


__all__ = [
    "EmitAcceptActorRecommendationNode",
    "EmitAcceptRecordedRecommendationNode",
    "EmitRejectActorRecommendationNode",
    "RecommendationAnswerSubject",
]
