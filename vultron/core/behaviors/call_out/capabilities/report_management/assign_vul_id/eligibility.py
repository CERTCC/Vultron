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
"""Core capability declarations for ``report_management.assign_vul_id.eligibility``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.assign_vul_id.eligibility``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from typing import Final

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    EvaluatorCapability,
)

#: Blackboard key for the ``EvaluateCveEligibility`` verdict (``bool``).
CVE_ELIGIBILITY_VERDICT_KEY: Final[str] = "cve_eligibility_verdict"

#: Blackboard key for the ``EvaluateCveEligibility`` rationale (``str``).
CVE_ELIGIBILITY_RATIONALE_KEY: Final[str] = "cve_eligibility_rationale"


class InScopeCapability(EvaluatorCapability):
    """Check whether the vulnerability is within scope for an ID assignment.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates vulnerability attributes from caller's DataLayer)
      Output keys: in_scope_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "in_scope_verdict": PortInformation(data_type=str, required=True),
    }


class ProductInCNAScopeCapability(EvaluatorCapability):
    """Evaluate whether the affected product is within this CNA's scope.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates product attributes from caller's DataLayer)
      Output keys: product_in_cna_scope: bool  (yes only)
                   product_in_cna_scope_rationale: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "product_in_cna_scope": PortInformation(data_type=bool, required=True),
        "product_in_cna_scope_rationale": PortInformation(
            data_type=str, required=True
        ),
    }


class IsMostAppropriateCNACapability(EvaluatorCapability):
    """Evaluate whether this CNA has first-refusal authority for the product.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates CNA registry from caller's DataLayer)
      Output keys: is_most_appropriate_cna: bool  (yes only)
                   is_most_appropriate_cna_rationale: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "is_most_appropriate_cna": PortInformation(
            data_type=bool, required=True
        ),
        "is_most_appropriate_cna_rationale": PortInformation(
            data_type=str, required=True
        ),
    }


class EvaluateCveEligibilityCapability(EvaluatorCapability):
    """Evaluate whether the vulnerability is eligible for a CVE ID.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates the report and product from caller's DataLayer)
      Output keys: cve_eligibility_verdict: bool  (yes only)
                   cve_eligibility_rationale: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        CVE_ELIGIBILITY_VERDICT_KEY: PortInformation(
            data_type=bool, required=True
        ),
        CVE_ELIGIBILITY_RATIONALE_KEY: PortInformation(
            data_type=str, required=True
        ),
    }


__all__ = [
    "CVE_ELIGIBILITY_RATIONALE_KEY",
    "CVE_ELIGIBILITY_VERDICT_KEY",
    "EvaluateCveEligibilityCapability",
    "InScopeCapability",
    "IsMostAppropriateCNACapability",
    "ProductInCNAScopeCapability",
]
