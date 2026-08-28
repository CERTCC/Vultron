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

"""Tests verifying EmitCaseStatusUpdateNode is wired into embargo trigger trees.

Per RSH-04-002: every EM mutation BT node MUST be immediately followed by a
CaseStatus ledger write via EmitCaseStatusUpdateNode (issue #2175).
"""

import py_trees
import pytest

from vultron.core.behaviors.embargo.nodes import (
    AcceptEmbargoLifecycleNode,
    RejectEmbargoLifecycleNode,
    RejectProposedEmbargoLifecycleNode,
    TerminateEmbargoLifecycleNode,
)
from vultron.core.behaviors.embargo.trigger_tree import (
    accept_embargo_trigger_bt,
    propose_embargo_trigger_bt,
    propose_embargo_revision_trigger_bt,
    reject_embargo_trigger_bt,
    reject_proposed_embargo_bt,
    terminate_embargo_bt,
)
from vultron.core.behaviors.status.nodes import EmitCaseStatusUpdateNode
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

CASE_ID = "https://example.org/cases/case-trigger-tree"
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
    )


@pytest.fixture
def result_out() -> dict:
    return {}


@pytest.fixture
def activity_builder():
    return lambda _: []


class TestProposeEmbargoTriggerBt:
    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_present(
        self, dummy_embargo, result_out, activity_builder
    ):
        tree = propose_embargo_trigger_bt(
            case_id=CASE_ID,
            embargo=dummy_embargo,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        all_nodes = _collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]
        assert (
            "EmitCaseStatusUpdateNode" in node_types
        ), "EmitCaseStatusUpdateNode must be present in propose_embargo_trigger_bt (RSH-04-002)"

    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_after_lifecycle_node(
        self, dummy_embargo, result_out, activity_builder
    ):
        tree = propose_embargo_trigger_bt(
            case_id=CASE_ID,
            embargo=dummy_embargo,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        children = _top_level_children(tree)
        child_types = [type(c).__name__ for c in children]
        persist_idx = next(
            (
                i
                for i, t in enumerate(child_types)
                if "PersistEmbargoEvent" in t
            ),
            None,
        )
        emit_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, EmitCaseStatusUpdateNode)
            ),
            None,
        )
        assert (
            emit_idx is not None
        ), "EmitCaseStatusUpdateNode must be a direct child"
        assert persist_idx is not None
        assert (
            emit_idx > persist_idx
        ), "EmitCaseStatusUpdateNode must appear after PersistEmbargoEventNode"


class TestProposeEmbargoRevisionTriggerBt:
    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_present(
        self, dummy_embargo, result_out, activity_builder
    ):
        tree = propose_embargo_revision_trigger_bt(
            case_id=CASE_ID,
            embargo=dummy_embargo,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        all_nodes = _collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]
        assert (
            "EmitCaseStatusUpdateNode" in node_types
        ), "EmitCaseStatusUpdateNode must be present in propose_embargo_revision_trigger_bt (RSH-04-002)"

    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_after_persist_node(
        self, dummy_embargo, result_out, activity_builder
    ):
        tree = propose_embargo_revision_trigger_bt(
            case_id=CASE_ID,
            embargo=dummy_embargo,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        children = _top_level_children(tree)
        child_types = [type(c).__name__ for c in children]
        persist_idx = next(
            (
                i
                for i, t in enumerate(child_types)
                if "PersistEmbargoEvent" in t
            ),
            None,
        )
        emit_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, EmitCaseStatusUpdateNode)
            ),
            None,
        )
        assert (
            emit_idx is not None
        ), "EmitCaseStatusUpdateNode must be a direct child"
        assert persist_idx is not None
        assert emit_idx > persist_idx


class TestAcceptEmbargoTriggerBt:
    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_present(self, result_out, activity_builder):
        tree = accept_embargo_trigger_bt(
            case_id=CASE_ID,
            embargo_id=EMBARGO_ID,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        all_nodes = _collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]
        assert (
            "EmitCaseStatusUpdateNode" in node_types
        ), "EmitCaseStatusUpdateNode must be present in accept_embargo_trigger_bt (RSH-04-002)"

    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_after_lifecycle_node(
        self, result_out, activity_builder
    ):
        tree = accept_embargo_trigger_bt(
            case_id=CASE_ID,
            embargo_id=EMBARGO_ID,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        children = _top_level_children(tree)
        lifecycle_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, AcceptEmbargoLifecycleNode)
            ),
            None,
        )
        emit_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, EmitCaseStatusUpdateNode)
            ),
            None,
        )
        assert (
            lifecycle_idx is not None
        ), "AcceptEmbargoLifecycleNode must be present"
        assert emit_idx is not None, "EmitCaseStatusUpdateNode must be present"
        assert (
            emit_idx == lifecycle_idx + 1
        ), "EmitCaseStatusUpdateNode must immediately follow AcceptEmbargoLifecycleNode"


class TestRejectEmbargoTriggerBt:
    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_present(self, result_out, activity_builder):
        tree = reject_embargo_trigger_bt(
            case_id=CASE_ID,
            embargo_id=EMBARGO_ID,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        all_nodes = _collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]
        assert (
            "EmitCaseStatusUpdateNode" in node_types
        ), "EmitCaseStatusUpdateNode must be present in reject_embargo_trigger_bt (RSH-04-002)"

    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_after_lifecycle_node(
        self, result_out, activity_builder
    ):
        tree = reject_embargo_trigger_bt(
            case_id=CASE_ID,
            embargo_id=EMBARGO_ID,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        children = _top_level_children(tree)
        lifecycle_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, RejectEmbargoLifecycleNode)
            ),
            None,
        )
        emit_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, EmitCaseStatusUpdateNode)
            ),
            None,
        )
        assert lifecycle_idx is not None
        assert emit_idx is not None
        assert (
            emit_idx == lifecycle_idx + 1
        ), "EmitCaseStatusUpdateNode must immediately follow RejectEmbargoLifecycleNode"


class TestRejectProposedEmbargoBt:
    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_present(self, result_out):
        tree = reject_proposed_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
        )
        all_nodes = _collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]
        assert (
            "EmitCaseStatusUpdateNode" in node_types
        ), "EmitCaseStatusUpdateNode must be present in reject_proposed_embargo_bt (RSH-04-002)"

    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_after_lifecycle_node(self, result_out):
        tree = reject_proposed_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
        )
        children = _top_level_children(tree)
        lifecycle_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, RejectProposedEmbargoLifecycleNode)
            ),
            None,
        )
        emit_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, EmitCaseStatusUpdateNode)
            ),
            None,
        )
        assert lifecycle_idx is not None
        assert emit_idx is not None
        assert (
            emit_idx == lifecycle_idx + 1
        ), "EmitCaseStatusUpdateNode must immediately follow RejectProposedEmbargoLifecycleNode"


class TestTerminateEmbargoBt:
    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_present(self, result_out, activity_builder):
        tree = terminate_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        all_nodes = _collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]
        assert (
            "EmitCaseStatusUpdateNode" in node_types
        ), "EmitCaseStatusUpdateNode must be present in terminate_embargo_bt (RSH-04-002)"

    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_after_lifecycle_node(
        self, result_out, activity_builder
    ):
        tree = terminate_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
            activity_builder=activity_builder,
        )
        children = _top_level_children(tree)
        lifecycle_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, TerminateEmbargoLifecycleNode)
            ),
            None,
        )
        emit_idx = next(
            (
                i
                for i, c in enumerate(children)
                if isinstance(c, EmitCaseStatusUpdateNode)
            ),
            None,
        )
        assert lifecycle_idx is not None
        assert emit_idx is not None
        assert (
            emit_idx == lifecycle_idx + 1
        ), "EmitCaseStatusUpdateNode must immediately follow TerminateEmbargoLifecycleNode"

    @pytest.mark.spec("RSH-04-002")
    def test_emit_node_present_without_activity_builder(self, result_out):
        tree = terminate_embargo_bt(
            case_id=CASE_ID,
            result_out=result_out,
        )
        all_nodes = _collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]
        assert "EmitCaseStatusUpdateNode" in node_types, (
            "EmitCaseStatusUpdateNode must be present in terminate_embargo_bt"
            " even without an activity_builder (cascade path)"
        )
