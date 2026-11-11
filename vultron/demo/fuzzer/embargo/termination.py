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

from vultron.core.behaviors.call_out.capabilities.embargo.termination import (
    EmbargoExitOverrideCapability,
    EmbargoExitPolicyGuardCapability,
    EmbargoTimerExpiredCapability,
    ExitEmbargoForOtherReasonCapability,
    ExitEmbargoWhenDeployedCapability,
    ExitEmbargoWhenFixReadyCapability,
    OnEmbargoExitCapability,
)
from vultron.demo.fuzzer.base import (
    AlwaysFail,
    AlwaysSucceed,
    OneInOneHundred,
    OneInTwoHundred,
    ProbablyFail,
    UsuallyFail,
)

# ---------------------------------------------------------------------------
# Embargo termination nodes
# ---------------------------------------------------------------------------


class ExitEmbargoWhenDeployed(ExitEmbargoWhenDeployedCapability, ProbablyFail):
    """Decide whether to exit an active embargo when the fix is deployed.

    Simulates :class:`ExitEmbargoWhenDeployedCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition/action — evaluate whether deployment of the fix is
        sufficient reason to exit the active embargo.  Models the common
        case where deployment alone is *not* a sufficient trigger (e.g.,
        partial rollout, emergency deployment, or pending coordinated
        announcement).

    Input category: Human decision / policy judgment.

    Success probability: 0.33 (``ProbablyFail``).

    Automation potential: **Medium** — deployment status is queryable via
    patch-management or case-state APIs; the *decision* to exit still
    requires policy-rule evaluation or human confirmation.
    """


class ExitEmbargoWhenFixReady(ExitEmbargoWhenFixReadyCapability, UsuallyFail):
    """Decide whether to exit an active embargo when the fix is ready.

    Simulates :class:`ExitEmbargoWhenFixReadyCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition/action — evaluate whether fix availability (without
        deployment) is sufficient reason to terminate the embargo.
        Vendors may prefer to coordinate simultaneous deployment across
        the affected population before ending the embargo.

    Input category: Human decision / policy judgment.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **Medium** — fix-readiness flag is queryable
    automatically; the exit decision depends on configurable organizational
    policy that may require human override.
    """


class ExitEmbargoForOtherReason(
    ExitEmbargoForOtherReasonCapability, OneInTwoHundred
):
    """Decide whether to exit an embargo for an uncommon or exceptional reason.

    Simulates :class:`ExitEmbargoForOtherReasonCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — catch-all for exiting an embargo for reasons other than
        fix readiness, deployment, timer expiry, public awareness, known
        exploits, or observed attacks.  Represents extraordinary
        circumstances that are rare in practice.

    Input category: Human decision.

    Success probability: 0.005 (``OneInTwoHundred``).

    Automation potential: **Low** — rare edge case representing
    extraordinary circumstances; fundamentally requires human judgment that
    cannot be anticipated by a general policy rule.
    """


class EmbargoTimerExpired(EmbargoTimerExpiredCapability, OneInOneHundred):
    """Check whether the embargo's agreed-upon deadline has passed.

    Simulates :class:`EmbargoTimerExpiredCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Environmental condition — compare the current system clock against
        the embargo expiry timestamp recorded in the case.  In simulation
        this fires rarely; in production it is a simple timestamp
        comparison.

    Input category: Environmental check.

    Success probability: 0.01 (``OneInOneHundred``).

    Automation potential: **High** — simple system-clock comparison against
    the recorded embargo expiry timestamp; fully automatable with no human
    involvement.
    """


class OnEmbargoExit(OnEmbargoExitCapability, AlwaysSucceed):
    """Execute site-specific tasks when leaving an active embargo.

    Simulates :class:`OnEmbargoExitCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action integration hook — trigger notifications, logging, and
        downstream system updates required when the embargo exits.  Must
        be idempotent in production.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — notification dispatch, state updates,
    and downstream triggers are fully automatable via APIs.
    """


# ---------------------------------------------------------------------------
# Embargo exit authorization nodes
# ---------------------------------------------------------------------------


class EmbargoExitPolicyGuard(EmbargoExitPolicyGuardCapability, AlwaysSucceed):
    """Check whether site policy permits voluntary embargo termination.

    Simulates :class:`EmbargoExitPolicyGuardCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — evaluate whether site policy allows the actor to proceed
        with voluntary embargo termination after a reason has been selected
        (e.g., no active revision negotiation, no pending approvals).
        Modeled as always permitting (happy path) in simulation.

    Input category: Automated policy evaluation.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — rule-based checks (pending revision,
    approval status) are fully automatable via case-management API calls.
    """


class EmbargoExitOverride(EmbargoExitOverrideCapability, AlwaysFail):
    """Actor explicitly overrides a policy veto to terminate the embargo.

    Simulates :class:`EmbargoExitOverrideCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — the actor accepts responsibility for overriding a
        policy veto and produces a distinct audit-trail entry for the
        override.  Modeled as never succeeding in simulation (override is
        not active by default).

    Input category: Explicit actor acknowledgment.

    Success probability: 0.00 (``AlwaysFail``).

    Automation potential: **Low** — override requires explicit actor
    acknowledgment for accountability; should not be auto-approved.
    """
