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
"""Call-out bundle for the report closure domain (BT-23-003, BT-23-005).

Provides :class:`CloseReportCallOutBundle` plus the pre-built singletons
:data:`CLOSE_REPORT_DETERMINISTIC` and :data:`CLOSE_REPORT_STOCHASTIC`.

Ceiling/floor mapping (BT-23-002):

- ``other_close_criteria_factory`` — OtherCloseCriteriaMet (p=0.25) → AlwaysFail
- ``pre_close_action_factory``     — PreCloseAction        (p=1.0) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlwaysSucceed

    return AlwaysSucceed(name)


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlwaysFail

    return AlwaysFail(name)


def _stochastic_other_close_criteria(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.close_report import (
        OtherCloseCriteriaMet,
    )

    return OtherCloseCriteriaMet(name)


def _stochastic_pre_close_action(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.close_report import (
        PreCloseAction,
    )

    return PreCloseAction(name)


@dataclass(frozen=True)
class CloseReportCallOutBundle:
    """Call-out backend bundle for the report closure domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.close_report_tree.create_close_report_tree`.
    """

    other_close_criteria_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    pre_close_action_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


CLOSE_REPORT_DETERMINISTIC = CloseReportCallOutBundle()
"""Deterministic bundle: ceiling/floor of stochastic p (BT-23-001, BT-23-002)."""

CLOSE_REPORT_STOCHASTIC = CloseReportCallOutBundle(
    other_close_criteria_factory=_stochastic_other_close_criteria,  # type: ignore[arg-type]
    pre_close_action_factory=_stochastic_pre_close_action,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "CloseReportCallOutBundle",
    "CLOSE_REPORT_DETERMINISTIC",
    "CLOSE_REPORT_STOCHASTIC",
]
