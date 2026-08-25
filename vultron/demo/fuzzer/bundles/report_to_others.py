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
"""STOCHASTIC call-out bundle for the report-to-others domain (BT-23-003, BT-23-005).

Provides the simulation-layer :data:`REPORT_TO_OTHERS_STOCHASTIC` singleton.  The
bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.report_to_others``) and are re-exported
here for backward-compatible import paths.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

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

import py_trees

from vultron.core.behaviors.call_out.bundles.report_to_others import (  # noqa: F401
    REPORT_TO_OTHERS_DETERMINISTIC,
    ReportToOthersCallOutBundle,
)


def _stochastic_all_parties_known(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        AllPartiesKnown,
    )

    return AllPartiesKnown(name)


def _stochastic_total_effort_limit(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        TotalEffortLimitMet,
    )

    return TotalEffortLimitMet(name)


def _stochastic_more_vendors(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        MoreVendors,
    )

    return MoreVendors(name)


def _stochastic_more_coordinators(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        MoreCoordinators,
    )

    return MoreCoordinators(name)


def _stochastic_more_others(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        MoreOthers,
    )

    return MoreOthers(name)


def _stochastic_suggest_vendor(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        InjectVendor,
    )

    return InjectVendor(name)


def _stochastic_suggest_coordinator(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        InjectCoordinator,
    )

    return InjectCoordinator(name)


def _stochastic_suggest_other(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.report_to_others import (
        InjectOther,
    )

    return InjectOther(name)


REPORT_TO_OTHERS_STOCHASTIC = ReportToOthersCallOutBundle(
    all_parties_known_factory=_stochastic_all_parties_known,  # type: ignore[arg-type]
    total_effort_limit_factory=_stochastic_total_effort_limit,  # type: ignore[arg-type]
    more_vendors_factory=_stochastic_more_vendors,  # type: ignore[arg-type]
    more_coordinators_factory=_stochastic_more_coordinators,  # type: ignore[arg-type]
    more_others_factory=_stochastic_more_others,  # type: ignore[arg-type]
    suggest_vendor_factory=_stochastic_suggest_vendor,  # type: ignore[arg-type]
    suggest_coordinator_factory=_stochastic_suggest_coordinator,  # type: ignore[arg-type]
    suggest_other_factory=_stochastic_suggest_other,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "ReportToOthersCallOutBundle",
    "REPORT_TO_OTHERS_DETERMINISTIC",
    "REPORT_TO_OTHERS_STOCHASTIC",
]
