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
"""Tests for the call-out time budget (BT-18-015, BT-18-026, BT-18-027).

Covers:

- :class:`TimeBoundedCallOut` raises :class:`CallOutBudgetExceededError`,
  naming the node and the budget, when its backend took longer than the
  budget, and discards the late answer whatever its verdict.
- Through :class:`BTBridge` the overrun is an internal error, not a protocol
  ``FAILURE``.
- The budget is ``ActorConfig.call_out_time_budget``, read when a bundle
  builds the node, and no literal duration appears at the seam.
- The seam measures on a :class:`StopwatchPort`; the system stopwatch is
  monotonic.
"""

from __future__ import annotations

import ast
import time
from datetime import timedelta
from pathlib import Path

import py_trees
import pytest
from py_trees.common import Access, Status
from pydantic import ValidationError

from test.support.call_out import FixedAnswerBackend
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.config.actor import DEFAULT_CALL_OUT_TIME_BUDGET, ActorConfig
from vultron.config.app import config_override, load_actor_config
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out import guard as guard_module
from vultron.core.behaviors.call_out.answer import (
    CallOutAnswer,
    CallOutContract,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.bundles.validation import (
    ValidationCallOutBundle,
)
from vultron.core.behaviors.call_out.guard import (
    CallOutBackendError,
    CallOutBudgetExceededError,
    CallOutContractError,
    SynchronousCallOut,
    TimeBoundedCallOut,
    guard_call_out_factory,
    time_bounded_call_out,
    unwrap_call_out,
)
from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.stopwatch import SystemStopwatch
from vultron.core.ports.clock import StopwatchPort
from vultron.errors import VultronError

ACTOR_ID = "https://example.org/actors/test-actor"
BUDGET = timedelta(milliseconds=100)
_YES = CallOutAnswer.yes({"probe_verdict": "ok"})

_CONTRACT = CallOutContract(
    outputs={"probe_verdict": str},
    refusal_reason_key="probe_refusal_reason",
)


class _FakeStopwatch:
    """A stopwatch the backend under test advances while it answers."""

    def __init__(self) -> None:
        self.now = 1000.0

    def seconds(self) -> float:
        return self.now


class _SlowBackend(FixedAnswerBackend):
    """Answers fixed, after advancing *stopwatch* by *took*."""

    def __init__(
        self,
        name: str,
        *,
        stopwatch: _FakeStopwatch,
        took: timedelta,
        fixed: CallOutAnswer,
    ) -> None:
        super().__init__(name, fixed=fixed, contract=_CONTRACT)
        self._stopwatch = stopwatch
        self._took = took

    def answer(self) -> CallOutAnswer:
        self._stopwatch.now += self._took.total_seconds()
        return super().answer()


class _SleepingBackend(CallOutBackend):
    """A backend that really blocks for a short time, then answers yes."""

    def answer(self) -> CallOutAnswer:
        time.sleep(0.05)
        return CallOutAnswer.yes()


def _seam(
    took: timedelta,
    fixed: CallOutAnswer = _YES,
) -> TimeBoundedCallOut:
    stopwatch = _FakeStopwatch()
    return TimeBoundedCallOut(
        _SlowBackend("Probe", stopwatch=stopwatch, took=took, fixed=fixed),
        budget=BUDGET,
        stopwatch=stopwatch,
    )


def _written(*keys: str) -> dict[str, object]:
    reader = py_trees.blackboard.Client(name="budget_probe_reader")
    for key in keys:
        reader.register_key(key, Access.READ)
    return {key: getattr(reader, key) for key in keys if reader.exists(key)}


@pytest.fixture(autouse=True)
def _clean_blackboard():
    py_trees.blackboard.Blackboard.clear()
    yield
    py_trees.blackboard.Blackboard.clear()


@pytest.fixture
def bridge() -> BTBridge:
    return BTBridge(
        datalayer=SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    )


# ---------------------------------------------------------------------------
# An overrun is an internal error naming the node and the budget (BT-18-027)
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-015")
@pytest.mark.spec("BT-18-027")
def test_overrun_surfaces_as_internal_error_naming_the_node(
    bridge: BTBridge,
) -> None:
    bt = bridge.setup_tree(
        tree=_seam(took=timedelta(milliseconds=250)), actor_id=ACTOR_ID
    )
    result = bridge.execute_tree(bt)
    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "CallOutBudgetExceededError" in result.feedback_message
    assert "'Probe'" in result.feedback_message
    assert "0.100s" in result.feedback_message


@pytest.mark.spec("BT-18-027")
def test_overrun_error_names_the_node_the_budget_and_the_time_taken() -> None:
    seam = _seam(took=timedelta(milliseconds=250))
    with pytest.raises(CallOutBudgetExceededError) as caught:
        seam.tick_once()
    assert caught.value.node_name == "Probe"
    assert caught.value.budget == BUDGET
    assert caught.value.elapsed == timedelta(milliseconds=250)
    assert str(caught.value).startswith("Call-out backend 'Probe' took 0.250s")
    assert "0.100s" in str(caught.value)


@pytest.mark.spec("BT-18-027")
def test_overrun_error_is_a_backend_error_not_a_vultron_error() -> None:
    error = CallOutBudgetExceededError("n", BUDGET, timedelta(seconds=1))
    assert isinstance(error, CallOutBackendError)
    assert isinstance(error, RuntimeError)
    assert not isinstance(error, VultronError)


@pytest.mark.spec("BT-18-027")
@pytest.mark.parametrize(
    "fixed",
    [
        pytest.param(CallOutAnswer.yes({"probe_verdict": "ok"}), id="yes"),
        pytest.param(CallOutAnswer.no("declined"), id="no"),
        pytest.param(CallOutAnswer.error("unreachable"), id="error"),
    ],
)
def test_late_answer_is_discarded_whatever_its_verdict(
    fixed: CallOutAnswer,
) -> None:
    seam = _seam(took=timedelta(milliseconds=250), fixed=fixed)
    with pytest.raises(CallOutBudgetExceededError):
        seam.tick_once()
    assert _written("probe_verdict", "probe_refusal_reason") == {}
    backend = unwrap_call_out(seam)
    assert isinstance(backend, CallOutBackend)
    assert backend.take_answer() is None


def test_overrun_is_logged_naming_the_node(
    caplog: pytest.LogCaptureFixture,
) -> None:
    seam = _seam(took=timedelta(milliseconds=250))
    with caplog.at_level("WARNING"), pytest.raises(CallOutBudgetExceededError):
        seam.tick_once()
    assert any(
        "'Probe'" in r.getMessage() and "0.100s" in r.getMessage()
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Within the budget the seam interprets the answer as before
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-015")
@pytest.mark.parametrize(
    "took",
    [timedelta(0), timedelta(milliseconds=50), BUDGET],
    ids=["instant", "within", "exactly-the-budget"],
)
def test_answer_within_the_budget_is_interpreted(took: timedelta) -> None:
    seam = _seam(took=took)
    seam.tick_once()
    assert seam.status == Status.SUCCESS
    assert _written("probe_verdict") == {"probe_verdict": "ok"}


def test_no_within_the_budget_is_a_protocol_failure(bridge: BTBridge) -> None:
    bt = bridge.setup_tree(
        tree=_seam(took=timedelta(0), fixed=CallOutAnswer.no("declined")),
        actor_id=ACTOR_ID,
    )
    result = bridge.execute_tree(bt)
    assert result.status == Status.FAILURE
    assert result.internal_error is False


def test_each_tick_is_timed_on_its_own() -> None:
    """A slow tick does not leak its start into the next one."""
    stopwatch = _FakeStopwatch()
    backend = _SlowBackend(
        "Probe",
        stopwatch=stopwatch,
        took=timedelta(milliseconds=60),
        fixed=CallOutAnswer.yes({"probe_verdict": "ok"}),
    )
    seam = TimeBoundedCallOut(backend, budget=BUDGET, stopwatch=stopwatch)
    for _ in range(3):
        seam.tick_once()
        assert seam.status == Status.SUCCESS


@pytest.mark.parametrize("budget", [timedelta(0), timedelta(seconds=-1)])
def test_seam_refuses_a_budget_that_is_not_positive(budget: timedelta) -> None:
    with pytest.raises(CallOutContractError, match="must be positive"):
        TimeBoundedCallOut(
            AlwaysSucceed("Probe"), budget=budget, stopwatch=SystemStopwatch()
        )


def test_seam_refuses_an_update_outside_its_own_tick() -> None:
    seam = TimeBoundedCallOut(
        AlwaysSucceed("Probe"), budget=BUDGET, stopwatch=SystemStopwatch()
    )
    with pytest.raises(CallOutContractError, match="outside its own tick"):
        seam.update()


# ---------------------------------------------------------------------------
# The budget comes from actor configuration (BT-18-026)
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-026")
def test_bundle_node_takes_the_budget_from_actor_configuration() -> None:
    with config_override(VULTRON_ACTOR__CALL_OUT_TIME_BUDGET="PT0.25S"):
        node = ValidationCallOutBundle().credibility_factory("Credibility")
    assert isinstance(node, TimeBoundedCallOut)
    assert node.budget == timedelta(milliseconds=250)


@pytest.mark.spec("BT-18-026")
def test_budget_is_read_when_the_tree_is_built_not_at_import() -> None:
    """One bundle built before the change still uses the configured value."""
    bundle = ValidationCallOutBundle()
    with config_override(VULTRON_ACTOR__CALL_OUT_TIME_BUDGET="PT2S"):
        node = bundle.credibility_factory("Credibility")
    assert isinstance(node, TimeBoundedCallOut)
    assert node.budget == timedelta(seconds=2)


@pytest.mark.spec("BT-18-026")
def test_default_budget_is_the_documented_actor_config_default() -> None:
    assert ActorConfig().call_out_time_budget == DEFAULT_CALL_OUT_TIME_BUDGET
    node = guard_call_out_factory(AlwaysSucceed)("Probe")
    assert isinstance(node, TimeBoundedCallOut)
    assert node.budget == load_actor_config().call_out_time_budget


@pytest.mark.parametrize("budget", [timedelta(0), timedelta(seconds=-1)])
def test_actor_config_refuses_a_budget_that_is_not_positive(
    budget: timedelta,
) -> None:
    with pytest.raises(ValidationError, match="must be positive"):
        ActorConfig(call_out_time_budget=budget)


@pytest.mark.spec("BT-18-015")
@pytest.mark.spec("BT-18-026")
@pytest.mark.spec("BT-18-027")
def test_configured_short_budget_catches_a_real_overrun(
    bridge: BTBridge,
) -> None:
    """End to end: configured budget, system stopwatch, a backend that blocks."""
    with config_override(VULTRON_ACTOR__CALL_OUT_TIME_BUDGET="PT0.001S"):
        node = ValidationCallOutBundle(
            credibility_factory=_SleepingBackend
        ).credibility_factory("SlowCredibility")
    bt = bridge.setup_tree(tree=node, actor_id=ACTOR_ID)
    result = bridge.execute_tree(bt)
    assert result.internal_error is True
    assert "'SlowCredibility'" in result.feedback_message
    assert "0.001s" in result.feedback_message


def _timedelta_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "timedelta"
    ]


@pytest.mark.spec("BT-18-026")
def test_no_literal_duration_appears_at_the_seam() -> None:
    source = Path(guard_module.__file__).read_text(encoding="utf-8")
    calls = _timedelta_calls(ast.parse(source))
    literal = [
        ast.unparse(call)
        for call in calls
        if any(
            isinstance(arg, ast.Constant)
            for arg in [*call.args, *(kw.value for kw in call.keywords)]
        )
    ]
    assert not literal, f"literal durations at the seam: {literal}"


# ---------------------------------------------------------------------------
# Wrapping is idempotent and name-transparent
# ---------------------------------------------------------------------------


def test_time_bounded_seam_is_name_transparent_and_a_seam() -> None:
    node = guard_call_out_factory(AlwaysSucceed)("Probe")
    assert node.name == "Probe"
    assert isinstance(node, SynchronousCallOut)
    assert isinstance(unwrap_call_out(node), AlwaysSucceed)


def test_time_bounding_a_time_bounded_seam_returns_it_unchanged() -> None:
    node = guard_call_out_factory(AlwaysSucceed)("Probe")
    assert time_bounded_call_out(node) is node


def test_plain_seam_from_a_factory_is_moved_behind_the_budget() -> None:
    backend = AlwaysSucceed("Probe")

    def factory(name: str) -> py_trees.behaviour.Behaviour:
        return SynchronousCallOut(backend)

    node = guard_call_out_factory(factory)("Probe")
    assert isinstance(node, TimeBoundedCallOut)
    assert node.decorated is backend
    assert backend.parent is node


# ---------------------------------------------------------------------------
# The stopwatch port
# ---------------------------------------------------------------------------


def test_system_stopwatch_is_a_monotonic_stopwatch_port() -> None:
    stopwatch = SystemStopwatch()
    assert isinstance(stopwatch, StopwatchPort)
    first = stopwatch.seconds()
    assert stopwatch.seconds() >= first
