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
close-report call-out points wired per ADR-0025 / BT-18-004:

Evaluator node:
- ``OtherCloseCriteriaMet``

Actuator node (reserved for Phase 2 — accepted but not yet wired):
- ``PreCloseAction``

Phase 1 contains only the ``OtherCloseCriteriaMet`` Evaluator as a stub
tree.  The full close-report workflow (deployed/deferred/invalid short-circuit
arms, pre-close actions) is deferred to a future issue.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
"""

import logging
from typing import TYPE_CHECKING

import py_trees

if TYPE_CHECKING:
    from vultron.demo.fuzzer.bundles.close_report import (
        CloseReportCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_close_report_tree(
    case_id: str,
    call_out: "CloseReportCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the report closure workflow (Phase 1 stub).

    Phase 1 exposes the ``OtherCloseCriteriaMet`` Evaluator call-out point
    as a stub root node.  The ``pre_close_action_factory`` Actuator parameter
    is accepted for BT-18-004 compliance but reserved for Phase 2 when the
    full pre-close sequence is built.  The full workflow (deployed/deferred/
    invalid short-circuit arms, pre-close actions, RM state transition) is
    deferred to a future issue.

    Args:
        case_id: ID of VulnerabilityCase being processed.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to :data:`~vultron.demo.fuzzer.bundles.close_report.CLOSE_REPORT_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the close-report behavior tree (Phase 1 stub).
    """
    from vultron.demo.fuzzer.bundles.close_report import (
        CLOSE_REPORT_DETERMINISTIC,
    )

    bundle = call_out if call_out is not None else CLOSE_REPORT_DETERMINISTIC
    # Phase 2: bundle.pre_close_action_factory is reserved for the full pre-close
    # sequence.
    root = bundle.other_close_criteria_factory("OtherCloseCriteriaMet")
    logger.info(f"Created CloseReportBT (Phase 1 stub) for case={case_id}")
    return root
