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
"""Tests for the collapsed publication behavior tree (Production Collapses 2 + 4).

Verifies ADR-0028 / BT-20-002 and ADR-0030 / BT-20-004:
- AC-1: PublicationIntentsSet flag check eliminated (not a leaf).
- AC-2: NoPublishExploit / NoPublishFix / NoPublishReport bypass leaves eliminated.
- AC-3: PrioritizePublicationIntents returns a typed PublicationIntentDecision.
- AC-4: Three named per-artifact arms gated by the intent-record booleans.
- AC-5: ADR-0025 factory pattern applied to every call-out point.
- Collapse 4: single Publish leaf replaced by draft-review-submit pipeline subtree.
"""

import pytest
import py_trees
from py_trees.common import Status

from vultron.core.behaviors.report.publication_tree import (
    INTENT_DECISION_KEY,
    PublicationIntentDecision,
    ShouldPublishExploit,
    ShouldPublishFix,
    ShouldPublishReport,
    create_publication_tree,
)
from vultron.demo.fuzzer.report_management.publication import (
    DraftAdvisoryArtifact,
    PrepareExploit,
    PrepareFix,
    PrepareReport,
    PrioritizePublicationIntents,
    ReviewAdvisoryDraft,
    ReviseAdvisoryDraft,
    SubmitAdvisoryArtifact,
)

CASE_ID = "https://example.org/cases/test-001"

_ARM_NAMES = [
    "ExploitPublicationArm",
    "FixPublicationArm",
    "ReportPublicationArm",
]


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
# AC-3: PublicationIntentDecision model
# ---------------------------------------------------------------------------


def test_intent_decision_defaults():
    """Defaults encode the standard CVD outcome: publish fix + report only."""
    decision = PublicationIntentDecision()
    assert decision.publish_exploit is False
    assert decision.publish_fix is True
    assert decision.publish_report is True
    assert decision.rationale == ""


def test_intent_decision_fields():
    decision = PublicationIntentDecision(
        publish_exploit=True,
        publish_fix=False,
        publish_report=False,
        rationale="Exploit already public; fix withheld pending embargo.",
    )
    assert decision.publish_exploit is True
    assert decision.publish_fix is False
    assert decision.publish_report is False
    assert decision.rationale.startswith("Exploit already public")


def test_evaluate_intents_output_key_is_structured_record():
    """AC-3: the Evaluator declares the structured intent-record output key."""
    node = PrioritizePublicationIntents("PrioritizePublicationIntents")
    assert INTENT_DECISION_KEY in node.output_keys
    assert node.output_keys[INTENT_DECISION_KEY] is PublicationIntentDecision


# ---------------------------------------------------------------------------
# Tree structure
# ---------------------------------------------------------------------------


def test_create_tree_returns_behaviour():
    tree = create_publication_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_tree_root_name():
    tree = create_publication_tree(case_id=CASE_ID)
    assert tree.name == "PublicationBT"


def test_root_is_sequence():
    """Root is a Sequence: intents first, then the three arms in order."""
    tree = create_publication_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.composites.Sequence)


def test_root_has_evaluator_plus_three_arms():
    """AC-4: PrioritizePublicationIntents + exactly three named arms."""
    tree = create_publication_tree(case_id=CASE_ID)
    assert len(tree.children) == 4
    assert isinstance(tree.children[0], PrioritizePublicationIntents)
    assert [c.name for c in tree.children[1:]] == _ARM_NAMES


def test_evaluator_is_first_child():
    """The intent Evaluator must run before any arm reads the record."""
    tree = create_publication_tree(case_id=CASE_ID)
    assert tree.children[0].name == "PrioritizePublicationIntents"


@pytest.mark.parametrize("arm_name", _ARM_NAMES)
def test_each_arm_is_selector(arm_name):
    """AC-4: each arm is a Selector(Do…, Inverter(gate)) for graceful skip."""
    tree = create_publication_tree(case_id=CASE_ID)
    arm = next(c for c in tree.children if c.name == arm_name)
    assert isinstance(arm, py_trees.composites.Selector)
    assert len(arm.children) == 2
    # First child: the Do<Arm> Sequence (gate → prepare → PublishArtifactBT_*).
    do_seq = arm.children[0]
    assert isinstance(do_seq, py_trees.composites.Sequence)
    assert len(do_seq.children) == 3
    # Third child of the Sequence is the publish pipeline subtree (Sequence).
    assert isinstance(do_seq.children[2], py_trees.composites.Sequence)
    assert do_seq.children[2].name.startswith("PublishArtifactBT_")
    # Second child: an Inverter skip guard.
    assert isinstance(arm.children[1], py_trees.decorators.Inverter)


def test_default_prepare_nodes_are_fuzzers():
    """AC-5: default prepare factories produce the fuzzer Composer nodes."""
    tree = create_publication_tree(case_id=CASE_ID)
    exploit_seq = tree.children[1].children[0]
    fix_seq = tree.children[2].children[0]
    report_seq = tree.children[3].children[0]

    assert isinstance(exploit_seq.children[0], ShouldPublishExploit)
    assert isinstance(exploit_seq.children[1], PrepareExploit)

    assert isinstance(fix_seq.children[0], ShouldPublishFix)
    assert isinstance(fix_seq.children[1], PrepareFix)

    assert isinstance(report_seq.children[0], ShouldPublishReport)
    assert isinstance(report_seq.children[1], PrepareReport)


def test_default_publish_pipeline_nodes_are_fuzzers():
    """Collapse 4: default pipeline factories produce fuzzer nodes per arm."""
    tree = create_publication_tree(case_id=CASE_ID)
    for arm, label in zip(tree.children[1:], ["Exploit", "Fix", "Report"]):
        pipeline = arm.children[0].children[2]  # PublishArtifactBT_<label>
        assert pipeline.name == f"PublishArtifactBT_{label}"
        assert isinstance(pipeline.children[0], DraftAdvisoryArtifact)
        assert isinstance(pipeline.children[1], ReviewAdvisoryDraft)
        # children[2] is the RevisionArm Selector
        revision_arm = pipeline.children[2]
        do_revise = revision_arm.children[0]
        assert isinstance(do_revise.children[1], ReviseAdvisoryDraft)
        assert isinstance(pipeline.children[3], SubmitAdvisoryArtifact)


# ---------------------------------------------------------------------------
# Behavior-contract integration (BT-18-001): the DEFAULT
# PrioritizePublicationIntents Evaluator writes a PublicationIntentDecision to
# the blackboard when the full tree is ticked to SUCCESS.
# ---------------------------------------------------------------------------


def test_full_tick_with_default_evaluator_writes_intent_record():
    """AC-1: a full tick with the default Evaluator writes the intent record.

    Unlike the structure tests above (and unlike the arm-gating tests, which
    write the record manually via ``_write_intent``), this exercises the real
    default ``PrioritizePublicationIntents`` factory — a deterministic
    ``AlwaysSucceed`` Evaluator — rather than a stub.  It therefore verifies
    the node's actual blackboard-write contract (BT-18-001): on SUCCESS the
    Evaluator writes a :class:`PublicationIntentDecision` to
    :data:`INTENT_DECISION_KEY`.

    Only the probabilistic ``Prepare*``/``Publish`` arm call-out points are
    replaced with deterministic marker stubs, so the tree ticks to SUCCESS on
    every run; the Evaluator factory is left at its default.  Follows the
    ``test_evaluate_exploit_strategy_writes_blackboard_on_success`` pattern in
    ``test_acquire_exploit_strategy_tree.py`` (AC-2): both tick the real
    ``create_*_tree`` builder and stub only the otherwise-probabilistic arms.
    """
    tree = create_publication_tree(
        case_id=CASE_ID,
        prepare_exploit_factory=_marker_factory("PrepExploit"),
        prepare_fix_factory=_marker_factory("PrepFix"),
        prepare_report_factory=_marker_factory("PrepReport"),
        draft_advisory_artifact_factory=_marker_factory("Draft"),
        review_advisory_draft_factory=_marker_factory("Review"),
        revise_advisory_draft_factory=_marker_factory("Revise"),
        submit_advisory_artifact_factory=_marker_factory("Submit"),
    )
    # Guard: the Evaluator under test is the real default node, not a stub.
    assert isinstance(tree.children[0], PrioritizePublicationIntents)

    tree.setup_with_descendants()
    tree.tick_once()

    # AC-1: the full tree reaches SUCCESS deterministically.  With the default
    # decision (publish fix + report, withhold exploit) the exploit arm is a
    # graceful Inverter no-op while the fix and report arms run their stubs.
    assert tree.status == Status.SUCCESS

    # AC-1: the Evaluator wrote a PublicationIntentDecision to the blackboard.
    storage_key = f"/{INTENT_DECISION_KEY}"
    assert storage_key in py_trees.blackboard.Blackboard.storage
    decision = py_trees.blackboard.Blackboard.storage[storage_key]
    assert isinstance(decision, PublicationIntentDecision)


# ---------------------------------------------------------------------------
# AC-1 + AC-2: eliminated nodes are absent as leaves anywhere in the tree
# ---------------------------------------------------------------------------


def _all_node_class_names(root):
    names = [root.__class__.__name__]
    for child in getattr(root, "children", []):
        names.extend(_all_node_class_names(child))
    return names


@pytest.mark.parametrize(
    "eliminated_class_name",
    [
        "PublicationIntentsSet",  # AC-1
        "NoPublishExploit",  # AC-2
        "NoPublishFix",  # AC-2
        "NoPublishReport",  # AC-2
        # ReprioritizeX Evaluators also collapse (ADR-0028 Consequences).
        "ReprioritizeExploit",
        "ReprioritizeFix",
        "ReprioritizeReport",
    ],
)
def test_eliminated_nodes_absent(eliminated_class_name):
    """AC-1/AC-2: bypass/flag/reprioritize nodes are not present as BT nodes."""
    tree = create_publication_tree(case_id=CASE_ID)
    assert eliminated_class_name not in _all_node_class_names(tree)


# ---------------------------------------------------------------------------
# AC-5: every call-out point is factory-injectable
# ---------------------------------------------------------------------------


def test_prioritize_intents_factory_used():
    """AC-5: custom prioritize_publication_intents_factory is wired in."""
    tree = create_publication_tree(
        case_id=CASE_ID,
        prioritize_publication_intents_factory=_marker_factory("CustomPPI"),
    )
    assert tree.children[0].name == "CustomPPI"
    assert not isinstance(tree.children[0], PrioritizePublicationIntents)


def test_prepare_factories_used():
    """AC-5: custom prepare_* factories are wired into their arms."""
    tree = create_publication_tree(
        case_id=CASE_ID,
        prepare_exploit_factory=_marker_factory("CustomPrepExploit"),
        prepare_fix_factory=_marker_factory("CustomPrepFix"),
        prepare_report_factory=_marker_factory("CustomPrepReport"),
    )
    assert tree.children[1].children[0].children[1].name == "CustomPrepExploit"
    assert tree.children[2].children[0].children[1].name == "CustomPrepFix"
    assert tree.children[3].children[0].children[1].name == "CustomPrepReport"


def test_publish_pipeline_factories_used_in_every_arm():
    """AC-5 / Collapse 4: the four pipeline factories are applied to all arms."""
    tree = create_publication_tree(
        case_id=CASE_ID,
        draft_advisory_artifact_factory=_marker_factory("CustomDraft"),
        review_advisory_draft_factory=_marker_factory("CustomReview"),
        revise_advisory_draft_factory=_marker_factory("CustomRevise"),
        submit_advisory_artifact_factory=_marker_factory("CustomSubmit"),
    )
    for arm in tree.children[1:]:
        pipeline = arm.children[0].children[2]
        assert pipeline.children[0].name == "CustomDraft"
        assert pipeline.children[1].name == "CustomReview"
        # pipeline.children[2] is RevisionArm; do_revise seq child[1] is revise node
        do_revise = pipeline.children[2].children[0]
        assert do_revise.children[1].name == "CustomRevise"
        assert pipeline.children[3].name == "CustomSubmit"
        assert not isinstance(pipeline.children[3], SubmitAdvisoryArtifact)


# ---------------------------------------------------------------------------
# AC-4: intent-record booleans gate arm execution
# ---------------------------------------------------------------------------


def _write_intent(decision: PublicationIntentDecision) -> None:
    bb = py_trees.blackboard.Client(name="intent-writer")
    bb.register_key(
        key=INTENT_DECISION_KEY, access=py_trees.common.Access.WRITE
    )
    setattr(bb, INTENT_DECISION_KEY, decision)


@pytest.mark.parametrize(
    "gate_cls, field",
    [
        (ShouldPublishExploit, "publish_exploit"),
        (ShouldPublishFix, "publish_fix"),
        (ShouldPublishReport, "publish_report"),
    ],
)
def test_should_publish_gate_true(gate_cls, field):
    """A gate returns SUCCESS when its intent-record field is True."""
    _write_intent(
        PublicationIntentDecision(
            publish_exploit=True, publish_fix=True, publish_report=True
        )
    )
    gate = gate_cls()
    gate.setup()
    assert gate.update() == Status.SUCCESS


@pytest.mark.parametrize(
    "gate_cls",
    [ShouldPublishExploit, ShouldPublishFix, ShouldPublishReport],
)
def test_should_publish_gate_false(gate_cls):
    """A gate returns FAILURE when its intent-record field is False."""
    _write_intent(
        PublicationIntentDecision(
            publish_exploit=False, publish_fix=False, publish_report=False
        )
    )
    gate = gate_cls()
    gate.setup()
    assert gate.update() == Status.FAILURE


@pytest.mark.parametrize(
    "gate_cls",
    [ShouldPublishExploit, ShouldPublishFix, ShouldPublishReport],
)
def test_should_publish_gate_missing_record_is_failure(gate_cls):
    """A gate returns FAILURE when no intent record has been written."""
    gate = gate_cls()
    gate.setup()
    assert gate.update() == Status.FAILURE


@pytest.mark.parametrize(
    "gate_cls",
    [ShouldPublishExploit, ShouldPublishFix, ShouldPublishReport],
)
@pytest.mark.parametrize(
    "bad_value", ["publish_exploit", {"publish_fix": True}, 42]
)
def test_should_publish_gate_wrong_type_record_is_failure(gate_cls, bad_value):
    """A gate FAILS (not silently) when the record is not a decision object.

    A present-but-wrong-type value on the intent key is a call-out-point
    contract violation; the gate must fail rather than let ``getattr(..., False)``
    silently degrade a truthy string/dict into a spurious skip-or-publish.
    """
    bb = py_trees.blackboard.Client(name="bad-writer")
    bb.register_key(
        key=INTENT_DECISION_KEY, access=py_trees.common.Access.WRITE
    )
    setattr(bb, INTENT_DECISION_KEY, bad_value)
    gate = gate_cls()
    gate.setup()
    assert gate.update() == Status.FAILURE
