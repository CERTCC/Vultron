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
report-to-others call-out points wired per ADR-0025 / BT-18-004:

Evaluator nodes:
- ``AllPartiesKnown``
- ``RecipientEffortExceeded``
- ``PolicyCompatible``
- ``TotalEffortLimitMet``

Actuator nodes (reserved for Phase 2 — accepted but not yet wired):
- ``RemoveRecipient``
- ``SetRcptQrmR``
- ``InjectParticipant`` (covers ``InjectVendor``, ``InjectCoordinator``,
  ``InjectOther`` via MRO; one factory parameter for the family)

Phase 1 contains only the four Evaluator call-out points as a stub Sequence.
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


# ---------------------------------------------------------------------------
# Actuator default factories (Phase 2 reserved)
# ---------------------------------------------------------------------------


def _default_remove_recipient_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        RemoveRecipient,
    )

    return RemoveRecipient(name)


def _default_set_rcpt_qrm_r_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        SetRcptQrmR,
    )

    return SetRcptQrmR(name)


def _default_inject_participant_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        InjectParticipant,
    )

    return InjectParticipant(name)


def create_report_to_others_tree(
    case_id: str,
    all_parties_known_factory: CallOutBackendFactory = _default_all_parties_known_factory,
    recipient_effort_exceeded_factory: CallOutBackendFactory = _default_recipient_effort_exceeded_factory,
    policy_compatible_factory: CallOutBackendFactory = _default_policy_compatible_factory,
    total_effort_limit_factory: CallOutBackendFactory = _default_total_effort_limit_factory,
    remove_recipient_factory: CallOutBackendFactory = _default_remove_recipient_factory,
    set_rcpt_qrm_r_factory: CallOutBackendFactory = _default_set_rcpt_qrm_r_factory,
    inject_participant_factory: CallOutBackendFactory = _default_inject_participant_factory,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the report-to-others workflow (Phase 1 stub).

    Phase 1 exposes the four Evaluator call-out points as a stub Sequence.
    The three Actuator factories (remove_recipient_factory,
    set_rcpt_qrm_r_factory, inject_participant_factory) are accepted for
    BT-18-004 compliance but reserved for Phase 2 when the full notification
    loop (recipient selection, RM state transitions, participant injection)
    is built.  ``inject_participant_factory`` covers ``InjectVendor``,
    ``InjectCoordinator``, and ``InjectOther`` via MRO.

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
        remove_recipient_factory: Factory for the Actuator call-out point that
            removes a recipient from the pending notification queue.  Reserved
            for Phase 2; accepted but not yet wired (BT-18-004).
        set_rcpt_qrm_r_factory: Factory for the Actuator call-out point that
            transitions a recipient's RM state to RECEIVED.  Reserved for Phase
            2; accepted but not yet wired (BT-18-004).
        inject_participant_factory: Factory for the Actuator call-out point
            that adds a new participant to the case.  Covers ``InjectVendor``,
            ``InjectCoordinator``, and ``InjectOther`` via MRO.  Reserved for
            Phase 2; accepted but not yet wired (BT-18-004).

    Returns:
        Root node of the report-to-others behavior tree (Phase 1 stub Sequence).
    """
    # Phase 2: remove_recipient_factory, set_rcpt_qrm_r_factory, and
    # inject_participant_factory are reserved for the full notification loop.
    # Accepting them here satisfies BT-18-004 without breaking callers.
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
