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

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory

logger = logging.getLogger(__name__)


def _default_id_assignable_factory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IdAssignable,
    )

    return IdAssignable(name)


def _default_in_scope_factory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import InScope

    return InScope(name)


def create_assign_vul_id_tree(
    case_id: str,
    id_assignable_factory: CallOutBackendFactory = _default_id_assignable_factory,
    in_scope_factory: CallOutBackendFactory = _default_in_scope_factory,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the VUL ID assignment workflow (Phase 1 stub).

    Phase 1 exposes the two Evaluator call-out points as a stub Sequence.
    The full workflow (authority check, request/assign branching, ID-already-
    assigned early exit) is deferred to a future issue.

    Args:
        case_id: ID of VulnerabilityCase being processed.
        id_assignable_factory: Factory for the Evaluator call-out point that
            checks whether the vulnerability qualifies for ID assignment.
            Defaults to the fuzzer backend (BT-18-004).
        in_scope_factory: Factory for the Evaluator call-out point that checks
            whether the vulnerability is within the applicable ID space scope.
            Defaults to the fuzzer backend (BT-18-004).

    Returns:
        Root node of the assign-VUL-ID behavior tree (Phase 1 stub Sequence).
    """
    root = py_trees.composites.Sequence(
        name="AssignVulIDBT",
        memory=False,
        children=[
            in_scope_factory("InScope"),
            id_assignable_factory("IdAssignable"),
        ],
    )
    logger.info(f"Created AssignVulIDBT (Phase 1 stub) for case={case_id}")
    return root
