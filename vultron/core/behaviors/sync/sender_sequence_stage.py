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

"""The received-tree stage that orders a sender's activities (SYNC-21).

:func:`create_sender_sequence_stage` builds the CASE_MANAGER's judgment of a
received activity's ``senderSequence`` (ADR-0178).
``create_receive_activity_tree`` places it in every received tree that names
its case and has a sender guard, after the door guards and the ledger
position answer and before the clock decisions and precondition guards, so
it sees only an activity the guards admit (SYNC-21-023) and the tree judges
each activity unchanged, in its sender's order::

    SenderSequenceIfCaseManager (CaseManagerGate)
    └─ SenderSequenceOrder (Sequence)
       ├─ ClassifySenderSequence
       ├─ AnswerBySenderSequence (Selector)
       │  ├─ SenderSequenceIs[not-numbered|judged-repeat|held-repeat|…]
       │  ├─ AdmitInOrder: SenderSequenceIs[next|past-skip], AdmitInOrderNode
       │  ├─ HoldPastGap: SenderSequenceIs[ahead], HoldPastGapNode
       │  └─ RefuseNumber: SenderSequenceIs[late|reused|missing],
       │        RefusalActTransaction[EmitSenderSequenceRefusalNotice]
       └─ SenderSequenceAdmits     # FAILURE ends the tree for all but judged

A held activity is judged later, as a delivery of its own, once it is due
(``queue_due_sender_sequence_replays``).
"""

from collections.abc import Callable

import py_trees

from vultron.core.behaviors.act_transaction import RefusalActTransaction
from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.sync.nodes.sender_sequence import (
    AdmitInOrderNode,
    ClassifySequenceNumberNode,
    EmitSequenceRefusalNoticeNode,
    HoldPastGapNode,
    SequenceAdmitsNode,
    SequenceOrderStage,
    SequenceStandingIsNode,
)
from vultron.core.services.sender_sequence_order import (
    NOTICED,
    SequenceStanding,
)

__all__ = ["SENDER_SEQUENCE_GATE_NAME", "create_sender_sequence_stage"]

SENDER_SEQUENCE_GATE_NAME = "SenderSequenceIfCaseManager"

#: The standings the stage answers by writing nothing.
_NOTHING_TO_WRITE = frozenset(
    {
        SequenceStanding.NOT_NUMBERED,
        SequenceStanding.JUDGED_REPEAT,
        SequenceStanding.HELD_REPEAT,
        SequenceStanding.REPEAT_REFUSED,
    }
)


def _arm(
    name: str, *children: py_trees.behaviour.Behaviour
) -> py_trees.composites.Sequence:
    return py_trees.composites.Sequence(
        name=name, memory=False, children=list(children)
    )


def create_sender_sequence_stage(
    case_id: str,
    sender_id: str,
    *,
    is_redelivery: Callable[[], bool] | None = None,
) -> CaseManagerGate:
    """The CASE_MANAGER's judgment of *sender_id*'s number on *case_id*.

    Runs only at the case's CASE_MANAGER; a store that does not hold the
    case skips it at ``debug`` level.  *is_redelivery* tells an activity this
    store had already archived, which the factory reads from intake.
    """
    classify = ClassifySequenceNumberNode(
        case_id=case_id,
        sender_id=sender_id,
        name="ClassifySenderSequence",
        is_redelivery=is_redelivery,
    )
    answer = py_trees.composites.Selector(
        name="AnswerBySenderSequence",
        memory=False,
        children=[
            SequenceStandingIsNode(classify, _NOTHING_TO_WRITE),
            _arm(
                "AdmitInOrder",
                SequenceStandingIsNode(
                    classify,
                    frozenset(
                        {SequenceStanding.NEXT, SequenceStanding.PAST_SKIP}
                    ),
                ),
                AdmitInOrderNode(classify),
            ),
            _arm(
                "HoldPastGap",
                SequenceStandingIsNode(
                    classify, frozenset({SequenceStanding.AHEAD})
                ),
                HoldPastGapNode(classify),
            ),
            _arm(
                "RefuseNumber",
                SequenceStandingIsNode(classify, NOTICED),
                RefusalActTransaction(
                    name="SenderSequenceRefusal",
                    children=[
                        EmitSequenceRefusalNoticeNode(
                            case_id=case_id,
                            classify=classify,
                            name="EmitSenderSequenceRefusalNotice",
                        )
                    ],
                ),
            ),
        ],
    )
    stage = SequenceOrderStage(
        name="SenderSequenceOrder",
        memory=False,
        children=[
            classify,
            answer,
            SequenceAdmitsNode(classify, name="SenderSequenceAdmits"),
        ],
    )
    return create_case_manager_gated_tree(
        name=SENDER_SEQUENCE_GATE_NAME,
        case_id=case_id,
        children=[stage],
        case_may_be_absent=True,
    )
