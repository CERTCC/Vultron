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
"""Call-out bundle for the report prioritization domain (BT-23-003, BT-23-005).

Provides :class:`PrioritizationCallOutBundle` and the pre-built core
DETERMINISTIC singleton :data:`PRIORITIZATION_DETERMINISTIC`.  The matching
STOCHASTIC singleton lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.prioritization.PRIORITIZATION_STOCHASTIC`).

Ceiling/floor mapping (BT-23-002):

- ``evaluate_priority_factory`` — EvaluateCasePriority     (p=1.0) → AlwaysSucceed
- ``on_accept_factory``         — OnAccept                 (p=1.0) → AlwaysSucceed
- ``on_defer_factory``          — OnDefer                  (p=1.0) → AlwaysSucceed
- ``enough_info_factory``       — EnoughPrioritizationInfo (p=0.75) → AlwaysSucceed
- ``gather_info_factory``       — GatherPrioritizationInfo (p=0.90) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


@dataclass(frozen=True)
class PrioritizationCallOutBundle:
    """Call-out backend bundle for the report prioritization domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree`.
    """

    evaluate_priority_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    on_accept_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    on_defer_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    enough_info_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    gather_info_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


PRIORITIZATION_DETERMINISTIC = PrioritizationCallOutBundle()
"""Deterministic bundle: all nodes use AlwaysSucceed (BT-23-001, BT-23-002)."""

__all__ = [
    "PrioritizationCallOutBundle",
    "PRIORITIZATION_DETERMINISTIC",
]
