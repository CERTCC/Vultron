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
"""Call-out bundle for the CVE ID assignment domain (BT-23-003, BT-23-005).

Provides :class:`AssignCveIdCallOutBundle` (6 factory fields, one per
call-out point excluding the two ProtocolInternal nodes) and the pre-built
core DETERMINISTIC singleton :data:`ASSIGN_CVE_ID_DETERMINISTIC`.

The matching STOCHASTIC singleton lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.assign_cve_id.ASSIGN_CVE_ID_STOCHASTIC`).

CVE eligibility is one call-out unit (BTND-05-007): a single
``EvaluateCveEligibility`` Evaluator applies every CNA Operational Rules
criterion of the reference edition :data:`CNA_RULES_REFERENCE_EDITION`
(BTND-05-008, ADR-0071) and returns one verdict.  Adopting a newer edition
replaces ``evaluate_cve_eligibility_factory`` and nothing else in the tree.

Ceiling/floor mapping (BT-23-002, p→deterministic):

- ``id_assigned_factory``              — p=0.25 → AlwaysFail
- ``in_scope_factory``                 — p=0.75 → AlwaysSucceed
- ``product_in_cna_scope_factory``     — p=0.75 → AlwaysSucceed
- ``is_most_appropriate_cna_factory``  — p=0.75 → AlwaysSucceed
- ``evaluate_cve_eligibility_factory`` — p=0.67 → DeterministicEvaluateCveEligibility
  (succeeds and writes its declared outputs, BT-23-013)
- ``assign_id_factory``                — p=1.00 → AlwaysSucceed
- ``request_id_factory``               — p=0.75 → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Final

import py_trees
from py_trees.common import Access, Status

from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory

#: CNA Operational Rules edition the reference ``EvaluateCveEligibility``
#: backends apply (BTND-05-008, ADR-0071).  Adopting a newer edition means
#: updating this value, the spec, and the implementing factory together.
CNA_RULES_REFERENCE_EDITION: Final[str] = "4.1.0"

#: Blackboard key for the ``EvaluateCveEligibility`` verdict (``bool``).
CVE_ELIGIBILITY_VERDICT_KEY: Final[str] = "cve_eligibility_verdict"

#: Blackboard key for the ``EvaluateCveEligibility`` rationale (``str``).
CVE_ELIGIBILITY_RATIONALE_KEY: Final[str] = "cve_eligibility_rationale"

#: Output keys every ``EvaluateCveEligibility`` backend writes on SUCCESS
#: (BT-18-001, BT-18-002).  The simulation node binds to this mapping rather
#: than restating it.
CVE_ELIGIBILITY_OUTPUT_KEYS: Final[dict[str, type]] = {
    CVE_ELIGIBILITY_VERDICT_KEY: bool,
    CVE_ELIGIBILITY_RATIONALE_KEY: str,
}


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysFail(name)


class DeterministicEvaluateCveEligibility(AlwaysSucceed):
    """DETERMINISTIC ``EvaluateCveEligibility``: always eligible, outputs written.

    The core ceiling backend for ``evaluate_cve_eligibility_factory``
    (BT-23-002).  It reports the vulnerability eligible for a CVE ID under
    CNA Operational Rules :data:`CNA_RULES_REFERENCE_EDITION` and, because the
    capability declares output keys, writes both of them on SUCCESS rather than
    returning a bare SUCCESS (BT-23-013).

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates the report from the caller's DataLayer)
      Output keys: cve_eligibility_verdict: bool  (SUCCESS only)
                   cve_eligibility_rationale: str  (SUCCESS only)

    Reference rules edition: CNA Operational Rules v4.1.0 (BTND-05-008).
    """

    #: BT-18-001: declared output keys written on SUCCESS.
    output_keys: ClassVar[dict[str, type]] = CVE_ELIGIBILITY_OUTPUT_KEYS

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self._eligibility_bb = self.attach_blackboard_client(
            name=f"{self.__class__.__name__}_writer"
        )
        for key in self.output_keys:
            self._eligibility_bb.register_key(key, Access.WRITE)

    def update(self) -> Status:
        status = super().update()
        if status == Status.SUCCESS:
            setattr(self._eligibility_bb, CVE_ELIGIBILITY_VERDICT_KEY, True)
            setattr(
                self._eligibility_bb,
                CVE_ELIGIBILITY_RATIONALE_KEY,
                "DETERMINISTIC default: eligible under CNA Operational Rules "
                f"v{CNA_RULES_REFERENCE_EDITION}",
            )
        return status


def _deterministic_evaluate_cve_eligibility(
    name: str,
) -> py_trees.behaviour.Behaviour:
    return DeterministicEvaluateCveEligibility(name)


@dataclass(frozen=True)
class AssignCveIdCallOutBundle(CallOutBundle):
    """Call-out backend bundle for the CVE ID assignment domain (BT-23-003).

    6 factory fields, one per call-out point (excluding the two ProtocolInternal
    nodes ``IsIDAssignmentAuthority`` and ``IsOrWillBePubliclyDisclosed`` which
    are constructed inline by the tree builder).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`.
    """

    # -- Early-exit Retriever ------------------------------------------------
    id_assigned_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    """IdAssigned: p=0.25 → AlwaysFail (deterministic: ID not yet assigned)."""

    # -- InScope Evaluator ---------------------------------------------------
    in_scope_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """InScope: p=0.75 → AlwaysSucceed."""

    # -- Authority-gate Evaluators -------------------------------------------
    product_in_cna_scope_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """ProductInCNAScope: p=0.75 → AlwaysSucceed."""

    is_most_appropriate_cna_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """IsMostAppropriateCNA: p=0.75 → AlwaysSucceed."""

    # -- CVE eligibility Evaluator (one call-out unit, BTND-05-007) ---------
    evaluate_cve_eligibility_factory: CallOutBackendFactory = field(
        default=_deterministic_evaluate_cve_eligibility  # type: ignore[assignment]
    )
    """EvaluateCveEligibility: p=0.67 → DeterministicEvaluateCveEligibility.

    Applies every CNA Operational Rules v4.1.0 eligibility criterion as a unit
    (BTND-05-008) and writes ``cve_eligibility_verdict`` and
    ``cve_eligibility_rationale`` on SUCCESS.
    """

    # -- Composer and Retriever action nodes ---------------------------------
    assign_id_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """AssignId: p=1.00 → AlwaysSucceed."""

    request_id_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """RequestId: p=0.75 → AlwaysSucceed."""


ASSIGN_CVE_ID_DETERMINISTIC = AssignCveIdCallOutBundle()
"""Deterministic bundle: AlwaysSucceed/AlwaysFail by ceiling/floor (BT-23-001, BT-23-002), with the output-writing eligibility default (BT-23-013)."""

__all__ = [
    "ASSIGN_CVE_ID_DETERMINISTIC",
    "AssignCveIdCallOutBundle",
    "CNA_RULES_REFERENCE_EDITION",
    "CVE_ELIGIBILITY_OUTPUT_KEYS",
    "CVE_ELIGIBILITY_RATIONALE_KEY",
    "CVE_ELIGIBILITY_VERDICT_KEY",
    "DeterministicEvaluateCveEligibility",
]
