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
"""Core capability declarations for ``embargo.proposal``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.embargo.proposal``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    EvaluatorCapability,
)


class StopProposingEmbargoCapability(EvaluatorCapability):
    """Decide whether to abandon an ongoing embargo negotiation.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates negotiation context from caller's DataLayer)
      Output keys: stop_proposing_embargo_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "stop_proposing_embargo_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class SelectEmbargoOfferTermsCapability(EvaluatorCapability):
    """Select the specific terms to include in an embargo proposal.

    Blackboard contract (BT-18-001):
      Input keys:  (none — selects terms based on case context from DataLayer)
      Output keys: selected_embargo_terms_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "selected_embargo_terms_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class WantToProposeEmbargoCapability(EvaluatorCapability):
    """Decide whether to initiate an embargo negotiation.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case and role context from caller's DataLayer)
      Output keys: want_to_propose_embargo_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "want_to_propose_embargo_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class WillingToCounterEmbargoProposalCapability(EvaluatorCapability):
    """Decide whether to counter an incoming embargo proposal.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates proposal context from caller's DataLayer)
      Output keys: willing_to_counter_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "willing_to_counter_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class ReasonToProposeEmbargoWhenDeployedCapability(EvaluatorCapability):
    """Decide whether to start a new embargo after the fix is already deployed.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from caller's DataLayer)
      Output keys: reason_to_propose_when_deployed_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "reason_to_propose_when_deployed_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


__all__ = [
    "ReasonToProposeEmbargoWhenDeployedCapability",
    "SelectEmbargoOfferTermsCapability",
    "StopProposingEmbargoCapability",
    "WantToProposeEmbargoCapability",
    "WillingToCounterEmbargoProposalCapability",
]
