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
"""STOCHASTIC call-out bundle for the status authorization domain (BT-23).

Provides the simulation-layer :data:`STATUS_AUTHORIZATION_STOCHASTIC` singleton.
The bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.status_authorization``) and are
re-exported here for backward-compatible import paths.

Unlike the report-management domains, the two-seam status authorization pattern
(ADR-0046) is production-only and has **no named simulator fuzzer nodes** to
wire.  Both seams are approval-style Evaluator call-outs, so the STOCHASTIC
singleton uses the generic ``AlmostAlwaysSucceed`` (p=0.90) ``WeightedBehavior``
from ``vultron.demo.fuzzer.base`` — matching the p=0.90 convention used by the
other Evaluator call-outs (report credibility/validity) and occasionally
exercising the reject/block path during fuzz runs.  The DETERMINISTIC ceiling of
p=0.90 is ``AlwaysSucceed`` (BT-23-002).
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.status_authorization import (  # noqa: F401
    STATUS_AUTHORIZATION_DETERMINISTIC,
    STATUS_AUTHORIZATION_PERMISSIVE,
    StatusAuthorizationCallOutBundle,
)


def _stochastic_status_adoption_gate(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlmostAlwaysSucceed

    return AlmostAlwaysSucceed(name)


def _stochastic_embargo_teardown_authorization_gate(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlmostAlwaysSucceed

    return AlmostAlwaysSucceed(name)


STATUS_AUTHORIZATION_STOCHASTIC = StatusAuthorizationCallOutBundle(
    status_adoption_gate_factory=_stochastic_status_adoption_gate,  # type: ignore[arg-type]
    embargo_teardown_authorization_gate_factory=_stochastic_embargo_teardown_authorization_gate,  # type: ignore[arg-type]
)
"""Stochastic bundle: both gates use AlmostAlwaysSucceed (p=0.90)."""

__all__ = [
    "StatusAuthorizationCallOutBundle",
    "STATUS_AUTHORIZATION_DETERMINISTIC",
    "STATUS_AUTHORIZATION_PERMISSIVE",
    "STATUS_AUTHORIZATION_STOCHASTIC",
]
