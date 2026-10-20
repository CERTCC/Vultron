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

The composite runs its children as a ``Sequence`` inside one
``act_transaction``; a failing or raising child keeps nothing any child
wrote (CLP-07-015, ADR-0146).  ``apply_after_rollback`` names the change of
an entry committed before the block opened, which the block applies again
after its rollback.
"""

from collections.abc import Callable, Iterator

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.act_transaction import (
    ActTransaction,
    act_transaction,
    apply_after_rollback,
)
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
    """A Sequence parent that sees FAILURE stops; the rollback already ran."""
    after_parent = _save(dl, "sibling")
    tree = py_trees.composites.Sequence(
        name="Parent",
        memory=False,
        children=[
            ActTransaction(
                name="Act",
                children=[_save(dl, "act", status=Status.FAILURE)],
            ),
            after_parent,
        ],
    )

    result = _run(dl, tree)

    assert result.status is Status.FAILURE
    assert not _held(dl, "act")
    assert not _held(dl, "sibling")


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


class TestApplyAfterRollback:
    """The change of an entry committed before the act stands with it."""

    def test_it_is_applied_after_the_rollback(self, dl: SqliteDataLayer):
        with pytest.raises(_Boom):
            with act_transaction(dl):
                apply_after_rollback(lambda: dl.save(_note("committed")))
                dl.save(_note("consequence"))
                _raise()

        assert _held(dl, "committed")
        assert not _held(dl, "consequence")

    def test_it_is_not_applied_when_the_act_commits(self, dl: SqliteDataLayer):
        applied: list[str] = []
        with act_transaction(dl):
            apply_after_rollback(lambda: applied.append("again"))

        assert applied == []

    def test_an_outer_rollback_applies_it_again(self, dl: SqliteDataLayer):
        """The inner act committed into the outer one, which then rolls back."""
        with pytest.raises(_Boom):
            with act_transaction(dl):
                with act_transaction(dl):
                    apply_after_rollback(lambda: dl.save(_note("committed")))
                    dl.save(_note("inner"))
                _raise()

        assert _held(dl, "committed")
        assert not _held(dl, "inner")

    def test_with_no_act_open_it_is_not_kept(self, dl: SqliteDataLayer):
        applied: list[str] = []
        apply_after_rollback(lambda: applied.append("again"))

        with pytest.raises(_Boom):
            with act_transaction(dl):
                _raise()

        assert applied == []
