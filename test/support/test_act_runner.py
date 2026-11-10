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
"""The test-side act runner runs each use case and tree as one act."""

import threading
from datetime import UTC, datetime, timedelta

import py_trees
import pytest
from py_trees.common import Status

from test.support.act_clock import ACT_AT, tree_lock_held
from test.support.act_runner import (
    FixedClock,
    in_act,
    run_dispatch,
    run_in_act,
    run_tree,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.bridge.act_instant import (
    inherited_act_instant,
    open_act,
    read_act_instant,
)

_ACTOR = "https://example.org/actors/runner"


def _bridge() -> BTBridge:
    return BTBridge(
        datalayer=SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    )


class _ReadsInstant:
    """A use case with no clock, as a received use case has none."""

    def __init__(self) -> None:
        self.seen: datetime | None = None
        self.locked = False

    def execute(self) -> str:
        self.seen = read_act_instant()
        self.locked = tree_lock_held()
        return "done"


class _OpensOwnAct:
    """A use case that holds a clock and opens its own act, as a trigger does."""

    def __init__(self, at: datetime) -> None:
        self._clock = FixedClock(at)
        self.seen: datetime | None = None

    def execute(self) -> str:
        with open_act(self._clock) as at:
            self.seen = at
            return "triggered"


class _ReadNode(py_trees.behaviour.Behaviour):
    def __init__(self) -> None:
        super().__init__(name="ReadNode")
        self.seen: datetime | None = None

    def update(self) -> Status:
        self.seen = read_act_instant()
        return Status.SUCCESS


def test_a_use_case_with_no_clock_runs_in_an_act_at_the_given_instant():
    uc = _ReadsInstant()

    assert run_in_act(uc, at=ACT_AT) == "done"

    assert uc.seen == ACT_AT
    assert uc.locked
    assert inherited_act_instant() is None


def test_the_instant_defaults_to_the_wall_clock():
    before = datetime.now(tz=UTC)
    uc = _ReadsInstant()

    run_in_act(uc)

    assert uc.seen is not None
    assert before <= uc.seen <= datetime.now(tz=UTC)


def test_a_use_case_that_opens_its_own_act_runs_from_its_own_clock():
    uc = _OpensOwnAct(ACT_AT)

    assert run_in_act(uc) == "triggered"

    assert uc.seen == ACT_AT


def test_an_instant_for_a_use_case_that_opens_its_own_act_is_refused():
    with pytest.raises(ValueError, match="FixedClock"):
        run_in_act(_OpensOwnAct(ACT_AT), at=ACT_AT)


def test_a_nested_run_inherits_the_open_acts_instant():
    uc = _ReadsInstant()

    with in_act(ACT_AT):
        run_in_act(uc)

    assert uc.seen == ACT_AT


def test_a_nested_run_with_another_instant_is_refused():
    with in_act(ACT_AT):
        with pytest.raises(ValueError, match="already open"):
            run_in_act(_ReadsInstant(), at=ACT_AT + timedelta(seconds=1))


def test_a_tree_runs_as_the_outermost_run_of_an_act():
    node = _ReadNode()

    result = run_tree(
        BTBridge(
            datalayer=SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
        ),
        node,
        actor_id=_ACTOR,
        at=ACT_AT,
    )

    assert result.status == Status.SUCCESS, result.feedback_message
    assert node.seen == ACT_AT
    assert inherited_act_instant() is None


def test_a_tree_run_inside_an_act_inherits_its_instant():
    node = _ReadNode()

    with in_act(ACT_AT):
        result = run_tree(
            BTBridge(
                datalayer=SqliteDataLayer(
                    "sqlite:///:memory:", actor_id=_ACTOR
                )
            ),
            node,
            actor_id=_ACTOR,
        )

    assert result.status == Status.SUCCESS, result.feedback_message
    assert node.seen == ACT_AT


def test_a_nested_run_may_restate_the_open_acts_instant():
    uc = _ReadsInstant()

    with in_act(ACT_AT):
        run_in_act(uc, at=ACT_AT)

    assert uc.seen == ACT_AT


def test_a_nested_tree_run_with_another_instant_is_refused():
    with in_act(ACT_AT):
        with pytest.raises(ValueError, match="already open"):
            run_tree(
                _bridge(),
                _ReadNode(),
                actor_id=_ACTOR,
                at=ACT_AT + timedelta(seconds=1),
            )


def test_another_threads_open_act_is_not_inherited():
    """The inherited check runs under the tree lock, as the bridge's does.

    ``/at`` is on the process-global blackboard, so a run that checked it
    before taking the lock would see this act as its own, run nested, and
    find no instant once the lock let it in.
    """
    opened = threading.Event()
    release = threading.Event()

    def hold_an_act() -> None:
        with in_act(ACT_AT):
            opened.set()
            release.wait(timeout=10)

    holder = threading.Thread(target=hold_an_act)
    holder.start()
    assert opened.wait(timeout=10)
    node = _ReadNode()
    result: list[object] = []
    runner = threading.Thread(
        target=lambda: result.append(
            run_tree(_bridge(), node, actor_id=_ACTOR)
        )
    )
    runner.start()
    # Give the runner time to reach its check while the act is still open.
    # It cannot finish meanwhile: either way it waits for the tree lock.
    runner.join(timeout=0.5)
    release.set()
    holder.join(timeout=10)
    runner.join(timeout=10)

    assert len(result) == 1
    # Its own act, at the wall clock, not the other thread's instant.
    assert node.seen is not None
    assert node.seen != ACT_AT


class _Dispatches:
    def __init__(self) -> None:
        self.seen: datetime | None = None

    def dispatch(self, event: object, dl: object, **kwargs: object) -> object:
        self.seen = read_act_instant()
        return kwargs


def test_a_dispatch_runs_in_an_act_and_passes_its_arguments_on():
    target = _Dispatches()

    assert run_dispatch(target, "event", "dl", at=ACT_AT, dispatcher="d") == {
        "dispatcher": "d"
    }

    assert target.seen == ACT_AT
