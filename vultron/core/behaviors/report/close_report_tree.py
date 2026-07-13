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
"""Report closure behavior tree composition (Phase 1 stub).

This module provides :func:`create_close_report_tree`, which hosts the
``OtherCloseCriteriaMet`` call-out point wired per ADR-0025 / BT-18-004.

Phase 1 contains only the injectable call-out point as a stub tree.
The full close-report workflow (deployed/deferred/invalid short-circuit
arms, pre-close actions) is deferred to a future issue.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
"""

import logging

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory

logger = logging.getLogger(__name__)


def _default_other_close_criteria_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.close_report import (
        OtherCloseCriteriaMet,
    )

    return OtherCloseCriteriaMet(name)


def create_close_report_tree(
    case_id: str,
    other_close_criteria_factory: CallOutBackendFactory = _default_other_close_criteria_factory,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the report closure workflow (Phase 1 stub).

    Phase 1 exposes the ``OtherCloseCriteriaMet`` Evaluator call-out point
    as a stub root node.  The full workflow (deployed/deferred/invalid
    short-circuit arms, pre-close actions, RM state transition) is deferred
    to a future issue.

    Args:
        case_id: ID of VulnerabilityCase being processed.
        other_close_criteria_factory: Factory for the Evaluator call-out point
            that checks whether site-specific closure criteria have been met.
            Defaults to the fuzzer backend (BT-18-004).

    Returns:
        Root node of the close-report behavior tree (Phase 1 stub).
    """
    root = other_close_criteria_factory("OtherCloseCriteriaMet")
    logger.info(f"Created CloseReportBT (Phase 1 stub) for case={case_id}")
    return root
