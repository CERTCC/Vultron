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
"""Call-out bundle for the fix development domain (BT-23-003, BT-23-005).

Provides :class:`DevelopFixCallOutBundle` and the pre-built core DETERMINISTIC
singleton :data:`DEVELOP_FIX_DETERMINISTIC`.  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.develop_fix.DEVELOP_FIX_STOCHASTIC`).

Ceiling/floor mapping (BT-23-002):

- ``create_fix_factory``  — CreateFix  (p=0.90) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


@dataclass(frozen=True)
class DevelopFixCallOutBundle:
    """Call-out backend bundle for the fix development domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.develop_fix_tree.create_develop_fix_tree`.
    """

    create_fix_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


DEVELOP_FIX_DETERMINISTIC = DevelopFixCallOutBundle()
"""Deterministic bundle: ceiling/floor of stochastic p (BT-23-001, BT-23-002).

``create_fix_factory`` → ``AlwaysSucceed`` (CreateFix p=0.90 → ceiling).
"""

__all__ = [
    "DevelopFixCallOutBundle",
    "DEVELOP_FIX_DETERMINISTIC",
]
