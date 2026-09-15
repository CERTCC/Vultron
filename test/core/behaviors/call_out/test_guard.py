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
"""Tests for the call-out seam RUNNING guard (BT-18-011, ADR-0080).

Covers:

- :class:`SynchronousCallOut` raises :class:`CallOutContractError` (a
  non-``VultronError``) when its child returns ``Status.RUNNING``.
- The failure surfaces through :class:`BTBridge` as ``internal_error=True``.
- ``SUCCESS`` / ``FAILURE`` pass through untouched and the guard is
  name-transparent.
- :func:`guard_call_out_factory` is idempotent (no double-wrap).
- Every core DETERMINISTIC bundle hands out guard-wrapped nodes.
"""

from __future__ import annotations

import dataclasses
import importlib
import pkgutil
from typing import Any

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out import bundles as core_bundles
from vultron.core.behaviors.call_out.guard import (
    CallOutContractError,
    SynchronousCallOut,
    guard_call_out_factory,
    unwrap_call_out,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.errors import VultronError

ACTOR_ID = "https://example.org/actors/test-actor"


class _RunningBackend(py_trees.behaviour.Behaviour):
    """A mis-wired call-out backend that returns RUNNING (forbidden)."""

    def update(self) -> Status:
        return Status.RUNNING


class _SuccessBackend(py_trees.behaviour.Behaviour):
    def update(self) -> Status:
        return Status.SUCCESS


class _FailureBackend(py_trees.behaviour.Behaviour):
    def update(self) -> Status:
        return Status.FAILURE


@pytest.fixture
def bridge() -> BTBridge:
    return BTBridge(
        datalayer=SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    )


# ---------------------------------------------------------------------------
# SynchronousCallOut unit behavior
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-011")
def test_guard_raises_call_out_contract_error_on_running() -> None:
    """A child returning RUNNING raises CallOutContractError naming the node."""
    guarded = SynchronousCallOut(_RunningBackend("BadBackend"))
    with pytest.raises(CallOutContractError) as excinfo:
        guarded.tick_once()
    assert "BadBackend" in str(excinfo.value)


@pytest.mark.spec("BT-18-011")
def test_call_out_contract_error_is_not_a_vultron_error() -> None:
    """The error MUST be a plain RuntimeError, not a VultronError (bridge classifies it)."""
    err = CallOutContractError("x")
    assert isinstance(err, RuntimeError)
    assert not isinstance(err, VultronError)


@pytest.mark.spec("BT-18-011")
def test_guard_passes_success_through() -> None:
    guarded = SynchronousCallOut(_SuccessBackend("Ok"))
    guarded.tick_once()
    assert guarded.status == Status.SUCCESS


@pytest.mark.spec("BT-18-011")
def test_guard_passes_failure_through() -> None:
    guarded = SynchronousCallOut(_FailureBackend("No"))
    guarded.tick_once()
    assert guarded.status == Status.FAILURE


def test_guard_is_name_transparent() -> None:
    """The guard adopts the child name; the child is reachable via unwrap."""
    child = AlwaysSucceed("EvaluateReportCredibility")
    guarded = SynchronousCallOut(child)
    assert guarded.name == "EvaluateReportCredibility"
    assert unwrap_call_out(guarded) is child


def test_unwrap_returns_node_when_not_guarded() -> None:
    node = AlwaysSucceed("Plain")
    assert unwrap_call_out(node) is node


# ---------------------------------------------------------------------------
# Bridge integration: RUNNING surfaces as internal_error
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-011")
def test_running_backend_surfaces_as_internal_error(bridge: BTBridge) -> None:
    """Through the bridge, a guarded RUNNING backend is an internal error.

    Not a protocol FAILURE: a mis-wired backend is a wiring bug, so the
    non-VultronError CallOutContractError must land in the bridge's
    ``except Exception`` branch (internal_error=True).
    """
    tree = SynchronousCallOut(_RunningBackend("BadBackend"))
    bt = bridge.setup_tree(tree=tree, actor_id=ACTOR_ID)

    result = bridge.execute_tree(bt)

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "CallOutContractError" in result.feedback_message


def test_success_backend_is_not_internal_error(bridge: BTBridge) -> None:
    tree = SynchronousCallOut(_SuccessBackend("Ok"))
    bt = bridge.setup_tree(tree=tree, actor_id=ACTOR_ID)

    result = bridge.execute_tree(bt)

    assert result.status == Status.SUCCESS
    assert result.internal_error is False


# ---------------------------------------------------------------------------
# guard_call_out_factory idempotence
# ---------------------------------------------------------------------------


def test_guard_factory_wraps_produced_node() -> None:
    guarded_factory = guard_call_out_factory(lambda name: AlwaysSucceed(name))
    node = guarded_factory("Node")
    assert isinstance(node, SynchronousCallOut)
    assert isinstance(unwrap_call_out(node), AlwaysSucceed)


def test_guard_factory_is_idempotent_on_factory() -> None:
    """Wrapping an already-guarded factory returns it unchanged."""
    once = guard_call_out_factory(lambda name: AlwaysFail(name))
    twice = guard_call_out_factory(once)
    assert twice is once


def test_guard_factory_does_not_double_wrap_node() -> None:
    """A node that is already a SynchronousCallOut is not wrapped again."""

    def factory(name: str) -> py_trees.behaviour.Behaviour:
        return SynchronousCallOut(AlwaysSucceed(name))

    node = guard_call_out_factory(factory)("Node")
    assert isinstance(node, SynchronousCallOut)
    # Not doubly wrapped: the decorated child is the leaf, not another guard.
    assert not isinstance(unwrap_call_out(node), SynchronousCallOut)


# ---------------------------------------------------------------------------
# Bundle boundary (AC-2): every core DETERMINISTIC bundle guards its factories
# ---------------------------------------------------------------------------


def _core_deterministic_singletons() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mod_info in pkgutil.iter_modules(core_bundles.__path__):
        module = importlib.import_module(
            f"{core_bundles.__name__}.{mod_info.name}"
        )
        for name in dir(module):
            if not name.endswith("_DETERMINISTIC"):
                continue
            obj = getattr(module, name)
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                out[name] = obj
    return out


@pytest.mark.spec("BT-18-011")
def test_every_core_bundle_factory_is_guarded() -> None:
    """Every factory on every core DETERMINISTIC bundle yields a guarded node."""
    singletons = _core_deterministic_singletons()
    assert singletons, "no DETERMINISTIC bundle singletons discovered"
    for singleton_name, singleton in singletons.items():
        for f in dataclasses.fields(singleton):
            node = getattr(singleton, f.name)(f.name)
            assert isinstance(node, SynchronousCallOut), (
                f"{singleton_name}.{f.name} did not hand out a guard-wrapped "
                "node"
            )
