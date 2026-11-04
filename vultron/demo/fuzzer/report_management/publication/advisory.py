"""Publish leaf pipeline fuzzer nodes: draft, review, revise and submit (ADR-0030, BT-20-004)."""

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

from vultron.core.behaviors.report.publish_artifact_tree import (
    AdvisoryReviewDecision,
)
from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    AlwaysSucceed,
)
from vultron.demo.fuzzer.call_out_point import (
    ActuatorCallOutPoint,
    ComposerCallOutPoint,
    EvaluatorCallOutPoint,
)

# ---------------------------------------------------------------------------
# Production Collapse 4 (ADR-0030 / BT-20-004): Publish leaf pipeline nodes
# ---------------------------------------------------------------------------


class DraftAdvisoryArtifact(ComposerCallOutPoint, AlmostAlwaysSucceed):
    """Draft the advisory artifact from case data.

    Semantic function:
        Action — generate a draft advisory artifact (CSAF JSON, CVE record,
        advisory text, or equivalent) from case data.  In production this
        would involve a templating engine or LLM-driven composition step
        that pulls vulnerability details, fix information, and affected
        product data from the case record.  The fuzzer succeeds almost
        always, allowing the rest of the pipeline to be exercised.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: draft_advisory_artifact: str  (SUCCESS only)

    Input category: System integration / Composer.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium–High** — structured artifact generation
    from well-formed case data (CSAF templates, CVE JSON schema) is
    automatable; narrative advisory text may benefit from human review.
    """

    output_keys: ClassVar[dict[str, type]] = {"draft_advisory_artifact": str}


class ReviewAdvisoryDraft(EvaluatorCallOutPoint, AlwaysSucceed):
    """Review and approve the advisory draft.

    Semantic function:
        Action — review the drafted advisory artifact and produce an
        :class:`~vultron.core.behaviors.report.publish_artifact_tree.
        AdvisoryReviewDecision` record indicating whether revision is
        required.  The default fuzzer implementation always succeeds with
        ``needs_revision=False`` so the pipeline functions end-to-end
        before a real review agent is available (AC-3, ADR-0030).  A real
        backend may involve human editorial review, automated QA checks, or
        both; to block submission for any reason it MUST return
        ``Status.FAILURE`` (BT-18-007).

    Blackboard contract (BT-18-001):
      Input keys:  draft_advisory_artifact: str  (reads the Composer output)
      Output keys: advisory_review_decision: AdvisoryReviewDecision
        (SUCCESS only; default instance written by fuzzer backend)

    Input category: Human decision / QA integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — automated schema validation and
    completeness checks are feasible; editorial approval and legal review
    typically require human judgment.
    """

    output_keys: ClassVar[dict[str, type]] = {
        "advisory_review_decision": AdvisoryReviewDecision
    }


class ReviseAdvisoryDraft(ComposerCallOutPoint, AlmostAlwaysSucceed):
    """Revise the advisory draft based on review feedback.

    Semantic function:
        Action — incorporate feedback from ``ReviewAdvisoryDraft`` and
        produce a revised advisory artifact.  This node runs only when the
        Evaluator sets ``needs_revision=True``; when the Evaluator approves
        without requesting changes the revision arm is a graceful no-op.
        The fuzzer succeeds almost always.

    Blackboard contract (BT-18-001):
      Input keys:  advisory_review_decision: AdvisoryReviewDecision
        (reads the Evaluator output for feedback guidance)
      Output keys: draft_advisory_artifact: str  (overwrites on SUCCESS)

    Input category: Human decision / Composer.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Low–Medium** — structured revision based on
    machine-readable feedback is partially automatable; editorial revisions
    typically require human involvement.
    """

    output_keys: ClassVar[dict[str, type]] = {"draft_advisory_artifact": str}


class SubmitAdvisoryArtifact(ActuatorCallOutPoint, AlmostAlwaysSucceed):
    """Submit the finalized advisory artifact to the external advisory platform.

    Semantic function:
        Action — submit the reviewed (and optionally revised) advisory
        artifact to the target advisory platform (NVD, CVE.org, CMS,
        package repository, or equivalent) via an API call.  In production
        this is the final side-effecting step; the fuzzer succeeds almost
        always, matching the original ``Publish`` Actuator probability.

    Blackboard contract (BT-18-001):
      Input keys:  (none — artifact context from construction time)
      Output keys: (none — side effect: publish artifact to advisory platform)

    Input category: System integration / Actuator.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — advisory platform APIs (NVD, CVE.org,
    CMS, package repository) enable fully automated artifact submission.
    """
