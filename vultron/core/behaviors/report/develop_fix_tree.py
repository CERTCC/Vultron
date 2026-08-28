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
"""Fix development behavior tree composition.

This module provides :func:`create_develop_fix_tree`, which composes the full
fix-development workflow as a ``DevelopFixBT`` Fallback:

.. code-block:: text

    DevelopFixBT (Fallback)
    ├─ CheckIsVendorRoleNode          # short-circuit: actor is not a vendor
    ├─ CheckCSFixNotYetReady           # short-circuit: fix already ready
    └─ _CreateFixForAcceptedReports (Sequence)
       ├─ CheckRMStateAccepted
       ├─ <CreateFix call-out point>   # Composer, injected via DevelopFixCallOutBundle
       ├─ TransitionCStoFixReady
       └─ EmitCFActivity

Call-out injection seams
------------------------
- **CreateFix** — ``DevelopFixCallOutBundle.create_fix_factory``
  Composer call-out point; ``output_keys = {"fix_artifact": str}`` (BT-18-001).

References
----------
- Issue: #1812
- Source Idea: #1247
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-06-001, BT-18-004
"""

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.report.nodes.conditions import (
    CheckRMStateAccepted,
)
from vultron.core.behaviors.report.nodes.develop_fix import (
    CheckCSFixNotYetReady,
    CheckIsVendorRoleNode,
    EmitCFActivity,
    TransitionCStoFixReady,
)

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.develop_fix import (
        DevelopFixCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_develop_fix_tree(
    case_id: str,
    actor_id: str,
    call_out: "DevelopFixCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the fix development workflow.

    Mirrors the legacy ``DevelopFix`` Fallback from
    ``vultron/bt/report_management/_behaviors/develop_fix.py`` with all
    guards and protocol-action nodes implemented as production-layer
    ``py_trees`` nodes.

    The tree short-circuits (returns SUCCESS) for non-vendor actors and for
    cases where a fix is already ready.  Vendors whose RM state is ACCEPTED
    and whose fix is not yet developed proceed through the
    ``_CreateFixForAcceptedReports`` Sequence.

    Call-out injection seams (ADR-0025 / BT-18-004):

    - ``CreateFix`` — ``DevelopFixCallOutBundle.create_fix_factory``
      Blackboard output: ``fix_artifact: str`` (BT-18-001)

    Args:
        case_id: ID of VulnerabilityCase being processed.
        actor_id: ID of the actor running this tree.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.develop_fix.DEVELOP_FIX_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the develop-fix behavior tree (Fallback).
    """
    from vultron.core.behaviors.call_out.bundles.develop_fix import (
        DEVELOP_FIX_DETERMINISTIC,
    )

    bundle = call_out if call_out is not None else DEVELOP_FIX_DETERMINISTIC

    result_out: dict = {}

    create_fix_sequence = py_trees.composites.Sequence(
        name="_CreateFixForAcceptedReports",
        memory=False,
        children=[
            CheckRMStateAccepted(case_id=case_id, actor_id=actor_id),
            bundle.create_fix_factory("CreateFix"),
            TransitionCStoFixReady(
                case_id=case_id, actor_id=actor_id, result_out=result_out
            ),
            EmitCFActivity(
                case_id=case_id, actor_id=actor_id, result_out=result_out
            ),
        ],
    )

    root = py_trees.composites.Selector(
        name="DevelopFixBT",
        memory=False,
        children=[
            CheckIsVendorRoleNode(case_id=case_id, actor_id=actor_id),
            CheckCSFixNotYetReady(case_id=case_id, actor_id=actor_id),
            create_fix_sequence,
        ],
    )

    logger.info("Created DevelopFixBT for case=%s actor=%s", case_id, actor_id)
    return root
