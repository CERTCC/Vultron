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
"""Core capability declarations for ``embargo.termination``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.embargo.termination``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    EvaluatorCapability,
    RetrieverCapability,
)


class ExitEmbargoWhenDeployedCapability(EvaluatorCapability):
    """Decide whether to exit an active embargo when the fix is deployed.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates deployment state from caller's DataLayer)
      Output keys: exit_embargo_when_deployed_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "exit_embargo_when_deployed_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class ExitEmbargoWhenFixReadyCapability(EvaluatorCapability):
    """Decide whether to exit an active embargo when the fix is ready.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates fix-readiness state from caller's DataLayer)
      Output keys: exit_embargo_when_fix_ready_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "exit_embargo_when_fix_ready_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class ExitEmbargoForOtherReasonCapability(EvaluatorCapability):
    """Decide whether to exit an embargo for an uncommon or exceptional reason.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from caller's DataLayer)
      Output keys: exit_embargo_other_reason_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "exit_embargo_other_reason_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class EmbargoTimerExpiredCapability(RetrieverCapability):
    """Check whether the embargo's agreed-upon deadline has passed.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries embargo expiry timestamp from case record)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **can** — the embargo end time is in the
    case's embargo register.  Core reads it there and compares it with the
    act's instant (``vultron/core/behaviors/embargo/end_time_tree.py``), so
    no core tree places this Retriever.
    """


class OnEmbargoExitCapability(ActuatorCapability):
    """Execute site-specific tasks when leaving an active embargo.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; embargo context from construction time)
      Output keys: (none — side effect: notify stakeholders, update downstream systems)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


class EmbargoExitPolicyGuardCapability(EvaluatorCapability):
    """Check whether site policy permits voluntary embargo termination.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads policy state from caller's DataLayer)
      Output keys: embargo_exit_policy_guard_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "embargo_exit_policy_guard_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class EmbargoExitOverrideCapability(EvaluatorCapability):
    """Actor explicitly overrides a policy veto to terminate the embargo.

    Blackboard contract (BT-18-001):
      Input keys:  (none — override is actor-initiated)
      Output keys: embargo_exit_override_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "embargo_exit_override_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


__all__ = [
    "EmbargoExitOverrideCapability",
    "EmbargoExitPolicyGuardCapability",
    "EmbargoTimerExpiredCapability",
    "ExitEmbargoForOtherReasonCapability",
    "ExitEmbargoWhenDeployedCapability",
    "ExitEmbargoWhenFixReadyCapability",
    "OnEmbargoExitCapability",
]
