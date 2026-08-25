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

Provides :class:`AssignCveIdCallOutBundle` (14 factory fields, one per
call-out point excluding the two ProtocolInternal nodes) and the pre-built
core DETERMINISTIC singleton :data:`ASSIGN_CVE_ID_DETERMINISTIC`.

The matching STOCHASTIC singleton lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.assign_cve_id.ASSIGN_CVE_ID_STOCHASTIC`).

Ceiling/floor mapping (BT-23-002, p→deterministic):

- ``id_assigned_factory``                     — p=0.25 → AlwaysFail
- ``in_scope_factory``                        — p=0.75 → AlwaysSucceed
- ``product_in_cna_scope_factory``            — p=0.75 → AlwaysSucceed
- ``is_most_appropriate_cna_factory``         — p=0.75 → AlwaysSucceed
- ``is_not_malicious_code_factory``           — p=0.90 → AlwaysSucceed
- ``is_not_dependency_update_factory``        — p=0.90 → AlwaysSucceed
- ``is_not_eol_status_alone_factory``         — p=0.90 → AlwaysSucceed
- ``is_not_deliberately_educational_factory`` — p=0.90 → AlwaysSucceed
- ``is_publicly_available_product_factory``   — p=0.80 → AlwaysSucceed
- ``no_duplicate_cve_factory``                — p=0.90 → AlwaysSucceed
- ``meets_evidence_bar_factory``              — p=0.80 → AlwaysSucceed
- ``is_real_vulnerability_factory``           — p=0.75 → AlwaysSucceed
- ``assign_id_factory``                       — p=1.00 → AlwaysSucceed
- ``request_id_factory``                      — p=0.75 → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysFail(name)


@dataclass(frozen=True)
class AssignCveIdCallOutBundle:
    """Call-out backend bundle for the CVE ID assignment domain (BT-23-003).

    14 factory fields, one per call-out point (excluding the two ProtocolInternal
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

    # -- IdAssignable subtree Evaluators (cheapest-first order) --------------
    is_not_malicious_code_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """IsNotMaliciousCode: p=0.90 → AlwaysSucceed."""

    is_not_dependency_update_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """IsNotDependencyUpdate: p=0.90 → AlwaysSucceed."""

    is_not_eol_status_alone_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """IsNotEOLStatusAlone: p=0.90 → AlwaysSucceed."""

    is_not_deliberately_educational_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """IsNotDeliberatelyEducational: p=0.90 → AlwaysSucceed."""

    is_publicly_available_product_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """IsPubliclyAvailableProduct: p=0.80 → AlwaysSucceed."""

    no_duplicate_cve_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """NoDuplicateCVE: p=0.90 → AlwaysSucceed."""

    meets_evidence_bar_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """MeetsEvidenceBar: p=0.80 → AlwaysSucceed."""

    is_real_vulnerability_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    """IsRealVulnerability: p=0.75 → AlwaysSucceed."""

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
"""Deterministic bundle: factories use AlwaysSucceed/AlwaysFail (BT-23-001, BT-23-002)."""

__all__ = [
    "AssignCveIdCallOutBundle",
    "ASSIGN_CVE_ID_DETERMINISTIC",
]
