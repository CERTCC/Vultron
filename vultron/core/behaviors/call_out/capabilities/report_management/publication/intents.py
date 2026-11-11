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
"""Core capability declarations for ``report_management.publication.intents``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.publication.intents``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    ComposerCapability,
    EvaluatorCapability,
)
from vultron.core.behaviors.report.publication_intent import (
    INTENT_DECISION_KEY,
    PublicationIntentDecision,
)


class PrioritizePublicationIntentsCapability(EvaluatorCapability):
    """Establish and record publication intentions for the case.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from caller's DataLayer)
      Output keys: publication_intent_decision: PublicationIntentDecision  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        INTENT_DECISION_KEY: PortInformation(
            data_type=PublicationIntentDecision, required=True
        ),
    }


class PublishCapability(ActuatorCapability):
    """Execute the publication of a prepared artifact to the intended audience.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; artifact context from construction time)
      Output keys: (none — side effect: publish artifact to intended audience)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


class PrepareExploitCapability(ComposerCapability):
    """Create, document, and stage the exploit artifact for publication.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: prepared_exploit_artifact: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "prepared_exploit_artifact": PortInformation(
            data_type=str, required=True
        ),
    }


class ReprioritizeExploitCapability(EvaluatorCapability):
    """Update the priority of the exploit artifact in the publication queue.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates exploit publication context from caller's DataLayer)
      Output keys: reprioritize_exploit_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "reprioritize_exploit_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class PrepareFixCapability(ComposerCapability):
    """Create, document, and stage the fix artifact for publication.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: prepared_fix_artifact: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "prepared_fix_artifact": PortInformation(data_type=str, required=True),
    }


class ReprioritizeFixCapability(EvaluatorCapability):
    """Update the priority of the fix artifact in the publication queue.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates fix publication context from caller's DataLayer)
      Output keys: reprioritize_fix_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "reprioritize_fix_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class PrepareReportCapability(ComposerCapability):
    """Create, review, and stage the vulnerability advisory for publication.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: prepared_report_artifact: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "prepared_report_artifact": PortInformation(
            data_type=str, required=True
        ),
    }


class ReprioritizeReportCapability(EvaluatorCapability):
    """Update the priority of the report artifact in the publication queue.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report publication context from caller's DataLayer)
      Output keys: reprioritize_report_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "reprioritize_report_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


__all__ = [
    "PrepareExploitCapability",
    "PrepareFixCapability",
    "PrepareReportCapability",
    "PrioritizePublicationIntentsCapability",
    "PublishCapability",
    "ReprioritizeExploitCapability",
    "ReprioritizeFixCapability",
    "ReprioritizeReportCapability",
]
