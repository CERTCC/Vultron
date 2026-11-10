"""CVE assignment eligibility fuzzer nodes: scope, CNA fit and CVE eligibility."""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from __future__ import annotations

from typing import ClassVar

from vultron.core.behaviors.call_out.bundles.assign_cve_id import (
    CVE_ELIGIBILITY_OUTPUT_KEYS,
)
from vultron.demo.fuzzer.base import (
    ProbablySucceed,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import (
    EvaluatorCallOutPoint,
)


class InScope(EvaluatorCallOutPoint, UsuallySucceed):
    """Check whether the vulnerability is within scope for an ID assignment.

    Semantic function:
        Environmental condition / policy — evaluate whether the vulnerability
        falls within the scope definition governing the relevant ID space.  For
        CVE ID assignment this means checking the CNA scope rules; other ID
        spaces may have different scope definitions.  An ID space that allows
        rapid assignment may have a very broad scope requiring little or no
        explicit scope checking.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates vulnerability attributes from caller's DataLayer)
      Output keys: in_scope_verdict: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **Medium** — scope rules for well-defined ID spaces
    (e.g., CVE scope per product/vendor) can be encoded and checked
    automatically; novel or ambiguous scope boundaries may still require human
    judgment.
    """

    output_keys: ClassVar[dict[str, type]] = {"in_scope_verdict": str}


class ProductInCNAScope(EvaluatorCallOutPoint, UsuallySucceed):
    """Evaluate whether the affected product is within this CNA's scope.

    Semantic function:
        Policy evaluation — check whether the affected product or component
        is listed in this CNA's declared scope (CNA Operational Rules §3.1,
        §4.2.16.1).  Returns SUCCESS when the product falls within scope,
        FAILURE when it does not.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates product attributes from caller's DataLayer)
      Output keys: product_in_cna_scope: bool  (SUCCESS only)
                   product_in_cna_scope_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **High** — CNA scope lists are machine-readable
    (e.g., CVE CNA scope registry); fully automatable via a policy lookup.
    """

    output_keys: ClassVar[dict[str, type]] = {
        "product_in_cna_scope": bool,
        "product_in_cna_scope_rationale": str,
    }


class IsMostAppropriateCNA(EvaluatorCallOutPoint, UsuallySucceed):
    """Evaluate whether this CNA has first-refusal authority for the product.

    Semantic function:
        Policy evaluation — check whether this CNA has first-refusal
        authority for the affected product (CNA Operational Rules §4.2.1.1,
        §4.2.16.6).  Returns SUCCESS when this is the most appropriate CNA,
        FAILURE when a more appropriate (e.g., product-vendor) CNA exists.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates CNA registry from caller's DataLayer)
      Output keys: is_most_appropriate_cna: bool  (SUCCESS only)
                   is_most_appropriate_cna_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **High** — first-refusal registries are
    machine-readable; fully automatable via a CNA hierarchy lookup.
    """

    output_keys: ClassVar[dict[str, type]] = {
        "is_most_appropriate_cna": bool,
        "is_most_appropriate_cna_rationale": str,
    }


class EvaluateCveEligibility(EvaluatorCallOutPoint, ProbablySucceed):
    """Evaluate whether the vulnerability is eligible for a CVE ID.

    Semantic function:
        Policy evaluation — apply every eligibility criterion of the CNA
        Operational Rules reference edition as one unit and return a single
        verdict (BTND-05-007, ADR-0071).  The criteria cover the exclusions
        (deliberately malicious code §4.1.8, a dependency update with no
        security fix §4.1.12, end-of-life status alone §4.1.13, deliberately
        educational content §4.2.18), the positive conditions (a publicly
        available product §4.2.10), the duplicate check (§4.2.6, §4.2.15),
        the evidence bar (§4.2.2.1.1) and the holistic "is this a real
        vulnerability" judgment (§4.1, §4.4).  Returns SUCCESS when the
        vulnerability is eligible, FAILURE when any criterion excludes it
        (BT-18-007).  The publication condition (§4.2.2.1.2) is not part of
        this capability: the tree checks it in the ProtocolInternal
        ``IsOrWillBePubliclyDisclosed`` gate just before this node.

    Reference rules edition: CNA Operational Rules v4.1.0
    (:data:`~vultron.core.behaviors.call_out.bundles.assign_cve_id.CNA_RULES_REFERENCE_EDITION`,
    BTND-05-008).  Adopting a newer edition replaces this capability's
    implementation as a whole; the surrounding tree does not change.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates the report and product from caller's DataLayer)
      Output keys: cve_eligibility_verdict: bool  (SUCCESS only)
                   cve_eligibility_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.6667 (``ProbablySucceed``).

    Automation potential: **Medium** — most criteria are checks against report
    and product metadata or a CVE corpus query, but the holistic "is this a
    real vulnerability" judgment can still need a human for a novel or
    ambiguous report.
    """

    output_keys: ClassVar[dict[str, type]] = dict(CVE_ELIGIBILITY_OUTPUT_KEYS)
