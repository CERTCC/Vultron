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
"""STOCHASTIC call-out bundle for the report prioritization domain (BT-23-003, BT-23-005).

Provides the simulation-layer :data:`PRIORITIZATION_STOCHASTIC` singleton.  The
bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.prioritization``) and are re-exported
here for backward-compatible import paths.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

- ``evaluate_priority_factory`` — EvaluateCasePriority     (p=1.0) → AlwaysSucceed
- ``on_accept_factory``         — OnAccept                 (p=1.0) → AlwaysSucceed
- ``on_defer_factory``          — OnDefer                  (p=1.0) → AlwaysSucceed
- ``enough_info_factory``       — EnoughPrioritizationInfo (p=0.75) → AlwaysSucceed
- ``gather_info_factory``       — GatherPrioritizationInfo (p=0.90) → AlwaysSucceed
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.prioritization import (  # noqa: F401
    PRIORITIZATION_DETERMINISTIC,
    PrioritizationCallOutBundle,
)


def _stochastic_evaluate_priority(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.prioritize import (
        EvaluateCasePriority,
    )

    return EvaluateCasePriority(name)


def _stochastic_on_accept(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.prioritize import OnAccept

    return OnAccept(name)


def _stochastic_on_defer(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.prioritize import OnDefer

    return OnDefer(name)


def _stochastic_enough_info(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.prioritize import (
        EnoughPrioritizationInfo,
    )

    return EnoughPrioritizationInfo(name)


def _stochastic_gather_info(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.prioritize import (
        GatherPrioritizationInfo,
    )

    return GatherPrioritizationInfo(name)


PRIORITIZATION_STOCHASTIC = PrioritizationCallOutBundle(
    evaluate_priority_factory=_stochastic_evaluate_priority,  # type: ignore[arg-type]
    on_accept_factory=_stochastic_on_accept,  # type: ignore[arg-type]
    on_defer_factory=_stochastic_on_defer,  # type: ignore[arg-type]
    enough_info_factory=_stochastic_enough_info,  # type: ignore[arg-type]
    gather_info_factory=_stochastic_gather_info,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "PrioritizationCallOutBundle",
    "PRIORITIZATION_DETERMINISTIC",
    "PRIORITIZATION_STOCHASTIC",
]
