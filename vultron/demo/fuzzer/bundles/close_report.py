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
"""STOCHASTIC call-out bundle for the report closure domain (BT-23-003, BT-23-005).

Provides the simulation-layer :data:`CLOSE_REPORT_STOCHASTIC` singleton.  The
bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.close_report``) and are re-exported
here for backward-compatible import paths.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

- ``other_close_criteria_factory`` — OtherCloseCriteriaMet (p=0.25) → AlwaysFail
- ``pre_close_action_factory``     — PreCloseAction        (p=1.0) → AlwaysSucceed
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.close_report import (  # noqa: F401
    CLOSE_REPORT_DETERMINISTIC,
    CloseReportCallOutBundle,
)


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
