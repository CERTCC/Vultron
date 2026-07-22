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
"""End-to-end tick tests for create_publication_tree (Production Collapse 2).

Verifies that the intent record produced by the Evaluator actually gates which
per-artifact arms perform Prepare→Publish work, and that a not-intended arm is
a graceful SUCCESS no-op (ADR-0028 / BT-20-002, AC-4).
"""

import py_trees
import pytest
from py_trees.common import Access, Status

from vultron.core.behaviors.report.publication_tree import (
    INTENT_DECISION_KEY,
    PublicationIntentDecision,
    create_publication_tree,
)

CASE_ID = "https://example.org/cases/test-001"


@pytest.fixture(autouse=True)
def clear_blackboard():
    """Clear py_trees global blackboard state between tests."""
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


class _RecordingPrepare(py_trees.behaviour.Behaviour):
    """Composer stand-in that records that it ran and always succeeds."""

    def __init__(self, name, ran):
        super().__init__(name=name)
        self._ran = ran

    def update(self):
        self._ran.add(self.name)
        return Status.SUCCESS


class _RecordingPublish(py_trees.behaviour.Behaviour):
    """Actuator stand-in that records that it ran and always succeeds."""

    def __init__(self, name, ran):
        super().__init__(name=name)
        self._ran = ran

    def update(self):
        self._ran.add(self.name)
        return Status.SUCCESS


def _intent_factory(decision):
    """Return an Evaluator factory that writes a fixed intent record."""

    class _FixedIntents(py_trees.behaviour.Behaviour):
        def setup(self, **kwargs):
            self.blackboard = self.attach_blackboard_client(name=self.name)
            self.blackboard.register_key(
                key=INTENT_DECISION_KEY, access=Access.WRITE
            )

        def update(self):
            setattr(self.blackboard, INTENT_DECISION_KEY, decision)
            return Status.SUCCESS

    return lambda name: _FixedIntents(name=name)


def _tick_to_completion(tree):
    bt = py_trees.trees.BehaviourTree(root=tree)
    bt.setup()
    for _ in range(10):
        bt.tick()
        if bt.root.status in (Status.SUCCESS, Status.FAILURE):
            break
    return bt.root.status


def _build(decision, ran):
    return create_publication_tree(
        case_id=CASE_ID,
        prioritize_publication_intents_factory=_intent_factory(decision),
        prepare_exploit_factory=lambda n: _RecordingPrepare(n, ran),
        prepare_fix_factory=lambda n: _RecordingPrepare(n, ran),
        prepare_report_factory=lambda n: _RecordingPrepare(n, ran),
        publish_factory=lambda n: _RecordingPublish(n, ran),
    )


def test_default_intents_publish_fix_and_report_only():
    """Default intent record runs the fix + report arms, skips exploit."""
    ran: set[str] = set()
    tree = _build(PublicationIntentDecision(), ran)
    assert _tick_to_completion(tree) == Status.SUCCESS
    assert "PrepareExploit" not in ran
    assert "PublishExploit" not in ran
    assert {
        "PrepareFix",
        "PublishFix",
        "PrepareReport",
        "PublishReport",
    } <= ran


def test_all_intended_runs_every_arm():
    """When all three artifacts are intended, all three arms run."""
    ran: set[str] = set()
    tree = _build(
        PublicationIntentDecision(
            publish_exploit=True, publish_fix=True, publish_report=True
        ),
        ran,
    )
    assert _tick_to_completion(tree) == Status.SUCCESS
    assert {
        "PrepareExploit",
        "PublishExploit",
        "PrepareFix",
        "PublishFix",
        "PrepareReport",
        "PublishReport",
    } <= ran


def test_none_intended_is_graceful_success_noop():
    """When nothing is intended, the tree succeeds and no arm does work."""
    ran: set[str] = set()
    tree = _build(
        PublicationIntentDecision(
            publish_exploit=False, publish_fix=False, publish_report=False
        ),
        ran,
    )
    assert _tick_to_completion(tree) == Status.SUCCESS
    assert ran == set()


def test_prepare_failure_fails_intended_arm():
    """A genuine Prepare failure in an intended arm fails the whole tree."""
    ran: set[str] = set()

    class _FailingPrepare(py_trees.behaviour.Behaviour):
        def update(self):
            return Status.FAILURE

    tree = create_publication_tree(
        case_id=CASE_ID,
        prioritize_publication_intents_factory=_intent_factory(
            PublicationIntentDecision(publish_fix=True, publish_report=True)
        ),
        prepare_fix_factory=lambda n: _FailingPrepare(name=n),
        prepare_report_factory=lambda n: _RecordingPrepare(n, ran),
        publish_factory=lambda n: _RecordingPublish(n, ran),
    )
    assert _tick_to_completion(tree) == Status.FAILURE
