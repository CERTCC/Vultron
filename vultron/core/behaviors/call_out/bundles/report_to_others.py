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
"""Call-out bundle for the report-to-others domain (BT-23-003, BT-23-005).

Provides :class:`ReportToOthersCallOutBundle` and the pre-built core
DETERMINISTIC singleton :data:`REPORT_TO_OTHERS_DETERMINISTIC`.  The matching
STOCHASTIC singleton lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.report_to_others.REPORT_TO_OTHERS_STOCHASTIC`).

Ceiling/floor mapping (BT-23-002):

- ``all_parties_known_factory``       — AllPartiesKnown       (p=0.50) → AlwaysSucceed (tie-break)
- ``total_effort_limit_factory``      — TotalEffortLimitMet   (p=0.10) → AlwaysFail
- ``more_vendors_factory``            — MoreVendors           (p=0.25) → AlwaysFail
- ``more_coordinators_factory``       — MoreCoordinators      (p=0.10) → AlwaysFail
- ``more_others_factory``             — MoreOthers            (p=0.10) → AlwaysFail
- ``suggest_vendor_factory``          — InjectVendor          (p=1.0) → AlwaysSucceed
- ``suggest_coordinator_factory``     — InjectCoordinator     (p=1.0) → AlwaysSucceed
- ``suggest_other_factory``           — InjectOther           (p=1.0) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysFail(name)


@dataclass(frozen=True)
class ReportToOthersCallOutBundle:
    """Call-out backend bundle for the report-to-others domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.report_to_others_tree.create_report_to_others_tree`.
    """

    all_parties_known_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    total_effort_limit_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    more_vendors_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    more_coordinators_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    more_others_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    suggest_vendor_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    suggest_coordinator_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    suggest_other_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


REPORT_TO_OTHERS_DETERMINISTIC = ReportToOthersCallOutBundle()
"""Deterministic bundle: ceiling/floor of stochastic p (BT-23-001, BT-23-002)."""

__all__ = [
    "ReportToOthersCallOutBundle",
    "REPORT_TO_OTHERS_DETERMINISTIC",
]
