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

"""``ActTransaction``: an act and its later nodes' consequences commit as one.

The composite runs its children as a ``Sequence`` inside one DataLayer
transaction; a failing or raising child keeps nothing any child wrote
(CLP-07-015, ADR-0146).
"""

from collections.abc import Callable, Iterator

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.act_transaction import ActTransaction
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

pytestmark = pytest.mark.spec("CLP-07-015")

_ACTOR = "https://example.org/actors/act-actor"


class _Boom(Exception):
    """The failure a test node raises part-way."""


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    try:
        yield store
    finally:
        store.close()


def _note(name: str) -> as_Note:
    return as_Note(id_=f"https://example.org/notes/{name}", content=name)


class _Do(py_trees.behaviour.Behaviour):
    """A leaf that runs *action* and returns *status*."""

    def __init__(
        self, name: str, action: Callable[[], None], status: Status
    ) -> None:
        super().__init__(name=name)
        self._action = action
        self._status = status

    def update(self) -> Status:
        self._action()
        return self._status


def _save(dl: SqliteDataLayer, name: str, status=Status.SUCCESS) -> _Do:
    return _Do(f"Save{name}", lambda: dl.save(_note(name)), status)


def _raise() -> None:
    raise _Boom("consequence failed")


def _run(dl: SqliteDataLayer, tree: py_trees.behaviour.Behaviour):
    return BTBridge(datalayer=dl).execute_with_setup(
        tree=tree, actor_id=_ACTOR
    )


def _held(dl: SqliteDataLayer, name: str) -> bool:
    return dl.read(_note(name).id_) is not None


def test_children_that_succeed_commit_every_write(dl: SqliteDataLayer):
    tree = ActTransaction(
        name="Act", children=[_save(dl, "act"), _save(dl, "consequence")]
    )

    result = _run(dl, tree)

    assert result.status is Status.SUCCESS
    assert _held(dl, "act")
    assert _held(dl, "consequence")


def test_a_later_child_that_fails_keeps_nothing(dl: SqliteDataLayer):
    tree = ActTransaction(
        name="Act",
        children=[
            _save(dl, "act"),
            _save(dl, "consequence", status=Status.FAILURE),
        ],
    )

    result = _run(dl, tree)

    assert result.status is Status.FAILURE
    assert not result.internal_error
    assert not _held(dl, "act")
    assert not _held(dl, "consequence")


def test_a_later_child_that_raises_keeps_nothing_and_is_internal(
    dl: SqliteDataLayer,
):
    tree = ActTransaction(
        name="Act",
        children=[
            _save(dl, "act"),
            _Do("Consequence", _raise, Status.SUCCESS),
        ],
    )

    result = _run(dl, tree)

    assert result.status is Status.FAILURE
    assert result.internal_error
    assert not _held(dl, "act")


def test_a_running_child_is_a_wiring_fault_that_keeps_nothing(
    dl: SqliteDataLayer,
):
    tree = ActTransaction(
        name="Act",
        children=[
            _save(dl, "act"),
            _Do("Waits", lambda: None, Status.RUNNING),
        ],
    )

    result = _run(dl, tree)

    assert result.status is Status.FAILURE
    assert result.internal_error
    assert "ActTransactionError" in result.feedback_message
    assert "'Waits' returned RUNNING" in result.feedback_message
    assert not _held(dl, "act")
    assert tree.status is Status.FAILURE
    assert all(child.status is not Status.RUNNING for child in tree.children)


def test_an_act_inside_another_rolls_back_with_it(dl: SqliteDataLayer):
    tree = ActTransaction(
        name="Outer",
        children=[
            ActTransaction(name="Inner", children=[_save(dl, "inner")]),
            _save(dl, "after", status=Status.FAILURE),
        ],
    )

    result = _run(dl, tree)

    assert result.status is Status.FAILURE
    assert not _held(dl, "inner")


def test_the_status_is_settled_before_the_parent_reads_it(
    dl: SqliteDataLayer,
):
    """A committed act is committed before its parent reads SUCCESS.

    A Selector stops at a child that succeeds and never resumes that
    child's tick.  Had the act yielded its status with its transaction still
    open, the transaction would be closed only when the tick is discarded,
    which rolls it back.
    """
    tree = py_trees.composites.Selector(
        name="Parent",
        memory=False,
        children=[
            ActTransaction(name="Act", children=[_save(dl, "act")]),
            _save(dl, "fallback"),
        ],
    )

    result = _run(dl, tree)

    assert result.status is Status.SUCCESS
    assert _held(dl, "act")
    assert not _held(dl, "fallback")


def test_a_failed_act_keeps_nothing_and_a_fallback_after_it_does(
    dl: SqliteDataLayer,
):
    """A Selector parent that sees FAILURE runs its fallback outside the act."""
    tree = py_trees.composites.Selector(
        name="Parent",
        memory=False,
        children=[
            ActTransaction(
                name="Act",
                children=[_save(dl, "act", status=Status.FAILURE)],
            ),
            _save(dl, "fallback"),
        ],
    )

    result = _run(dl, tree)

    assert result.status is Status.SUCCESS
    assert not _held(dl, "act")
    assert _held(dl, "fallback")


def test_an_inner_act_that_rolls_back_inside_an_outer_one_that_commits(
    dl: SqliteDataLayer,
):
    """Only the inner act's writes are undone; the outer act keeps its own."""
    tree = ActTransaction(
        name="Outer",
        children=[
            _save(dl, "outer"),
            py_trees.composites.Selector(
                name="InnerOrFallback",
                memory=False,
                children=[
                    ActTransaction(
                        name="Inner",
                        children=[
                            _save(dl, "inner"),
                            _save(dl, "fails", status=Status.FAILURE),
                        ],
                    ),
                    _save(dl, "fallback"),
                ],
            ),
        ],
    )

    result = _run(dl, tree)

    assert result.status is Status.SUCCESS
    assert _held(dl, "outer")
    assert _held(dl, "fallback")
    assert not _held(dl, "inner")
    assert not _held(dl, "fails")


def test_a_case_manager_gate_body_can_be_one_act():
    gate = create_case_manager_gated_tree(
        name="Arm",
        case_id="https://example.org/cases/c",
        children=[py_trees.behaviours.Success(name="Only")],
        as_one_act=True,
    )

    body = gate.gated_branch
    assert isinstance(body, ActTransaction)
    assert body.name == "ArmBody"


def test_a_missing_datalayer_fails_without_running_the_children():
    ran: list[str] = []
    tree = ActTransaction(
        name="Act",
        children=[_Do("Child", lambda: ran.append("child"), Status.SUCCESS)],
    )
    tree.setup()

    statuses = [node.status for node in tree.tick()]

    assert statuses == [Status.FAILURE]
    assert ran == []


def test_a_received_act_block_at_a_replica_keeps_no_replica_write(
    dl: SqliteDataLayer,
):
    """At a participant replica the commit gate skips, and the act block
    still holds the replica effects: when a later one fails, none of their
    writes is kept, so the received act fails as a whole there too
    (ADR-0151)."""
    from vultron.core.behaviors.case.receive_activity_tree import (
        create_receive_activity_tree,
    )

    tree = create_receive_activity_tree(
        name="ReplicaBT",
        # A case this store does not hold: not its CASE_MANAGER.
        case_id="https://example.org/cases/not-held",
        precondition_guards=[],
        case_may_be_absent=True,
        replica_effects=[
            _save(dl, "persisted"),
            _save(dl, "answer", status=Status.FAILURE),
        ],
    )
    act = tree.children[-1]
    assert isinstance(act, ActTransaction)

    result = _run(dl, act)

    assert result.status is Status.FAILURE
    assert not _held(dl, "persisted")
    assert not _held(dl, "answer")


def test_a_received_act_block_at_a_replica_keeps_its_replica_writes(
    dl: SqliteDataLayer,
):
    """The control for the test above: when every replica effect succeeds,
    the commit gate skips and both writes are kept, so the replica effects
    do run inside the act block (ADR-0151)."""
    from vultron.core.behaviors.case.receive_activity_tree import (
        create_receive_activity_tree,
    )

    tree = create_receive_activity_tree(
        name="ReplicaBT",
        case_id="https://example.org/cases/not-held",
        precondition_guards=[],
        case_may_be_absent=True,
        replica_effects=[_save(dl, "persisted"), _save(dl, "answer")],
    )
    act = tree.children[-1]
    assert isinstance(act, ActTransaction)

    result = _run(dl, act)

    assert result.status is Status.SUCCESS
    assert _held(dl, "persisted")
    assert _held(dl, "answer")
