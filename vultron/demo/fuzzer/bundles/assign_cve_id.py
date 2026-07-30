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
"""STOCHASTIC call-out bundle for the CVE ID assignment domain (BT-23).

Provides the simulation-layer :data:`ASSIGN_CVE_ID_STOCHASTIC` singleton.  The
bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.assign_cve_id``) and are re-exported
here for stable import paths.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-23
- Notes: ``notes/bt-fuzzer-rm-id-assignment.md``
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.assign_cve_id import (  # noqa: F401
    ASSIGN_CVE_ID_DETERMINISTIC,
    AssignCveIdCallOutBundle,
)


def _stochastic_id_assigned(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import IdAssigned

    return IdAssigned(name)


def _stochastic_in_scope(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import InScope

    return InScope(name)


def _stochastic_product_in_cna_scope(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        ProductInCNAScope,
    )

    return ProductInCNAScope(name)


def _stochastic_is_most_appropriate_cna(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IsMostAppropriateCNA,
    )

    return IsMostAppropriateCNA(name)


def _stochastic_is_not_malicious_code(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IsNotMaliciousCode,
    )

    return IsNotMaliciousCode(name)


def _stochastic_is_not_dependency_update(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IsNotDependencyUpdate,
    )

    return IsNotDependencyUpdate(name)


def _stochastic_is_not_eol_status_alone(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IsNotEOLStatusAlone,
    )

    return IsNotEOLStatusAlone(name)


def _stochastic_is_not_deliberately_educational(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IsNotDeliberatelyEducational,
    )

    return IsNotDeliberatelyEducational(name)


def _stochastic_is_publicly_available_product(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IsPubliclyAvailableProduct,
    )

    return IsPubliclyAvailableProduct(name)


def _stochastic_no_duplicate_cve(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        NoDuplicateCVE,
    )

    return NoDuplicateCVE(name)


def _stochastic_meets_evidence_bar(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        MeetsEvidenceBar,
    )

    return MeetsEvidenceBar(name)


def _stochastic_is_real_vulnerability(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IsRealVulnerability,
    )

    return IsRealVulnerability(name)


def _stochastic_assign_id(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import AssignId

    return AssignId(name)


def _stochastic_request_id(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.assign_vul_id import RequestId

    return RequestId(name)


ASSIGN_CVE_ID_STOCHASTIC = AssignCveIdCallOutBundle(
    id_assigned_factory=_stochastic_id_assigned,  # type: ignore[arg-type]
    in_scope_factory=_stochastic_in_scope,  # type: ignore[arg-type]
    product_in_cna_scope_factory=_stochastic_product_in_cna_scope,  # type: ignore[arg-type]
    is_most_appropriate_cna_factory=_stochastic_is_most_appropriate_cna,  # type: ignore[arg-type]
    is_not_malicious_code_factory=_stochastic_is_not_malicious_code,  # type: ignore[arg-type]
    is_not_dependency_update_factory=_stochastic_is_not_dependency_update,  # type: ignore[arg-type]
    is_not_eol_status_alone_factory=_stochastic_is_not_eol_status_alone,  # type: ignore[arg-type]
    is_not_deliberately_educational_factory=_stochastic_is_not_deliberately_educational,  # type: ignore[arg-type]
    is_publicly_available_product_factory=_stochastic_is_publicly_available_product,  # type: ignore[arg-type]
    no_duplicate_cve_factory=_stochastic_no_duplicate_cve,  # type: ignore[arg-type]
    meets_evidence_bar_factory=_stochastic_meets_evidence_bar,  # type: ignore[arg-type]
    is_real_vulnerability_factory=_stochastic_is_real_vulnerability,  # type: ignore[arg-type]
    assign_id_factory=_stochastic_assign_id,  # type: ignore[arg-type]
    request_id_factory=_stochastic_request_id,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "AssignCveIdCallOutBundle",
    "ASSIGN_CVE_ID_DETERMINISTIC",
    "ASSIGN_CVE_ID_STOCHASTIC",
]
