"""VUL ID lookup, request and assignment fuzzer nodes."""

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

from vultron.core.behaviors.call_out.answer import (
    CallOutContract,
)
from vultron.demo.fuzzer.base import (
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
        production this is a lookup against an external ID registry, such as
        the CVE database.  The fuzzer models the common case where the
        workflow has not yet assigned an ID (i.e., the condition fails most of
        the time), so that subsequent ID-assignment steps are exercised.

    Store-held answer (BT-18-039): **cannot** — the case file has no field
    for an assigned identifier, so no read-first guard precedes it (see
    ``AssignCveIdCallOutBundle.id_assigned_factory``).

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries an external ID registry)
      Output keys: (none — binary result only, per BT-18-006)

    Input category: Environmental check.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **High** — a registry lookup is fully automatable
    with no human involvement required.
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
      Output keys: id_assignable_verdict: str  (yes only)

    Input category: Environmental check.

    Success probability: 0.6667 (``ProbablySucceed``).

    Automation potential: **Medium** — basic eligibility criteria (product
    in scope, CNA authority) can often be checked automatically against
    organizational metadata; edge cases or out-of-scope products may still
    require human review.
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"id_assignable_verdict": str}
    )


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

    Store-held answer (BT-18-039): **cannot** — it asks an outside
    authority for a new identifier, which nothing in the case file or the
    actor's store holds before the answer.

    Blackboard contract (BT-18-001):
      Input keys:  (none — submits request to external ID authority)
      Output keys: assigned_id: str  (yes only)

    Input category: System integration.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **High** — CNA APIs (e.g., CVE Services API) support
    automated CVE ID reservation; a production implementation could submit the
    request without human intervention in most cases.
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"assigned_id": str}
    )


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
      Output keys: assigned_vul_id: str  (yes only)

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — assignment from a managed ID pool or
    internal tracking system is fully automatable; no human involvement is
    required once the allocation decision is made.
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"assigned_vul_id": str}
    )
