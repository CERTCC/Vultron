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
"""VUL ID assignment behavior tree composition (Phase 1 stub).

This module provides :func:`create_assign_vul_id_tree`, which hosts the
``IdAssignable`` and ``InScope`` call-out points wired per ADR-0025 / BT-18-004.

Phase 1 contains only the two injectable call-out points as a stub tree.
The full VUL ID assignment workflow (authority check, request/assign branching)
is deferred to a future issue.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
"""

import logging
from typing import TYPE_CHECKING

import py_trees

if TYPE_CHECKING:
    from vultron.demo.fuzzer.bundles.assign_vul_id import (
        AssignVulIdCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_assign_vul_id_tree(
    case_id: str,
    call_out: "AssignVulIdCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the VUL ID assignment workflow (Phase 1 stub).

    Phase 1 exposes the two Evaluator call-out points as a stub Sequence.
    The full workflow (authority check, request/assign branching, ID-already-
    assigned early exit) is deferred to a future issue.

    Args:
        case_id: ID of VulnerabilityCase being processed.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to :data:`~vultron.demo.fuzzer.bundles.assign_vul_id.ASSIGN_VUL_ID_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the assign-VUL-ID behavior tree (Phase 1 stub Sequence).
    """
    from vultron.demo.fuzzer.bundles.assign_vul_id import (
        ASSIGN_VUL_ID_DETERMINISTIC,
    )

    bundle = call_out if call_out is not None else ASSIGN_VUL_ID_DETERMINISTIC
    root = py_trees.composites.Sequence(
        name="AssignVulIDBT",
        memory=False,
        children=[
            bundle.in_scope_factory("InScope"),
            bundle.id_assignable_factory("IdAssignable"),
        ],
    )
    logger.info(f"Created AssignVulIDBT (Phase 1 stub) for case={case_id}")
    return root
