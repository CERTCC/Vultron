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

"""Unit tests for BT bridge layer."""

from typing import Any

import pytest
import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

# Test behavior nodes for verifying bridge functionality


class AlwaysSucceed(py_trees.behaviour.Behaviour):
    """Test node that always succeeds immediately."""

    def __init__(self, name: str = "AlwaysSucceed"):
        super().__init__(name=name)

    def update(self) -> Status:
        self.logger.debug("AlwaysSucceed: returning SUCCESS")
        self.feedback_message = "Success"
        return Status.SUCCESS


class AlwaysFail(py_trees.behaviour.Behaviour):
    """Test node that always fails immediately."""

    def __init__(self, name: str = "AlwaysFail"):
        super().__init__(name=name)

    def update(self) -> Status:
        self.logger.debug("AlwaysFail: returning FAILURE")
        self.feedback_message = "Failure"
        return Status.FAILURE


class RunNTimes(py_trees.behaviour.Behaviour):
    """Test node that runs N times before succeeding."""

    def __init__(self, n: int, name: str = "RunNTimes"):
        super().__init__(name=name)
        self.target_ticks = n
        self.tick_count = 0

    def initialise(self) -> None:
        self.tick_count = 0

    def update(self) -> Status:
        self.tick_count += 1
        self.logger.debug(
            f"RunNTimes: tick {self.tick_count}/{self.target_ticks}"
        )

        if self.tick_count < self.target_ticks:
            self.feedback_message = (
                f"Running: {self.tick_count}/{self.target_ticks}"
            )
            return Status.RUNNING

        self.feedback_message = f"Completed after {self.tick_count} ticks"
        return Status.SUCCESS


class CheckBlackboard(py_trees.behaviour.Behaviour):
    """Test node that verifies blackboard data is accessible."""

    def __init__(self, name: str = "CheckBlackboard"):
        super().__init__(name=name)

    def setup(self, **kwargs) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key="datalayer", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="actor_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        try:
            # Verify required keys exist
            datalayer = self.blackboard.datalayer
            actor_id = self.blackboard.actor_id

            if datalayer is None or actor_id is None:
                self.feedback_message = "Missing required blackboard data"
                return Status.FAILURE

            self.feedback_message = f"Blackboard verified for actor {actor_id}"
            return Status.SUCCESS

        except KeyError as e:
            self.feedback_message = f"Missing blackboard key: {e}"
            return Status.FAILURE


class ExceptionNode(py_trees.behaviour.Behaviour):
    """Test node that raises an exception during execution."""

    def __init__(self, name: str = "ExceptionNode"):
        super().__init__(name=name)

    def update(self) -> Status:
        self.logger.debug("ExceptionNode: raising exception")
        raise RuntimeError("Intentional test exception")


# Fixtures


@pytest.fixture
def datalayer():
    """Provide in-memory TinyDB data layer."""
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


@pytest.fixture
def bridge(datalayer):
    """Provide BTBridge instance with data layer."""
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def test_actor_id():
    """Provide test actor ID."""
    return "https://example.org/actors/test-actor"


# Tests for setup_tree


def test_setup_tree_basic(bridge, test_actor_id):
    """Test basic tree setup with actor ID."""
    tree = AlwaysSucceed()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    assert isinstance(bt, py_trees.trees.BehaviourTree)
    assert bt.root == tree


def _read_blackboard():
    """Return a client that can read the blackboard's datalayer and actor_id."""
    blackboard = py_trees.blackboard.Client(name="test")
    blackboard.register_key(
        key="datalayer", access=py_trees.common.Access.READ
    )
    blackboard.register_key(key="actor_id", access=py_trees.common.Access.READ)
    return blackboard


def test_setup_tree_blackboard_datalayer_is_the_executing_actors_store(
    bridge, datalayer, test_actor_id
):
    """BT-05-005: the blackboard datalayer is the store of the blackboard actor_id.

    This used to assert ``blackboard.datalayer == datalayer`` — that the store
    put on the blackboard is exactly the one handed to the bridge.  Under
    ADR-0072 that is the wrong invariant, and asserting it would forbid the fix:
    ``datalayer`` and ``actor_id`` were two independent facts that could
    disagree, which is how a delegated emit created an activity in the
    requester's store and queued it in the CaseActor's outbox.  The store now
    follows the executing actor, so what must hold is that the two agree.
    """
    bt = bridge.setup_tree(tree=CheckBlackboard(), actor_id=test_actor_id)
    bt.setup()

    blackboard = _read_blackboard()
    assert blackboard.actor_id == test_actor_id
    assert blackboard.datalayer.actor_id == test_actor_id
    # The injected store belonged to a different actor, so it was re-scoped.
    assert datalayer.actor_id != test_actor_id
    assert blackboard.datalayer is not datalayer


def test_setup_tree_keeps_the_injected_store_when_it_already_matches(
    datalayer,
):
    """No needless cloning: an already-correct store is passed through as-is.

    The complement of the test above.  Without it, ``_store_for_actor`` could
    satisfy BT-05-005 by cloning unconditionally, which would discard any
    caller-configured state on the injected instance.
    """
    bridge = BTBridge(datalayer=datalayer)
    bt = bridge.setup_tree(tree=CheckBlackboard(), actor_id=datalayer.actor_id)
    bt.setup()

    blackboard = _read_blackboard()
    assert blackboard.actor_id == datalayer.actor_id
    assert blackboard.datalayer is datalayer


def test_setup_tree_with_activity(bridge, test_actor_id):
    """Test blackboard populated with activity."""
    tree = AlwaysSucceed()
    test_activity = {"type": "Create", "object": {"type": "Note"}}

    bt = bridge.setup_tree(
        tree=tree, actor_id=test_actor_id, activity=test_activity
    )
    bt.setup()

    blackboard = py_trees.blackboard.Client(name="test")
    blackboard.register_key(key="activity", access=py_trees.common.Access.READ)

    assert blackboard.activity == test_activity


def test_setup_tree_with_context_data(bridge, test_actor_id):
    """Test blackboard populated with additional context data."""
    tree = AlwaysSucceed()
    context = {"report_id": "report-123", "case_id": "case-456"}

    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id, **context)
    bt.setup()

    blackboard = py_trees.blackboard.Client(name="test")
    blackboard.register_key(
        key="report_id", access=py_trees.common.Access.READ
    )
    blackboard.register_key(key="case_id", access=py_trees.common.Access.READ)

    assert blackboard.report_id == "report-123"
    assert blackboard.case_id == "case-456"


# Tests for execute_tree


def test_execute_tree_success(bridge, test_actor_id):
    """Test successful tree execution returns SUCCESS."""
    tree = AlwaysSucceed()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert isinstance(result, BTExecutionResult)
    assert result.status == Status.SUCCESS
    assert result.feedback_message == "Success"
    assert result.errors is None


def test_execute_tree_failure(bridge, test_actor_id):
    """Test failed tree execution returns FAILURE."""
    tree = AlwaysFail()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert result.status == Status.FAILURE
    assert result.feedback_message == "Failure"
    assert result.errors is None


def test_execute_tree_running_then_success(bridge, test_actor_id):
    """Test tree that runs multiple ticks before succeeding."""
    tree = RunNTimes(n=5)
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert result.status == Status.SUCCESS
    assert "5 ticks" in result.feedback_message
    assert result.errors is None


def test_execute_tree_max_iterations(bridge, test_actor_id):
    """Test tree execution stops at max iterations."""
    tree = RunNTimes(n=200)  # Will never complete within default limit
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt, max_iterations=10)

    assert result.status == Status.FAILURE
    assert "exceeded max iterations" in result.feedback_message
    assert result.errors is not None
    assert len(result.errors) == 1


def test_execute_tree_with_exception(bridge, test_actor_id):
    """Test tree execution handles exceptions gracefully."""
    tree = ExceptionNode()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert result.status == Status.FAILURE
    assert "exception" in result.feedback_message.lower()
    assert result.errors is not None
    assert len(result.errors) == 1


def test_execute_tree_verifies_blackboard_access(bridge, test_actor_id):
    """Test tree can access blackboard data during execution."""
    tree = CheckBlackboard()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert result.status == Status.SUCCESS
    assert test_actor_id in result.feedback_message


# Tests for execute_with_setup (convenience method)


def test_execute_with_setup_success(bridge, test_actor_id):
    """Test convenience method for setup + execution."""
    tree = AlwaysSucceed()

    result = bridge.execute_with_setup(tree=tree, actor_id=test_actor_id)

    assert result.status == Status.SUCCESS
    assert result.errors is None


def test_execute_with_setup_with_activity(bridge, test_actor_id):
    """Test convenience method with activity parameter."""
    tree = AlwaysSucceed()
    test_activity = {"type": "Accept"}

    result = bridge.execute_with_setup(
        tree=tree, actor_id=test_actor_id, activity=test_activity
    )

    assert result.status == Status.SUCCESS


def test_execute_with_setup_with_context(bridge, test_actor_id):
    """Test convenience method with additional context."""
    tree = CheckBlackboard()

    result = bridge.execute_with_setup(
        tree=tree, actor_id=test_actor_id, report_id="test-report"
    )

    assert result.status == Status.SUCCESS


def test_execute_with_setup_custom_max_iterations(bridge, test_actor_id):
    """Test convenience method respects max_iterations parameter."""
    tree = RunNTimes(n=50)

    result = bridge.execute_with_setup(
        tree=tree, actor_id=test_actor_id, max_iterations=10
    )

    assert result.status == Status.FAILURE
    assert "exceeded max iterations" in result.feedback_message


def test_execute_with_setup_releases_bridge_context_keys(
    bridge, test_actor_id
):
    """Bridge releases the datalayer key after execution."""
    tree = AlwaysSucceed()

    result = bridge.execute_with_setup(
        tree=tree, actor_id=test_actor_id, report_id="report-123"
    )

    assert result.status == Status.SUCCESS
    assert "/datalayer" not in py_trees.blackboard.Blackboard.storage


def test_execute_with_setup_restores_preexisting_context(
    bridge, test_actor_id
):
    """Pre-existing blackboard values survive bridge execution."""
    storage = py_trees.blackboard.Blackboard.storage
    sentinel_dl = object()
    storage["/datalayer"] = sentinel_dl

    result = bridge.execute_with_setup(
        tree=AlwaysSucceed(), actor_id=test_actor_id
    )

    assert result.status == Status.SUCCESS
    assert storage["/datalayer"] is sentinel_dl


# Integration tests


def test_bridge_isolates_actor_executions(bridge, datalayer):
    """Test multiple actors have isolated BT executions."""
    actor1 = "https://example.org/actor1"
    actor2 = "https://example.org/actor2"

    result1 = bridge.execute_with_setup(
        tree=CheckBlackboard(), actor_id=actor1, custom_data="actor1-data"
    )

    result2 = bridge.execute_with_setup(
        tree=CheckBlackboard(), actor_id=actor2, custom_data="actor2-data"
    )

    # Both should succeed independently
    assert result1.status == Status.SUCCESS
    assert actor1 in result1.feedback_message

    assert result2.status == Status.SUCCESS
    assert actor2 in result2.feedback_message


def test_bridge_sequential_executions(bridge, test_actor_id):
    """Test multiple sequential BT executions work correctly."""
    results = []

    for i in range(3):
        tree = AlwaysSucceed(name=f"Test-{i}")
        result = bridge.execute_with_setup(tree=tree, actor_id=test_actor_id)
        results.append(result)

    # All should succeed
    assert all(r.status == Status.SUCCESS for r in results)
    assert len(results) == 3


# get_failure_reason tests


def test_get_failure_reason_returns_empty_for_success():
    """get_failure_reason returns '' when tree succeeds."""
    tree = AlwaysSucceed()
    tree.setup()
    tree.tick_once()
    assert BTBridge.get_failure_reason(tree) == ""


def test_get_failure_reason_returns_message_for_leaf_failure():
    """get_failure_reason returns feedback_message from failing leaf."""
    tree = AlwaysFail()
    tree.setup()
    tree.tick_once()
    assert BTBridge.get_failure_reason(tree) == "Failure"


def test_get_failure_reason_returns_class_name_when_no_message():
    """get_failure_reason returns class name when feedback_message is empty."""

    class SilentFail(py_trees.behaviour.Behaviour):
        def update(self) -> Status:
            return Status.FAILURE

    node = SilentFail(name="SilentFail")
    node.setup()
    node.tick_once()
    result = BTBridge.get_failure_reason(node)
    assert result == "SilentFail"


def test_get_failure_reason_finds_first_failing_child():
    """get_failure_reason depth-first finds the first failing child."""
    root = py_trees.composites.Sequence(name="Root", memory=False)
    root.add_children([AlwaysFail(name="FailA"), AlwaysSucceed(name="OkB")])
    root.setup_with_descendants()
    root.tick_once()
    result = BTBridge.get_failure_reason(root)
    assert result == "Failure"


# Log-level tests


@pytest.mark.parametrize("tree_factory", [AlwaysSucceed, AlwaysFail])
def test_final_bt_state_logged_at_debug(
    bridge, test_actor_id, caplog, tree_factory
):
    """Final BT state tree dump is DEBUG-only scaffolding (SL-04-007)."""
    import logging

    tree = tree_factory()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    with caplog.at_level(logging.DEBUG):
        bridge.execute_tree(bt)

    final_state_records = [
        r for r in caplog.records if "Final BT state" in r.message
    ]
    assert final_state_records, "Expected 'Final BT state' log entry"
    assert all(
        r.levelno == logging.DEBUG for r in final_state_records
    ), f"Expected DEBUG but got {final_state_records[0].levelname}"


def test_bt_structure_logged_at_debug(bridge, test_actor_id, caplog):
    """The pre-execution BT structure dump is DEBUG-only (SL-04-007)."""
    import logging

    with caplog.at_level(logging.DEBUG):
        bridge.setup_tree(tree=AlwaysSucceed(), actor_id=test_actor_id)

    structure_records = [
        r for r in caplog.records if "BT structure" in r.message
    ]
    assert structure_records, "Expected 'BT structure' log entry"
    assert all(r.levelno == logging.DEBUG for r in structure_records)


def test_bt_structure_not_emitted_at_info(bridge, test_actor_id, caplog):
    """No 'BT structure' record reaches an INFO-only handler (SL-04-007)."""
    import logging

    with caplog.at_level(logging.INFO):
        bridge.setup_tree(tree=AlwaysSucceed(), actor_id=test_actor_id)

    assert not [r for r in caplog.records if "BT structure" in r.message]


def _completion_records(caplog):
    import logging

    return [
        r
        for r in caplog.records
        if "BT execution completed" in r.getMessage()
        and r.levelno == logging.INFO
    ]


def test_failure_reason_folded_into_completion_line(
    bridge, test_actor_id, caplog
):
    """AC-18: the FAILURE completion line carries a reason, not a bare status.

    ``AlwaysFail`` sets ``feedback_message``, so that is the reason reported.
    """
    import logging

    with caplog.at_level(logging.INFO):
        result = bridge.execute_with_setup(
            tree=AlwaysFail(), actor_id=test_actor_id
        )

    assert result.status == Status.FAILURE
    records = _completion_records(caplog)
    assert records, "Expected a BT completion line at INFO"
    assert "Failure" in records[0].getMessage()


def test_failure_reason_recovered_when_root_has_no_feedback(
    bridge, test_actor_id, caplog
):
    """A silent root reports the failing leaf's identity, not an empty tail.

    Without the ``get_failure_reason()`` fallback this line read
    ``... Status.FAILURE after 1 ticks - `` with nothing after the dash — the
    exact symptom CONCERN-1968 flagged.
    """
    import logging

    root = py_trees.composites.Sequence(name="SilentRoot", memory=False)
    root.add_child(AlwaysFail(name="InnerFail"))

    with caplog.at_level(logging.INFO):
        bridge.execute_with_setup(tree=root, actor_id=test_actor_id)

    records = _completion_records(caplog)
    assert records, "Expected a BT completion line at INFO"
    message = records[0].getMessage()
    assert not message.rstrip().endswith("-"), (
        "FAILURE completion line must not end with a bare dash;"
        f" got {message!r}"
    )
    assert "Failure" in message


def test_only_one_completion_record_per_failure(bridge, test_actor_id, caplog):
    """The reason is folded in, not added as a second INFO record.

    Many callers treat FAILURE as an expected idempotent skip and log their
    own explanation at DEBUG; a second INFO line would triple-log a benign
    no-op.
    """
    import logging

    with caplog.at_level(logging.INFO):
        bridge.execute_with_setup(tree=AlwaysFail(), actor_id=test_actor_id)

    assert len(_completion_records(caplog)) == 1


# ---------------------------------------------------------------------------
# wire_render_port injection tests (AC-4)
# ---------------------------------------------------------------------------


class _StubWireRenderPort:
    """Minimal stub that satisfies the WireRenderPort Protocol."""

    def render(self, obj):
        return {"type": "stub"}


class CheckWireRenderPort(py_trees.behaviour.Behaviour):
    """BT node that verifies wire_render_port is on the blackboard."""

    def setup(self, **kwargs) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key="wire_render_port", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        try:
            port = self.blackboard.wire_render_port
            if port is None:
                self.feedback_message = "wire_render_port is None"
                return Status.FAILURE
            self.feedback_message = "wire_render_port present"
            return Status.SUCCESS
        except KeyError as e:
            self.feedback_message = f"Missing key: {e}"
            return Status.FAILURE


def test_bridge_wire_render_port_published_to_blackboard(
    datalayer, test_actor_id
):
    """AC-4: wire_render_port is placed on the blackboard when provided."""
    stub = _StubWireRenderPort()
    bridge = BTBridge(datalayer=datalayer, wire_render_port=stub)

    tree = CheckWireRenderPort(name="CheckWireRenderPort")
    result = bridge.execute_with_setup(tree=tree, actor_id=test_actor_id)

    assert result.status == Status.SUCCESS, result.feedback_message


def test_bridge_wire_render_port_not_on_blackboard_when_absent(
    bridge, test_actor_id
):
    """AC-4: wire_render_port key is absent from the blackboard when not provided."""
    storage = py_trees.blackboard.Blackboard.storage
    # Run without wire_render_port
    bridge.execute_with_setup(tree=AlwaysSucceed(), actor_id=test_actor_id)
    assert "/wire_render_port" not in storage


def test_bridge_wire_render_port_is_correct_object(datalayer, test_actor_id):
    """The blackboard receives the exact port object passed to BTBridge."""
    stub = _StubWireRenderPort()
    bridge = BTBridge(datalayer=datalayer, wire_render_port=stub)

    bt = bridge.setup_tree(tree=AlwaysSucceed(), actor_id=test_actor_id)
    bt.setup()

    blackboard = py_trees.blackboard.Client(name="test-wire-render")
    blackboard.register_key(
        key="wire_render_port", access=py_trees.common.Access.READ
    )
    assert blackboard.wire_render_port is stub


# ---------------------------------------------------------------------------
# Delegated emit: the ports follow the executing actor too (DL-07-009, #2548)
# ---------------------------------------------------------------------------


class _StoreHoldingPort:
    """A driven-adapter double shaped like the real ones.

    ``TriggerActivityAdapter`` and ``SyncActivityAdapter`` are each constructed
    once per request against the *addressed* actor's store and keep that
    reference in ``self._dl``; ``for_store`` is how they opt into being rebound.
    """

    def __init__(self, dl):
        self._dl = dl

    def for_store(self, dl):
        if dl is self._dl:
            return self
        return type(self)(dl)


class _StatelessPort:
    """A port with no store of its own, so nothing to reconcile."""


class EmitThroughPort(py_trees.behaviour.Behaviour):
    """Reproduces the two-halved write of a delegated emit.

    Creates the activity through the port (as
    ``TriggerActivityAdapter.invite_actor_to_case`` does) and queues its id
    through the blackboard store (as ``EmitInviteActorToCaseNode.update`` does).
    Fails when the store that holds the outbox entry cannot read the activity —
    exactly the state the outbox handler reports as "not found in DataLayer for
    actor ...; skipping delivery".
    """

    def setup(self, **kwargs) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        for key in ("datalayer", "trigger_activity_factory"):
            self.blackboard.register_key(
                key=key, access=py_trees.common.Access.READ
            )

    def update(self) -> Status:
        port = self.blackboard.trigger_activity_factory
        store = self.blackboard.datalayer
        note = as_Note(content="delegated emit")
        port._dl.create(note)
        store.outbox_append(note.id_)
        if store.read(note.id_) is None:
            self.feedback_message = (
                f"activity {note.id_} queued in {store.actor_id}'s outbox is"
                " absent from that actor's own store"
            )
            return Status.FAILURE
        self.feedback_message = "activity and outbox entry share one store"
        return Status.SUCCESS


#: A co-located ``case-actor`` on the same node as the ``datalayer`` fixture's
#: actor.  It must be a *distinct slug*: stores are keyed on the slug, so reusing
#: ``test-actor`` (as the module's ``test_actor_id`` fixture does) would put both
#: actors on one store and every split-store assertion below would pass
#: vacuously.
_CO_HOSTED_CASE_ACTOR = "https://test.example/api/v2/actors/case-actor-abc"


def _ports_blackboard():
    """Return a client that can read the three driven ports."""
    blackboard = py_trees.blackboard.Client(name="test-ports")
    for key in ("trigger_activity_factory", "sync_port", "wire_render_port"):
        blackboard.register_key(key=key, access=py_trees.common.Access.READ)
    return blackboard


@pytest.mark.spec("DL-07-009")
def test_a_delegated_emit_writes_activity_and_outbox_to_one_store(
    datalayer,
):
    """ISSUE-2548: the emit must not split across two actors' stores.

    A case owner's ``invite-actor-to-case`` trigger emits from the CaseActor's
    identity (PCR-08-007), so the BT executes as an actor other than the one the
    ports were built for.  Reconciling only ``blackboard.datalayer`` left the
    port creating the ``Invite`` in the requesting actor's store while the node
    appended its id to the executing actor's outbox.  Nothing raised: delivery
    found the queue entry, could not read the activity, warned, and skipped — so
    the invitee was never told it had been invited.
    """
    port: Any = _StoreHoldingPort(datalayer)
    bridge = BTBridge(datalayer=datalayer, trigger_activity=port)

    result = bridge.execute_with_setup(
        tree=EmitThroughPort(name="EmitThroughPort"),
        actor_id=_CO_HOSTED_CASE_ACTOR,
    )

    assert result.status == Status.SUCCESS, result.feedback_message


@pytest.mark.spec("DL-07-009")
def test_ports_are_rebound_to_the_executing_actors_store(datalayer):
    """DL-07-009: every store-holding port follows the executing actor."""
    trigger: Any = _StoreHoldingPort(datalayer)
    sync: Any = _StoreHoldingPort(datalayer)
    bridge = BTBridge(
        datalayer=datalayer, trigger_activity=trigger, sync_port=sync
    )

    bt = bridge.setup_tree(
        tree=AlwaysSucceed(), actor_id=_CO_HOSTED_CASE_ACTOR
    )
    bt.setup()

    blackboard = _ports_blackboard()
    for published, original in (
        (blackboard.trigger_activity_factory, trigger),
        (blackboard.sync_port, sync),
    ):
        assert published is not original
        assert published._dl.actor_id == _CO_HOSTED_CASE_ACTOR


@pytest.mark.spec("DL-07-009")
def test_ports_are_left_alone_when_the_store_already_matches(datalayer):
    """The non-delegated path — every other trigger — must allocate nothing."""
    trigger: Any = _StoreHoldingPort(datalayer)
    sync: Any = _StoreHoldingPort(datalayer)
    bridge = BTBridge(
        datalayer=datalayer, trigger_activity=trigger, sync_port=sync
    )

    bt = bridge.setup_tree(tree=AlwaysSucceed(), actor_id=datalayer.actor_id)
    bt.setup()

    blackboard = _ports_blackboard()
    assert blackboard.trigger_activity_factory is trigger
    assert blackboard.sync_port is sync


@pytest.mark.spec("DL-07-009")
def test_a_port_without_a_store_is_published_unchanged(
    datalayer, test_actor_id
):
    """A stateless port has nothing to reconcile and must not be swapped out.

    ``wire_render_port`` is one: it renders objects handed to it and never reads
    or writes a store.
    """
    stateless: Any = _StatelessPort()
    bridge = BTBridge(datalayer=datalayer, wire_render_port=stateless)

    bt = bridge.setup_tree(tree=AlwaysSucceed(), actor_id=test_actor_id)
    bt.setup()

    blackboard = _ports_blackboard()
    assert blackboard.wire_render_port is stateless
