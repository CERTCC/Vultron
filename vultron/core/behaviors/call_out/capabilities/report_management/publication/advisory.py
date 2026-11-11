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
"""Core capability declarations for ``report_management.publication.advisory``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.publication.advisory``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    ComposerCapability,
    EvaluatorCapability,
)
from vultron.core.behaviors.report.advisory_review import (
    DRAFT_ARTIFACT_KEY,
    REVIEW_DECISION_KEY,
    AdvisoryReviewDecision,
)


class DraftAdvisoryArtifactCapability(ComposerCapability):
    """Draft the advisory artifact from case data.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: draft_advisory_artifact: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        DRAFT_ARTIFACT_KEY: PortInformation(data_type=str, required=True),
    }


class ReviewAdvisoryDraftCapability(EvaluatorCapability):
    """Review and approve the advisory draft.

    Blackboard contract (BT-18-001):
      Input keys:  draft_advisory_artifact: str  (reads the Composer output)
      Output keys: advisory_review_decision: AdvisoryReviewDecision  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    INPUT_PORTS = {
        DRAFT_ARTIFACT_KEY: PortInformation(data_type=str, required=True),
    }
    OUTPUT_PORTS = {
        REVIEW_DECISION_KEY: PortInformation(
            data_type=AdvisoryReviewDecision, required=True
        ),
    }


class ReviseAdvisoryDraftCapability(ComposerCapability):
    """Revise the advisory draft based on review feedback.

    Blackboard contract (BT-18-001):
      Input keys:  advisory_review_decision: AdvisoryReviewDecision
                   (reads the Evaluator output for feedback guidance)
      Output keys: draft_advisory_artifact: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    INPUT_PORTS = {
        REVIEW_DECISION_KEY: PortInformation(
            data_type=AdvisoryReviewDecision, required=True
        ),
    }
    OUTPUT_PORTS = {
        DRAFT_ARTIFACT_KEY: PortInformation(data_type=str, required=True),
    }


class SubmitAdvisoryArtifactCapability(ActuatorCapability):
    """Submit the finalized advisory artifact to the external advisory platform.

    Blackboard contract (BT-18-001):
      Input keys:  (none — artifact context from construction time)
      Output keys: (none — side effect: publish artifact to advisory platform)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


__all__ = [
    "DraftAdvisoryArtifactCapability",
    "ReviewAdvisoryDraftCapability",
    "ReviseAdvisoryDraftCapability",
    "SubmitAdvisoryArtifactCapability",
]
