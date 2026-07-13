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
"""Report-to-others behavior tree composition (Phase 1 stub).

This module provides :func:`create_report_to_others_tree`, which hosts the
four injectable call-out points from the report-to-others workflow
(``AllPartiesKnown``, ``RecipientEffortExceeded``, ``PolicyCompatible``,
``TotalEffortLimitMet``) wired per ADR-0025 / BT-18-004.

Phase 1 contains only the injectable call-out points as a stub Sequence.
The full notification workflow (party identification loop, recipient
selection, effort-limit checks, RM state management, participant injection)
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


def _default_all_parties_known_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        AllPartiesKnown,
    )

    return AllPartiesKnown(name)


def _default_recipient_effort_exceeded_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        RecipientEffortExceeded,
    )

    return RecipientEffortExceeded(name)


def _default_policy_compatible_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        PolicyCompatible,
    )

    return PolicyCompatible(name)


def _default_total_effort_limit_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        TotalEffortLimitMet,
    )

    return TotalEffortLimitMet(name)


def create_report_to_others_tree(
    case_id: str,
    all_parties_known_factory: CallOutBackendFactory = _default_all_parties_known_factory,
    recipient_effort_exceeded_factory: CallOutBackendFactory = _default_recipient_effort_exceeded_factory,
    policy_compatible_factory: CallOutBackendFactory = _default_policy_compatible_factory,
    total_effort_limit_factory: CallOutBackendFactory = _default_total_effort_limit_factory,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the report-to-others workflow (Phase 1 stub).

    Phase 1 exposes the four Evaluator call-out points as a stub Sequence.
    The full notification workflow (party identification loop, recipient
    selection and pruning, effort-limit guards, RM state transitions, and
    participant injection) is deferred to a future issue.

    Args:
        case_id: ID of VulnerabilityCase being processed.
        all_parties_known_factory: Factory for the Evaluator call-out point
            that checks whether all relevant notification parties have been
            identified.  Defaults to the fuzzer backend (BT-18-004).
        recipient_effort_exceeded_factory: Factory for the Evaluator call-out
            point that checks whether per-recipient notification effort has
            exceeded the policy threshold.  Defaults to the fuzzer backend
            (BT-18-004).
        policy_compatible_factory: Factory for the Evaluator call-out point
            that checks whether a recipient's disclosure policy is compatible
            with the case embargo.  Defaults to the fuzzer backend (BT-18-004).
        total_effort_limit_factory: Factory for the Evaluator call-out point
            that checks whether total notification effort has reached the
            organizational ceiling.  Defaults to the fuzzer backend (BT-18-004).

    Returns:
        Root node of the report-to-others behavior tree (Phase 1 stub Sequence).
    """
    root = py_trees.composites.Sequence(
        name="ReportToOthersBT",
        memory=False,
        children=[
            all_parties_known_factory("AllPartiesKnown"),
            recipient_effort_exceeded_factory("RecipientEffortExceeded"),
            policy_compatible_factory("PolicyCompatible"),
            total_effort_limit_factory("TotalEffortLimitMet"),
        ],
    )
    logger.info(f"Created ReportToOthersBT (Phase 1 stub) for case={case_id}")
    return root
