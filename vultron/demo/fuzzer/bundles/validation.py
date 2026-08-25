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
"""STOCHASTIC call-out bundle for the report validation domain (BT-23-003, BT-23-005).

Provides the simulation-layer :data:`VALIDATION_STOCHASTIC` singleton, which
wires the probabilistic ``WeightedBehavior`` fuzzer nodes into the core-owned
:class:`~vultron.core.behaviors.call_out.bundles.validation.ValidationCallOutBundle`.

The bundle dataclass and the DETERMINISTIC default are core concerns and live in
``vultron.core.behaviors.call_out.bundles.validation``; they are re-exported here
for backward-compatible import paths.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

- ``credibility_factory``   — EvaluateReportCredibility (p=0.90) → AlwaysSucceed
- ``validity_factory``      — EvaluateReportValidity    (p=0.90) → AlwaysSucceed
- ``gather_info_factory``   — GatherValidationInfo      (p=0.90) → AlwaysSucceed
"""

from __future__ import annotations

import py_trees

# Core-owned bundle dataclass + DETERMINISTIC default (re-exported for
# backward-compatible import paths).
from vultron.core.behaviors.call_out.bundles.validation import (  # noqa: F401
    VALIDATION_DETERMINISTIC,
    ValidationCallOutBundle,
)


def _stochastic_credibility(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.validate import (
        EvaluateReportCredibility,
    )

    return EvaluateReportCredibility(name)


def _stochastic_validity(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.validate import (
        EvaluateReportValidity,
    )

    return EvaluateReportValidity(name)


def _stochastic_gather_info(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.validate import (
        GatherValidationInfo,
    )

    return GatherValidationInfo(name)


VALIDATION_STOCHASTIC = ValidationCallOutBundle(
    credibility_factory=_stochastic_credibility,  # type: ignore[arg-type]
    validity_factory=_stochastic_validity,  # type: ignore[arg-type]
    gather_info_factory=_stochastic_gather_info,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "ValidationCallOutBundle",
    "VALIDATION_DETERMINISTIC",
    "VALIDATION_STOCHASTIC",
]
