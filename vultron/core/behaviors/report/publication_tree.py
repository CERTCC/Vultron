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
hosts the publication call-out points wired per ADR-0025 / BT-18-004:

Composer node:
- ``PrepareReport``

Evaluator nodes (reserved for Phase 2 — accepted but not yet wired):
- ``PrioritizePublicationIntents``
- ``ReprioritizeExploit``
- ``ReprioritizeFix``
- ``ReprioritizeReport``

Actuator node (reserved for Phase 2 — accepted but not yet wired):
- ``Publish``

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


def _default_prioritize_publication_intents_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        PrioritizePublicationIntents,
    )

    return PrioritizePublicationIntents(name)


def _default_reprioritize_exploit_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        ReprioritizeExploit,
    )

    return ReprioritizeExploit(name)


def _default_reprioritize_fix_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        ReprioritizeFix,
    )

    return ReprioritizeFix(name)


def _default_reprioritize_report_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        ReprioritizeReport,
    )

    return ReprioritizeReport(name)


def _default_publish_factory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import Publish

    return Publish(name)


def create_publication_tree(
    case_id: str,
    prepare_report_factory: CallOutBackendFactory = _default_prepare_report_factory,
    prioritize_publication_intents_factory: CallOutBackendFactory = _default_prioritize_publication_intents_factory,
    reprioritize_exploit_factory: CallOutBackendFactory = _default_reprioritize_exploit_factory,
    reprioritize_fix_factory: CallOutBackendFactory = _default_reprioritize_fix_factory,
    reprioritize_report_factory: CallOutBackendFactory = _default_reprioritize_report_factory,
    publish_factory: CallOutBackendFactory = _default_publish_factory,
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
        prioritize_publication_intents_factory: Factory for the Evaluator
            call-out point that ranks publication intents.  Reserved for Phase
            2; accepted but not yet wired into the Phase 1 tree body (BT-18-004).
        reprioritize_exploit_factory: Factory for the Evaluator call-out point
            that re-scores exploit publication priority.  Reserved for Phase 2;
            not wired in Phase 1 (BT-18-004).
        reprioritize_fix_factory: Factory for the Evaluator call-out point that
            re-scores fix publication priority.  Reserved for Phase 2; not wired
            in Phase 1 (BT-18-004).
        reprioritize_report_factory: Factory for the Evaluator call-out point
            that re-scores report publication priority.  Reserved for Phase 2;
            not wired in Phase 1 (BT-18-004).
        publish_factory: Factory for the Actuator call-out point that publishes
            a prepared artifact to the intended audience.  Reserved for Phase 2;
            accepted but not yet wired into the Phase 1 tree body (BT-18-004).

    Returns:
        Root node of the publication behavior tree.
    """
    # Phase 2: all factories except prepare_report_factory are reserved for the
    # full multi-arm publication workflow tracked in issue #1251.  Accepting them
    # here satisfies BT-18-004 without breaking callers.
    root = prepare_report_factory("PrepareReport")
    logger.info(f"Created PublicationBT (Phase 1 stub) for case={case_id}")
    return root
