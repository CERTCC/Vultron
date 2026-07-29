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
"""STOCHASTIC call-out bundle for the fix development domain (BT-23-003, BT-23-005).

Provides the simulation-layer :data:`DEVELOP_FIX_STOCHASTIC` singleton.  The
bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.develop_fix``) and are re-exported
here for backward-compatible import paths.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

- ``create_fix_factory``  — CreateFix  (p=0.90) → AlwaysSucceed
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.develop_fix import (  # noqa: F401
    DEVELOP_FIX_DETERMINISTIC,
    DevelopFixCallOutBundle,
)


def _stochastic_create_fix(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.develop_fix import CreateFix

    return CreateFix(name)


DEVELOP_FIX_STOCHASTIC = DevelopFixCallOutBundle(
    create_fix_factory=_stochastic_create_fix,  # type: ignore[arg-type]
)
"""Stochastic bundle: CreateFix uses the probabilistic fuzzer class (p=0.90)."""

__all__ = [
    "DevelopFixCallOutBundle",
    "DEVELOP_FIX_DETERMINISTIC",
    "DEVELOP_FIX_STOCHASTIC",
]
