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

A received answer's entry is committed by the guarded commit before the
effects run (ADR-0111), so :class:`EmbargoAnswerAppliesNode` makes the same decision
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
from vultron.errors import INTERNAL_FAULTS, VultronError


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


class EmbargoDecisionAppliesNode(DataLayerConditionWithPorts):
    """Shared frame: a received act's decision records what the case can take.

    A received act's entry is committed by the guarded commit before its
    effects run (ADR-0111), so the CASE_MANAGER makes the act's decision among the
    tree's guards too, on a staged store, and writes nothing: an act whose
    decision the lifecycle refuses, or whose entries would not apply, is
    refused before it is committed (ADR-0124, SYNC-12-001).  A subclass
    names the decision (:meth:`_decide`) and the act (:meth:`_act`).  A
    decision fault (``VultronBTInternalError``) raises.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def _decide(self, datalayer: CasePersistence) -> EmbargoDecision:
        """The act's decision on *datalayer*, staged; raises on a refusal."""
        raise NotImplementedError

    def _act(self) -> str:
        """The act, as the refusal's feedback names it."""
        raise NotImplementedError

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            self._decide(self.datalayer)
        except INTERNAL_FAULTS:
            raise  # never a refusal, so never answered (ADR-0095)
        except VultronError as exc:
            self.feedback_message = (
                f"{self._act()} records nothing on case '{self.case_id}':"
                f" {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


class EmbargoAnswerAppliesNode(EmbargoDecisionAppliesNode):
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
        super().__init__(case_id, name=name)
        self.embargo_id = embargo_id
        self.answering_actor_id = answering_actor_id
        self.accept = accept

    def _decide(self, datalayer: CasePersistence) -> EmbargoDecision:
        return decide_answer(
            datalayer,
            case_id=self.case_id,
            embargo_id=self.embargo_id,
            actor_id=self.answering_actor_id,
            accept=self.accept,
        )

    def _act(self) -> str:
        return (
            f"'{self.answering_actor_id}''s answer to embargo"
            f" '{self.embargo_id}'"
        )


def case_manager_decision_guard(
    name: str, case_id: str, guard: EmbargoDecisionAppliesNode
) -> py_trees.behaviour.Behaviour:
    """*guard*, run only at the CASE_MANAGER (a precondition guard).

    A participant replica skips it as ``SUCCESS``: only the CASE_MANAGER
    records the act (BT-17-001), and the gate reports the replica's refusal
    (HP-01-005).
    """
    return create_case_manager_gated_tree(
        name=f"{name}IfCaseManager",
        case_id=case_id,
        body_name=name,
        children=[guard],
    )


def case_manager_admits_answer_change_guard(
    case_id: str, embargo_id: str, answering_actor_id: str, *, accept: bool
) -> py_trees.behaviour.Behaviour:
    """Precondition guard: at the CASE_MANAGER, the answer records a change."""
    return case_manager_decision_guard(
        "EmbargoAnswerApplies",
        case_id,
        EmbargoAnswerAppliesNode(
            case_id=case_id,
            embargo_id=embargo_id,
            answering_actor_id=answering_actor_id,
            accept=accept,
        ),
    )


__all__ = [
    "EmbargoAnswerAppliesNode",
    "EmbargoDecisionAppliesNode",
    "case_manager_admits_answer_change_guard",
    "case_manager_decision_guard",
    "decide_answer",
]
