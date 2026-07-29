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
"""Call-out bundle for the vulnerability ID assignment domain (BT-23-003, BT-23-005).

Provides :class:`AssignVulIdCallOutBundle` and the pre-built core DETERMINISTIC
singleton :data:`ASSIGN_VUL_ID_DETERMINISTIC`.  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.assign_vul_id.ASSIGN_VUL_ID_STOCHASTIC`).

Ceiling/floor mapping (BT-23-002):

- ``id_assignable_factory`` — IdAssignable (p=0.67) → AlwaysSucceed
- ``in_scope_factory``      — InScope      (p=0.75) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


@dataclass(frozen=True)
class AssignVulIdCallOutBundle:
    """Call-out backend bundle for the vulnerability ID assignment domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.assign_vul_id_tree.create_assign_vul_id_tree`.
    """

    id_assignable_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    in_scope_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


ASSIGN_VUL_ID_DETERMINISTIC = AssignVulIdCallOutBundle()
"""Deterministic bundle: all nodes use AlwaysSucceed (BT-23-001, BT-23-002)."""

__all__ = [
    "AssignVulIdCallOutBundle",
    "ASSIGN_VUL_ID_DETERMINISTIC",
]
