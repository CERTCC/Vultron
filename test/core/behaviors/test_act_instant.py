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
"""An act reads the clock once, and its tree runs carry that instant (ADR-0176)."""

from datetime import UTC, datetime, timedelta
from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import make_embargo_case_with_actor
from test.support.act_clock import CountingClock, tree_lock_held
from test.support.embargo_register import activate
from test.support.objects import make
from vultron.adapters.driven.clock import SystemBookkeepingClock, SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.bridge.act_instant import (
    ACT_INSTANT_KEY,
    act_instant_in_tree_run,
    open_act,
    read_act_instant,
)
from vultron.core.behaviors.case.case_clock_decisions import (
    case_clock_decisions,
)
from vultron.core.behaviors.case.nodes.clock_decision_stage import (
    create_clock_decision_gate,
)
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.models._helpers import SteppingClock, clock as helpers_clock
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.clock import BookkeepingClockPort, ClockPort
from vultron.errors import (
    VultronMissingActInstantError,
    VultronWiringError,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_ACTOR = "https://example.org/actors/act-instant"
_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


class _ReadsInstant(py_trees.behaviour.Behaviour):
    """A leaf that reads the act's instant when it ticks, as a node must."""

    def __init__(self, seen: list[datetime]) -> None:
        super().__init__(name="ReadsInstant")
        self._seen = seen

    def update(self) -> Status:
        self._seen.append(read_act_instant())
        return Status.SUCCESS


class _RunsNested(py_trees.behaviour.Behaviour):
    """A leaf that runs a nested bridge, as an emit node runs its commit tree."""

    def __init__(
        self,
        dl: SqliteDataLayer,
        seen: list[datetime],
        at: datetime | None = None,
    ) -> None:
        super().__init__(name="RunsNested")
        self._dl = dl
        self._seen = seen
        self._at = at
        self.result: BTExecutionResult | None = None

    def update(self) -> Status:
        result = BTBridge(datalayer=self._dl).execute_with_setup(
            _ReadsInstant(self._seen), actor_id=_ACTOR, at=self._at
        )
        self.result = result
        return (
            Status.SUCCESS
            if result.status == Status.SUCCESS
            else (Status.FAILURE)
        )


@pytest.fixture
def dl():
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    yield store
    store.close()


def _at_on_blackboard() -> bool:
    storage = py_trees.blackboard.Blackboard.storage
    return any(
        alias in storage for alias in (ACT_INSTANT_KEY, f"/{ACT_INSTANT_KEY}")
    )


class TestOpenAct:
    @pytest.mark.spec("CS-13-002")
    def test_reads_the_clock_once_after_taking_the_tree_lock(self):
        clock = CountingClock()

        with open_act(clock) as at:
            assert tree_lock_held()

        assert at == _AT
        assert clock.reads == 1
        assert clock.locked_at_read == [True]
        assert not tree_lock_held()

    @pytest.mark.spec("CS-13-001")
    def test_a_naive_instant_is_a_wiring_fault(self):
        class _Naive:
            def now(self) -> datetime:
                return datetime.fromisoformat("2026-03-01T00:00:00")

        with pytest.raises(VultronWiringError, match="naive"):
            with open_act(_Naive()):
                pass  # pragma: no cover

    @pytest.mark.spec("CS-13-002")
    def test_a_nested_act_reads_its_own_instant(self):
        later = _AT + timedelta(seconds=5)
        clock = CountingClock(_AT, later)

        with open_act(clock) as outer:
            with open_act(clock) as inner:
                pass

        assert (outer, inner) == (_AT, later)


class TestTreeRunInstant:
    @pytest.mark.spec("CS-13-002")
    def test_the_outermost_run_carries_the_instant_it_is_given(self, dl):
        seen: list[datetime] = []

        result = BTBridge(datalayer=dl).execute_with_setup(
            _ReadsInstant(seen), actor_id=_ACTOR, at=_AT
        )

        assert result.status == Status.SUCCESS
        assert seen == [_AT]
        # One act's instant never reaches the next act.
        assert not _at_on_blackboard()

    @pytest.mark.spec("CS-13-002")
    def test_a_nested_run_inherits_the_acts_instant(self, dl):
        seen: list[datetime] = []
        nested = _RunsNested(dl, seen)

        result = BTBridge(datalayer=dl).execute_with_setup(
            nested, actor_id=_ACTOR, at=_AT
        )

        assert result.status == Status.SUCCESS
        assert seen == [_AT]

    @pytest.mark.spec("CS-13-002")
    def test_a_nested_run_may_restate_the_same_instant(self, dl):
        seen: list[datetime] = []

        result = BTBridge(datalayer=dl).execute_with_setup(
            _RunsNested(dl, seen, at=_AT), actor_id=_ACTOR, at=_AT
        )

        assert result.status == Status.SUCCESS
        assert seen == [_AT]

    @pytest.mark.spec("CS-13-002")
    def test_a_nested_run_handed_another_instant_fails(self, dl):
        seen: list[datetime] = []
        nested = _RunsNested(dl, seen, at=_AT + timedelta(seconds=1))

        BTBridge(datalayer=dl).execute_with_setup(
            nested, actor_id=_ACTOR, at=_AT
        )

        assert nested.result is not None
        assert nested.result.status == Status.FAILURE
        assert nested.result.internal_error
        assert "VultronConflictingActInstantError" in (
            nested.result.feedback_message
        )
        assert seen == []

    @pytest.mark.spec("ARCH-10-001")
    def test_a_node_in_a_run_without_an_instant_fails_and_reads_no_clock(
        self, dl, monkeypatch
    ):
        stepping = SteppingClock(_AT)
        monkeypatch.setattr(helpers_clock, "datetime", stepping)
        seen: list[datetime] = []

        result = BTBridge(datalayer=dl).execute_with_setup(
            _ReadsInstant(seen), actor_id=_ACTOR
        )

        assert result.status == Status.FAILURE
        assert result.internal_error
        assert VultronMissingActInstantError.__name__ in (
            result.feedback_message
        )
        assert seen == []
        # The clock was never asked: its next read is still its first.
        assert stepping.now() == _AT + timedelta(seconds=1)

    @pytest.mark.spec("ARCH-10-001")
    def test_reading_outside_any_run_raises(self):
        with pytest.raises(VultronMissingActInstantError):
            read_act_instant()

    def test_act_instant_in_tree_run_restores_what_was_there(self):
        later = _AT + timedelta(seconds=1)
        with act_instant_in_tree_run(_AT):
            with act_instant_in_tree_run(later):
                assert read_act_instant() == later
            assert read_act_instant() == _AT
        assert not _at_on_blackboard()

    def test_act_instant_in_tree_run_refuses_a_naive_instant(self):
        with pytest.raises(VultronWiringError, match="naive"):
            with act_instant_in_tree_run(
                datetime.fromisoformat("2026-03-01T00:00:00")
            ):
                pass  # pragma: no cover


class TestSystemClocks:
    def test_the_system_clocks_satisfy_their_ports_and_not_each_other(self):
        assert isinstance(SystemClock(), ClockPort)
        assert isinstance(SystemBookkeepingClock(), BookkeepingClockPort)
        # Distinct operations, so neither clock is accepted for the other.
        assert not isinstance(SystemClock(), BookkeepingClockPort)
        assert not isinstance(SystemBookkeepingClock(), ClockPort)

    def test_the_act_clock_follows_a_recording_clock(self, monkeypatch):
        monkeypatch.setattr(
            helpers_clock, "datetime", SteppingClock(_AT, timedelta(0))
        )

        assert SystemClock().now() == _AT

    def test_the_bookkeeping_clock_is_unseen_by_a_recording_clock(
        self, monkeypatch
    ):
        stepping = SteppingClock(_AT)
        monkeypatch.setattr(helpers_clock, "datetime", stepping)

        stamp = SystemBookkeepingClock().bookkeeping_now()

        assert stamp.tzinfo is not None
        assert stamp != _AT + timedelta(seconds=1)
        # A bookkeeping read never moves the recording clock (ADR-0176).
        assert stepping.now() == _AT + timedelta(seconds=1)


class _PortsNodeReadsInstant(DataLayerConditionWithPorts):
    """A ports node reading the act's instant through its declared port."""

    def __init__(self, seen: list[datetime]) -> None:
        super().__init__(name="PortsNodeReadsInstant")
        self._seen = seen

    def update(self) -> Status:
        self._seen.append(self._require_act_instant())
        return Status.SUCCESS


class _ActionNodeReadsInstant(DataLayerActionWithPorts):
    """The same read on the action base."""

    def __init__(self, seen: list[datetime]) -> None:
        super().__init__(name="ActionNodeReadsInstant")
        self._seen = seen

    def update(self) -> Status:
        self._seen.append(self._require_act_instant())
        return Status.SUCCESS


@pytest.mark.parametrize(
    "node_type", [_PortsNodeReadsInstant, _ActionNodeReadsInstant]
)
class TestPortsNodeReadsTheInstant:
    @pytest.mark.spec("BTND-03-001")
    @pytest.mark.spec("CS-13-002")
    def test_reads_the_runs_instant_through_its_port(self, dl, node_type):
        seen: list[datetime] = []

        result = BTBridge(datalayer=dl).execute_with_setup(
            node_type(seen), actor_id=_ACTOR, at=_AT
        )

        assert result.status == Status.SUCCESS
        assert seen == [_AT]

    @pytest.mark.spec("ARCH-10-001")
    def test_fails_as_an_internal_error_without_one(self, dl, node_type):
        seen: list[datetime] = []

        result = BTBridge(datalayer=dl).execute_with_setup(
            node_type(seen), actor_id=_ACTOR
        )

        assert result.status == Status.FAILURE
        assert result.internal_error
        assert VultronMissingActInstantError.__name__ in (
            result.feedback_message
        )
        assert seen == []


_CASE = "https://example.org/cases/act-instant-no-act"


@pytest.mark.spec("CS-13-002")
def test_a_clock_decision_outside_an_act_is_an_internal_error() -> None:
    """With no instant in the run, a deciding node raises; it never reads
    the clock instead (ARCH-10-001)."""
    store, _, case, embargo = make_embargo_case_with_actor(
        _CASE, _ACTOR, case_manager_actor_id=_ACTOR
    )
    store.save(
        make(
            as_EmbargoEvent,
            id_=embargo.id_,
            context=_CASE,
            end_time=_AT + timedelta(days=30),
        )
    )
    stored = cast(VulnerabilityCase, store.read(case.id_))
    activate(stored, embargo.id_)
    store.save(stored)
    gate = create_clock_decision_gate(_CASE, case_clock_decisions(_CASE))
    tree = py_trees.composites.Sequence(
        name="NoAct", memory=False, children=[gate]
    )

    result = BTBridge(datalayer=store).execute_with_setup(
        tree, actor_id=_ACTOR
    )

    assert result.internal_error
    assert "act instant" in result.feedback_message
