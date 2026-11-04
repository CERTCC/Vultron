"""Embargo termination and exit-authorization fuzzer nodes."""

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
    AlwaysFail,
    AlwaysSucceed,
    OneInOneHundred,
    OneInTwoHundred,
    ProbablyFail,
    UsuallyFail,
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

    output_keys: ClassVar[dict[str, type]] = {
        "exit_embargo_when_deployed_verdict": str
    }


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

    output_keys: ClassVar[dict[str, type]] = {
        "exit_embargo_when_fix_ready_verdict": str
    }


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

    output_keys: ClassVar[dict[str, type]] = {
        "exit_embargo_other_reason_verdict": str
    }


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
# Embargo exit authorization nodes
# ---------------------------------------------------------------------------


class EmbargoExitPolicyGuard(EvaluatorCallOutPoint, AlwaysSucceed):
    """Check whether site policy permits voluntary embargo termination.

    Semantic function:
        Condition — evaluate whether site policy allows the actor to proceed
        with voluntary embargo termination after a reason has been selected
        (e.g., no active revision negotiation, no pending approvals).
        Modeled as always permitting (happy path) in simulation.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads policy state from caller's DataLayer)
      Output keys: embargo_exit_policy_guard_verdict: str  (SUCCESS only)

    Input category: Automated policy evaluation.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — rule-based checks (pending revision,
    approval status) are fully automatable via case-management API calls.
    """

    output_keys: ClassVar[dict[str, type]] = {
        "embargo_exit_policy_guard_verdict": str
    }


class EmbargoExitOverride(EvaluatorCallOutPoint, AlwaysFail):
    """Actor explicitly overrides a policy veto to terminate the embargo.

    Semantic function:
        Condition — the actor accepts responsibility for overriding a
        policy veto and produces a distinct audit-trail entry for the
        override.  Modeled as never succeeding in simulation (override is
        not active by default).

    Blackboard contract (BT-18-001):
      Input keys:  (none — override is actor-initiated)
      Output keys: embargo_exit_override_verdict: str  (SUCCESS only)

    Input category: Explicit actor acknowledgment.

    Success probability: 0.00 (``AlwaysFail``).

    Automation potential: **Low** — override requires explicit actor
    acknowledgment for accountability; should not be auto-approved.
    """

    output_keys: ClassVar[dict[str, type]] = {
        "embargo_exit_override_verdict": str
    }
