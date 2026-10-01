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

"""Receive-side tree composition: the four-stage shared factory (ADR-0111).

:func:`create_receive_activity_tree` is the one way to build a received-side
BT.  It fixes the stage order intake → precondition guards → guarded commit →
protocol effects (CLP-10-006, CLP-10-010) and supplies the shared intake node
itself (CLP-10-017), so no handler opts out of recording what arrived.

:func:`create_guarded_commit_case_ledger_entry_tree` is the commit stage.  It
is called here and nowhere else: a tree factory that calls it directly forks
the chain (CLP-09-001) and is a CLP-10-006 ordering violation caught by
``test/architecture/test_receive_side_bt_commit_ordering.py``.

Split out of ``nodes/lifecycle.py`` when that module came within the
BTND-07-004 split window of its cap; ``lifecycle.py`` keeps the commit *node*, and this tree-factory module
sits at the area root as BTND-07-003 requires.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)

logger = logging.getLogger(__name__)


def create_guarded_commit_case_ledger_entry_tree(
    case_id: str | None = None,
    case_may_be_absent: bool = False,
) -> py_trees.composites.Selector:
    """Create a guarded commit subtree for canonical case-ledger entries.

    The commit runs only when the executing actor holds ``CVDRole.CASE_MANAGER``
    for the case; see :func:`create_case_manager_gated_tree` for the gate's
    failure-mode semantics.

    Called internally by :func:`create_receive_activity_tree`.  Direct callers
    in tree-factory modules are a CLP-10-006 ordering violation; use
    ``create_receive_activity_tree`` instead.

    ``case_may_be_absent`` is passed to the gate; see
    :func:`create_receive_activity_tree`.
    """
    return create_case_manager_gated_tree(
        name="GuardedCommitCaseLedgerEntryBT",
        case_id=case_id,
        children=[CommitCaseLedgerEntryNode(case_id=case_id)],
        case_may_be_absent=case_may_be_absent,
    )


def create_receive_activity_tree(
    name: str,
    case_id: str | None,
    precondition_guards: list[py_trees.behaviour.Behaviour],
    effect_nodes: list[py_trees.behaviour.Behaviour],
    case_may_be_absent: bool = False,
) -> py_trees.composites.Sequence:
    """Compose a receive-side BT with the four CLP-10-010 stages in order.

    Structurally enforces the receive-side ordering (ADR-0111)::

        Intake → [*precondition_guards] → GuardedCommit(receipt) → [*effect_nodes]

    Intake is one shared :class:`IntakeReceivedActivityNode` that archives the
    received activity exactly as received, idempotently, and writes nothing
    else — in particular no core record from any object inlined in it, which
    an effect node writes from the event's copy after the guards
    (CLP-10-017).  It runs first so a guard that refuses the assertion still
    leaves the receiver holding what arrived (CLP-10-018).  Precondition guards are read-only checks that may
    return FAILURE to abort the tree before any protocol effect.  The guarded
    commit ledgers receipt of the triggering activity (which is on the
    blackboard before any node runs, placed there by
    ``BTBridge.execute_with_setup``).  Effect nodes perform state
    transitions, outbox enqueues, and participant mutations — all of which
    happen only after the receipt is recorded.

    When ``case_id`` is ``None`` the commit step is omitted entirely,
    preserving behaviour for trees that receive no explicit case context;
    intake still runs.

    Set ``case_may_be_absent`` when the receiver legitimately holds no replica
    of the case yet — an invitee holds only the Invite's case stub
    (MV-10-004).  The commit gate then skips at ``debug`` level for a case
    the receiver does not hold, instead of reporting it as an ADR-0087
    Regime 1 anomaly.

    Per ``specs/case-ledger-processing.yaml`` CLP-10-006, CLP-10-010,
    CLP-10-017.
    """
    children: list[py_trees.behaviour.Behaviour] = [
        IntakeReceivedActivityNode()
    ]
    children.extend(precondition_guards)
    if case_id is not None:
        children.append(
            create_guarded_commit_case_ledger_entry_tree(
                case_id=case_id, case_may_be_absent=case_may_be_absent
            )
        )
    else:
        logger.debug(
            "create_receive_activity_tree(%s): case_id is None"
            " — commit step omitted",
            name,
        )
    children.extend(effect_nodes)
    return py_trees.composites.Sequence(
        name=name,
        memory=False,
        children=children,
    )
