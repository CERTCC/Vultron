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

"""Unit tests for embargo cascade/persistence nodes (cascade.py)."""

import logging
from unittest.mock import patch

import py_trees

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.cascade import (
    CommitLogCascadeNode,
    PersistEmbargoEventNode,
)
from vultron.core.models.embargo_event import EmbargoEvent as CoreEmbargoEvent
from vultron.core.states.em import EM

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)


def _make_core_embargo(suffix: str = "1") -> CoreEmbargoEvent:
    """Create a minimal core-layer EmbargoEvent for persistence tests."""
    return CoreEmbargoEvent(
        id_=f"https://example.org/embargo_events/e{suffix}",
        context=f"https://example.org/cases/case_{suffix}",
    )


def _setup_blackboard_null_dl() -> None:
    """Populate blackboard with datalayer=None to exercise null-DL guards."""
    py_trees.blackboard.Blackboard.enable_activity_stream()
    blackboard = py_trees.blackboard.Client(name="test-null-dl")
    blackboard.register_key(
        key="datalayer", access=py_trees.common.Access.WRITE
    )
    blackboard.register_key(
        key="actor_id", access=py_trees.common.Access.WRITE
    )
    blackboard.datalayer = None
    blackboard.actor_id = None


class TestPersistEmbargoEventNode:
    """Tests for PersistEmbargoEventNode."""

    def test_persists_embargo_event_on_success(self):
        """Node persists a new EmbargoEvent and returns SUCCESS."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        embargo = _make_core_embargo("pen1")

        setup_blackboard(dl)
        node = PersistEmbargoEventNode(embargo=embargo)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        stored = dl.read(embargo.id_)
        assert stored is not None
        assert getattr(stored, "id_", None) == embargo.id_

    def test_idempotent_when_already_exists(self, caplog):
        """Node returns SUCCESS and logs WARNING when event already persisted."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        embargo = _make_core_embargo("pen2")
        dl.create(embargo)  # pre-persist

        setup_blackboard(dl)
        node = PersistEmbargoEventNode(embargo=embargo)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.WARNING):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert any("already exists" in r.message for r in caplog.records)

    def test_returns_failure_when_datalayer_unavailable(self):
        """Node returns FAILURE when the DataLayer is None on the blackboard."""
        embargo = _make_core_embargo("pen3")

        _setup_blackboard_null_dl()

        node = PersistEmbargoEventNode(embargo=embargo)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE


class TestCommitLogCascadeNode:
    """Tests for CommitLogCascadeNode."""

    def test_returns_success_and_skips_when_case_id_empty(self, caplog):
        """Node returns SUCCESS with a warning when case_id is empty."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        setup_blackboard(dl)

        node = CommitLogCascadeNode(
            case_id="",
            object_id="https://example.org/obj/1",
            event_type="test_event",
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.WARNING):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert any("cascade skipped" in r.message for r in caplog.records)

    def test_returns_success_and_skips_when_object_id_empty(self, caplog):
        """Node returns SUCCESS with a warning when object_id is empty."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        setup_blackboard(dl)

        node = CommitLogCascadeNode(
            case_id="https://example.org/cases/c1",
            object_id="",
            event_type="test_event",
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.WARNING):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert any("cascade skipped" in r.message for r in caplog.records)

    def test_returns_success_when_datalayer_unavailable(self):
        """Node returns SUCCESS (idempotent) when DataLayer is None."""
        _setup_blackboard_null_dl()

        node = CommitLogCascadeNode(
            case_id="https://example.org/cases/c1",
            object_id="https://example.org/obj/1",
            event_type="test_event",
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_success_and_skips_when_no_case_actor(self, caplog):
        """Node returns SUCCESS with warning when CaseActor cannot be resolved."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("clcn1", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = CommitLogCascadeNode(
            case_id=case.id_,
            object_id="https://example.org/obj/1",
            event_type="test_event",
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.WARNING):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert any("cascade skipped" in r.message for r in caplog.records)

    def test_returns_failure_when_cascade_raises(self, caplog):
        """Node returns FAILURE (BT-14-001) when commit_log_entry_trigger raises."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("clcn2", em_state=EM.ACTIVE)
        dl.create(case)
        setup_blackboard(dl)

        node = CommitLogCascadeNode(
            case_id=case.id_,
            object_id="https://example.org/obj/1",
            event_type="test_event",
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        target = "vultron.core.use_cases.received.actor" "._find_case_actor_id"
        with (
            patch(target, return_value="https://example.org/actors/ca"),
            patch(
                "vultron.core.use_cases.triggers.sync"
                ".commit_log_entry_trigger",
                side_effect=RuntimeError("boom"),
            ),
            caplog.at_level(logging.ERROR),
        ):
            bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
        assert any("BT-14-001" in r.message for r in caplog.records)
