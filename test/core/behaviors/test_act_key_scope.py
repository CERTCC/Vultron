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
"""The interim key seeder: the seed reaches the node, and nothing else.

:func:`~vultron.core.behaviors.act_key_scope.with_act_keys` seeds any
vocabulary key for one node's tick and restores it on success, failure and
exception (BT-17-007); ``with_case_id`` is that seeder called for
``/case_id``.
"""

from dataclasses import replace

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.act_inputs import published_act_keys
from vultron.core.behaviors.act_key_scope import (
    ActKeyScope,
    seeded_value,
    unscoped,
    with_act_keys,
)
from vultron.core.behaviors.act_keys import (
    CASE_ID,
    INVITEE_ID,
    REPORT_ID,
)
from vultron.core.behaviors.case_id_scope import seeded_case_id, with_case_id

_CASE = "https://example.org/c/1"
_INVITEE = "https://example.org/actors/invitee"
_KEYS = ("/case_id", "case_id", "/invitee_id", "invitee_id")


@pytest.fixture(autouse=True)
def _clean_keys():
    storage = py_trees.blackboard.Blackboard.storage
    for key in _KEYS:
        storage.pop(key, None)
    yield
    for key in _KEYS:
        storage.pop(key, None)


class _Fixed(py_trees.behaviour.Behaviour):
    """Returns *status* and records the act keys it sees when ticked."""

    def __init__(self, name: str, status: Status = Status.SUCCESS) -> None:
        super().__init__(name=name)
        self._status = status
        self.seen: list[tuple[object, object]] = []

    def update(self) -> Status:
        storage = py_trees.blackboard.Blackboard.storage
        self.seen.append(
            (
                storage.get("/case_id", "<absent>"),
                storage.get("/invitee_id", "<absent>"),
            )
        )
        return self._status


class _Raises(py_trees.behaviour.Behaviour):
    def update(self) -> Status:
        raise RuntimeError("boom")


def _tick(root: py_trees.behaviour.Behaviour) -> None:
    for _ in root.tick():
        pass


def _storage() -> dict[str, object]:
    return py_trees.blackboard.Blackboard.storage


@pytest.mark.spec("BT-17-007")
def test_every_key_is_seeded_for_the_node_alone() -> None:
    """A later sibling, and a later execution, see what they saw before."""
    seeded, after = _Fixed("Seeded"), _Fixed("After")
    root = py_trees.composites.Sequence(
        name="Root",
        memory=False,
        children=[
            with_act_keys(seeded, {CASE_ID: _CASE, INVITEE_ID: _INVITEE}),
            after,
        ],
    )

    _tick(root)

    assert seeded.seen == [(_CASE, _INVITEE)]
    assert after.seen == [("<absent>", "<absent>")]
    assert not set(_KEYS) & set(_storage())


@pytest.mark.spec("BT-17-007")
@pytest.mark.parametrize("status", [Status.SUCCESS, Status.FAILURE])
def test_published_values_are_restored_on_success_and_failure(
    status: Status,
) -> None:
    _storage()["/case_id"] = "https://example.org/c/published"
    node = _Fixed("Seeded", status)
    scope = with_act_keys(node, {CASE_ID: _CASE, INVITEE_ID: _INVITEE})

    _tick(scope)

    assert scope.status is status
    assert node.seen == [(_CASE, _INVITEE)]
    assert _storage()["/case_id"] == "https://example.org/c/published"
    assert "/invitee_id" not in _storage()


@pytest.mark.spec("BT-17-007")
def test_the_keys_are_restored_when_the_node_raises() -> None:
    _storage()["/invitee_id"] = "https://example.org/actors/published"
    scope = with_act_keys(
        _Raises(name="Raises"), {CASE_ID: _CASE, INVITEE_ID: _INVITEE}
    )
    with pytest.raises(RuntimeError, match="boom"):
        _tick(scope)
    assert "/case_id" not in _storage()
    assert _storage()["/invitee_id"] == "https://example.org/actors/published"


@pytest.mark.spec("BT-17-007")
@pytest.mark.parametrize(
    ("composite", "first_status"),
    [
        (py_trees.composites.Sequence, Status.FAILURE),
        (py_trees.composites.Selector, Status.SUCCESS),
    ],
)
def test_the_keys_are_restored_when_the_parent_stops_at_the_scoped_child(
    composite: type[
        py_trees.composites.Sequence | py_trees.composites.Selector
    ],
    first_status: Status,
) -> None:
    """A Sequence that fails, or a Selector that succeeds, at its scoped first
    child returns without resuming that child's tick.  The keys are restored
    anyway, so the next tick, and the next execution, see what was there."""
    _storage()["/case_id"] = "https://example.org/c/published"
    first = _Fixed("First", first_status)
    root = composite(
        name="Root",
        memory=False,
        children=[
            with_act_keys(first, {CASE_ID: _CASE, INVITEE_ID: _INVITEE}),
            _Fixed("Second"),
        ],
    )
    _tick(root)

    assert root.status is first_status
    assert first.seen == [(_CASE, _INVITEE)]
    assert _storage()["/case_id"] == "https://example.org/c/published"
    assert "/invitee_id" not in _storage()


def test_the_next_sibling_reads_the_restored_value() -> None:
    _storage()["/case_id"] = "https://example.org/c/published"
    first, second = _Fixed("First"), _Fixed("Second")
    _tick(
        py_trees.composites.Sequence(
            name="Root",
            memory=False,
            children=[with_act_keys(first, {CASE_ID: _CASE}), second],
        )
    )
    assert first.seen == [(_CASE, "<absent>")]
    assert second.seen == [("https://example.org/c/published", "<absent>")]


def test_the_scope_passes_the_nodes_status_and_reason_through() -> None:
    class _Refuses(py_trees.behaviour.Behaviour):
        def update(self) -> Status:
            self.feedback_message = "refused for a reason"
            return Status.FAILURE

    node = _Refuses(name="Refuses")
    scope = with_act_keys(node, {INVITEE_ID: _INVITEE})
    assert isinstance(scope, ActKeyScope)
    assert scope.name == "Refuses"
    assert unscoped(scope) is node
    assert seeded_value(node, INVITEE_ID) == _INVITEE
    assert seeded_value(node, CASE_ID) is None

    _tick(scope)

    assert scope.status is Status.FAILURE
    assert scope.feedback_message == "refused for a reason"


@pytest.mark.spec("BT-25-011")
def test_a_scope_publishes_the_keys_it_seeds() -> None:
    """So the one-source check counts it as a source of each key."""
    scope = with_act_keys(
        _Fixed("Node"), {CASE_ID: _CASE, INVITEE_ID: _INVITEE}
    )
    assert published_act_keys(scope) == {CASE_ID, INVITEE_ID}


@pytest.mark.parametrize("missing", [None, ""])
def test_a_key_with_no_value_is_not_seeded(missing: str | None) -> None:
    node = _Fixed("Bare")
    assert with_act_keys(node, {CASE_ID: missing}) is node
    assert unscoped(node) is node
    assert seeded_value(node, CASE_ID) is None

    scope = with_act_keys(node, {CASE_ID: _CASE, INVITEE_ID: missing})
    assert isinstance(scope, ActKeyScope)
    assert dict(scope.seeds) == {CASE_ID: _CASE}


def test_seeding_a_seeded_node_adds_to_its_one_scope() -> None:
    """A seeded node always sits exactly one level below an unseeded one."""
    node = _Fixed("Node")
    scope = with_act_keys(
        with_act_keys(node, {CASE_ID: _CASE}), {INVITEE_ID: _INVITEE}
    )
    assert isinstance(scope, ActKeyScope)
    assert unscoped(scope) is node
    assert node.parent is scope
    assert dict(scope.seeds) == {CASE_ID: _CASE, INVITEE_ID: _INVITEE}

    again = with_act_keys(scope, {CASE_ID: _CASE})
    assert isinstance(again, ActKeyScope)
    assert dict(again.seeds) == dict(scope.seeds)


def test_seeding_a_key_again_with_another_value_raises() -> None:
    scope = with_act_keys(_Fixed("Node"), {CASE_ID: _CASE})
    with pytest.raises(ValueError, match="already seeded"):
        with_act_keys(scope, {CASE_ID: "https://example.org/c/other"})


@pytest.mark.spec("BTND-03-022")
def test_a_key_outside_the_vocabulary_is_refused() -> None:
    impostor = replace(REPORT_ID)
    with pytest.raises(TypeError, match="act-key vocabulary"):
        ActKeyScope(_Fixed("Node"), {impostor: "https://example.org/r/1"})


@pytest.mark.parametrize("missing", [None, ""])
def test_a_scope_built_with_no_value_is_refused(missing: str | None) -> None:
    with pytest.raises(ValueError, match="no value"):
        ActKeyScope(_Fixed("Node"), {CASE_ID: _CASE, INVITEE_ID: missing})


def test_an_empty_scope_is_refused() -> None:
    with pytest.raises(ValueError, match="must seed a key"):
        ActKeyScope(_Fixed("Node"), {})


def test_the_seeds_are_read_only() -> None:
    scope = ActKeyScope(_Fixed("Node"), {CASE_ID: _CASE})
    with pytest.raises(TypeError):
        scope.seeds[INVITEE_ID] = _INVITEE  # type: ignore[index]


# ---------------------------------------------------------------------------
# with_case_id is the seeder called for /case_id
# ---------------------------------------------------------------------------


@pytest.mark.spec("BTND-01-006")
def test_with_case_id_is_the_seeder_for_case_id() -> None:
    node = _Fixed("Node")
    scope = with_case_id(node, _CASE)
    assert isinstance(scope, ActKeyScope)
    assert dict(scope.seeds) == {CASE_ID: _CASE}
    assert seeded_case_id(node) == _CASE

    _tick(scope)

    assert node.seen == [(_CASE, "<absent>")]
    assert "/case_id" not in _storage()


@pytest.mark.spec("BTND-01-006")
@pytest.mark.parametrize("case_id", [None, ""])
def test_no_case_leaves_the_node_unwrapped(case_id: str | None) -> None:
    """A tree that names no case leaves the port to its tick-time writer."""
    node = _Fixed("Bare")
    assert with_case_id(node, case_id) is node
    assert seeded_case_id(node) is None
