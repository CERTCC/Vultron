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
"""Embargo management fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
Embargo Management (EM) workflow.  Each node represents an external-dependency
touchpoint — a human decision, environmental check, or system integration
hook — that will eventually be replaced by production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 (named integration-point
nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/embargo_management/fuzzer.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Notes: ``notes/bt-fuzzer-nodes-embargo.md``
"""

from __future__ import annotations

from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    AlmostCertainlyFail,
    AlwaysSucceed,
    OneInOneHundred,
    OneInTwoHundred,
    ProbablyFail,
    RandomSucceedFail,
    UsuallyFail,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import (
    ActuatorCallOutPoint,
    EvaluatorCallOutPoint,
    RetrieverCallOutPoint,
)

# ---------------------------------------------------------------------------
# Embargo termination nodes
# ---------------------------------------------------------------------------


class ExitEmbargoWhenDeployed(EvaluatorCallOutPoint, ProbablyFail):
    """Decide whether to exit an active embargo when the fix is deployed.

    Semantic function:
        Condition/action — evaluate whether deployment of the fix is
        sufficient reason to exit the active embargo.  Models the common
        case where deployment alone is *not* a sufficient trigger (e.g.,
        partial rollout, emergency deployment, or pending coordinated
        announcement).

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates deployment state from caller's DataLayer)
      Output keys: exit_embargo_when_deployed_verdict: str  (SUCCESS only)

    Input category: Human decision / policy judgment.

    Success probability: 0.33 (``ProbablyFail``).

    Automation potential: **Medium** — deployment status is queryable via
    patch-management or case-state APIs; the *decision* to exit still
    requires policy-rule evaluation or human confirmation.
    """

    output_keys = {"exit_embargo_when_deployed_verdict": str}


class ExitEmbargoWhenFixReady(EvaluatorCallOutPoint, UsuallyFail):
    """Decide whether to exit an active embargo when the fix is ready.

    Semantic function:
        Condition/action — evaluate whether fix availability (without
        deployment) is sufficient reason to terminate the embargo.
        Vendors may prefer to coordinate simultaneous deployment across
        the affected population before ending the embargo.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates fix-readiness state from caller's DataLayer)
      Output keys: exit_embargo_when_fix_ready_verdict: str  (SUCCESS only)

    Input category: Human decision / policy judgment.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **Medium** — fix-readiness flag is queryable
    automatically; the exit decision depends on configurable organizational
    policy that may require human override.
    """

    output_keys = {"exit_embargo_when_fix_ready_verdict": str}


class ExitEmbargoForOtherReason(EvaluatorCallOutPoint, OneInTwoHundred):
    """Decide whether to exit an embargo for an uncommon or exceptional reason.

    Semantic function:
        Condition — catch-all for exiting an embargo for reasons other than
        fix readiness, deployment, timer expiry, public awareness, known
        exploits, or observed attacks.  Represents extraordinary
        circumstances that are rare in practice.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from caller's DataLayer)
      Output keys: exit_embargo_other_reason_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.005 (``OneInTwoHundred``).

    Automation potential: **Low** — rare edge case representing
    extraordinary circumstances; fundamentally requires human judgment that
    cannot be anticipated by a general policy rule.
    """

    output_keys = {"exit_embargo_other_reason_verdict": str}


class EmbargoTimerExpired(RetrieverCallOutPoint, OneInOneHundred):
    """Check whether the embargo's agreed-upon deadline has passed.

    Semantic function:
        Environmental condition — compare the current system clock against
        the embargo expiry timestamp recorded in the case.  In simulation
        this fires rarely; in production it is a simple timestamp
        comparison.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries embargo expiry timestamp from case record)
      Output keys: (none — binary result only, per BT-18-006)

    Input category: Environmental check.

    Success probability: 0.01 (``OneInOneHundred``).

    Automation potential: **High** — simple system-clock comparison against
    the recorded embargo expiry timestamp; fully automatable with no human
    involvement.
    """


class OnEmbargoExit(ActuatorCallOutPoint, AlwaysSucceed):
    """Execute site-specific tasks when leaving an active embargo.

    Semantic function:
        Action integration hook — trigger notifications, logging, and
        downstream system updates required when the embargo exits.  Must
        be idempotent in production.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; embargo context from construction time)
      Output keys: (none — side effect: notify stakeholders, update downstream systems)

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — notification dispatch, state updates,
    and downstream triggers are fully automatable via APIs.
    """


# ---------------------------------------------------------------------------
# Embargo negotiation / proposal nodes
# ---------------------------------------------------------------------------


class StopProposingEmbargo(EvaluatorCallOutPoint, UsuallyFail):
    """Decide whether to abandon an ongoing embargo negotiation.

    Semantic function:
        Condition — human or policy decision to give up on negotiating an
        embargo (e.g., too many counter-proposals, time pressure).
        Modeled as uncommon; parties are usually willing to keep
        negotiating.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates negotiation context from caller's DataLayer)
      Output keys: stop_proposing_embargo_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **Low** — negotiation-fatigue judgment depends on
    relationship context and subjective assessment of negotiation
    prospects; requires human decision.
    """

    output_keys = {"stop_proposing_embargo_verdict": str}


class SelectEmbargoOfferTerms(EvaluatorCallOutPoint, AlwaysSucceed):
    """Select the specific terms to include in an embargo proposal.

    Semantic function:
        Action — choose duration, conditions, and other terms for a new
        embargo proposal or counter-proposal.  In production may involve
        negotiation-support tooling or organizational policy lookup.

    Blackboard contract (BT-18-001):
      Input keys:  (none — selects terms based on case context from DataLayer)
      Output keys: selected_embargo_terms_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — standard terms can be drawn from
    organizational policy templates automatically; atypical situations may
    need human review.
    """

    output_keys = {"selected_embargo_terms_verdict": str}


class WantToProposeEmbargo(EvaluatorCallOutPoint, RandomSucceedFail):
    """Decide whether to initiate an embargo negotiation.

    Semantic function:
        Condition — does the participant currently wish to propose an
        embargo?  Depends on case context, role, and organizational
        policy.  The fuzzer exercises both paths equally; in production
        the recommended default is to propose an embargo.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case and role context from caller's DataLayer)
      Output keys: want_to_propose_embargo_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.50 (``RandomSucceedFail``).

    Automation potential: **Medium** — default policy (always propose) can
    be automated; exceptions (already-public vulnerability, no vendor
    identified) could be rule-encoded, but edge cases may need human
    override.
    """

    output_keys = {"want_to_propose_embargo_verdict": str}


class WillingToCounterEmbargoProposal(EvaluatorCallOutPoint, UsuallyFail):
    """Decide whether to counter an incoming embargo proposal.

    Semantic function:
        Condition — is the participant willing to respond to an incoming
        proposal with a counter-proposal rather than accepting or
        rejecting outright?  The recommended behavior is to accept the
        current proposal and negotiate revisions separately; countering is
        intentionally modeled as uncommon.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates proposal context from caller's DataLayer)
      Output keys: willing_to_counter_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **Low** — nuanced negotiation judgment about
    whether countering is strategically preferable to accepting and
    revising; best left to human discretion.
    """

    output_keys = {"willing_to_counter_verdict": str}


class AvoidEmbargoCounterProposal(UsuallySucceed):
    """Prefer accepting an embargo proposal over issuing a counter-proposal.

    Semantic function:
        Condition — convenience complement of
        ``WillingToCounterEmbargoProposal``.  Returns ``SUCCESS`` when
        the participant should *not* counter (i.e., accept or reject
        directly), and ``FAILURE`` when a counter-proposal is warranted.
        Derived as the logical inversion of
        ``WillingToCounterEmbargoProposal`` (p=0.25 → p=0.75).

    Input category: Human decision (derived).

    Success probability: 0.75 (complement of ``WillingToCounterEmbargoProposal``).

    Automation potential: **Low** — mirrors the inverted decision from
    ``WillingToCounterEmbargoProposal``; same human-discretion constraints
    apply.
    """


class ReasonToProposeEmbargoWhenDeployed(
    EvaluatorCallOutPoint, AlmostCertainlyFail
):
    """Decide whether to start a new embargo after the fix is already deployed.

    Semantic function:
        Condition — is there an unusual reason to propose an embargo even
        though the fix has already been deployed?  Post-deployment embargo
        proposals are exceptional and very rare.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from caller's DataLayer)
      Output keys: reason_to_propose_when_deployed_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.07 (``AlmostCertainlyFail``).

    Automation potential: **Low** — highly exceptional circumstance; no
    general rule can anticipate valid reasons, so human judgment is
    required.
    """

    output_keys = {"reason_to_propose_when_deployed_verdict": str}


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

    output_keys = {"evaluate_embargo_proposal_verdict": str}


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

    output_keys = {"current_embargo_acceptable_verdict": str}
