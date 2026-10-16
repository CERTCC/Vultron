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

"""What a participant's answer to an embargo Invite records (ADR-0122).

An ``Accept`` or ``Reject(Invite(EmbargoEvent))`` is its sender's own
consent, so its entry is the answerer's row's entry: it carries the row the
answer states (:meth:`ConsentRowChange.answer`), and no second entry records
it (CLP-07-013).  The CASE_MANAGER decides it with the lifecycle operation
on a staged store (:func:`decide_answer`), and the decision must write
exactly that row, or nothing when the row already holds it.

A received answer's entry is committed by intake before the effects run
(ADR-0111), so :class:`EmbargoAnswerAppliesNode` makes the same decision
among the tree's guards: an answer that would record nothing the case can
take is refused before it is committed, and no replica is sent an entry it
could not apply (ADR-0124, SYNC-12-001).
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.embargo.decided_entries import (
    EmbargoDecision,
    decide_embargo_act,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.embargo_apply import ConsentRowChange
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.errors import VultronBTInternalError, VultronError


def decide_answer(
    datalayer: CasePersistence,
    *,
    case_id: str,
    embargo_id: str,
    actor_id: str,
    accept: bool,
) -> EmbargoDecision:
    """The decision *actor_id*'s answer to *embargo_id* makes, on a stage.

    Raises:
        VultronError: the lifecycle refuses the answer, or the answer records
            nothing the case can take; nothing is written.
    """

    def _decide(staged: CasePersistence) -> object:
        lifecycle = EmbargoLifecycle(persistence=staged)
        if accept:
            return lifecycle.accept_embargo_invite(
                case_id=case_id, embargo_id=embargo_id, actor_id=actor_id
            )
        return lifecycle.record_embargo_rejection(
            case_id=case_id, actor_id=actor_id, embargo_id=embargo_id
        )

    return decide_embargo_act(
        datalayer,
        case_id,
        _decide,
        answer=ConsentRowChange.answer(
            embargo_id=embargo_id, actor_id=actor_id, accept=accept
        ),
    )


class EmbargoAnswerAppliesNode(DataLayerConditionWithPorts):
    """Guard: the answer records a change the case can take, or one it holds.

    Runs :func:`decide_answer` and writes nothing.  FAILURE, so the answer is
    refused before its entry is committed, when the lifecycle refuses it or
    when the row it states cannot be written (no register entry, a final
    one, no participant record).  A decision fault raises.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        answering_actor_id: str,
        accept: bool,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.answering_actor_id = answering_actor_id
        self.accept = accept

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            decide_answer(
                self.datalayer,
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=self.answering_actor_id,
                accept=self.accept,
            )
        except VultronBTInternalError:
            raise
        except VultronError as exc:
            self.feedback_message = (
                f"'{self.answering_actor_id}''s answer to embargo"
                f" '{self.embargo_id}' records nothing on case"
                f" '{self.case_id}': {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


def case_manager_admits_answer_change_guard(
    case_id: str, embargo_id: str, answering_actor_id: str, *, accept: bool
) -> py_trees.behaviour.Behaviour:
    """Precondition guard: at the CASE_MANAGER, the answer records a change.

    A participant replica skips it as ``SUCCESS``: only the CASE_MANAGER
    records an answer (BT-17-001), and the gate reports the replica's
    refusal (HP-01-005).
    """
    return create_case_manager_gated_tree(
        name="EmbargoAnswerAppliesIfCaseManager",
        case_id=case_id,
        body_name="EmbargoAnswerApplies",
        children=[
            EmbargoAnswerAppliesNode(
                case_id=case_id,
                embargo_id=embargo_id,
                answering_actor_id=answering_actor_id,
                accept=accept,
            )
        ],
    )


__all__ = [
    "EmbargoAnswerAppliesNode",
    "case_manager_admits_answer_change_guard",
    "decide_answer",
]
