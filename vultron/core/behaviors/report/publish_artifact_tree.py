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
    ├── RevisionArm           (Selector)       — optional; no-op when no revision needed
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
- Catalog: ``docs/developer/reference/bt-fuzzer/rm-publication.md``
  § "Production Collapse 4: Publish leaf → draft-review-submit pipeline"
- Precedent: ``vultron.core.behaviors.report.publication_tree``
  (Production Collapse 2, ADR-0028)
"""

from __future__ import annotations

import logging
from typing import Any

import py_trees
from py_trees.common import Status
from py_trees.ports import BehaviourWithPorts, NoDataAvailable, PortInformation

from vultron.core.behaviors.call_out.actuator import actuator_call
from vultron.core.behaviors.call_out.bundles.publication import (
    PUBLICATION_DETERMINISTIC,
    PublicationCallOutBundle,
)
from vultron.core.behaviors.call_out.guard import guard_call_out_factory
from vultron.core.behaviors.call_out_point import CallOutBackendFactory
from vultron.core.behaviors.node_logger import node_logger, port_wiring_logger
from vultron.core.behaviors.report.advisory_review import (
    DRAFT_ARTIFACT_KEY,  # noqa: F401 — re-exported (moved, CS-05-003)
    REVIEW_DECISION_KEY,
    AdvisoryReviewDecision,
)

logger = logging.getLogger(__name__)


class _NeedsRevisionGate(BehaviourWithPorts):
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
        self.logger = node_logger(self)  # type: ignore[assignment]

    # data_type=object: accept any value; isinstance check in update()
    # handles the type contract (avoid TypeError from get_input).
    INPUT_PORTS: dict[str, PortInformation] = {
        REVIEW_DECISION_KEY: PortInformation(data_type=object, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {}

    def setup(self, **kwargs: Any) -> None:
        """Wire input port to the shared review-decision blackboard key."""
        self.setup_ports(
            port_remappings={REVIEW_DECISION_KEY: f"/{REVIEW_DECISION_KEY}"},
            logger=port_wiring_logger(),
        )

    def update(self) -> Status:
        """Return SUCCESS when the review decision requests revision.

        Returns:
            SUCCESS when the decision record's ``needs_revision`` field is
            truthy; FAILURE when it is falsy or when no decision has been
            written (i.e., the auto-approve path, which skips revision).
        """
        try:
            decision = self.get_input(REVIEW_DECISION_KEY)
        except KeyError, NoDataAvailable, NotImplementedError:
            self.logger.debug(
                "%s: no %s on blackboard — skipping revision",
                self.name,
                REVIEW_DECISION_KEY,
            )
            return Status.FAILURE

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


def advisory_target(case_id: str, artifact_label: str = "") -> str:
    """The one target a ``SubmitAdvisoryArtifact`` call acts on (BT-18-041).

    The case's advisory for *artifact_label*, so each per-artifact arm of the
    publication tree submits its own artifact under its own idempotency id
    (BT-18-042).  An unlabelled pipeline targets the case's advisory.
    """
    if not artifact_label:
        return case_id
    return f"{case_id}#advisory-{artifact_label.lower()}"


def create_publish_artifact_tree(
    case_id: str,
    artifact_label: str = "",
    draft_advisory_artifact_factory: CallOutBackendFactory = PUBLICATION_DETERMINISTIC.draft_advisory_artifact_factory,
    review_advisory_draft_factory: CallOutBackendFactory = PUBLICATION_DETERMINISTIC.review_advisory_draft_factory,
    revise_advisory_draft_factory: CallOutBackendFactory = PUBLICATION_DETERMINISTIC.revise_advisory_draft_factory,
    submit_advisory_artifact_factory: CallOutBackendFactory = PUBLICATION_DETERMINISTIC.submit_advisory_artifact_factory,
    call_out: PublicationCallOutBundle | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the publish-artifact pipeline (Production Collapse 4).

    Replaces the single ``Publish`` Actuator leaf in each per-artifact arm of
    :func:`~vultron.core.behaviors.report.publication_tree.create_publication_tree`
    with a four-step pipeline per ADR-0030 / BT-20-004.

    Tree structure::

        PublishArtifactBT (Sequence)
        ├── DraftAdvisoryArtifact (Composer)
        ├── ReviewAdvisoryDraft   (Evaluator)
        ├── RevisionArm           (Selector — optional; no-op when no revision needed)
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
            to the ``PUBLICATION_DETERMINISTIC`` field, an ``AlwaysSucceed``
            that writes ``draft_advisory_artifact`` (ADR-0025, BT-23-002,
            BT-23-013); inject ``call_out=PUBLICATION_STOCHASTIC`` for the
            probabilistic fuzzer node.
        review_advisory_draft_factory: Factory for the Evaluator call-out
            point that reviews and approves the draft.  The default
            auto-approve DETERMINISTIC backend writes an
            :class:`AdvisoryReviewDecision` that asks for no revision, so
            the pipeline functions before a real review agent is available
            (ADR-0030, BT-23-013).
        revise_advisory_draft_factory: Factory for the optional Composer
            call-out point that revises the draft based on review feedback.
            Runs only when the Evaluator sets ``needs_revision=True``.
            Defaults to the ``PUBLICATION_DETERMINISTIC`` field.
        submit_advisory_artifact_factory: Factory for the Actuator call-out
            point that submits the finalized artifact to the external advisory
            platform.  Defaults to the ``PUBLICATION_DETERMINISTIC`` field,
            a ``NoOpActuator``.  It is placed on :func:`advisory_target`, the one
            target its call acts on (BT-18-041).

    Returns:
        Root Sequence node of the publish-artifact pipeline.
    """
    if call_out is not None:
        draft_advisory_artifact_factory = (
            call_out.draft_advisory_artifact_factory
        )
        review_advisory_draft_factory = call_out.review_advisory_draft_factory
        revise_advisory_draft_factory = call_out.revise_advisory_draft_factory
        submit_advisory_artifact_factory = (
            call_out.submit_advisory_artifact_factory
        )

    # A factory passed here directly, not through a bundle, still puts its
    # backend behind the call-out seam (BT-18-032); guarding is idempotent.
    draft_advisory_artifact_factory = guard_call_out_factory(
        draft_advisory_artifact_factory
    )
    review_advisory_draft_factory = guard_call_out_factory(
        review_advisory_draft_factory
    )
    revise_advisory_draft_factory = guard_call_out_factory(
        revise_advisory_draft_factory
    )
    submit_advisory_artifact_factory = guard_call_out_factory(
        submit_advisory_artifact_factory
    )

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
        name=f"SkipRevisionArm{suffix}",
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
            actuator_call(
                submit_advisory_artifact_factory,
                f"SubmitAdvisoryArtifact{suffix}",
                target=advisory_target(case_id, artifact_label),
            ),
        ],
    )
    logger.info(
        "Created PublishArtifactBT%s (Production Collapse 4) for case=%s",
        suffix,
        case_id,
    )
    return root
