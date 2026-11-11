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
"""Core capability declarations for ``embargo.evaluation``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.embargo.evaluation``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    EvaluatorCapability,
)


class EvaluateEmbargoProposalCapability(EvaluatorCapability):
    """Assess an incoming embargo proposal and decide whether to accept it.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates incoming proposal from caller's DataLayer)
      Output keys: evaluate_embargo_proposal_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "evaluate_embargo_proposal_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class OnEmbargoAcceptCapability(ActuatorCapability):
    """Execute site-specific tasks when an embargo proposal is accepted.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; proposal context from construction time)
      Output keys: (none — side effect: notify stakeholders, initialize embargo timer)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


class OnEmbargoRejectCapability(ActuatorCapability):
    """Execute site-specific tasks when an embargo proposal is rejected.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; proposal context from construction time)
      Output keys: (none — side effect: notify stakeholders, log rejection)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


class CaseOwnerApprovesEmbargoResponseCapability(EvaluatorCapability):
    """Adjudication call-out: non-owner actor requests CASE_OWNER approval.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads actor/case context from construction time)
      Output keys: (none — pass/fail gate only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


class CurrentEmbargoAcceptableCapability(EvaluatorCapability):
    """Decide whether the current active embargo terms remain acceptable.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates active embargo terms from caller's DataLayer)
      Output keys: current_embargo_acceptable_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "current_embargo_acceptable_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


__all__ = [
    "CaseOwnerApprovesEmbargoResponseCapability",
    "CurrentEmbargoAcceptableCapability",
    "EvaluateEmbargoProposalCapability",
    "OnEmbargoAcceptCapability",
    "OnEmbargoRejectCapability",
]
