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
"""Tests for the publish-artifact behavior tree (Production Collapse 4).

Verifies ADR-0030 / BT-20-004:
- AC-1: Single Publish leaf replaced by Composer→Evaluator→Composer(opt)→Actuator pipeline.
- AC-2: _NeedsRevisionGate reads AdvisoryReviewDecision.needs_revision correctly.
- AC-3: Default auto-approve path skips the optional revision arm.
- AC-5: All four pipeline stages are independently injectable.
"""

import pytest
import py_trees
from py_trees.common import Access, Status

from vultron.core.behaviors.report.publish_artifact_tree import (
    DRAFT_ARTIFACT_KEY,
    REVIEW_DECISION_KEY,
    AdvisoryReviewDecision,
    _NeedsRevisionGate,
    create_publish_artifact_tree,
)
from vultron.demo.fuzzer.report_management.publication import (
    DraftAdvisoryArtifact,
    ReviewAdvisoryDraft,
    ReviseAdvisoryDraft,
    SubmitAdvisoryArtifact,
)

CASE_ID = "https://example.org/cases/test-001"


@pytest.fixture(autouse=True)
def clear_blackboard():
    """Clear py_trees global blackboard state between tests."""
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def _marker_factory(label):
    def factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return Status.SUCCESS

        return _Marker(name=label)

    return factory


# ---------------------------------------------------------------------------
# AdvisoryReviewDecision model
# ---------------------------------------------------------------------------


def test_review_decision_defaults():
    """Defaults encode the auto-approve path: approved, no revision needed."""
    d = AdvisoryReviewDecision()
    assert d.approved is True
    assert d.needs_revision is False
    assert d.feedback == ""


def test_review_decision_needs_revision():
    d = AdvisoryReviewDecision(
        approved=False, needs_revision=True, feedback="Fix title."
    )
    assert d.approved is False
    assert d.needs_revision is True
    assert d.feedback == "Fix title."


# ---------------------------------------------------------------------------
# _NeedsRevisionGate
# ---------------------------------------------------------------------------


def _write_review(decision):
    bb = py_trees.blackboard.Client(name="test-writer")
    bb.register_key(key=REVIEW_DECISION_KEY, access=Access.WRITE)
    setattr(bb, REVIEW_DECISION_KEY, decision)


def test_needs_revision_gate_true():
    """Gate returns SUCCESS when needs_revision=True."""
    _write_review(AdvisoryReviewDecision(needs_revision=True))
    gate = _NeedsRevisionGate()
    gate.setup()
    assert gate.update() == Status.SUCCESS


def test_needs_revision_gate_false():
    """Gate returns FAILURE when needs_revision=False (auto-approve path)."""
    _write_review(AdvisoryReviewDecision(needs_revision=False))
    gate = _NeedsRevisionGate()
    gate.setup()
    assert gate.update() == Status.FAILURE


def test_needs_revision_gate_missing_record_is_failure():
    """Gate returns FAILURE when no review decision has been written."""
    gate = _NeedsRevisionGate()
    gate.setup()
    assert gate.update() == Status.FAILURE


@pytest.mark.parametrize(
    "bad_value", ["needs_revision", {"needs_revision": True}, 42]
)
def test_needs_revision_gate_wrong_type_is_failure(bad_value):
    """Gate returns FAILURE for a present-but-wrong-type value (contract violation)."""
    bb = py_trees.blackboard.Client(name="bad-writer")
    bb.register_key(key=REVIEW_DECISION_KEY, access=Access.WRITE)
    setattr(bb, REVIEW_DECISION_KEY, bad_value)
    gate = _NeedsRevisionGate()
    gate.setup()
    assert gate.update() == Status.FAILURE


def test_needs_revision_gate_custom_name():
    gate = _NeedsRevisionGate(name="CustomGate")
    assert gate.name == "CustomGate"


# ---------------------------------------------------------------------------
# Tree structure
# ---------------------------------------------------------------------------


def test_create_tree_returns_behaviour():
    tree = create_publish_artifact_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_tree_root_name_no_label():
    tree = create_publish_artifact_tree(case_id=CASE_ID)
    assert tree.name == "PublishArtifactBT"


def test_create_tree_root_name_with_label():
    tree = create_publish_artifact_tree(
        case_id=CASE_ID, artifact_label="Exploit"
    )
    assert tree.name == "PublishArtifactBT_Exploit"


def test_root_is_sequence():
    tree = create_publish_artifact_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.composites.Sequence)


def test_root_has_four_children():
    """AC-1: pipeline has exactly 4 children: Draft, Review, RevisionArm, Submit."""
    tree = create_publish_artifact_tree(case_id=CASE_ID)
    assert len(tree.children) == 4


def test_draft_is_first_child():
    tree = create_publish_artifact_tree(case_id=CASE_ID)
    assert isinstance(tree.children[0], DraftAdvisoryArtifact)


def test_review_is_second_child():
    tree = create_publish_artifact_tree(case_id=CASE_ID)
    assert isinstance(tree.children[1], ReviewAdvisoryDraft)


def test_revision_arm_is_third_child():
    """AC-1: optional revision arm is a Selector (positive gate with Inverter skip)."""
    tree = create_publish_artifact_tree(case_id=CASE_ID)
    revision_arm = tree.children[2]
    assert isinstance(revision_arm, py_trees.composites.Selector)
    assert revision_arm.name.startswith("RevisionArm")
    assert len(revision_arm.children) == 2
    # First: DoRevise Sequence(NeedsRevisionGate, ReviseAdvisoryDraft)
    do_revise = revision_arm.children[0]
    assert isinstance(do_revise, py_trees.composites.Sequence)
    assert len(do_revise.children) == 2
    assert isinstance(do_revise.children[0], _NeedsRevisionGate)
    assert isinstance(do_revise.children[1], ReviseAdvisoryDraft)
    # Second: Inverter(NeedsRevisionGate) skip guard
    skip_guard = revision_arm.children[1]
    assert isinstance(skip_guard, py_trees.decorators.Inverter)
    assert isinstance(skip_guard.children[0], _NeedsRevisionGate)


def test_submit_is_fourth_child():
    tree = create_publish_artifact_tree(case_id=CASE_ID)
    assert isinstance(tree.children[3], SubmitAdvisoryArtifact)


def test_artifact_label_applied_to_all_node_names():
    """artifact_label suffix appears in all node names including internal revision arm nodes."""
    tree = create_publish_artifact_tree(case_id=CASE_ID, artifact_label="Fix")
    assert tree.children[0].name == "DraftAdvisoryArtifact_Fix"
    assert tree.children[1].name == "ReviewAdvisoryDraft_Fix"
    revision_arm = tree.children[2]
    assert revision_arm.name == "RevisionArm_Fix"
    do_revise = revision_arm.children[0]
    assert do_revise.name == "DoRevise_Fix"
    assert do_revise.children[0].name == "NeedsRevision_Fix"
    skip_guard = revision_arm.children[1]
    assert skip_guard.children[0].name == "NeedsRevisionSkip_Fix"
    assert tree.children[3].name == "SubmitAdvisoryArtifact_Fix"


# ---------------------------------------------------------------------------
# AC-5: factory injection
# ---------------------------------------------------------------------------


def test_draft_factory_used():
    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        draft_advisory_artifact_factory=_marker_factory("CustomDraft"),
    )
    assert tree.children[0].name == "CustomDraft"
    assert not isinstance(tree.children[0], DraftAdvisoryArtifact)


def test_review_factory_used():
    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        review_advisory_draft_factory=_marker_factory("CustomReview"),
    )
    assert tree.children[1].name == "CustomReview"
    assert not isinstance(tree.children[1], ReviewAdvisoryDraft)


def test_revise_factory_used():
    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        revise_advisory_draft_factory=_marker_factory("CustomRevise"),
    )
    do_revise = tree.children[2].children[0]
    assert do_revise.children[1].name == "CustomRevise"
    assert not isinstance(do_revise.children[1], ReviseAdvisoryDraft)


def test_submit_factory_used():
    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        submit_advisory_artifact_factory=_marker_factory("CustomSubmit"),
    )
    assert tree.children[3].name == "CustomSubmit"
    assert not isinstance(tree.children[3], SubmitAdvisoryArtifact)


# ---------------------------------------------------------------------------
# AC-3: auto-approve path skips revision (integration ticks)
# ---------------------------------------------------------------------------


class _WritingReview(py_trees.behaviour.Behaviour):
    """Evaluator stub that writes a fixed AdvisoryReviewDecision."""

    def __init__(self, name, decision):
        super().__init__(name=name)
        self._decision = decision

    def setup(self, **kwargs):
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key=REVIEW_DECISION_KEY, access=Access.WRITE
        )

    def update(self):
        setattr(self.blackboard, REVIEW_DECISION_KEY, self._decision)
        return Status.SUCCESS


class _Recording(py_trees.behaviour.Behaviour):
    def __init__(self, name, ran):
        super().__init__(name=name)
        self._ran = ran

    def update(self):
        self._ran.add(self.name)
        return Status.SUCCESS


def _tick_tree(tree):
    bt = py_trees.trees.BehaviourTree(root=tree)
    bt.setup()
    for _ in range(10):
        bt.tick()
        if bt.root.status in (Status.SUCCESS, Status.FAILURE):
            break
    return bt.root.status


def test_auto_approve_skips_revision_arm():
    """AC-3: when the Evaluator sets needs_revision=False, revision does not run."""
    ran: set[str] = set()
    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        draft_advisory_artifact_factory=lambda name: _Recording(name, ran),
        review_advisory_draft_factory=lambda name: _WritingReview(
            name, AdvisoryReviewDecision(needs_revision=False)
        ),
        revise_advisory_draft_factory=lambda name: _Recording(name, ran),
        submit_advisory_artifact_factory=lambda name: _Recording(name, ran),
    )
    status = _tick_tree(tree)
    assert status == Status.SUCCESS
    assert "DraftAdvisoryArtifact" in ran
    assert "SubmitAdvisoryArtifact" in ran
    assert "ReviseAdvisoryDraft" not in ran


def test_needs_revision_runs_revision_arm():
    """When the Evaluator sets needs_revision=True, revision runs before submit."""
    ran: set[str] = set()
    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        draft_advisory_artifact_factory=lambda name: _Recording(name, ran),
        review_advisory_draft_factory=lambda name: _WritingReview(
            name, AdvisoryReviewDecision(needs_revision=True)
        ),
        revise_advisory_draft_factory=lambda name: _Recording(name, ran),
        submit_advisory_artifact_factory=lambda name: _Recording(name, ran),
    )
    status = _tick_tree(tree)
    assert status == Status.SUCCESS
    assert "DraftAdvisoryArtifact" in ran
    assert "ReviseAdvisoryDraft" in ran
    assert "SubmitAdvisoryArtifact" in ran


def test_draft_failure_fails_pipeline():
    """A Draft failure propagates to the root Sequence."""
    ran: set[str] = set()

    class _Fail(py_trees.behaviour.Behaviour):
        def update(self):
            return Status.FAILURE

    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        draft_advisory_artifact_factory=lambda name: _Fail(name=name),
        review_advisory_draft_factory=_marker_factory("Review"),
        revise_advisory_draft_factory=_marker_factory("Revise"),
        submit_advisory_artifact_factory=lambda name: _Recording(name, ran),
    )
    status = _tick_tree(tree)
    assert status == Status.FAILURE
    assert "SubmitAdvisoryArtifact" not in ran


def test_review_failure_fails_pipeline():
    """A Review failure propagates to the root Sequence."""
    ran: set[str] = set()

    class _Fail(py_trees.behaviour.Behaviour):
        def update(self):
            return Status.FAILURE

    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        draft_advisory_artifact_factory=_marker_factory("Draft"),
        review_advisory_draft_factory=lambda name: _Fail(name=name),
        revise_advisory_draft_factory=_marker_factory("Revise"),
        submit_advisory_artifact_factory=lambda name: _Recording(name, ran),
    )
    status = _tick_tree(tree)
    assert status == Status.FAILURE
    assert "SubmitAdvisoryArtifact" not in ran


def test_revise_failure_fails_pipeline():
    """When revision is required, a Revise failure propagates to root."""
    ran: set[str] = set()

    class _Fail(py_trees.behaviour.Behaviour):
        def update(self):
            return Status.FAILURE

    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        draft_advisory_artifact_factory=_marker_factory("Draft"),
        review_advisory_draft_factory=lambda name: _WritingReview(
            name, AdvisoryReviewDecision(needs_revision=True)
        ),
        revise_advisory_draft_factory=lambda name: _Fail(name=name),
        submit_advisory_artifact_factory=lambda name: _Recording(name, ran),
    )
    status = _tick_tree(tree)
    assert status == Status.FAILURE
    assert "SubmitAdvisoryArtifact" not in ran


def test_submit_failure_fails_pipeline():
    """When Submit fails, the root Sequence returns FAILURE."""

    class _Fail(py_trees.behaviour.Behaviour):
        def update(self):
            return Status.FAILURE

    tree = create_publish_artifact_tree(
        case_id=CASE_ID,
        draft_advisory_artifact_factory=_marker_factory("Draft"),
        review_advisory_draft_factory=_marker_factory("Review"),
        revise_advisory_draft_factory=_marker_factory("Revise"),
        submit_advisory_artifact_factory=lambda name: _Fail(name=name),
    )
    status = _tick_tree(tree)
    assert status == Status.FAILURE


# ---------------------------------------------------------------------------
# Blackboard contract: DraftAdvisoryArtifact writes DRAFT_ARTIFACT_KEY
# ---------------------------------------------------------------------------


def test_draft_artifact_key_is_declared():
    """AC-1: DraftAdvisoryArtifact declares the draft_advisory_artifact output key."""
    assert DRAFT_ARTIFACT_KEY in DraftAdvisoryArtifact.output_keys
    assert DraftAdvisoryArtifact.output_keys[DRAFT_ARTIFACT_KEY] is str


def test_review_decision_key_is_declared():
    """AC-1: ReviewAdvisoryDraft declares the advisory_review_decision output key."""
    assert REVIEW_DECISION_KEY in ReviewAdvisoryDraft.output_keys
    assert (
        ReviewAdvisoryDraft.output_keys[REVIEW_DECISION_KEY]
        is AdvisoryReviewDecision
    )
