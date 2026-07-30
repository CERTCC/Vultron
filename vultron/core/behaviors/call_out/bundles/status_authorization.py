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
"""Call-out bundle for the received-side status authorization domain (BT-23).

Provides :class:`StatusAuthorizationCallOutBundle` and the pre-built core
DETERMINISTIC singleton :data:`STATUS_AUTHORIZATION_DETERMINISTIC`.  The matching
STOCHASTIC singleton lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.status_authorization.STATUS_AUTHORIZATION_STOCHASTIC`).

The two fields back the two authorization seams of the received-side
CaseStatus canonicalization model (ADR-0046):

- ``status_update_guard_factory`` — Seam 1, the ``CaseOwnerApprovesStatusUpdate``
  Evaluator call-out inside the ``StatusUpdateGuard`` Fallback in
  ``add_participant_status_tree``.  Decides whether a non-owner participant's
  reported CaseStatus is adopted as canonical (RSH-01).
- ``side_effects_guard_factory`` — Seam 2, the ``SideEffectsGuard`` Evaluator
  call-out in ``add_case_status_tree``.  Gates execution of
  ``ThreatTerminationBranchNode`` (embargo teardown) after the canonical write
  (RSH-02).

Ceiling/floor mapping (BT-23-002):

- ``status_update_guard_factory`` — CaseOwnerApprovesStatusUpdate → AlwaysSucceed
  (all status updates adopted automatically until a real policy engine is wired
  in; RSH-01-002)
- ``side_effects_guard_factory``  — SideEffectsGuard → AlwaysSucceed
  (teardown side-effects execute by default; RSH-02-002)

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- ADR-0046: ``docs/adr/0046-received-status-authorization.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-23;
  ``specs/received-status-handling.yaml`` RSH-01, RSH-02
- Notes: ``notes/received-status-authorization.md``,
  ``notes/call-out-configuration.md``
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


@dataclass(frozen=True)
class StatusAuthorizationCallOutBundle:
    """Call-out backend bundle for the received-side status authorization domain.

    Fields map to the two authorization seams of ADR-0046:

    - ``status_update_guard_factory`` → the ``CaseOwnerApprovesStatusUpdate``
      Evaluator call-out in
      :func:`~vultron.core.behaviors.status.add_participant_status_tree.add_participant_status_tree`
      (Seam 1).
    - ``side_effects_guard_factory`` → the ``SideEffectsGuard`` Evaluator
      call-out in
      :func:`~vultron.core.behaviors.status.add_case_status_tree.add_case_status_tree`
      (Seam 2).

    Both default to ``AlwaysSucceed`` so existing behavior is unchanged until a
    real policy engine or human-in-the-loop backend is injected (BT-23-002).
    """

    status_update_guard_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    side_effects_guard_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


STATUS_AUTHORIZATION_DETERMINISTIC = StatusAuthorizationCallOutBundle()
"""Deterministic bundle: both seams use AlwaysSucceed (BT-23-001, BT-23-002)."""

__all__ = [
    "StatusAuthorizationCallOutBundle",
    "STATUS_AUTHORIZATION_DETERMINISTIC",
]
