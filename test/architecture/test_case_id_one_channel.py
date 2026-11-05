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
"""Architecture test: a node with a ``case_id`` port takes no ``case_id`` argument.

A node that declares ``case_id`` as an input port reads it from the
blackboard in some tree.  BTND-01-006 says it then reads it from that port in
every tree, never also from a constructor argument: a constructor value with
a port fallback is the dual channel that let a ``/case_id`` left by one
delivery decide a later delivery's path (#5803).  A tree that knows the case
at build time seeds the port with
:func:`~vultron.core.behaviors.case_id_scope.with_case_id` instead
(BTND-10-005, ADR-0089).

The check is over every ``PortsMixin`` class under ``vultron.core.behaviors``,
found by import rather than by a list of names, so a new node with both
channels fails it whatever it is called.
"""

import importlib
import inspect
import pkgutil

import py_trees
import pytest
from py_trees.ports import PortsMixin

import vultron.core.behaviors
from vultron.core.behaviors.case_id_scope import (
    CaseIdScope,
    seeded_case_id,
    unscoped,
    with_case_id,
)
from vultron.subclasses import all_subclasses

_PORT = "case_id"


def _import_all_behavior_modules() -> None:
    for info in pkgutil.walk_packages(
        vultron.core.behaviors.__path__, "vultron.core.behaviors."
    ):
        importlib.import_module(info.name)


def _case_id_port_classes() -> list[type]:
    """Every vultron ``PortsMixin`` class that declares a ``case_id`` input."""
    _import_all_behavior_modules()
    # PortsMixin is abstract, which mypy refuses as a ``type[T]`` argument.
    root: type[object] = PortsMixin
    found = [
        cls
        for cls in all_subclasses(root)
        if cls.__module__.startswith("vultron.")
        and _PORT in (getattr(cls, "INPUT_PORTS", None) or {})
    ]
    return sorted(found, key=lambda c: f"{c.__module__}.{c.__qualname__}")


def _takes_case_id(cls: type) -> bool:
    """True when ``cls(...)`` accepts a ``case_id`` argument."""
    parameters = inspect.signature(cls).parameters
    return _PORT in parameters


@pytest.mark.spec("BTND-01-006")
def test_case_id_port_classes_are_discovered() -> None:
    """Guards the check below against passing vacuously."""
    names = {cls.__name__ for cls in _case_id_port_classes()}
    assert {
        "ReceivedPathNode",
        "CheckIsCaseManagerNode",
        "CommitCaseLedgerEntryNode",
        "CheckLedgerFreshnessNode",
        "ActorHoldsRoleInCaseNode",
        "SenderIsCaseOwnerNode",
        "CreateParticipantStatusNode",
    } <= names


@pytest.mark.spec("BTND-01-006")
@pytest.mark.spec("BTND-10-005")
def test_no_node_reads_case_id_from_both_a_port_and_its_constructor() -> None:
    dual = [
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in _case_id_port_classes()
        if _takes_case_id(cls)
    ]
    assert dual == [], (
        "These nodes declare a case_id input port and also accept a case_id"
        " constructor argument.  Read it from the port alone, and have"
        " build-time callers seed the port with with_case_id(node, case_id)"
        " (BTND-01-006, BTND-10-005):\n" + "\n".join(f"  {d}" for d in dual)
    )


# ---------------------------------------------------------------------------
# The seeding scope itself: the seed reaches the node, and nothing else
# ---------------------------------------------------------------------------


class _ReadCaseId(py_trees.behaviour.Behaviour):
    """Records the ``/case_id`` it sees when ticked."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.seen: list[object] = []

    def update(self) -> py_trees.common.Status:
        storage = py_trees.blackboard.Blackboard.storage
        self.seen.append(storage.get("/case_id", "<absent>"))
        return py_trees.common.Status.SUCCESS


def _tick(root: py_trees.behaviour.Behaviour) -> None:
    for _ in root.tick():
        pass


@pytest.mark.spec("BTND-01-006")
@pytest.mark.spec("BT-09-002")
def test_the_seed_is_visible_to_the_node_alone() -> None:
    """A later sibling, and a later execution, see what they saw before."""
    storage = py_trees.blackboard.Blackboard.storage
    storage.pop("/case_id", None)
    storage.pop("case_id", None)
    seeded, after = _ReadCaseId("Seeded"), _ReadCaseId("After")
    root = py_trees.composites.Sequence(
        name="Root",
        memory=False,
        children=[with_case_id(seeded, "https://example.org/c/1"), after],
    )

    _tick(root)

    assert seeded.seen == ["https://example.org/c/1"]
    assert after.seen == ["<absent>"]
    assert "/case_id" not in storage


@pytest.mark.spec("BTND-01-006")
def test_the_seed_restores_a_case_an_earlier_node_published() -> None:
    storage = py_trees.blackboard.Blackboard.storage
    storage["/case_id"] = "https://example.org/c/published"
    try:
        node = _ReadCaseId("Seeded")
        _tick(with_case_id(node, "https://example.org/c/seeded"))
        assert node.seen == ["https://example.org/c/seeded"]
        assert storage["/case_id"] == "https://example.org/c/published"
    finally:
        storage.pop("/case_id", None)


@pytest.mark.spec("BTND-01-006")
def test_the_seed_is_restored_when_the_node_raises() -> None:
    class _Raises(py_trees.behaviour.Behaviour):
        def update(self) -> py_trees.common.Status:
            raise RuntimeError("boom")

    storage = py_trees.blackboard.Blackboard.storage
    storage.pop("/case_id", None)
    with pytest.raises(RuntimeError, match="boom"):
        _tick(with_case_id(_Raises(name="Raises"), "https://example.org/c/1"))
    assert "/case_id" not in storage


@pytest.mark.spec("BTND-01-006")
@pytest.mark.parametrize("case_id", [None, ""])
def test_no_case_leaves_the_node_unwrapped(case_id: str | None) -> None:
    """A tree that names no case leaves the port to its tick-time writer."""
    node = _ReadCaseId("Bare")
    assert with_case_id(node, case_id) is node
    assert unscoped(node) is node
    assert seeded_case_id(node) is None


@pytest.mark.spec("BTND-01-006")
def test_the_scope_passes_the_nodes_status_and_reason_through() -> None:
    class _Refuses(py_trees.behaviour.Behaviour):
        def update(self) -> py_trees.common.Status:
            self.feedback_message = "refused for a reason"
            return py_trees.common.Status.FAILURE

    node = _Refuses(name="Refuses")
    scope = with_case_id(node, "https://example.org/c/1")
    assert isinstance(scope, CaseIdScope)
    assert unscoped(scope) is node
    assert seeded_case_id(node) == "https://example.org/c/1"

    _tick(scope)

    assert scope.status is py_trees.common.Status.FAILURE
    assert scope.feedback_message == "refused for a reason"
