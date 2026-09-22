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

import logging
from typing import Any

import pytest
import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.store_scope import same_authority
from vultron.errors import VultronError
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.wire.as2.vocab.base.objects.object_types import as_Note


@pytest.fixture(autouse=True)
def clear_blackboard():
    """Reset the process-global blackboard before every test.

    setup_tree() writes /is_leader (and other keys) to Blackboard.storage.
    Tests that call setup_tree() directly — without going through
    execute_with_setup()'s managed_keys cleanup — would otherwise leave
    /is_leader permanently on the blackboard, contaminating later tests.
    """
    py_trees.blackboard.Blackboard.enable_activity_stream()
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


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


class StageLedgerOverrideThenFail(py_trees.behaviour.Behaviour):
    """Stage the ledger override on the blackboard, then FAILURE (#3101).

    Reproduces the short-circuit shape from ``add_case_status_tree``: a node
    writes ``ledger_payload_object_override`` to the process-global blackboard
    and a later node in the same ``memory=False`` Sequence FAILUREs before
    ``FinalizeCsFilterNode`` — the key's owner — can clear it.  Writes the
    ``/``-prefixed alias the port machinery uses.
    """

    def __init__(self, name: str = "StageLedgerOverrideThenFail"):
        super().__init__(name=name)

    def update(self) -> Status:
        py_trees.blackboard.Blackboard.storage[
            "/ledger_payload_object_override"
        ] = {"object_id": "stale-object-from-vanished-case"}
        self.feedback_message = "staged override then aborting"
        return Status.FAILURE


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
    bridge, datalayer
):
    """BT-05-005: the blackboard datalayer is the store of the blackboard actor_id.

    This used to assert ``blackboard.datalayer == datalayer`` — that the store
    put on the blackboard is exactly the one handed to the bridge.  Under
    ADR-0073 that is the wrong invariant, and asserting it would forbid the fix:
    ``datalayer`` and ``actor_id`` were two independent facts that could
    disagree, which is how a delegated emit created an activity in the
    requester's store and queued it in the CaseActor's outbox.  The store now
    follows the executing actor, so what must hold is that the two agree.

    The executing actor is a *sibling on the same authority* here, rather than
    the cross-authority ``test_actor_id`` this once used.  Re-scoping is only
    meaningful within an authority: a node hosts the actors under its own
    authority and can open a store for any of them, which is what makes
    following the executing actor the right move.  Across authorities it is not
    — see
    :func:`test_setup_tree_keeps_the_injected_store_for_a_foreign_authority`.
    """
    sibling_actor_id = "https://test.example/api/v2/actors/other-actor"
    assert same_authority(datalayer.actor_id, sibling_actor_id)

    bt = bridge.setup_tree(tree=CheckBlackboard(), actor_id=sibling_actor_id)
    bt.setup()

    blackboard = _read_blackboard()
    assert blackboard.actor_id == sibling_actor_id
    assert blackboard.datalayer.actor_id == sibling_actor_id
    # The injected store belonged to a different actor, so it was re-scoped.
    assert datalayer.actor_id != sibling_actor_id
    assert blackboard.datalayer is not datalayer


def test_setup_tree_keeps_the_injected_store_for_a_foreign_authority(
    bridge, datalayer, test_actor_id
):
    """A store is never re-scoped to an actor this node does not host (#2484).

    ``_find_case_actor_id`` resolves a case's authority from the participant
    roster — the ``CVDRole.CASE_MANAGER`` role (ADR-0088, ARCH-24-004) — which
    names remote actors just as readily as local ones, since a roster records
    who holds the role and not where they are hosted.  That matters after a
    handoff, when the authority is on the container that first received the
    report (CP-08-003) while the case owner is elsewhere.  ``setup_tree`` then
    runs with that foreign actor as the executing actor.

    Re-scoping there would mint an empty local store under a foreign actor's
    name, and nothing would raise: the tree would simply run against nothing.
    That is not a degradation but a hard failure — with no case there is no
    genesis hash to anchor the ledger chain, so the commit is refused
    (CLP-08-005) and ``invite-actor-to-case`` answers 422.  So the handed store
    is kept, and it is the right one: it belongs to the actor whose request this
    is, and it holds the case and its ledger.  The Invite's *wire* identity is
    unaffected (PCR-08-007).
    """
    assert not same_authority(datalayer.actor_id, test_actor_id)

    bt = bridge.setup_tree(tree=CheckBlackboard(), actor_id=test_actor_id)
    bt.setup()

    blackboard = _read_blackboard()
    assert blackboard.actor_id == test_actor_id
    assert blackboard.datalayer is datalayer, (
        "a foreign-authority executing actor must not cause a fresh local store"
        " to be minted in its name; the handed store is the only one this node"
        f" can actually write. got actor_id={blackboard.datalayer.actor_id!r}"
    )


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
    # Assert the classification, not a substring: the old check looked for
    # "exception" in the message, which only matched because the raised
    # RuntimeError's own text happened to contain the word.
    assert result.internal_error is True
    assert "RuntimeError" in result.feedback_message
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


def test_execute_with_setup_clears_stale_ledger_override(
    bridge, test_actor_id
):
    """A FAILURE short-circuit leaves no stale ledger override (#3101).

    ``ledger_payload_object_override`` is a within-execution hand-off written by
    ``FinalizeCsFilterNode`` and consumed by ``CommitCaseLedgerEntryNode``.  If
    an earlier node in the ``memory=False`` Sequence FAILUREs first, Finalize
    never ticks to clear it, so before #3101 the value stranded on the
    process-global blackboard and the *next* execution misread it.  The bridge
    now resets the key at the execution boundary regardless of outcome, so it
    must be absent after a short-circuiting run and the following run must start
    clean.
    """
    storage = py_trees.blackboard.Blackboard.storage

    result = bridge.execute_with_setup(
        tree=StageLedgerOverrideThenFail(), actor_id=test_actor_id
    )

    assert result.status == Status.FAILURE
    assert "ledger_payload_object_override" not in storage
    assert "/ledger_payload_object_override" not in storage

    # A subsequent execution must not see the vanished-case override.
    captured: dict[str, Any] = {}

    class _CaptureOverride(py_trees.behaviour.Behaviour):
        def update(self) -> Status:
            captured["present"] = (
                "/ledger_payload_object_override" in storage
                or "ledger_payload_object_override" in storage
            )
            return Status.SUCCESS

    second = bridge.execute_with_setup(
        tree=_CaptureOverride(name="CaptureOverride"), actor_id=test_actor_id
    )
    assert second.status == Status.SUCCESS
    assert captured["present"] is False


def test_execute_with_setup_restores_preexisting_ledger_override(
    bridge, test_actor_id
):
    """A caller-set ledger override is restored, not unconditionally deleted.

    The bridge resets the key to its *pre-execution* state (ADR-0087), so a
    value present before the run survives it — the cleanup targets only what the
    execution itself left behind.
    """
    storage = py_trees.blackboard.Blackboard.storage
    sentinel = {"object_id": "caller-provided"}
    storage["/ledger_payload_object_override"] = sentinel

    try:
        result = bridge.execute_with_setup(
            tree=StageLedgerOverrideThenFail(), actor_id=test_actor_id
        )
        assert result.status == Status.FAILURE
        assert storage["/ledger_payload_object_override"] is sentinel
    finally:
        storage.pop("/ledger_payload_object_override", None)


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


# ---------------------------------------------------------------------------
# Failure classification: protocol outcome vs. programming error (CONCERN-3019)
# ---------------------------------------------------------------------------


class _DomainErrorNode(py_trees.behaviour.Behaviour):
    """Node that raises a domain error the way ~28 production nodes do."""

    def update(self) -> Status:
        raise VultronError("canonical entry rejected")


class _InvalidStatusNode(py_trees.behaviour.Behaviour):
    """Node that reports INVALID mid-execution."""

    def update(self) -> Status:
        return Status.INVALID


class _BrokenNode(py_trees.behaviour.Behaviour):
    """Node that dies of a wrong-typed value, the way #2907 did."""

    def update(self) -> Status:
        raise TypeError("value is not of type VulnerabilityCase")


class _SilentBugNode(py_trees.behaviour.Behaviour):
    """Node whose exception carries no message — an empty ``str(e)``."""

    def update(self) -> Status:
        raise AttributeError()


class _BadSetupNode(py_trees.behaviour.Behaviour):
    """Node that crashes in ``setup()``, before any tick."""

    def setup(self, **kwargs: Any) -> None:
        raise TypeError("setup wired wrong")

    def update(self) -> Status:  # pragma: no cover - never reached
        return Status.SUCCESS


class _BadShutdownNode(py_trees.behaviour.Behaviour):
    """Node that crashes in both ``update()`` and ``shutdown()``."""

    def update(self) -> Status:
        raise TypeError("the failure that actually matters")

    def shutdown(self) -> None:
        raise RuntimeError("shutdown also broken")


class TestFailureClassification:
    """A bare FAILURE conflated a protocol outcome with a crash.

    ``BTBridge.execute_tree`` catches both, so callers that decide whether to
    retry, re-buffer, or log loudly could not tell them apart. The operative
    question for the flag is "would retrying converge?" — for a deliberate
    domain raise yes, for a code bug never.
    """

    def test_domain_raise_is_not_an_internal_error(
        self, bridge, test_actor_id
    ) -> None:
        """A deliberate ``VultronError`` stays a protocol outcome."""
        bt = bridge.setup_tree(
            tree=_DomainErrorNode(name="DomainError"), actor_id=test_actor_id
        )
        result = bridge.execute_tree(bt)

        assert result.status == Status.FAILURE
        assert result.internal_error is False
        assert "canonical entry rejected" in result.feedback_message

    def test_programming_error_is_flagged(self, bridge, test_actor_id) -> None:
        """A ``TypeError`` is caught but marked as not-a-protocol-outcome."""
        bt = bridge.setup_tree(
            tree=_BrokenNode(name="Broken"), actor_id=test_actor_id
        )
        result = bridge.execute_tree(bt)

        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert "TypeError" in result.feedback_message

    def test_exception_type_is_named_in_the_message(
        self, bridge, test_actor_id
    ) -> None:
        """The type name is in the message; an empty ``str(e)`` is common."""
        bt = bridge.setup_tree(
            tree=_SilentBugNode(name="SilentBug"), actor_id=test_actor_id
        )
        result = bridge.execute_tree(bt)

        assert result.internal_error is True
        assert "AttributeError" in result.feedback_message

    def test_max_iterations_is_an_internal_error(
        self, bridge, test_actor_id
    ) -> None:
        """A tree that will not settle will not settle on a retry either."""
        bt = bridge.setup_tree(tree=RunNTimes(n=200), actor_id=test_actor_id)
        result = bridge.execute_tree(bt, max_iterations=5)

        assert result.status == Status.FAILURE
        assert result.internal_error is True
        # Pin the branch: without this, the assertions are byte-identical to
        # test_invalid_status_is_an_internal_error and either test would pass
        # on the other's path (CONCERN-3019).
        assert "exceeded max iterations (5)" in result.feedback_message

    def test_invalid_status_is_an_internal_error(
        self, bridge, test_actor_id
    ) -> None:
        """A root in INVALID mid-execution is malformed, not a protocol no."""
        bt = bridge.setup_tree(
            tree=_InvalidStatusNode(name="InvalidStatus"),
            actor_id=test_actor_id,
        )
        result = bridge.execute_tree(bt)

        assert result.status == Status.FAILURE
        assert result.internal_error is True
        # Pin the branch — see test_max_iterations_is_an_internal_error.
        assert "entered INVALID state" in result.feedback_message

    def test_ordinary_failure_is_not_an_internal_error(
        self, bridge, test_actor_id
    ) -> None:
        """A node returning FAILURE is the ordinary protocol path."""
        bt = bridge.setup_tree(tree=AlwaysFail(), actor_id=test_actor_id)
        result = bridge.execute_tree(bt)

        assert result.status == Status.FAILURE
        assert result.internal_error is False

    def test_success_is_not_an_internal_error(
        self, bridge, test_actor_id
    ) -> None:
        bt = bridge.setup_tree(tree=AlwaysSucceed(), actor_id=test_actor_id)
        result = bridge.execute_tree(bt)

        assert result.status == Status.SUCCESS
        assert result.internal_error is False

    def test_default_is_not_an_internal_error(self) -> None:
        """Callers constructing a result directly get the safe default."""
        assert BTExecutionResult(status=Status.FAILURE).internal_error is False


class TestClassificationRobustness:
    """The classification must survive the tree lifecycle around the ticks."""

    def test_setup_time_crash_is_caught_and_flagged(
        self, bridge, test_actor_id
    ) -> None:
        """A crash in ``setup()`` used to escape ``execute_tree`` entirely."""
        bt = bridge.setup_tree(
            tree=_BadSetupNode(name="BadSetup"), actor_id=test_actor_id
        )
        result = bridge.execute_tree(bt)

        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert "TypeError" in result.feedback_message

    def test_shutdown_crash_does_not_mask_the_result(
        self, bridge, test_actor_id
    ) -> None:
        """A raise in the ``finally`` block must not replace the return value."""
        bt = bridge.setup_tree(
            tree=_BadShutdownNode(name="BadShutdown"), actor_id=test_actor_id
        )
        result = bridge.execute_tree(bt)

        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert "the failure that actually matters" in result.feedback_message

    def test_domain_error_message_names_its_type(
        self, bridge, test_actor_id
    ) -> None:
        """Both branches name the type, so triage does not need the traceback."""
        bt = bridge.setup_tree(
            tree=_DomainErrorNode(name="DomainError"), actor_id=test_actor_id
        )
        result = bridge.execute_tree(bt)

        assert result.internal_error is False
        assert "VultronError" in result.feedback_message

    def test_setup_tree_crash_is_classified_not_raised(
        self, bridge, test_actor_id
    ) -> None:
        """``setup_tree`` was the one fallible call outside the net.

        ``execute_with_setup`` used to call it before entering any ``try``, so a
        wiring bug escaped ``BTBridge`` entirely and reached the caller — a
        FastAPI background task — as a bare exception with no
        ``BTExecutionResult`` at all (CONCERN-3019).
        """

        def _explode(*args: Any, **kwargs: Any) -> Any:
            raise TypeError("store wired wrong")

        bridge.setup_tree = _explode  # type: ignore[method-assign]
        result = bridge.execute_with_setup(
            tree=AlwaysSucceed(), actor_id=test_actor_id
        )

        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert "TypeError" in result.feedback_message
        assert "store wired wrong" in result.feedback_message

    def test_setup_tree_domain_error_is_not_an_internal_error(
        self, bridge, test_actor_id
    ) -> None:
        """A ``VultronError`` from setup keeps the protocol classification."""

        def _reject(*args: Any, **kwargs: Any) -> Any:
            raise VultronError("actor store is not readable")

        bridge.setup_tree = _reject  # type: ignore[method-assign]
        result = bridge.execute_with_setup(
            tree=AlwaysSucceed(), actor_id=test_actor_id
        )

        assert result.status == Status.FAILURE
        assert result.internal_error is False
        assert "VultronError" in result.feedback_message


# ---------------------------------------------------------------------------
# Phase labelling: setup errors and execution errors are distinguishable
# (#3085)
# ---------------------------------------------------------------------------


class TestPhaseLabelling:
    """``execute_with_setup`` must name the phase that actually failed.

    Both calls used to share one ``try``, so anything escaping ``execute_tree``
    was reported as ``"BT setup failed"`` — sending a reader to the wiring when
    the bug was in a node (#3085).  ``execute_tree``'s own catch-all means only
    a patched ``execute_tree`` can reach the execution handlers, which is
    exactly what the split exists to keep true if that catch-all is narrowed.
    """

    def test_a_setup_crash_is_labelled_setup(
        self, bridge, test_actor_id
    ) -> None:
        def _explode(*args: Any, **kwargs: Any) -> Any:
            raise TypeError("store wired wrong")

        bridge.setup_tree = _explode  # type: ignore[method-assign]
        result = bridge.execute_with_setup(
            tree=AlwaysSucceed(), actor_id=test_actor_id
        )

        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert "BT setup failed" in result.feedback_message
        assert "BT execution failed" not in result.feedback_message

    def test_an_execution_crash_is_not_labelled_setup(
        self, bridge, test_actor_id
    ) -> None:
        """The mislabelling #3085 names, reproduced at its own boundary."""

        def _explode(*args: Any, **kwargs: Any) -> Any:
            raise TypeError("tick machinery wired wrong")

        bridge.execute_tree = _explode  # type: ignore[method-assign]
        result = bridge.execute_with_setup(
            tree=AlwaysSucceed(), actor_id=test_actor_id
        )

        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert "BT execution failed" in result.feedback_message
        assert "BT setup failed" not in result.feedback_message
        assert "tick machinery wired wrong" in result.feedback_message

    def test_an_execution_domain_error_keeps_its_classification(
        self, bridge, test_actor_id
    ) -> None:
        """A ``VultronError`` escaping the ticks is still a protocol outcome."""

        def _reject(*args: Any, **kwargs: Any) -> Any:
            raise VultronError("peer message rejected")

        bridge.execute_tree = _reject  # type: ignore[method-assign]
        result = bridge.execute_with_setup(
            tree=AlwaysSucceed(), actor_id=test_actor_id
        )

        assert result.status == Status.FAILURE
        assert result.internal_error is False
        assert "BT execution failed: VultronError" in result.feedback_message

    def test_the_teardown_still_runs_when_execution_raises(
        self, bridge, test_actor_id
    ) -> None:
        """Splitting the ``try`` must not move either phase out of ``finally``."""
        storage = py_trees.blackboard.Blackboard.storage
        sentinel = object()
        storage["/datalayer"] = sentinel

        def _explode(*args: Any, **kwargs: Any) -> Any:
            raise TypeError("tick machinery wired wrong")

        bridge.execute_tree = _explode  # type: ignore[method-assign]
        result = bridge.execute_with_setup(
            tree=AlwaysSucceed(), actor_id=test_actor_id
        )

        assert result.status == Status.FAILURE
        assert storage["/datalayer"] is sentinel


class TestExceptionResultConsistency:
    """One helper builds every classifying handler's result (#3084).

    The handlers were near-identical copies, and a log-level divergence between
    two of them was #3080.  ``_exception_result`` derives the message, the log
    level, and the ``internal_error`` flag from one input, so they cannot drift
    apart again (CS-22-001).
    """

    def test_a_protocol_outcome_logs_at_warning_without_a_traceback(
        self, bridge, test_actor_id, caplog
    ) -> None:
        def _reject(*args: Any, **kwargs: Any) -> Any:
            raise VultronError("actor store is not readable")

        bridge.setup_tree = _reject  # type: ignore[method-assign]
        with caplog.at_level(logging.DEBUG):
            bridge.execute_with_setup(
                tree=AlwaysSucceed(), actor_id=test_actor_id
            )

        records = [
            r for r in caplog.records if "BT setup failed" in r.getMessage()
        ]
        assert [r.levelno for r in records] == [logging.WARNING]
        assert records[0].exc_info is None

    def test_an_internal_error_logs_at_error_with_a_traceback(
        self, bridge, test_actor_id, caplog
    ) -> None:
        def _explode(*args: Any, **kwargs: Any) -> Any:
            raise TypeError("store wired wrong")

        bridge.setup_tree = _explode  # type: ignore[method-assign]
        with caplog.at_level(logging.DEBUG):
            bridge.execute_with_setup(
                tree=AlwaysSucceed(), actor_id=test_actor_id
            )

        records = [
            r for r in caplog.records if "BT setup failed" in r.getMessage()
        ]
        assert [r.levelno for r in records] == [logging.ERROR]
        assert records[0].exc_info is not None

    @pytest.mark.parametrize(
        "patched,raised,expected_prefix,expected_flag",
        [
            ("setup_tree", VultronError("boom"), "BT setup failed", False),
            ("setup_tree", TypeError("boom"), "BT setup failed", True),
            (
                "execute_tree",
                VultronError("boom"),
                "BT execution failed",
                False,
            ),
            ("execute_tree", TypeError("boom"), "BT execution failed", True),
        ],
    )
    def test_every_handler_reports_one_consistent_message(
        self,
        bridge,
        test_actor_id,
        patched: str,
        raised: Exception,
        expected_prefix: str,
        expected_flag: bool,
    ) -> None:
        """All four boundaries agree across phase, flag, and both channels."""

        def _raise(*args: Any, **kwargs: Any) -> Any:
            raise raised

        local_bridge = BTBridge(datalayer=bridge.datalayer)
        setattr(local_bridge, patched, _raise)
        result = local_bridge.execute_with_setup(
            tree=AlwaysSucceed(), actor_id=test_actor_id
        )

        assert result.status == Status.FAILURE
        assert result.internal_error is expected_flag
        assert result.feedback_message.startswith(expected_prefix)
        # feedback_message and the sole errors entry are the same string, and
        # the exception type is named in it because str(e) is empty for several
        # common cases (a bare AttributeError, for one).
        assert result.errors == [result.feedback_message]
        assert type(raised).__name__ in result.feedback_message
        assert "boom" in result.feedback_message

    @pytest.mark.parametrize(
        "node,expected_flag",
        [
            (_DomainErrorNode(name="DomainErrorInTick"), False),
            (_BrokenNode(name="BrokenInTick"), True),
        ],
    )
    def test_the_tick_handlers_report_the_message_in_both_channels(
        self, bridge, test_actor_id, node, expected_flag: bool
    ) -> None:
        """The two handlers a real node reaches, exercised through a real tick.

        Patching ``setup_tree``/``execute_tree`` cannot reach ``execute_tree``'s
        own pair — and those are the two where the substitution changed code:
        ``errors.append(msg); errors=errors`` became the helper's
        ``errors=[msg]``.  That is only equivalent because ``errors`` is empty
        on both paths, which this asserts rather than assumes.
        """
        result = bridge.execute_with_setup(tree=node, actor_id=test_actor_id)

        assert result.status == Status.FAILURE
        assert result.internal_error is expected_flag
        assert result.feedback_message.startswith("BT execution failed")
        assert result.errors == [result.feedback_message]


# ---------------------------------------------------------------------------
# Nested executions: /activity and context_data keys are execution-scoped
# (#3161)
# ---------------------------------------------------------------------------


class _NestedExecution(py_trees.behaviour.Behaviour):
    """Run a second ``execute_with_setup`` from inside a tick.

    Many production nodes do exactly this — ``case/nodes/lifecycle.py`` and
    ``status/nodes/case_status.py`` among them.  The node records what the
    process-global blackboard held immediately before and after the inner call,
    which is the window the outer tree's remaining ticks read from.
    """

    def __init__(
        self,
        bridge: BTBridge,
        actor_id: str,
        inner_kwargs: dict[str, Any],
        observed: dict[str, Any],
        inner_tree: py_trees.behaviour.Behaviour | None = None,
        name: str = "NestedExecution",
    ):
        super().__init__(name=name)
        self._bridge = bridge
        self._actor_id = actor_id
        self._inner_kwargs = inner_kwargs
        self._observed = observed
        self._inner_tree = inner_tree or AlwaysSucceed(name="InnerTree")

    def update(self) -> Status:
        storage = py_trees.blackboard.Blackboard.storage
        self._observed["before"] = dict(storage)
        inner = self._bridge.execute_with_setup(
            tree=self._inner_tree,
            actor_id=self._actor_id,
            **self._inner_kwargs,
        )
        self._observed["inner_status"] = inner.status
        self._observed["after"] = dict(storage)
        return Status.SUCCESS


class _RecordResolvedActor(DataLayerAction):
    """Record the actor id this node's own base class resolves for it.

    Module-level per CONCERN-2321 (`notes/testing-pitfalls.md`): py_trees keys
    its class registry by class name, so a BT subclass defined inside a test
    function can be clobbered by a same-named local class in another test.  The
    recording list is injected rather than closed over, which is what makes the
    module-level definition possible.
    """

    def __init__(self, seen: list[str | None], name: str):
        super().__init__(name=name)
        self._seen = seen

    def update(self) -> Status:
        self._seen.append(self.actor_id)
        return Status.SUCCESS


class TestNestedExecutionKeyIsolation:
    """An inner execution must hand the outer execution's keys back.

    ``setup_tree`` writes ``/activity`` and one key per ``context_data`` entry.
    Before #3510 those were outside ``managed_keys``, so a nested call
    overwrote them and never restored them — the outer tree finished its ticks
    reading the inner call's activity (#3161).
    """

    def test_an_inner_activity_does_not_clobber_the_outer_one(
        self, bridge, test_actor_id
    ) -> None:
        observed: dict[str, Any] = {}
        outer_activity = {"type": "Create", "id": "outer"}
        inner_activity = {"type": "Accept", "id": "inner"}

        result = bridge.execute_with_setup(
            tree=_NestedExecution(
                bridge,
                test_actor_id,
                {"activity": inner_activity},
                observed,
            ),
            actor_id=test_actor_id,
            activity=outer_activity,
        )

        assert result.status == Status.SUCCESS
        assert observed["inner_status"] == Status.SUCCESS
        # Prove the harness really seeded the outer key, so the assertion
        # below is about the restore and not about an absent key.
        assert observed["before"]["/activity"] is outer_activity
        assert observed["after"]["/activity"] is outer_activity

    def test_an_inner_context_key_does_not_clobber_the_outer_one(
        self, bridge, test_actor_id
    ) -> None:
        observed: dict[str, Any] = {}

        result = bridge.execute_with_setup(
            tree=_NestedExecution(
                bridge, test_actor_id, {"case_id": "inner-case"}, observed
            ),
            actor_id=test_actor_id,
            case_id="outer-case",
        )

        assert result.status == Status.SUCCESS
        assert observed["before"]["/case_id"] == "outer-case"
        assert observed["after"]["/case_id"] == "outer-case"

    def test_a_key_the_outer_execution_never_set_is_removed_again(
        self, bridge, test_actor_id
    ) -> None:
        """Absence is a state to restore, not a reason to skip the restore."""
        observed: dict[str, Any] = {}

        result = bridge.execute_with_setup(
            tree=_NestedExecution(
                bridge,
                test_actor_id,
                {"activity": {"type": "Accept"}, "case_id": "inner-case"},
                observed,
            ),
            actor_id=test_actor_id,
        )

        assert result.status == Status.SUCCESS
        assert "/activity" not in observed["before"]
        assert "/activity" not in observed["after"]
        assert "/case_id" not in observed["after"]

    @pytest.mark.parametrize(
        "key",
        [
            "datalayer",
            "trigger_activity_factory",
            "sync_port",
            "is_leader",
            "wire_render_port",
            "ledger_payload_object_override",
            "actor_id",
        ],
    )
    def test_every_fixed_managed_key_is_restored(
        self, bridge, test_actor_id, key: str
    ) -> None:
        """BT-17-007 says "every managed key", so cover the whole fixed list.

        The dynamic half (``activity`` and the ``context_data`` keys) is covered
        by the nested-call tests above.  A non-callable sentinel is safe for
        ``is_leader``: ``execute_with_setup`` ignores a non-callable under that
        key and falls back to its own guard.
        """
        storage = py_trees.blackboard.Blackboard.storage
        sentinel = object()
        storage[f"/{key}"] = sentinel

        result = bridge.execute_with_setup(
            tree=AlwaysSucceed(), actor_id=test_actor_id
        )

        assert result.status == Status.SUCCESS
        assert storage[f"/{key}"] is sentinel

    def test_the_outer_execution_leaves_no_context_key_behind(
        self, bridge, test_actor_id
    ) -> None:
        """The same rule at the outermost boundary: nothing leaks to the next run."""
        storage = py_trees.blackboard.Blackboard.storage

        result = bridge.execute_with_setup(
            tree=AlwaysSucceed(),
            actor_id=test_actor_id,
            activity={"type": "Create"},
            case_id="outer-case",
        )

        assert result.status == Status.SUCCESS
        assert "/activity" not in storage
        assert "/case_id" not in storage

    def test_an_inner_actor_id_does_not_clobber_the_outer_one(
        self, bridge, test_actor_id
    ) -> None:
        """A nested execution's actor must not outlive it on the blackboard.

        A nested call can legitimately run as a different actor — the case that
        makes the two diverge is ``_store_for_actor``'s foreign-authority
        fall-through, where the injected store is kept rather than re-scoped.
        Without the restore that inner actor stays on the blackboard for the rest
        of the outer tree's ticks.
        """
        observed: dict[str, Any] = {}
        inner_seen: list[str | None] = []
        inner_actor = "https://example.org/actors/case-actor"

        result = bridge.execute_with_setup(
            tree=_NestedExecution(
                bridge,
                inner_actor,
                {},
                observed,
                inner_tree=_RecordResolvedActor(
                    seen=inner_seen, name="RecordInnerActor"
                ),
            ),
            actor_id=test_actor_id,
        )

        assert result.status == Status.SUCCESS
        # Harness validity: the inner execution ran, and it ran as a *different*
        # actor.  Without these two the assertion below passes trivially if the
        # inner call is leadership-skipped or if setup_tree stops writing the
        # key at all.
        assert observed["inner_status"] == Status.SUCCESS
        assert inner_seen == [inner_actor]

        assert observed["before"]["/actor_id"] == test_actor_id
        assert observed["after"]["/actor_id"] == test_actor_id

    def test_a_later_sibling_reads_its_own_trees_actor(
        self, bridge, test_actor_id
    ) -> None:
        """The reachable consequence, at the layer that actually suffered it.

        Node bases re-read ``/actor_id`` in ``initialise()`` — not ``setup()`` —
        and py_trees calls ``initialise()`` on every tick in which the node was
        not RUNNING.  So asserting on the raw blackboard is not enough: this
        asserts what a *sibling node* resolves, which is what
        ``OwnerLeaveSeq``'s ledger-committing node does downstream of a nested
        call (``case/receive_close_case_tree.py``).
        """
        inner_actor = "https://example.org/actors/case-actor"
        outer_seen: list[str | None] = []
        inner_seen: list[str | None] = []
        observed: dict[str, Any] = {}

        sequence = py_trees.composites.Sequence(
            name="NestedThenSibling",
            memory=False,
            children=[
                _NestedExecution(
                    bridge,
                    inner_actor,
                    {},
                    observed,
                    inner_tree=_RecordResolvedActor(
                        seen=inner_seen, name="RecordInnerActor"
                    ),
                ),
                _RecordResolvedActor(seen=outer_seen, name="RecordOuterActor"),
            ],
        )

        result = bridge.execute_with_setup(
            tree=sequence, actor_id=test_actor_id
        )

        assert result.status == Status.SUCCESS
        assert observed["inner_status"] == Status.SUCCESS
        # Harness validity: the inner tree really did run as a *different*
        # actor, so the assertion below is about the restore rather than about
        # a key nothing ever changed.
        assert inner_seen == [inner_actor]
        assert outer_seen == [test_actor_id]
