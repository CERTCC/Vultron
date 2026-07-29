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
"""STOCHASTIC call-out bundle for the vulnerability ID assignment domain (BT-23).

Provides the simulation-layer :data:`ASSIGN_VUL_ID_STOCHASTIC` singleton.  The
bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.assign_vul_id``) and are re-exported
here for backward-compatible import paths.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

- ``id_assignable_factory`` — IdAssignable (p=0.67) → AlwaysSucceed
- ``in_scope_factory``      — InScope      (p=0.75) → AlwaysSucceed
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.assign_vul_id import (  # noqa: F401
    ASSIGN_VUL_ID_DETERMINISTIC,
    AssignVulIdCallOutBundle,
)


def _stochastic_id_assignable(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IdAssignable,
    )

    return IdAssignable(name)


def _stochastic_in_scope(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import InScope

    return InScope(name)


ASSIGN_VUL_ID_STOCHASTIC = AssignVulIdCallOutBundle(
    id_assignable_factory=_stochastic_id_assignable,  # type: ignore[arg-type]
    in_scope_factory=_stochastic_in_scope,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "AssignVulIdCallOutBundle",
    "ASSIGN_VUL_ID_DETERMINISTIC",
    "ASSIGN_VUL_ID_STOCHASTIC",
]
