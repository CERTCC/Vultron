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

Provides :class:`StatusAuthorizationCallOutBundle` and the two pre-built core
singletons:

- :data:`STATUS_AUTHORIZATION_DETERMINISTIC` — conservative default; both gates
  use :class:`~vultron.core.behaviors.call_out.nodes.RequireCaseOwnerApprovalNode`
  (ADR-0076, RSH-07-001, RSH-07-002).
- :data:`STATUS_AUTHORIZATION_PERMISSIVE` — explicit override for demos and
  trusted-participant deployments; both gates use ``AlwaysSucceed`` (RSH-07-003).

The matching STOCHASTIC singleton lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.status_authorization.STATUS_AUTHORIZATION_STOCHASTIC`).

The two fields back the two authorization gates of the received-side
CaseStatus canonicalization model (ADR-0046):

- ``status_adoption_gate_factory`` — StatusAdoptionGate, the ``CaseOwnerApprovesStatusUpdate``
  Evaluator call-out inside the ``StatusAdoptionGate`` Fallback in
  ``add_participant_status_tree``.  Decides whether a non-owner participant's
  reported CaseStatus is adopted as canonical (RSH-01).
- ``embargo_teardown_authorization_gate_factory`` — EmbargoTeardownAuthorizationGate, the ``EmbargoTeardownAuthorizationGate`` Evaluator
  call-out in ``add_case_status_tree``.  Gates execution of
  ``ThreatTerminationBranchNode`` (embargo teardown) after the canonical write
  (RSH-02).

Security-significant gate exception (ADR-0076): both gates control unilateral
state change, so the DETERMINISTIC default MUST be ``RequireCaseOwnerApproval``
(most restrictive), not ``AlwaysSucceed``.  Permissive behavior requires an
explicit ``STATUS_AUTHORIZATION_PERMISSIVE`` override (RSH-07-003).

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- ADR-0046: ``docs/adr/0046-received-status-authorization.md``
- ADR-0076: ``docs/adr/0076-security-significant-gates-default-require-case-owner-approval.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-23;
  ``specs/received-status-handling.yaml`` RSH-01, RSH-02, RSH-07
- Notes: ``notes/received-status-authorization.md``,
  ``notes/call-out-configuration.md``
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import (
    AlwaysSucceed,
    RequireCaseOwnerApprovalNode,
)
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


def _require_case_owner_approval(name: str) -> py_trees.behaviour.Behaviour:
    return RequireCaseOwnerApprovalNode(name)


@dataclass(frozen=True)
class StatusAuthorizationCallOutBundle:
    """Call-out backend bundle for the received-side status authorization domain.

    Fields map to the two authorization gates of ADR-0046:

    - ``status_adoption_gate_factory`` → the ``CaseOwnerApprovesStatusUpdate``
      Evaluator call-out in
      :func:`~vultron.core.behaviors.status.add_participant_status_tree.add_participant_status_tree`
      (StatusAdoptionGate).
    - ``embargo_teardown_authorization_gate_factory`` → the ``EmbargoTeardownAuthorizationGate`` Evaluator
      call-out in
      :func:`~vultron.core.behaviors.status.add_case_status_tree.add_case_status_tree`
      (EmbargoTeardownAuthorizationGate).

    Both default to ``RequireCaseOwnerApprovalNode`` (conservative: blocks
    until Case Owner approves).  Use :data:`STATUS_AUTHORIZATION_PERMISSIVE`
    for demos and trusted-participant deployments (RSH-07-003, ADR-0076).
    """

    status_adoption_gate_factory: CallOutBackendFactory = field(
        default=_require_case_owner_approval  # type: ignore[assignment]
    )
    embargo_teardown_authorization_gate_factory: CallOutBackendFactory = field(
        default=_require_case_owner_approval  # type: ignore[assignment]
    )


STATUS_AUTHORIZATION_DETERMINISTIC = StatusAuthorizationCallOutBundle()
"""Conservative deterministic bundle: both seams use RequireCaseOwnerApprovalNode (ADR-0076, RSH-07-001, RSH-07-002)."""

STATUS_AUTHORIZATION_PERMISSIVE = StatusAuthorizationCallOutBundle(
    status_adoption_gate_factory=_always_succeed,  # type: ignore[arg-type]
    embargo_teardown_authorization_gate_factory=_always_succeed,  # type: ignore[arg-type]
)
"""Permissive bundle: both seams use AlwaysSucceed.

MUST be explicitly configured — never the default (RSH-07-003, ADR-0076).
Suitable for demos and trusted-participant deployments only.
"""

__all__ = [
    "StatusAuthorizationCallOutBundle",
    "STATUS_AUTHORIZATION_DETERMINISTIC",
    "STATUS_AUTHORIZATION_PERMISSIVE",
]
