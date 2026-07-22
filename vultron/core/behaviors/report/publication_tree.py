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
"""Collapsed publication behavior tree (Production Collapse 2 + 4).

Implements ADR-0028 / BT-20-002 (Production Collapse 2) and ADR-0030 /
BT-20-004 (Production Collapse 4).

Production Collapse 2 replaces the twelve simulator publication nodes
(``PublicationIntentsSet``, ``PrioritizePublicationIntents``,
``NoPublishExploit``, ``ExploitReady``, ``PrepareExploit``,
``ReprioritizeExploit``, ``NoPublishFix``, ``PrepareFix``, ``ReprioritizeFix``,
``NoPublishReport``, ``PrepareReport``, ``ReprioritizeReport``) with a single
Evaluator that drives three named per-artifact arms:

1. ``PrioritizePublicationIntents`` (Evaluator) — writes a structured
   :class:`PublicationIntentDecision` record to the blackboard on SUCCESS.
2. Three named per-artifact arms (exploit, fix, report).  Each arm is gated by
   a ``ShouldPublish*`` condition that reads the intent record; when the
   artifact is intended, the arm runs its ``Prepare*`` Composer followed by the
   publish pipeline, otherwise the arm is a graceful no-op.

The ``PublicationIntentsSet`` flag check and the ``NoPublish*`` bypass leaves
are eliminated — they were ProtocolInternal structural artifacts of the
simulator representation, not real call-out points.  The ``ReprioritizeX``
Evaluators likewise disappear: the intent record produced by step 1 is the
single source of truth for which arms execute.

Arm shape (positive-condition gate with Inverter skip, per BTND-08-001)::

    ExploitPublicationArm (Selector)
    ├── Sequence(ShouldPublishExploit, PrepareExploit, PublishArtifactBT)
    └── Inverter(ShouldPublishExploit)   # SUCCESS no-op when not intended

Production Collapse 4 expands the single ``Publish`` Actuator in each arm
into the draft-review-submit pipeline from
:func:`~vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree`
(ADR-0030 / BT-20-004).  The per-arm ``Prepare*`` Composer still runs first;
the publish pipeline follows it inside the same Sequence.

References
----------
- ADR-0028: ``docs/adr/0028-publication-intent-bt-collapse.md``
- ADR-0030: ``docs/adr/0030-publish-leaf-draft-review-submit-pipeline.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-20-002, BT-20-004
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
  § "Production Collapse 2" and "Production Collapse 4"
- Precedent: ``vultron.core.behaviors.report.acquire_exploit_strategy_tree``
  (Production Collapse 1, ADR-0027)
"""

from __future__ import annotations

import logging
from typing import Any

import py_trees
from py_trees.common import Access, Status
from pydantic import BaseModel

from vultron.core.behaviors.call_out_point import CallOutBackendFactory
from vultron.core.behaviors.report.publish_artifact_tree import (
    _default_draft_advisory_artifact_factory,
    _default_review_advisory_draft_factory,
    _default_revise_advisory_draft_factory,
    _default_submit_advisory_artifact_factory,
    create_publish_artifact_tree,
)

logger = logging.getLogger(__name__)

#: Blackboard key under which the ``PrioritizePublicationIntents`` Evaluator
#: writes its :class:`PublicationIntentDecision` record and from which the
#: ``ShouldPublish*`` gate nodes read it (BT-18-001).
INTENT_DECISION_KEY = "publication_intent_decision"


class PublicationIntentDecision(BaseModel):
    """Structured output record for the PrioritizePublicationIntents call-out point.

    Written to the blackboard key :data:`INTENT_DECISION_KEY` by the
    ``PrioritizePublicationIntents`` Evaluator node on SUCCESS (BT-18-001).
    The three boolean fields directly gate the three named per-artifact
    publication arms (ADR-0028); the removed ``NoPublish*`` bypass leaves are
    replaced by ``ShouldPublish*`` reads on these fields.

    Field defaults encode the standard CVD outcome — publish the fix and the
    vulnerability report, withhold the exploit — matching the simulator's
    ``NoPublishFix`` / ``NoPublishReport`` (``AlmostAlwaysFail``) and
    ``NoPublishExploit`` (``UsuallySucceed``) probabilities.  A real Evaluator
    backend overrides these per case policy.

    Attributes:
        publish_exploit: Whether the exploit artifact should be published.
        publish_fix: Whether the fix artifact should be published.
        publish_report: Whether the vulnerability report/advisory should be
            published.
        rationale: Human-readable or machine-generated explanation of the
            publication-intent decision.
    """

    publish_exploit: bool = False
    publish_fix: bool = True
    publish_report: bool = True
    rationale: str = ""


class _ShouldPublishArtifactGate(py_trees.behaviour.Behaviour):
    """ProtocolInternal gate: read the intent record and check one artifact flag.

    Reads the :class:`PublicationIntentDecision` written to
    :data:`INTENT_DECISION_KEY` by ``PrioritizePublicationIntents`` and returns
    SUCCESS when the artifact named by :attr:`_intent_field` is intended for
    publication, FAILURE otherwise (including when no decision has been
    recorded).

    This is a ProtocolInternal read of a flag written by the protocol's own BT
    execution — not a call-out point — so it is constructed directly by the
    tree builder rather than injected via a factory (ADR-0025).  Subclasses use
    positive names (``ShouldPublish*``) per BTND-08-001.
    """

    #: Attribute name on :class:`PublicationIntentDecision` this gate reads.
    _intent_field: str = ""

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def setup(self, **kwargs: Any) -> None:
        """Register READ access to the shared intent-decision blackboard key."""
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key=INTENT_DECISION_KEY, access=Access.READ
        )

    def update(self) -> Status:
        """Return SUCCESS if this artifact is intended for publication.

        Returns:
            SUCCESS when the intent record's :attr:`_intent_field` is truthy;
            FAILURE when it is falsy or when no intent record has been written.
        """
        if not self.blackboard.exists(INTENT_DECISION_KEY):
            self.logger.debug(
                "%s: no %s on blackboard — treating as 'do not publish'",
                self.name,
                INTENT_DECISION_KEY,
            )
            return Status.FAILURE

        decision = self.blackboard.get(INTENT_DECISION_KEY)
        if not isinstance(decision, PublicationIntentDecision):
            # A present-but-wrong-type value is a call-out-point contract
            # violation (the Evaluator must write a PublicationIntentDecision on
            # SUCCESS, BT-18-002).  Fail loudly rather than silently degrading
            # to "do not publish" — a bare getattr() default would mask the bug.
            self.logger.warning(
                "%s: %s holds %s, not a PublicationIntentDecision — "
                "treating as 'do not publish'",
                self.name,
                INTENT_DECISION_KEY,
                type(decision).__name__,
            )
            return Status.FAILURE

        if getattr(decision, self._intent_field):
            self.logger.debug(
                "%s: %s is intended for publication",
                self.name,
                self._intent_field,
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: %s is not intended for publication",
            self.name,
            self._intent_field,
        )
        return Status.FAILURE


class ShouldPublishExploit(_ShouldPublishArtifactGate):
    """Gate the exploit arm on ``PublicationIntentDecision.publish_exploit``."""

    _intent_field = "publish_exploit"


class ShouldPublishFix(_ShouldPublishArtifactGate):
    """Gate the fix arm on ``PublicationIntentDecision.publish_fix``."""

    _intent_field = "publish_fix"


class ShouldPublishReport(_ShouldPublishArtifactGate):
    """Gate the report arm on ``PublicationIntentDecision.publish_report``."""

    _intent_field = "publish_report"


def _default_prioritize_publication_intents_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    # Deferred import: the demo fuzzer module imports PublicationIntentDecision
    # from this module at module level (mirrors acquire_exploit.py / ADR-0027).
    from vultron.demo.fuzzer.report_management.publication import (
        PrioritizePublicationIntents,
    )

    return PrioritizePublicationIntents(name)


def _default_prepare_exploit_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        PrepareExploit,
    )

    return PrepareExploit(name)


def _default_prepare_fix_factory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import PrepareFix

    return PrepareFix(name)


def _default_prepare_report_factory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import PrepareReport

    return PrepareReport(name)


def _make_artifact_arm(
    case_id: str,
    arm_name: str,
    artifact_label: str,
    gate_cls: type[_ShouldPublishArtifactGate],
    prepare_factory: CallOutBackendFactory,
    prepare_node_name: str,
    draft_advisory_artifact_factory: CallOutBackendFactory,
    review_advisory_draft_factory: CallOutBackendFactory,
    revise_advisory_draft_factory: CallOutBackendFactory,
    submit_advisory_artifact_factory: CallOutBackendFactory,
) -> py_trees.behaviour.Behaviour:
    """Build one intent-gated per-artifact publication arm.

    Shape (positive-condition gate with Inverter skip, per BTND-08-001)::

        Selector(arm_name)
        ├── Sequence(gate, Prepare, PublishArtifactBT)
        └── Inverter(gate)   # SUCCESS no-op when the artifact is not intended

    The ``PublishArtifactBT`` subtree is the draft-review-submit pipeline from
    :func:`~vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree`
    (Production Collapse 4, ADR-0030 / BT-20-004).
    """
    do_publish = py_trees.composites.Sequence(
        name=f"Do{arm_name}",
        memory=False,
        children=[
            gate_cls(),
            prepare_factory(prepare_node_name),
            create_publish_artifact_tree(
                case_id=case_id,
                artifact_label=artifact_label,
                draft_advisory_artifact_factory=draft_advisory_artifact_factory,
                review_advisory_draft_factory=review_advisory_draft_factory,
                revise_advisory_draft_factory=revise_advisory_draft_factory,
                submit_advisory_artifact_factory=submit_advisory_artifact_factory,
            ),
        ],
    )
    skip_if_not_intended = py_trees.decorators.Inverter(
        name=f"Skip{arm_name}IfNotIntended",
        child=gate_cls(name=f"{gate_cls.__name__}Skip"),
    )
    return py_trees.composites.Selector(
        name=arm_name,
        memory=False,
        children=[do_publish, skip_if_not_intended],
    )


def create_publication_tree(
    case_id: str,
    prioritize_publication_intents_factory: CallOutBackendFactory = _default_prioritize_publication_intents_factory,
    prepare_exploit_factory: CallOutBackendFactory = _default_prepare_exploit_factory,
    prepare_fix_factory: CallOutBackendFactory = _default_prepare_fix_factory,
    prepare_report_factory: CallOutBackendFactory = _default_prepare_report_factory,
    draft_advisory_artifact_factory: CallOutBackendFactory = _default_draft_advisory_artifact_factory,
    review_advisory_draft_factory: CallOutBackendFactory = _default_review_advisory_draft_factory,
    revise_advisory_draft_factory: CallOutBackendFactory = _default_revise_advisory_draft_factory,
    submit_advisory_artifact_factory: CallOutBackendFactory = _default_submit_advisory_artifact_factory,
) -> py_trees.behaviour.Behaviour:
    """Create the collapsed publication behavior tree (Production Collapses 2 + 4).

    Implements ADR-0028 / BT-20-002 (Production Collapse 2) and ADR-0030 /
    BT-20-004 (Production Collapse 4).

    A single ``PrioritizePublicationIntents`` Evaluator writes a
    :class:`PublicationIntentDecision` record whose boolean fields gate three
    named per-artifact arms (exploit, fix, report).  Each arm runs a
    ``Prepare*`` Composer followed by the draft-review-submit pipeline from
    :func:`~vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree`.

    Tree structure::

        PublicationBT (Sequence)
        ├── PrioritizePublicationIntents (Evaluator → writes intent record)
        ├── ExploitPublicationArm (Selector, gated on publish_exploit)
        │   ├── Sequence(ShouldPublishExploit, PrepareExploit, PublishArtifactBT_Exploit)
        │   └── Inverter(ShouldPublishExploit)
        ├── FixPublicationArm (Selector, gated on publish_fix)
        │   ├── Sequence(ShouldPublishFix, PrepareFix, PublishArtifactBT_Fix)
        │   └── Inverter(ShouldPublishFix)
        └── ReportPublicationArm (Selector, gated on publish_report)
            ├── Sequence(ShouldPublishReport, PrepareReport, PublishArtifactBT_Report)
            └── Inverter(ShouldPublishReport)

    Args:
        case_id: ID of the VulnerabilityCase to publish for.
        prioritize_publication_intents_factory: Factory for the Evaluator
            call-out point that writes the :class:`PublicationIntentDecision`
            record.  Defaults to the fuzzer backend (ADR-0025).
        prepare_exploit_factory: Factory for the Composer call-out point that
            drafts and stages the exploit artifact.  Defaults to the fuzzer
            backend.
        prepare_fix_factory: Factory for the Composer call-out point that drafts
            and stages the fix artifact.  Defaults to the fuzzer backend.
        prepare_report_factory: Factory for the Composer call-out point that
            authors and stages the vulnerability advisory artifact.  Defaults to
            the fuzzer backend.
        draft_advisory_artifact_factory: Factory for the Composer that drafts
            the advisory artifact in the publish pipeline.  Shared across all
            three per-artifact arms.  Defaults to the fuzzer backend.
        review_advisory_draft_factory: Factory for the Evaluator that reviews
            and approves the draft.  Defaults to the auto-approve fuzzer
            backend (AC-3, ADR-0030).
        revise_advisory_draft_factory: Factory for the optional Composer that
            revises the draft based on review feedback.  Defaults to the fuzzer
            backend.
        submit_advisory_artifact_factory: Factory for the Actuator that submits
            the finalized artifact to the external advisory platform.  Defaults
            to the fuzzer backend.

    Returns:
        Root Sequence node of the collapsed publication behavior tree.
    """
    root = py_trees.composites.Sequence(
        name="PublicationBT",
        memory=False,
        children=[
            prioritize_publication_intents_factory(
                "PrioritizePublicationIntents"
            ),
            _make_artifact_arm(
                case_id=case_id,
                arm_name="ExploitPublicationArm",
                artifact_label="Exploit",
                gate_cls=ShouldPublishExploit,
                prepare_factory=prepare_exploit_factory,
                prepare_node_name="PrepareExploit",
                draft_advisory_artifact_factory=draft_advisory_artifact_factory,
                review_advisory_draft_factory=review_advisory_draft_factory,
                revise_advisory_draft_factory=revise_advisory_draft_factory,
                submit_advisory_artifact_factory=submit_advisory_artifact_factory,
            ),
            _make_artifact_arm(
                case_id=case_id,
                arm_name="FixPublicationArm",
                artifact_label="Fix",
                gate_cls=ShouldPublishFix,
                prepare_factory=prepare_fix_factory,
                prepare_node_name="PrepareFix",
                draft_advisory_artifact_factory=draft_advisory_artifact_factory,
                review_advisory_draft_factory=review_advisory_draft_factory,
                revise_advisory_draft_factory=revise_advisory_draft_factory,
                submit_advisory_artifact_factory=submit_advisory_artifact_factory,
            ),
            _make_artifact_arm(
                case_id=case_id,
                arm_name="ReportPublicationArm",
                artifact_label="Report",
                gate_cls=ShouldPublishReport,
                prepare_factory=prepare_report_factory,
                prepare_node_name="PrepareReport",
                draft_advisory_artifact_factory=draft_advisory_artifact_factory,
                review_advisory_draft_factory=review_advisory_draft_factory,
                revise_advisory_draft_factory=revise_advisory_draft_factory,
                submit_advisory_artifact_factory=submit_advisory_artifact_factory,
            ),
        ],
    )
    logger.info(
        "Created PublicationBT (Production Collapses 2+4) for case=%s",
        case_id,
    )
    return root
