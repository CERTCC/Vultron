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
"""Core capability declarations for ``report_management.prioritize``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.prioritize``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    EvaluatorCapability,
    RetrieverCapability,
)


class NoNewPrioritizationInfoCapability(RetrieverCapability):
    """Check whether new information has arrived that should trigger
    re-prioritization of the report.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries prioritization-relevant information sources)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — whether new information
    reached the outside sources since the last evaluation is not recorded
    in the case file or the actor's store.
    """


class EnoughPrioritizationInfoCapability(EvaluatorCapability):
    """Determine whether sufficient context exists to make an accept/defer
    decision.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates available context from caller's DataLayer)
      Output keys: enough_prioritization_info_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "enough_prioritization_info_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class GatherPrioritizationInfoCapability(RetrieverCapability):
    """Collect additional context needed to support a prioritization decision.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries external sources directly)
      Output keys: prioritization_info_gathered: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — it collects outside
    context, such as scores and threat data, that the case file does not
    record.
    """

    OUTPUT_PORTS = {
        "prioritization_info_gathered": PortInformation(
            data_type=str, required=True
        ),
    }


class OnAcceptCapability(ActuatorCapability):
    """Execute site-specific tasks when a report is accepted.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; case context from construction time)
      Output keys: (none — side effect: notify stakeholders, initialize workflow)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


class EvaluateCasePriorityCapability(EvaluatorCapability):
    """Evaluate whether to engage or defer a case using prioritization policy.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from construction time)
      Output keys: evaluate_case_priority_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "evaluate_case_priority_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class OnDeferCapability(ActuatorCapability):
    """Execute site-specific tasks when a report is deferred.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; case context from construction time)
      Output keys: (none — side effect: notify stakeholders, schedule follow-up)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


__all__ = [
    "EnoughPrioritizationInfoCapability",
    "EvaluateCasePriorityCapability",
    "GatherPrioritizationInfoCapability",
    "NoNewPrioritizationInfoCapability",
    "OnAcceptCapability",
    "OnDeferCapability",
]
