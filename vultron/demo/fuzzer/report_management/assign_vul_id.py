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
    AlwaysSucceed,
    OftenSucceed,
    ProbablySucceed,
    UsuallyFail,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import (
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


class AssignId(AlwaysSucceed):
    """Assign a Vulnerability ID directly to the vulnerability.

    Semantic function:
        Action — record the assignment of a VUL ID (e.g., a CVE ID) to the
        vulnerability.  This node is exercised when the local organization is
        itself an ID assignment authority.  In production this may be an
        automated internal allocation from a pre-reserved ID pool or an API
        call to the local ID management system.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — assignment from a managed ID pool or
    internal tracking system is fully automatable; no human involvement is
    required once the allocation decision is made.
    """


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
