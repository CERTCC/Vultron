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
"""Publication behavior tree composition (Phase 1 stub).

This module provides a minimal :func:`create_publication_tree` factory that
hosts the Composer-shaped ``PrepareReport`` call-out point exemplar, wired
per ADR-0025 / BT-18-004.

Phase 1 contains only the ``PrepareReport`` Composer node.  The full
publication workflow (advisory sequencing, fix/exploit publication arms,
intent prioritization) is tracked in issue #1251.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
- Full publication workflow: issue #1251
"""

import logging

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory

logger = logging.getLogger(__name__)


def _default_prepare_report_factory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import PrepareReport

    return PrepareReport(name)


def create_publication_tree(
    case_id: str,
    prepare_report_factory: CallOutBackendFactory = _default_prepare_report_factory,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the publication workflow (Phase 1 stub).

    Phase 1 contains only the ``PrepareReport`` Composer call-out point.
    The full multi-arm publication workflow (report/fix/exploit arms,
    intent prioritization, and the ``Publish`` Actuator) is tracked in
    issue #1251.

    Args:
        case_id: ID of VulnerabilityCase to publish for.
        prepare_report_factory: Factory for the Composer call-out point that
            authors and stages the vulnerability advisory artifact.  Defaults
            to the fuzzer backend (BT-18-004).

    Returns:
        Root node of the publication behavior tree.
    """
    root = prepare_report_factory("PrepareReport")
    logger.info(f"Created PublicationBT (Phase 1 stub) for case={case_id}")
    return root
