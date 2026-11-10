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
"""Report validation fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
Report Management validation workflow (``RMValidateBt``).  Each node
represents an external-dependency touchpoint — a human decision,
environmental check, or system integration hook — that will eventually be
replaced by production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 and BT-16-007 (named
integration-point nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/report_management/fuzzer/validate_report.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Catalog: ``docs/developer/reference/bt-fuzzer/rm-validation.md``
"""

from __future__ import annotations

from typing import ClassVar

from vultron.core.behaviors.call_out.answer import (
    CallOutContract,
)
from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    ProbablySucceed,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import (
    EvaluatorCallOutPoint,
    RetrieverCallOutPoint,
)


class NoNewValidationInfo(RetrieverCallOutPoint, ProbablySucceed):
    """Check whether any new information has arrived that should trigger
    re-evaluation of the report's validity.

    Semantic function:
        Condition — ask the sources of validation-relevant information
        (reporter follow-up, credibility updates, threat intelligence)
        whether anything new has arrived that should trigger re-evaluation
        of the report's validity.  In most cases there will be no new
        information, so this condition succeeds, avoiding redundant
        re-evaluation loops.  A binary Retriever: the tree asks on its own
        tick, so this is a call-out, not a Sentinel (BT-18-006, BT-18-013).

    Store-held answer (BT-18-039): **cannot** — whether new information
    reached the outside sources since the last evaluation is not recorded
    in the case file or the actor's store.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries validation-relevant information sources)
      Output keys: (none — binary result only, per BT-18-006)

    Input category: Environmental check.

    Success probability: 0.67 (``ProbablySucceed``).

    Automation potential: **High** — event subscription on the case
    record or metadata timestamp comparison; fully automatable.
    """


class EvaluateReportCredibility(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Assess whether the report's source and content are credible.

    Semantic function:
        Condition — assess whether the report's source and content are
        credible (i.e., likely to describe a real vulnerability).
        Credibility criteria may include reporter reputation, technical
        plausibility, and SSVC exploitation status.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report context from caller's DataLayer)
      Output keys: report_credibility_verdict: str  (yes only)

    Input category: Human decision.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium** — SSVC exploitation status, reporter
    reputation scoring, and technical plausibility checks can be
    partially automated; final credibility determination typically
    requires human analyst review.
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"report_credibility_verdict": str}
    )


class EvaluateReportValidity(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Assess whether the report is valid for this organization's scope.

    Semantic function:
        Condition — assess whether the report is valid for this
        organization's scope (credible AND meeting org-specific
        acceptance criteria).  A report can be credible but out of
        scope; validity is contextual and role-dependent.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report context from caller's DataLayer)
      Output keys: report_validity_verdict: str  (yes only)

    Input category: Human decision.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium** — scope checks against well-defined
    CNA/charter rules are automatable; organizational-context validity
    judgment often requires human review.
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"report_validity_verdict": str}
    )


class EnoughValidationInfo(UsuallySucceed):
    """Determine whether sufficient information is available to validate.

    Semantic function:
        Condition — determine whether sufficient information is available
        to reach a validation decision.  Sufficient information is the
        normal case; absence triggers a gathering phase.

    Input category: Human decision / Environmental check.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **Medium** — completeness check against
    required fields or evidence criteria can be automated; the
    sufficiency threshold for a final decision often involves human
    judgment.
    """


class GatherValidationInfo(RetrieverCallOutPoint, AlmostAlwaysSucceed):
    """Request or collect additional information needed to validate.

    Semantic function:
        Action — request or collect additional information needed to
        validate the report (e.g., reproduction steps, affected
        versions, proof-of-concept).  Succeeds most of the time in
        simulation to keep the workflow progressing.

    Store-held answer (BT-18-039): **cannot** — it collects outside
    information, such as reproduction steps, that the case file does not
    record.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries external source / reporter directly)
      Output keys: validation_info_gathered: str  (yes only)

    Input category: System integration / Human analyst outreach.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Low–Medium** — structured intake form
    follow-ups and automated case-update requests are partially
    automatable; direct reporter outreach typically requires human
    involvement.
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"validation_info_gathered": str}
    )
