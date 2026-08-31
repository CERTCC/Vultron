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

"""Unit tests for _SendEmbargoActivityBase in emit.py."""

from unittest.mock import MagicMock, patch

import py_trees
import pytest

from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.emit import _SendEmbargoActivityBase
from vultron.core.states.em import EM

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    make_case_with_manager,
    setup_blackboard,
)

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case_emit1"
EMBARGO_ID = "https://example.org/cases/case_emit1/embargo_events/e1"
ACTIVITY_ID = "https://example.org/activities/act1"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


def _make_concrete(
    *,
    factory_missing_returns: Status = Status.FAILURE,
    resolve_result: "tuple[str, str] | Status" = (
        EMBARGO_ID,
        CASE_MANAGER_ACTOR,
    ),
    call_result: "tuple[str, str] | Exception" = (ACTIVITY_ID, "{}"),
    outbox_fail_returns: Status = Status.FAILURE,
) -> "_SendEmbargoActivityBase":
    """Create a minimal concrete subclass for contract testing."""

    class _ConcreteNode(_SendEmbargoActivityBase, register=False):
        def _on_factory_unavailable(self) -> Status:
            return factory_missing_returns

        def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
            return resolve_result

        def _call_factory(
            self, _actor_id: str, _embargo_id: str, _case_manager_id: str
        ) -> tuple[str, object]:
            if isinstance(call_result, Exception):
                raise call_result
            return call_result

        def _on_outbox_write_failure(
            self, _activity_id: str, _exc: Exception
        ) -> Status:
            return outbox_fail_returns

    return _ConcreteNode(case_id=CASE_ID, name="_ConcreteNode")


def _setup_with_factory(dl: SqliteDataLayer, factory: MagicMock) -> None:
    py_trees.blackboard.Blackboard.enable_activity_stream()
    bb = py_trees.blackboard.Client(name="test-emit-setup")
    for key in ("datalayer", "actor_id", "trigger_activity_factory"):
        bb.register_key(key=key, access=py_trees.common.Access.WRITE)
    bb.datalayer = dl
    bb.actor_id = ACTOR_ID
    bb.trigger_activity_factory = factory


class TestSendEmbargoActivityBaseContract:
    """Contract tests for _SendEmbargoActivityBase dispatch skeleton."""

    def test_success_path_calls_factory_and_queues(self):
        """Happy-path: factory called and activity queued to outbox."""
        _, _, dl = make_case_with_manager("emit1", em_state=EM.ACTIVE)
        factory = MagicMock()
        _setup_with_factory(dl, factory)

        node = _make_concrete()
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == Status.SUCCESS

    def test_factory_unavailable_delegates_to_hook(self):
        """When factory is None, _on_factory_unavailable determines the status."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        setup_blackboard(dl, actor_id=ACTOR_ID)

        for expected in (Status.SUCCESS, Status.FAILURE):
            py_trees.blackboard.Blackboard.storage.clear()
            setup_blackboard(dl, actor_id=ACTOR_ID)

            node = _make_concrete(factory_missing_returns=expected)
            bt = py_trees.trees.BehaviourTree(root=node)
            bt.setup()
            bt.tick()

            assert node.status == expected

    def test_resolve_failure_propagated(self):
        """When _resolve_embargo_and_manager returns FAILURE, update() returns FAILURE."""
        _, _, dl = make_case_with_manager("emit2", em_state=EM.ACTIVE)
        factory = MagicMock()
        _setup_with_factory(dl, factory)

        node = _make_concrete(resolve_result=Status.FAILURE)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == Status.FAILURE
        factory.assert_not_called()

    def test_resolve_success_skip_propagated(self):
        """When _resolve_embargo_and_manager returns SUCCESS (graceful skip), no factory call."""
        _, _, dl = make_case_with_manager("emit3", em_state=EM.ACTIVE)
        factory = MagicMock()
        _setup_with_factory(dl, factory)

        node = _make_concrete(resolve_result=Status.SUCCESS)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == Status.SUCCESS
        factory.assert_not_called()

    def test_factory_exception_returns_failure(self):
        """When _call_factory raises, update() returns FAILURE."""
        _, _, dl = make_case_with_manager("emit4", em_state=EM.ACTIVE)
        factory = MagicMock()
        _setup_with_factory(dl, factory)

        node = _make_concrete(call_result=RuntimeError("factory boom"))
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == Status.FAILURE

    def test_outbox_write_failure_delegates_to_hook(self):
        """When outbox write fails, _on_outbox_write_failure determines the status."""
        _, _, dl = make_case_with_manager("emit5", em_state=EM.ACTIVE)
        factory = MagicMock()
        _setup_with_factory(dl, factory)

        patch_target = (
            "vultron.core.behaviors.embargo.nodes.emit.add_activity_to_outbox"
        )
        for expected in (Status.SUCCESS, Status.FAILURE):
            py_trees.blackboard.Blackboard.storage.clear()
            _setup_with_factory(dl, factory)

            node = _make_concrete(outbox_fail_returns=expected)
            bt = py_trees.trees.BehaviourTree(root=node)
            bt.setup()

            with patch(patch_target, side_effect=RuntimeError("outbox error")):
                bt.tick()

            assert node.status == expected

    def test_missing_datalayer_returns_failure(self):
        """FAILURE when blackboard has no datalayer."""
        py_trees.blackboard.Blackboard.enable_activity_stream()
        bb = py_trees.blackboard.Client(name="test-no-dl")
        for key in ("datalayer", "actor_id", "trigger_activity_factory"):
            bb.register_key(key=key, access=py_trees.common.Access.WRITE)
        bb.datalayer = None
        bb.actor_id = ACTOR_ID
        bb.trigger_activity_factory = MagicMock()

        node = _make_concrete()
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == Status.FAILURE
