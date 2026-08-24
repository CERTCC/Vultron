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

"""Typed-Ports isolation tests for inbox pipeline nodes (AC-2, issue #1887).

Covers BTND-03-011 (NoDataAvailable on missing required port) for each
migrated inbox node, plus a happy-path write test for BuildOutcomeNode.
"""

import py_trees
import pytest
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.inbox.nodes.pipeline import (
    BuildOutcomeNode,
    DeferCheckNode,
    DispatchNode,
    ExtractSemanticsNode,
    KEY_ACTIVITY,
    KEY_DISPATCH,
    KEY_EVENT,
    KEY_INGRESS,
    KEY_OUTCOME_STATUS,
    KEY_PAYLOAD,
    ParsePayloadNode,
    RehydrateActivityNode,
)


@pytest.fixture(autouse=True)
def _clear_blackboard():
    yield
    py_trees.blackboard.Blackboard.enable_activity_stream()
    py_trees.blackboard.Blackboard.storage.clear()
    py_trees.blackboard.Blackboard.clients.clear()


# ---------------------------------------------------------------------------
# ParsePayloadNode
# ---------------------------------------------------------------------------


class TestParsePayloadNodePorts:
    def test_missing_inbox_payload_raises_no_data_available(self) -> None:
        node = ParsePayloadNode(name="ParsePayloadNode")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input(KEY_PAYLOAD)

    def test_missing_inbox_ingress_raises_no_data_available(self) -> None:
        node = ParsePayloadNode(name="ParsePayloadNode")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input(KEY_INGRESS)


# ---------------------------------------------------------------------------
# RehydrateActivityNode
# ---------------------------------------------------------------------------


class TestRehydrateActivityNodePorts:
    def test_missing_inbox_activity_in_raises_no_data_available(self) -> None:
        node = RehydrateActivityNode(name="RehydrateActivityNode")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input(RehydrateActivityNode._PORT_ACTIVITY_IN)

    def test_missing_inbox_ingress_raises_no_data_available(self) -> None:
        node = RehydrateActivityNode(name="RehydrateActivityNode")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input(KEY_INGRESS)


# ---------------------------------------------------------------------------
# ExtractSemanticsNode
# ---------------------------------------------------------------------------


class TestExtractSemanticsNodePorts:
    def test_missing_inbox_activity_raises_no_data_available(self) -> None:
        node = ExtractSemanticsNode(name="ExtractSemanticsNode")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input(KEY_ACTIVITY)


# ---------------------------------------------------------------------------
# DeferCheckNode
# ---------------------------------------------------------------------------


class TestDeferCheckNodePorts:
    def test_missing_inbox_event_raises_no_data_available(self) -> None:
        node = DeferCheckNode(name="DeferCheckNode")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input(KEY_EVENT)


# ---------------------------------------------------------------------------
# DispatchNode
# ---------------------------------------------------------------------------


class TestDispatchNodePorts:
    def test_missing_inbox_event_raises_no_data_available(self) -> None:
        node = DispatchNode(name="DispatchNode")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input(KEY_EVENT)

    def test_missing_inbox_dispatch_raises_no_data_available(self) -> None:
        node = DispatchNode(name="DispatchNode")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input(KEY_DISPATCH)


# ---------------------------------------------------------------------------
# BuildOutcomeNode — writes inbox_outcome_status = "processed"
# ---------------------------------------------------------------------------


class TestBuildOutcomeNodePorts:
    def test_writes_processed_outcome(self) -> None:
        """BuildOutcomeNode writes 'processed' to /inbox_outcome_status."""
        node = BuildOutcomeNode(name="BuildOutcomeNode")
        tree = py_trees.trees.BehaviourTree(root=node)
        tree.setup()
        tree.tick()
        assert node.status == Status.SUCCESS
        stored = py_trees.blackboard.Blackboard.storage.get(
            f"/{KEY_OUTCOME_STATUS}"
        )
        assert stored == "processed"
