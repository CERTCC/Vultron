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

"""Structure of the embargo trigger trees.

Per RSH-04-002 every EM mutation BT node MUST be followed by a CaseStatus
declaration via ``EmitCaseStatusUpdateNode`` (issue #2175).  A trigger writes
shared EM state only as the CASE_MANAGER (EP-09-008), so the mutation, its
ledger commit (#4085) and the declaration all sit in the CASE_MANAGER arm,
in that order, and the other arm declares nothing.
"""

import py_trees
import pytest

from vultron.core.behaviors.case_status_snapshot import (
    EmitCaseStatusUpdateNode,
)
from vultron.core.behaviors.embargo.nodes import (
    AbandonEmbargoProposalsLifecycleNode,
    AcceptEmbargoLifecycleNode,
    CommitEmbargoAbandonmentNode,
    CommitEmbargoDecisionNode,
    CommitEmbargoTeardownNode,
    LeaveAbandonmentToCaseManagerNode,
    ProposeEmbargoLifecycleNode,
    ReadOpenEmbargoProposalsNode,
    RejectEmbargoLifecycleNode,
    TerminateEmbargoLifecycleNode,
)
from vultron.core.behaviors.embargo.trigger_tree import (
    ABANDONMENT_LEFT_TO_CASE_MANAGER,
    accept_embargo_trigger_bt,
    propose_embargo_revision_trigger_bt,
    propose_embargo_trigger_bt,
    reject_embargo_trigger_bt,
    reject_proposed_embargo_bt,
    terminate_embargo_bt,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.states.embargo_register import TerminationReason
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

CASE_ID = "https://example.org/cases/case-trigger-tree"
ACTOR_ID = "https://example.org/actors/proposer"
EMBARGO_ID = "https://example.org/cases/case-trigger-tree/embargos/e1"


def _collect_nodes(
    node: py_trees.behaviour.Behaviour,
) -> list[py_trees.behaviour.Behaviour]:
    result = [node]
    for child in getattr(node, "children", []):
        result.extend(_collect_nodes(child))
    return result


def _child_types(
    node: py_trees.behaviour.Behaviour,
) -> list[str]:
    return [type(c).__name__ for c in getattr(node, "children", [])]


def _top_level_children(
    root: py_trees.behaviour.Behaviour,
) -> list[py_trees.behaviour.Behaviour]:
    return list(getattr(root, "children", []))


@pytest.fixture
def dummy_embargo() -> "as_EmbargoEvent":
    return as_EmbargoEvent(
        id_=EMBARGO_ID,
        context=CASE_ID,
        end_time=days_from_now_utc(45),
    )


@pytest.fixture
def result_out() -> dict:
    return {}


@pytest.fixture
def activity_builder():
    return lambda _to: ("", "")


def _arm(
    tree: py_trees.behaviour.Behaviour, suffix: str
) -> list[py_trees.behaviour.Behaviour]:
    """Pre-order descendants of the one role arm whose name ends *suffix*."""
    arms = [n for n in _collect_nodes(tree) if n.name.endswith(suffix)]
    assert len(arms) == 1, [n.name for n in arms]
    return _collect_nodes(arms[0])


def _assert_manager_arm_order(
    tree: py_trees.behaviour.Behaviour,
    lifecycle_type: type,
    commit_type: type = CommitEmbargoDecisionNode,
    other_suffix: str = "AskCaseManager",
) -> None:
    """Write → commit → declare, as the CASE_MANAGER only."""
    manager = _arm(tree, "AsCaseManager")
    index = {type(n): i for i, n in reversed(list(enumerate(manager)))}
    for needed in (lifecycle_type, commit_type, EmitCaseStatusUpdateNode):
        assert needed in index, f"{needed.__name__} missing from manager arm"
    assert (
        index[lifecycle_type]
        < index[commit_type]
        < index[EmitCaseStatusUpdateNode]
    ), "the EM write is committed before it is declared"
    other = _arm(tree, other_suffix)
    assert not any(
        isinstance(n, (lifecycle_type, commit_type, EmitCaseStatusUpdateNode))
        for n in other
    ), "a non-manager writes, commits and declares nothing (EP-09-008)"


@pytest.mark.spec("RSH-04-002")
@pytest.mark.spec("EP-09-008")
class TestProposeEmbargoTriggerBt:
    def test_manager_arm_writes_commits_then_declares(
        self, dummy_embargo, result_out, activity_builder
    ):
        tree = propose_embargo_trigger_bt(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            embargo=dummy_embargo,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        _assert_manager_arm_order(tree, ProposeEmbargoLifecycleNode)


@pytest.mark.spec("RSH-04-002")
@pytest.mark.spec("EP-09-008")
class TestProposeEmbargoRevisionTriggerBt:
    def test_manager_arm_writes_commits_then_declares(
        self, dummy_embargo, result_out, activity_builder
    ):
        tree = propose_embargo_revision_trigger_bt(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            embargo=dummy_embargo,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        _assert_manager_arm_order(tree, ProposeEmbargoLifecycleNode)


@pytest.mark.spec("RSH-04-002")
@pytest.mark.spec("EP-09-008")
class TestAcceptEmbargoTriggerBt:
    def test_manager_arm_writes_commits_then_declares(
        self, result_out, activity_builder
    ):
        tree = accept_embargo_trigger_bt(
            case_id=CASE_ID,
            embargo_id=EMBARGO_ID,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        _assert_manager_arm_order(tree, AcceptEmbargoLifecycleNode)


@pytest.mark.spec("RSH-04-002")
@pytest.mark.spec("EP-09-008")
class TestRejectEmbargoTriggerBt:
    def test_manager_arm_writes_commits_then_declares(
        self, result_out, activity_builder
    ):
        tree = reject_embargo_trigger_bt(
            case_id=CASE_ID,
            embargo_id=EMBARGO_ID,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        _assert_manager_arm_order(tree, RejectEmbargoLifecycleNode)


@pytest.mark.spec("RSH-04-002")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("EMB-16-001")
class TestRejectProposedEmbargoBt:
    def test_manager_arm_writes_commits_then_declares(self, result_out):
        tree = reject_proposed_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
        )
        _assert_manager_arm_order(
            tree,
            AbandonEmbargoProposalsLifecycleNode,
            CommitEmbargoAbandonmentNode,
            other_suffix=ABANDONMENT_LEFT_TO_CASE_MANAGER,
        )

    @pytest.mark.spec("EMB-16-002")
    def test_non_manager_arm_neither_writes_nor_asks(self, result_out):
        tree = reject_proposed_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
        )
        assert not any(
            n.name.endswith("AskCaseManager") for n in _collect_nodes(tree)
        ), "the non-manager arm asks nothing, and is not named as if it did"
        other = _arm(tree, ABANDONMENT_LEFT_TO_CASE_MANAGER)
        assert any(
            isinstance(n, LeaveAbandonmentToCaseManagerNode) for n in other
        )
        assert not any(
            isinstance(n, ReadOpenEmbargoProposalsNode) for n in other
        ), "only the manager reads the proposals it answers"
        manager = _arm(tree, "AsCaseManager")
        assert any(
            isinstance(n, ReadOpenEmbargoProposalsNode) for n in manager
        )


@pytest.mark.spec("RSH-04-002")
@pytest.mark.spec("EP-09-008")
class TestTerminateEmbargoBt:
    def test_manager_arm_writes_commits_then_declares(
        self, result_out, activity_builder
    ):
        tree = terminate_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
            reason=TerminationReason.EARLY,
            activity_builder=activity_builder,
        )
        _assert_manager_arm_order(tree, TerminateEmbargoLifecycleNode)

    def test_cascade_manager_arm_writes_commits_then_declares(
        self, result_out
    ):
        tree = terminate_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
            reason=TerminationReason.EARLY,
        )
        _assert_manager_arm_order(
            tree, TerminateEmbargoLifecycleNode, CommitEmbargoTeardownNode
        )

    def test_emit_node_present_without_activity_builder(self, result_out):
        tree = terminate_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
            reason=TerminationReason.EARLY,
        )
        all_nodes = _collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]
        assert "EmitCaseStatusUpdateNode" in node_types, (
            "EmitCaseStatusUpdateNode must be present in terminate_embargo_bt"
            " even without an activity_builder (cascade path)"
        )
