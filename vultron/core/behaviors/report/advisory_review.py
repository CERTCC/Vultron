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
"""Blackboard contract of the advisory draft-review-submit capabilities.

The ``DraftAdvisoryArtifact``, ``ReviewAdvisoryDraft`` and
``ReviseAdvisoryDraft`` capability declarations in
:mod:`vultron.core.behaviors.call_out.capabilities.report_management.publication`
name these keys and :class:`AdvisoryReviewDecision` in their ports, and the
publish-artifact tree and every backend read or give them, so they live in a
module that imports none of them (CS-05-003).
"""

from pydantic import BaseModel

#: Blackboard key written by ``DraftAdvisoryArtifact`` Composer on SUCCESS.
DRAFT_ARTIFACT_KEY = "draft_advisory_artifact"

#: Blackboard key written by ``ReviewAdvisoryDraft`` Evaluator on SUCCESS.
REVIEW_DECISION_KEY = "advisory_review_decision"


class AdvisoryReviewDecision(BaseModel):
    """Structured output record for the ReviewAdvisoryDraft call-out point.

    Written to the blackboard key :data:`REVIEW_DECISION_KEY` by the
    ``ReviewAdvisoryDraft`` Evaluator node on SUCCESS (BT-18-001).

    The ``needs_revision`` field drives the optional revision arm: when
    ``True``, the ``ReviseAdvisoryDraft`` Composer runs before
    ``SubmitAdvisoryArtifact``; when ``False`` (the default auto-approve
    path), the revision arm is a graceful no-op and the pipeline proceeds
    directly to submission.

    To block submission for any reason (legal hold, compliance failure,
    editorial rejection) the backend MUST return ``Status.FAILURE`` from
    ``update()`` — that is the universal BT blocking idiom (BT-18-007).
    There is no separate approval flag: FAILURE is both necessary and
    sufficient to stop the pipeline.

    The default instance (``needs_revision=False``) encodes the auto-approve
    path used when no real review agent is available (AC-3, ADR-0030).

    Attributes:
        needs_revision: Whether the draft requires revision before submission.
            When ``True``, the optional ``ReviseAdvisoryDraft`` Composer runs.
        feedback: Human-readable or machine-generated review feedback.
    """

    needs_revision: bool = False
    feedback: str = ""


__all__ = [
    "AdvisoryReviewDecision",
    "DRAFT_ARTIFACT_KEY",
    "REVIEW_DECISION_KEY",
]
