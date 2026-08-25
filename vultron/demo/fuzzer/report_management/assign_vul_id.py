#!/usr/bin/env python
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
"""VUL ID assignment fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
VUL ID assignment sub-workflow within Report Management.  Each node represents
an external-dependency touchpoint — a human decision, environmental check, or
system integration hook — that will eventually be replaced by production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 (named integration-point
nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/report_management/fuzzer/assign_vul_id.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
"""

from __future__ import annotations

from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    OftenSucceed,
    ProbablySucceed,
    UsuallyFail,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import (
    ComposerCallOutPoint,
    EvaluatorCallOutPoint,
    RetrieverCallOutPoint,
)


class IdAssigned(RetrieverCallOutPoint, UsuallyFail):
    """Check whether the vulnerability has already been assigned an identity.

    Semantic function:
        Environmental condition — verify that a vulnerability identifier (such
        as a CVE ID) has already been assigned to this vulnerability.  In
        production this is a simple lookup against the case record.  The fuzzer
        models the common case where the workflow has not yet assigned an ID
        (i.e., the condition fails most of the time), so that subsequent
        ID-assignment steps are exercised.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries case record or external ID registry)
      Output keys: (none — binary result only, per BT-18-006)

    Input category: Environmental check.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **High** — the ID assignment status is a structured
    field on the case record; fully automatable via a read from the case
    DataLayer with no human involvement required.
    """


class IdAssignable(EvaluatorCallOutPoint, ProbablySucceed):
    """Check whether the vulnerability qualifies for an ID assignment.

    Semantic function:
        Environmental condition — evaluate whether the vulnerability meets the
        eligibility criteria of the relevant ID-assignment authority.  For
        example, when using CVE ID assignment rules, this checks whether the
        evaluating party is the authoritative CNA for the affected product and
        whether the vulnerability is within that CNA's scope.  A vulnerability
        may be in scope for an ID space yet not assignable by the current
        party.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates vulnerability attributes from caller's DataLayer)
      Output keys: id_assignable_verdict: str  (SUCCESS only)

    Input category: Environmental check.

    Success probability: 0.6667 (``ProbablySucceed``).

    Automation potential: **Medium** — basic eligibility criteria (product
    in scope, CNA authority) can often be checked automatically against
    organizational metadata; edge cases or out-of-scope products may still
    require human review.
    """

    output_keys = {"id_assignable_verdict": str}


class IsIDAssignmentAuthority(OftenSucceed):
    """Check whether the organization is itself an ID assignment authority.

    Semantic function:
        Environmental condition — determine whether the local organization
        holds an assignment authority role (e.g., is a CVE Numbering Authority)
        that allows it to directly assign IDs rather than requesting them from
        an upstream authority.  This is a generic condition and is not specific
        to CVE ID assignment except as an illustrative example.

    Input category: Environmental check.

    Success probability: 0.70 (``OftenSucceed``).

    Automation potential: **High** — the authority role is a static property
    of the organization's metadata; fully automatable as a lookup with no
    human involvement required.
    """


class RequestId(RetrieverCallOutPoint, UsuallySucceed):
    """Request a Vulnerability ID assignment from an external authority.

    Semantic function:
        Action — submit a request for a VUL ID to the applicable assignment
        authority.  For CVE IDs this corresponds to submitting a request to the
        relevant CNA.  In production this step may be automatable via an API
        call, or may involve prompting a human operator to file the request
        manually.

    Blackboard contract (BT-18-001):
      Input keys:  (none — submits request to external ID authority)
      Output keys: assigned_id: str  (SUCCESS only)

    Input category: System integration.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **High** — CNA APIs (e.g., CVE Services API) support
    automated CVE ID reservation; a production implementation could submit the
    request without human intervention in most cases.
    """

    output_keys = {"assigned_id": str}


class AssignId(ComposerCallOutPoint, AlwaysSucceed):
    """Assign a Vulnerability ID directly to the vulnerability.

    Semantic function:
        Action — record the assignment of a VUL ID (e.g., a CVE ID) to the
        vulnerability.  This node is exercised when the local organization is
        itself an ID assignment authority.  In production this may be an
        automated internal allocation from a pre-reserved ID pool or an API
        call to the local ID management system.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: assigned_vul_id: str  (SUCCESS only)

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — assignment from a managed ID pool or
    internal tracking system is fully automatable; no human involvement is
    required once the allocation decision is made.
    """

    output_keys = {"assigned_vul_id": str}


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

    output_keys = {"in_scope_verdict": str}


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

    output_keys = {
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

    output_keys = {
        "is_most_appropriate_cna": bool,
        "is_most_appropriate_cna_rationale": str,
    }


class IsNotMaliciousCode(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Exclusion guard: report is NOT about deliberately malicious code.

    Semantic function:
        Exclusion guard — returns SUCCESS when the vulnerability report is
        not about deliberately malicious code (CNA Operational Rules §4.1.8).
        Placed first in the ``IdAssignable`` sequence as the cheapest guard;
        a clear malicious-code report is detectable from report metadata
        without deep analysis.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report classification from caller's DataLayer)
      Output keys: is_not_malicious_code_verdict: bool  (SUCCESS only)
                   is_not_malicious_code_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — report classification flags are
    available on the blackboard; fully automatable from report metadata.
    """

    output_keys = {
        "is_not_malicious_code_verdict": bool,
        "is_not_malicious_code_rationale": str,
    }


class IsNotDependencyUpdate(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Exclusion guard: report is NOT a dependency update without a security fix.

    Semantic function:
        Exclusion guard — returns SUCCESS when the report is not a pure
        dependency update that carries no security fix (CNA Operational
        Rules §4.1.12).  A dependency update that introduces or fixes a
        security vulnerability is not excluded.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report type flags from caller's DataLayer)
      Output keys: is_not_dependency_update_verdict: bool  (SUCCESS only)
                   is_not_dependency_update_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — report type flags are available on
    the blackboard; fully automatable from report metadata.
    """

    output_keys = {
        "is_not_dependency_update_verdict": bool,
        "is_not_dependency_update_rationale": str,
    }


class IsNotEOLStatusAlone(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Exclusion guard: report is NOT solely about end-of-life status.

    Semantic function:
        Exclusion guard — returns SUCCESS when the report covers more than
        mere end-of-life status (CNA Operational Rules §4.1.13).  Reports
        about vulnerabilities in EOL software are eligible; reports that only
        announce EOL status with no associated security vulnerability are not.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report classification from caller's DataLayer)
      Output keys: is_not_eol_status_alone_verdict: bool  (SUCCESS only)
                   is_not_eol_status_alone_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — report classification flags are
    available on the blackboard; fully automatable from report metadata.
    """

    output_keys = {
        "is_not_eol_status_alone_verdict": bool,
        "is_not_eol_status_alone_rationale": str,
    }


class IsNotDeliberatelyEducational(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Exclusion guard: report is NOT about deliberately educational content.

    Semantic function:
        Exclusion guard — returns SUCCESS when the report is not about content
        created deliberately for educational purposes rather than describing a
        real vulnerability (CNA Operational Rules §4.2.18).

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report metadata from caller's DataLayer)
      Output keys: is_not_deliberately_educational_verdict: bool  (SUCCESS only)
                   is_not_deliberately_educational_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — report metadata flags are available on
    the blackboard; fully automatable from report classification metadata.
    """

    output_keys = {
        "is_not_deliberately_educational_verdict": bool,
        "is_not_deliberately_educational_rationale": str,
    }


class IsPubliclyAvailableProduct(EvaluatorCallOutPoint, UsuallySucceed):
    """Condition: the affected product is publicly available.

    Semantic function:
        Positive condition — returns SUCCESS when the affected product is
        publicly available to users (CNA Operational Rules §4.2.10).  Private
        or internal-only products that will never be publicly released are not
        eligible for CVE assignment.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates product metadata from caller's DataLayer)
      Output keys: is_publicly_available_product_verdict: bool  (SUCCESS only)
                   is_publicly_available_product_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **High** — product availability metadata is on
    the blackboard; fully automatable from product registry lookup.
    """

    output_keys = {
        "is_publicly_available_product_verdict": bool,
        "is_publicly_available_product_rationale": str,
    }


class NoDuplicateCVE(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Condition: no existing CVE already covers this vulnerability.

    Semantic function:
        Deduplication judgment — returns SUCCESS when the CVE corpus does
        not already contain an entry describing this vulnerability
        (CNA Operational Rules §4.2.6, §4.2.15).  Makes a confidence-weighted
        judgment rather than a binary database query, since duplicate detection
        across differently-described vulnerabilities is inherently evaluative.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries CVE corpus via caller's DataLayer)
      Output keys: no_duplicate_cve_verdict: bool  (SUCCESS only)
                   no_duplicate_cve_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — CVE corpus queries are automatable
    via the CVE Services API or local mirrored corpus; confidence scoring
    can automate most deduplication decisions.
    """

    output_keys = {
        "no_duplicate_cve_verdict": bool,
        "no_duplicate_cve_rationale": str,
    }


class MeetsEvidenceBar(EvaluatorCallOutPoint, UsuallySucceed):
    """Condition: the report meets the evidence quality bar for CVE assignment.

    Semantic function:
        Structural completeness evaluation — returns SUCCESS when the report
        provides sufficient evidence and structural completeness to support a
        CVE assignment (CNA Operational Rules §4.2.2.1.1).  Distinct from
        ``IsRealVulnerability``: this node checks whether the evidence
        threshold is met; ``IsRealVulnerability`` makes the holistic judgment
        about whether the described issue is a genuine vulnerability.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report structure from caller's DataLayer)
      Output keys: meets_evidence_bar_verdict: bool  (SUCCESS only)
                   meets_evidence_bar_rationale: str  (SUCCESS only)

    Input category: Environmental check / policy.

    Success probability: 0.80 (``UsuallySucceed`` — uses ``UsuallySucceed``
    ceiling for p=0.80; see BT-23-002).

    Automation potential: **High** — structural field completeness checks
    are fully automatable; evidence threshold thresholds can be configured
    as policy rules.
    """

    output_keys = {
        "meets_evidence_bar_verdict": bool,
        "meets_evidence_bar_rationale": str,
    }


class IsRealVulnerability(EvaluatorCallOutPoint, UsuallySucceed):
    """Holistic judgment: the report describes a genuine vulnerability.

    Semantic function:
        Holistic §4.1 judgment — returns SUCCESS when the report describes
        a genuine vulnerability per CNA Operational Rules §4.1 and §4.4.
        Placed last in the ``IdAssignable`` sequence as the most expensive
        evaluation (may require human review).  Distinct from
        ``MeetsEvidenceBar`` (structural check): a structurally complete
        report can still describe a non-vulnerability.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates full report from caller's DataLayer)
      Output keys: is_real_vul: bool  (SUCCESS only) — placeholder stub pending #1558
                   is_real_vul_rationale: str  (SUCCESS only) — placeholder stub pending #1558

    Input category: Environmental check / human judgment.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **Medium** — well-structured reports with clear
    vulnerability descriptions can be evaluated automatically; novel or
    ambiguous cases may still require human expert judgment.

    Note:
        ``output_keys`` types ``bool`` and ``str`` are placeholder stubs
        pending structured dataclass replacement in issue #1558.
    """

    output_keys = {
        "is_real_vul": bool,
        "is_real_vul_rationale": str,
    }
