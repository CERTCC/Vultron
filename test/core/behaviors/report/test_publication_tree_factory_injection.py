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
"""End-to-end tick tests for create_publication_tree (Production Collapses 2 + 4).

Verifies that the intent record produced by the Evaluator actually gates which
per-artifact arms perform Prepare→Submit work, and that a not-intended arm is
a graceful SUCCESS no-op (ADR-0028 / BT-20-002, AC-4).  The terminal publish
leaf has been replaced by the draft-review-submit pipeline (ADR-0030 / BT-20-004).
"""

import py_trees
from py_trees.common import Status

from test.support.call_out import (
    no as call_out_no,
    yes as call_out_yes,
    yes_with,
)
from vultron.core.behaviors.call_out.answer import CallOutAnswer
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.report.publication_intent import (
    INTENT_DECISION_KEY,
    PublicationIntentDecision,
)
from vultron.core.behaviors.report.publication_tree import (
    create_publication_tree,
)
from vultron.demo.fuzzer.bundles.publication import PublicationCallOutBundle

CASE_ID = "https://example.org/cases/test-001"


class _RecordingPrepare(CallOutBackend):
    """Composer stand-in that records that it ran and always succeeds."""

    def __init__(self, name, ran):
        super().__init__(name=name)
        self._ran = ran

    def answer(self) -> CallOutAnswer:
        self._ran.add(self.name)
        return CallOutAnswer.yes()


class _RecordingSubmit(CallOutBackend):
    """Actuator stand-in that records that it ran and always succeeds."""

    def __init__(self, name, ran):
        super().__init__(name=name)
        self._ran = ran

    def answer(self) -> CallOutAnswer:
        self._ran.add(self.name)
        return CallOutAnswer.yes()


def _intent_factory(decision):
    """Return an Evaluator factory that answers *yes* with a fixed intent record."""
    return yes_with({INTENT_DECISION_KEY: decision})


def _tick_to_completion(tree):
    bt = py_trees.trees.BehaviourTree(root=tree)
    bt.setup()
    for _ in range(10):
        bt.tick()
        if bt.root.status in (Status.SUCCESS, Status.FAILURE):
            break
    return bt.root.status


_always_succeed_factory = call_out_yes


def _build(decision, ran):
    bundle = PublicationCallOutBundle(
        prioritize_publication_intents_factory=_intent_factory(decision),  # type: ignore[arg-type]
        prepare_exploit_factory=lambda n: _RecordingPrepare(n, ran),  # type: ignore[arg-type]
        prepare_fix_factory=lambda n: _RecordingPrepare(n, ran),  # type: ignore[arg-type]
        prepare_report_factory=lambda n: _RecordingPrepare(n, ran),  # type: ignore[arg-type]
        draft_advisory_artifact_factory=_always_succeed_factory,  # type: ignore[arg-type]
        review_advisory_draft_factory=_always_succeed_factory,  # type: ignore[arg-type]
        revise_advisory_draft_factory=_always_succeed_factory,  # type: ignore[arg-type]
        submit_advisory_artifact_factory=lambda n: _RecordingSubmit(n, ran),  # type: ignore[arg-type]
    )
    return create_publication_tree(case_id=CASE_ID, call_out=bundle)


def test_default_intents_publish_fix_and_report_only():
    """Default intent record runs the fix + report arms, skips exploit."""
    ran: set[str] = set()
    tree = _build(PublicationIntentDecision(), ran)
    assert _tick_to_completion(tree) == Status.SUCCESS
    assert "PrepareExploit" not in ran
    assert not any(
        n.startswith("SubmitAdvisoryArtifact") and "Exploit" in n for n in ran
    )
    assert {
        "PrepareFix",
        "PrepareReport",
    } <= ran
    # The Submit nodes (not just Prepare) ran for the intended arms.
    assert any(
        n.startswith("SubmitAdvisoryArtifact") and "Fix" in n for n in ran
    )
    assert any(
        n.startswith("SubmitAdvisoryArtifact") and "Report" in n for n in ran
    )


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
        "PrepareFix",
        "PrepareReport",
    } <= ran
    # All three submit nodes ran (names are e.g. "SubmitAdvisoryArtifact_Exploit")
    assert any(
        n.startswith("SubmitAdvisoryArtifact") and "Exploit" in n for n in ran
    )
    assert any(
        n.startswith("SubmitAdvisoryArtifact") and "Fix" in n for n in ran
    )
    assert any(
        n.startswith("SubmitAdvisoryArtifact") and "Report" in n for n in ran
    )


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

    bundle = PublicationCallOutBundle(
        prioritize_publication_intents_factory=_intent_factory(  # type: ignore[arg-type]
            PublicationIntentDecision(publish_fix=True, publish_report=True)
        ),
        prepare_fix_factory=call_out_no,  # type: ignore[arg-type]
        prepare_report_factory=lambda n: _RecordingPrepare(n, ran),  # type: ignore[arg-type]
        draft_advisory_artifact_factory=_always_succeed_factory,  # type: ignore[arg-type]
        review_advisory_draft_factory=_always_succeed_factory,  # type: ignore[arg-type]
        revise_advisory_draft_factory=_always_succeed_factory,  # type: ignore[arg-type]
        submit_advisory_artifact_factory=lambda n: _RecordingSubmit(n, ran),  # type: ignore[arg-type]
    )
    tree = create_publication_tree(case_id=CASE_ID, call_out=bundle)
    assert _tick_to_completion(tree) == Status.FAILURE
