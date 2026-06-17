#!/usr/bin/env python
"""Behavior tree factory for the inbox orchestration pipeline.

Creates the BT Sequence that enforces fixed pipeline ordering:
parse → rehydrate → extract → defer-check → dispatch → outcome.

Per specs/inbox-orchestration.yaml IO-02-002.
"""

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

import py_trees

from vultron.core.behaviors.inbox.nodes import (
    BuildOutcomeNode,
    DeferCheckNode,
    DispatchNode,
    ExtractSemanticsNode,
    ParsePayloadNode,
    RehydrateActivityNode,
)


def create_inbox_bt() -> py_trees.behaviour.Behaviour:
    """Return a fresh BT Sequence for one inbox pipeline execution.

    The Sequence enforces that each step succeeds before the next runs.
    On any failure the remaining steps are skipped and the failure step
    records the outcome status on the blackboard for
    :func:`~vultron.core.behaviors.inbox.process_payload` to read.

    Tree structure (IO-02-002):

    .. code-block:: text

        Sequence
          ├─ ParsePayloadNode
          ├─ RehydrateActivityNode
          ├─ ExtractSemanticsNode
          ├─ DeferCheckNode
          ├─ DispatchNode
          └─ BuildOutcomeNode
    """
    return py_trees.composites.Sequence(
        name="InboxPipelineBT",
        memory=False,
        children=[
            ParsePayloadNode(name="ParsePayload"),
            RehydrateActivityNode(name="RehydrateActivity"),
            ExtractSemanticsNode(name="ExtractSemantics"),
            DeferCheckNode(name="DeferCheck"),
            DispatchNode(name="Dispatch"),
            BuildOutcomeNode(name="BuildOutcome"),
        ],
    )
