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

Provides :class:`CloseReportCallOutBundle` and the pre-built core DETERMINISTIC
singleton :data:`CLOSE_REPORT_DETERMINISTIC`.  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.close_report.CLOSE_REPORT_STOCHASTIC`).

Ceiling/floor mapping (BT-23-002):

- ``other_close_criteria_factory`` — OtherCloseCriteriaMet (p=0.25) → AlwaysFail
- ``pre_close_action_factory``     — PreCloseAction        (p=1.0) → AlwaysSucceed
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

__all__ = [
    "CloseReportCallOutBundle",
    "CLOSE_REPORT_DETERMINISTIC",
]
