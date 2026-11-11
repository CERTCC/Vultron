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

Provides :class:`AssignCveIdCallOutBundle` (7 factory fields, one per
call-out point excluding the two ProtocolInternal nodes) and the pre-built
core DETERMINISTIC singleton :data:`ASSIGN_CVE_ID_DETERMINISTIC`.

The matching STOCHASTIC singleton lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.assign_cve_id.ASSIGN_CVE_ID_STOCHASTIC`).

CVE eligibility is one call-out unit (BTND-05-007): a single
``EvaluateCveEligibility`` Evaluator applies the eligibility criteria of the
CNA Operational Rules reference edition :data:`CNA_RULES_REFERENCE_EDITION`
(BTND-05-008, ADR-0071) and returns one verdict.  The scope and CNA-fit
checks and the publication condition stay separate nodes in the tree.
Adopting a newer edition replaces ``evaluate_cve_eligibility_factory`` and
nothing else in the tree.

Ceiling/floor mapping (BT-23-002, p→deterministic):

- ``id_assigned_factory``              — p=0.25 → AlwaysFail
- ``in_scope_factory``                 — p=0.75 → AlwaysSucceed
- ``product_in_cna_scope_factory``     — p=0.75 → AlwaysSucceed
- ``is_most_appropriate_cna_factory``  — p=0.75 → AlwaysSucceed
- ``evaluate_cve_eligibility_factory`` — p=0.67 → DeterministicEvaluateCveEligibility
  (answers *yes* with its declared outputs, BT-23-013)
- ``assign_id_factory``                — p=1.00 → AlwaysSucceed
- ``request_id_factory``               — p=0.75 → AlwaysSucceed
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar, Final

import py_trees

from vultron.core.behaviors.call_out.answer import (
    CallOutAnswer,
    CallOutContract,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
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

#: Output keys every ``EvaluateCveEligibility`` backend gives on *yes*
#: (BT-18-001, BT-18-002).
CVE_ELIGIBILITY_OUTPUT_KEYS: Final[Mapping[str, type]] = MappingProxyType(
    {
        CVE_ELIGIBILITY_VERDICT_KEY: bool,
        CVE_ELIGIBILITY_RATIONALE_KEY: str,
    }
)

#: The ``EvaluateCveEligibility`` capability declaration (ADR-0183).  The
#: simulation node binds to it rather than restating it.
CVE_ELIGIBILITY_CONTRACT: Final[CallOutContract] = CallOutContract(
    outputs=CVE_ELIGIBILITY_OUTPUT_KEYS
)


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysFail(name)


class DeterministicEvaluateCveEligibility(CallOutBackend):
    """DETERMINISTIC ``EvaluateCveEligibility``: always eligible, outputs given.

    The core ceiling backend for ``evaluate_cve_eligibility_factory``
    (BT-23-002).  It answers *yes*, reporting the vulnerability eligible for a
    CVE ID under CNA Operational Rules :data:`CNA_RULES_REFERENCE_EDITION`,
    and, because the capability declares output ports, carries both of them
    rather than a bare *yes* (BT-23-013).  The seam writes them.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates the report from the caller's DataLayer)
      Output keys: cve_eligibility_verdict: bool  (yes only)
                   cve_eligibility_rationale: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Reference rules edition: CNA Operational Rules v4.1.0 (BTND-05-008).
    """

    #: Read-only rate interface parity with the simulation backends.
    success_rate: float = 1.0

    contract: ClassVar[CallOutContract] = CVE_ELIGIBILITY_CONTRACT

    def answer(self) -> CallOutAnswer:
        return CallOutAnswer.yes(
            {
                CVE_ELIGIBILITY_VERDICT_KEY: True,
                CVE_ELIGIBILITY_RATIONALE_KEY: (
                    "DETERMINISTIC default: eligible under CNA Operational "
                    f"Rules v{CNA_RULES_REFERENCE_EDITION}"
                ),
            }
        )


def _deterministic_evaluate_cve_eligibility(
    name: str,
) -> py_trees.behaviour.Behaviour:
    return DeterministicEvaluateCveEligibility(name)


@dataclass(frozen=True)
class AssignCveIdCallOutBundle(CallOutBundle):
    """Call-out backend bundle for the CVE ID assignment domain (BT-23-003).

    7 factory fields, one per call-out point (excluding the two ProtocolInternal
    nodes ``IsIDAssignmentAuthority`` and ``IsOrWillBePubliclyDisclosed`` which
    are constructed inline by the tree builder).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`.
    """

    # -- Early-exit Retriever ------------------------------------------------
    id_assigned_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    """IdAssigned: p=0.25 → AlwaysFail (deterministic: ID not yet assigned).

    Store-held answer (BT-18-039): **cannot**.  The case file has no field
    for an assigned identifier, and a ``VulnerabilityItem`` in the actor's
    store names no case, so no read-first guard precedes this Retriever.  The
    ``ids`` a ``ReportClaimsRecord`` lists are what a sender's attached
    document claims, not an assignment, so they do not answer it either.
    """

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

    Applies the CNA Operational Rules v4.1.0 eligibility criteria as a unit
    (BTND-05-008), apart from the publication condition the tree checks just
    before it, and gives ``cve_eligibility_verdict`` and
    ``cve_eligibility_rationale`` on *yes*.
    """

    # -- Composer and Retriever action nodes ---------------------------------
    assign_id_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """AssignId: p=1.00 → AlwaysSucceed."""

    request_id_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """RequestId (Retriever): p=0.75 → AlwaysSucceed.

    Store-held answer (BT-18-039): **cannot**.  It asks an outside authority
    for a new identifier, which nothing in the case file or the actor's store
    holds before the answer, so no read-first guard precedes this Retriever.
    """


ASSIGN_CVE_ID_DETERMINISTIC = AssignCveIdCallOutBundle()
"""Deterministic bundle (BT-23-001, BT-23-002, BT-23-013).

AlwaysSucceed/AlwaysFail by ceiling/floor, plus the output-writing
eligibility default.
"""

__all__ = [
    "ASSIGN_CVE_ID_DETERMINISTIC",
    "AssignCveIdCallOutBundle",
    "CNA_RULES_REFERENCE_EDITION",
    "CVE_ELIGIBILITY_CONTRACT",
    "CVE_ELIGIBILITY_OUTPUT_KEYS",
    "CVE_ELIGIBILITY_RATIONALE_KEY",
    "CVE_ELIGIBILITY_VERDICT_KEY",
    "DeterministicEvaluateCveEligibility",
]
