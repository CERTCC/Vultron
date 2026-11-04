"""Embargo proposal, inbound-response and active-embargo evaluation fuzzer nodes."""

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

from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import (
    ActuatorCallOutPoint,
    EvaluatorCallOutPoint,
)

# ---------------------------------------------------------------------------
# Embargo proposal evaluation nodes
# ---------------------------------------------------------------------------


class EvaluateEmbargoProposal(EvaluatorCallOutPoint, UsuallySucceed):
    """Assess an incoming embargo proposal and decide whether to accept it.

    Semantic function:
        Condition/action — review the proposed terms and determine whether
        they are acceptable.  In production may involve automated policy
        compatibility checks or structured human analyst review.  Modeled
        as usually succeeding (acceptance is the common outcome).

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates incoming proposal from caller's DataLayer)
      Output keys: evaluate_embargo_proposal_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **Medium** — basic compatibility check (is the
    proposed duration within policy bounds?) is automatable; final
    accept/reject for out-of-range proposals typically needs human review.
    """

    output_keys: ClassVar[dict[str, type]] = {
        "evaluate_embargo_proposal_verdict": str
    }


class OnEmbargoAccept(ActuatorCallOutPoint, AlwaysSucceed):
    """Execute site-specific tasks when an embargo proposal is accepted.

    Semantic function:
        Action integration hook — notify stakeholders, record the
        agreement, and start the embargo timer when the proposal is
        accepted.  Must be idempotent in production.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; proposal context from construction time)
      Output keys: (none — side effect: notify stakeholders, initialize embargo timer)

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — notification dispatch, timer
    initialization, and state-update actions are fully automatable via
    APIs.
    """


class OnEmbargoReject(ActuatorCallOutPoint, AlwaysSucceed):
    """Execute site-specific tasks when an embargo proposal is rejected.

    Semantic function:
        Action integration hook — notify stakeholders and log the
        rejection rationale when the proposal is not accepted.  Must be
        idempotent in production.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; proposal context from construction time)
      Output keys: (none — side effect: notify stakeholders, log rejection)

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — notification dispatch and logging
    actions are fully automatable via APIs.
    """


# ---------------------------------------------------------------------------
# Inbound embargo-response decision nodes (EMB-15)
# ---------------------------------------------------------------------------


class CaseOwnerApprovesEmbargoResponse(EvaluatorCallOutPoint, AlwaysSucceed):
    """Adjudication call-out: non-owner actor requests CASE_OWNER approval.

    Semantic function:
        Condition — a non-CASE_OWNER actor (e.g. a CaseActor processing an
        inbound overture on the owner's behalf) requests authorization from the
        case owner before accepting or countering.  Defaults to approval in
        simulation (owner approval assumed).

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads actor/case context from construction time)
      Output keys: (none — pass/fail gate only)

    Input category: Human approval / adjudication.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Low** — final authority rests with the case owner
    (a human or a configured policy agent).
    """


# ---------------------------------------------------------------------------
# Active embargo evaluation nodes
# ---------------------------------------------------------------------------


class CurrentEmbargoAcceptable(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Decide whether the current active embargo terms remain acceptable.

    Semantic function:
        Condition — is the participant satisfied with the current active
        embargo, or do they wish to propose a revision?  Modeled as
        usually acceptable; revision proposals are relatively uncommon.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates active embargo terms from caller's DataLayer)
      Output keys: current_embargo_acceptable_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium** — automated comparison of current
    terms against policy preferences is feasible; edge cases and dynamic
    negotiation contexts may still require human judgment.
    """

    output_keys: ClassVar[dict[str, type]] = {
        "current_embargo_acceptable_verdict": str
    }
