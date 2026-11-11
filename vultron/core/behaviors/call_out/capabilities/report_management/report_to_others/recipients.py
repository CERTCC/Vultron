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
"""Core capability declarations for ``report_management.report_to_others.recipients``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.report_to_others.recipients``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    EvaluatorCapability,
    RetrieverCapability,
)


class AllPartiesKnownCapability(EvaluatorCapability):
    """Check whether all relevant parties for notification have been identified.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates party-identification state from caller's DataLayer)
      Output keys: all_parties_known_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "all_parties_known_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class IdentifyVendorsCapability(RetrieverCapability):
    """Identify the software vendors responsible for the affected product(s).

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries CPE/product databases and SBOM data)
      Output keys: identified_vendors: list  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **can**, in part — vendors already in
    the case are in its participant list, so a tree that places this
    Retriever reads that list first and asks only for vendors the case does
    not list.  No core tree places it today.
    """

    OUTPUT_PORTS = {
        "identified_vendors": PortInformation(data_type=list, required=True),
    }


class IdentifyCoordinatorsCapability(RetrieverCapability):
    """Identify coordinator organizations that should be involved.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries FIRST member directory and CSIRT registries)
      Output keys: identified_coordinators: list  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **can**, in part — coordinators already
    in the case are in its participant list, so a tree that places this
    Retriever reads that list first and asks only for coordinators the case
    does not list.  No core tree places it today.
    """

    OUTPUT_PORTS = {
        "identified_coordinators": PortInformation(
            data_type=list, required=True
        ),
    }


class ChooseRecipientCapability(RetrieverCapability):
    """Select the next recipient from the identified-parties list.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads pending notification queue from DataLayer)
      Output keys: chosen_recipient: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — its answer is a choice
    among the identified parties, not a fact the case file or the actor's
    store holds.
    """

    OUTPUT_PORTS = {
        "chosen_recipient": PortInformation(data_type=str, required=True),
    }


class RemoveRecipientCapability(ActuatorCapability):
    """Remove a recipient from the pending notification queue.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; recipient context from construction time)
      Output keys: (none — side effect: remove recipient from notification queue)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


class RecipientEffortExceededCapability(EvaluatorCapability):
    """Check whether notification effort for a recipient has exceeded a limit.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates per-recipient effort counter from caller's DataLayer)
      Output keys: recipient_effort_exceeded_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "recipient_effort_exceeded_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class PolicyCompatibleCapability(EvaluatorCapability):
    """Check whether the recipient's disclosure policy is compatible with the case.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates recipient and case policy from caller's DataLayer)
      Output keys: policy_compatible_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "policy_compatible_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class SetRcptQrmRCapability(ActuatorCapability):
    """Record notification by transitioning recipient's RM state to RECEIVED.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; recipient context from construction time)
      Output keys: (none — side effect: transition recipient RM state to RECEIVED)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


class TotalEffortLimitMetCapability(EvaluatorCapability):
    """Check whether the total notification effort ceiling has been reached.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates total effort counter from caller's DataLayer)
      Output keys: total_effort_limit_met_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "total_effort_limit_met_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


__all__ = [
    "AllPartiesKnownCapability",
    "ChooseRecipientCapability",
    "IdentifyCoordinatorsCapability",
    "IdentifyVendorsCapability",
    "PolicyCompatibleCapability",
    "RecipientEffortExceededCapability",
    "RemoveRecipientCapability",
    "SetRcptQrmRCapability",
    "TotalEffortLimitMetCapability",
]
