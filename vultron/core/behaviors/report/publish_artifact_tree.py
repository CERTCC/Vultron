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
"""Publish artifact behavior tree (Production Collapse 4).

Implements ADR-0030 / BT-20-004.  Replaces the single ``Publish`` Actuator
leaf used in each per-artifact arm of :func:`~vultron.core.behaviors.report.
publication_tree.create_publication_tree` with a multi-step pipeline:

1. ``DraftAdvisoryArtifact`` (Composer) — draft the advisory artifact from
   case data (CSAF/CVE JSON/advisory text).
2. ``ReviewAdvisoryDraft`` (Evaluator) — review and approve the draft.
3. ``ReviseAdvisoryDraft`` (Composer, optional) — revise the draft based on
   review feedback (optional arm; skipped when the Evaluator approves
   without requesting changes).
4. ``SubmitAdvisoryArtifact`` (Actuator) — submit the finalized artifact to
   the external advisory platform.

Open design question (AC-4): whether the review phase should include a
broadcast-for-participant-comment step has been resolved at this implementation
by **deferring** it to a follow-on issue.  The broadcast would involve emitting
an outbound Activity (a protocol-visible action); that scope is out of bounds
for this task.  The pipeline functions without it — the Evaluator review step
has a default auto-approve implementation (``AlwaysSucceed``) so the tree
operates correctly before a real review agent is available (AC-3).

Tree structure per artifact::

    PublishArtifactBT (Sequence)
    ├── DraftAdvisoryArtifact (Composer)       — writes draft_advisory_artifact key
    ├── ReviewAdvisoryDraft   (Evaluator)      — writes advisory_review_decision key
    ├── RevisionArm           (Selector)       — optional revision; graceful no-op
    │   ├── Sequence(NeedsRevision, ReviseAdvisoryDraft)
    │   └── Inverter(NeedsRevision)
    └── SubmitAdvisoryArtifact (Actuator)      — submits to advisory platform

The ``NeedsRevision`` condition reads the ``AdvisoryReviewDecision.needs_revision``
boolean written by the Evaluator.  When the Evaluator sets
``needs_revision=False`` (the default auto-approve path), the revision arm is
a graceful ``Inverter(NeedsRevision)`` no-op.  When ``needs_revision=True`` the
revision Composer runs.

References
----------
- ADR-0030: ``docs/adr/0030-publish-leaf-draft-review-submit-pipeline.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-20-004
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
  § "Production Collapse 4: Publish leaf → draft-review-submit pipeline"
- Precedent: ``vultron.core.behaviors.report.publication_tree``
  (Production Collapse 2, ADR-0028)
"""

from __future__ import annotations

import logging
from typing import Any

import py_trees
from py_trees.common import Access, Status
from pydantic import BaseModel

from vultron.core.behaviors.call_out_point import CallOutBackendFactory

logger = logging.getLogger(__name__)

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

    The ``approved`` field is metadata for the ``ReviewAdvisoryDraft``
    backend to record its decision.  The pipeline does not gate submission on
    it — a backend that needs to block submission without requesting edits
    (e.g. a legal hold) MUST return ``Status.FAILURE`` from ``update()`` so
    the Sequence fails.  Gating submission on ``approved=False`` is tracked
    as a follow-on design question (see AC-4 in issue #1312).

    The default instance (``approved=True``, ``needs_revision=False``) encodes
    the auto-approve path used when no real review agent is available (AC-3).

    Attributes:
        approved: Informational flag indicating the Evaluator's approval
            decision.  Not read by the pipeline tree.
        needs_revision: Whether the draft requires revision before submission.
            When ``True``, the optional ``ReviseAdvisoryDraft`` Composer runs.
        feedback: Human-readable or machine-generated review feedback.
    """

    approved: bool = True
    needs_revision: bool = False
    feedback: str = ""


class _NeedsRevisionGate(py_trees.behaviour.Behaviour):
    """ProtocolInternal gate: read the review decision and check needs_revision.

    Reads the :class:`AdvisoryReviewDecision` written to :data:`REVIEW_DECISION_KEY`
    by ``ReviewAdvisoryDraft`` and returns SUCCESS when ``needs_revision`` is
    True, FAILURE otherwise (including when no decision has been recorded).

    Used as the gate in the optional revision arm so that the arm is a graceful
    no-op when the Evaluator approves without requesting changes (BTND-08-001).
    """

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def setup(self, **kwargs: Any) -> None:
        """Register READ access to the shared review-decision blackboard key."""
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key=REVIEW_DECISION_KEY, access=Access.READ
        )

    def update(self) -> Status:
        """Return SUCCESS when the review decision requests revision.

        Returns:
            SUCCESS when the decision record's ``needs_revision`` field is
            truthy; FAILURE when it is falsy or when no decision has been
            written (i.e., the auto-approve path, which skips revision).
        """
        if not self.blackboard.exists(REVIEW_DECISION_KEY):
            self.logger.debug(
                "%s: no %s on blackboard — skipping revision",
                self.name,
                REVIEW_DECISION_KEY,
            )
            return Status.FAILURE

        decision = self.blackboard.get(REVIEW_DECISION_KEY)
        if not isinstance(decision, AdvisoryReviewDecision):
            self.logger.warning(
                "%s: %s holds %s, not an AdvisoryReviewDecision — "
                "skipping revision",
                self.name,
                REVIEW_DECISION_KEY,
                type(decision).__name__,
            )
            return Status.FAILURE

        if decision.needs_revision:
            self.logger.debug(
                "%s: review requests revision — running revision arm",
                self.name,
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: review approved without revision — skipping revision arm",
            self.name,
        )
        return Status.FAILURE


def _default_draft_advisory_artifact_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    # Deferred import: demo/publication.py imports AdvisoryReviewDecision from
    # this module at module level, creating a circular dependency.
    from vultron.demo.fuzzer.report_management.publication import (
        DraftAdvisoryArtifact,
    )

    return DraftAdvisoryArtifact(name)


def _default_review_advisory_draft_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    # Deferred import: avoids circular dependency — demo/publication.py imports
    # AdvisoryReviewDecision from this module at module level.
    from vultron.demo.fuzzer.report_management.publication import (
        ReviewAdvisoryDraft,
    )

    return ReviewAdvisoryDraft(name)


def _default_revise_advisory_draft_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    # Deferred import: avoids circular dependency — demo/publication.py imports
    # AdvisoryReviewDecision from this module at module level.
    from vultron.demo.fuzzer.report_management.publication import (
        ReviseAdvisoryDraft,
    )

    return ReviseAdvisoryDraft(name)


def _default_submit_advisory_artifact_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    # Deferred import: avoids circular dependency — demo/publication.py imports
    # AdvisoryReviewDecision from this module at module level.
    from vultron.demo.fuzzer.report_management.publication import (
        SubmitAdvisoryArtifact,
    )

    return SubmitAdvisoryArtifact(name)


def create_publish_artifact_tree(
    case_id: str,
    artifact_label: str = "",
    draft_advisory_artifact_factory: CallOutBackendFactory = _default_draft_advisory_artifact_factory,
    review_advisory_draft_factory: CallOutBackendFactory = _default_review_advisory_draft_factory,
    revise_advisory_draft_factory: CallOutBackendFactory = _default_revise_advisory_draft_factory,
    submit_advisory_artifact_factory: CallOutBackendFactory = _default_submit_advisory_artifact_factory,
) -> py_trees.behaviour.Behaviour:
    """Create the publish-artifact pipeline (Production Collapse 4).

    Replaces the single ``Publish`` Actuator leaf in each per-artifact arm of
    :func:`~vultron.core.behaviors.report.publication_tree.create_publication_tree`
    with a four-step pipeline per ADR-0030 / BT-20-004.

    Tree structure::

        PublishArtifactBT (Sequence)
        ├── DraftAdvisoryArtifact (Composer)
        ├── ReviewAdvisoryDraft   (Evaluator)
        ├── RevisionArm           (Selector — optional; no-op when approved)
        │   ├── Sequence(NeedsRevision, ReviseAdvisoryDraft)
        │   └── Inverter(NeedsRevision)
        └── SubmitAdvisoryArtifact (Actuator)

    The open design question from ADR-0030 (participant-comment broadcast
    in the review phase) is deferred — see AC-4 in issue #1312.

    Args:
        case_id: ID of the VulnerabilityCase being published.
        artifact_label: Short label suffix for node names (e.g. "Exploit",
            "Fix", "Report"); used to distinguish per-arm pipeline instances
            in the py_trees display tree.  Optional — defaults to empty string.
        draft_advisory_artifact_factory: Factory for the Composer call-out
            point that drafts the advisory artifact from case data.  Defaults
            to the fuzzer backend (ADR-0025).
        review_advisory_draft_factory: Factory for the Evaluator call-out
            point that reviews and approves the draft.  The default
            auto-approve fuzzer implementation allows the pipeline to function
            before a real review agent is available (AC-3, ADR-0030).
        revise_advisory_draft_factory: Factory for the optional Composer
            call-out point that revises the draft based on review feedback.
            Runs only when the Evaluator sets ``needs_revision=True``.
            Defaults to the fuzzer backend.
        submit_advisory_artifact_factory: Factory for the Actuator call-out
            point that submits the finalized artifact to the external advisory
            platform.  Defaults to the fuzzer backend.

    Returns:
        Root Sequence node of the publish-artifact pipeline.
    """
    suffix = f"_{artifact_label}" if artifact_label else ""

    needs_revision_do = py_trees.composites.Sequence(
        name=f"DoRevise{suffix}",
        memory=False,
        children=[
            _NeedsRevisionGate(name=f"NeedsRevision{suffix}"),
            revise_advisory_draft_factory(f"ReviseAdvisoryDraft{suffix}"),
        ],
    )
    needs_revision_skip = py_trees.decorators.Inverter(
        name=f"SkipRevisionIfApproved{suffix}",
        child=_NeedsRevisionGate(name=f"NeedsRevisionSkip{suffix}"),
    )
    revision_arm = py_trees.composites.Selector(
        name=f"RevisionArm{suffix}",
        memory=False,
        children=[needs_revision_do, needs_revision_skip],
    )

    root = py_trees.composites.Sequence(
        name=f"PublishArtifactBT{suffix}",
        memory=False,
        children=[
            draft_advisory_artifact_factory(f"DraftAdvisoryArtifact{suffix}"),
            review_advisory_draft_factory(f"ReviewAdvisoryDraft{suffix}"),
            revision_arm,
            submit_advisory_artifact_factory(
                f"SubmitAdvisoryArtifact{suffix}"
            ),
        ],
    )
    logger.info(
        "Created PublishArtifactBT%s (Production Collapse 4) for case=%s",
        suffix,
        case_id,
    )
    return root
