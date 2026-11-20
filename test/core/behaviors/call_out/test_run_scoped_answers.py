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
"""A call-out's answer lives for the run that wrote it (BT-17-020, #6789).

A seam writes its answer through its own blackboard client, and a later
sibling of the same run reads it.  ``BTBridge.execute_with_setup`` restores
every key a seam of the tree it runs may write, so the next run never sees
the answer or the refusal reason, and a nested run puts back the outer run's.
"""

from __future__ import annotations

import py_trees
import pytest
from py_trees.common import Status

from test.support.act_runner import run_tree
from test.support.call_out import FixedAnswerBackend
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out.answer import (
    CallOutAnswer,
    CallOutContract,
)
from vultron.core.behaviors.call_out.guard import (
    SynchronousCallOut,
    call_out_written_keys,
)

ACTOR_ID = "https://example.org/actors/test-actor"

_CONTRACT = CallOutContract(
    outputs={"probe_verdict": str},
    refusal_reason_key="probe_refusal_reason",
    refusal_fields={"probe_refusal_code": str},
)
_WRITTEN = ("probe_verdict", "probe_refusal_reason", "probe_refusal_code")


class _Peek(py_trees.behaviour.Behaviour):
    """Record what each written key holds when this node ticks."""

    def __init__(self) -> None:
        super().__init__(name="Peek")
        self.seen: dict[str, object] = {}

    def update(self) -> Status:
        storage = py_trees.blackboard.Blackboard.storage
        self.seen = {
            key: storage[f"/{key}"] for key in _WRITTEN if f"/{key}" in storage
        }
        return Status.SUCCESS


def _seam(answer: CallOutAnswer) -> SynchronousCallOut:
    return SynchronousCallOut(
        FixedAnswerBackend("Probe", fixed=answer, contract=_CONTRACT)
    )


def _seam_then_peek(
    answer: CallOutAnswer,
) -> tuple[py_trees.behaviour.Behaviour, _Peek]:
    """A seam whose answer a later sibling reads, as a tree reads it."""
    peek = _Peek()
    tree = py_trees.composites.Selector(
        name="AnswerThenPeek",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="Asks", memory=False, children=[_seam(answer), peek]
            ),
            _peek_after_refusal(peek),
        ],
    )
    return tree, peek


def _peek_after_refusal(peek: _Peek) -> py_trees.behaviour.Behaviour:
    """A refusal arm: the reader runs after the seam's *no*, too."""

    class _Again(py_trees.behaviour.Behaviour):
        def update(self) -> Status:
            peek.update()
            return Status.SUCCESS

    return _Again(name="PeekAfterRefusal")


def _peek_only() -> tuple[py_trees.behaviour.Behaviour, _Peek]:
    """A later run whose call-out does not tick: only the reader runs."""
    peek = _Peek()
    tree = py_trees.composites.Selector(
        name="AnswerSkipped",
        memory=False,
        children=[
            peek,
            _seam(CallOutAnswer.yes({"probe_verdict": "unreached"})),
        ],
    )
    return tree, peek


@pytest.fixture
def bridge() -> BTBridge:
    return BTBridge(
        datalayer=SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    )


def _storage_keys() -> set[str]:
    return set(py_trees.blackboard.Blackboard.storage)


@pytest.mark.spec("BT-17-020")
@pytest.mark.parametrize(
    ("answer", "within_run"),
    [
        pytest.param(
            CallOutAnswer.yes({"probe_verdict": "admit"}),
            {"probe_verdict": "admit"},
            id="yes",
        ),
        pytest.param(
            CallOutAnswer.no("declined", {"probe_refusal_code": "X"}),
            {"probe_refusal_reason": "declined", "probe_refusal_code": "X"},
            id="no",
        ),
    ],
)
def test_one_runs_answer_is_not_visible_to_the_next_run(
    bridge: BTBridge,
    answer: CallOutAnswer,
    within_run: dict[str, object],
) -> None:
    first, first_peek = _seam_then_peek(answer)
    run_tree(bridge, first, actor_id=ACTOR_ID)
    # The later sibling of the same run read the answer ...
    assert first_peek.seen == within_run
    # ... and nothing of it outlives the run, under either spelling.
    assert _storage_keys().isdisjoint(
        {alias for key in _WRITTEN for alias in (key, f"/{key}")}
    )

    second, second_peek = _peek_only()
    result = run_tree(bridge, second, actor_id=ACTOR_ID)
    assert result.status == Status.SUCCESS
    assert second_peek.seen == {}


@pytest.mark.spec("BT-17-020")
def test_a_nested_runs_answer_puts_back_the_outer_runs(
    bridge: BTBridge,
) -> None:
    """The inner run restores its seams' keys to the outer run's values."""
    outer_seen: dict[str, object] = {}

    class _RunNested(py_trees.behaviour.Behaviour):
        def update(self) -> Status:
            inner, _ = _seam_then_peek(
                CallOutAnswer.yes({"probe_verdict": "inner"})
            )
            run_tree(bridge, inner, actor_id=ACTOR_ID)
            storage = py_trees.blackboard.Blackboard.storage
            outer_seen["probe_verdict"] = storage.get("/probe_verdict")
            return Status.SUCCESS

    outer = py_trees.composites.Sequence(
        name="Outer",
        memory=False,
        children=[
            _seam(CallOutAnswer.yes({"probe_verdict": "outer"})),
            _RunNested(name="RunNested"),
        ],
    )
    run_tree(bridge, outer, actor_id=ACTOR_ID)
    assert outer_seen == {"probe_verdict": "outer"}
    assert "/probe_verdict" not in py_trees.blackboard.Blackboard.storage


@pytest.mark.spec("BT-17-020")
def test_a_value_present_before_the_run_is_put_back(
    bridge: BTBridge,
) -> None:
    storage = py_trees.blackboard.Blackboard.storage
    storage["/probe_verdict"] = "before"
    tree, peek = _seam_then_peek(CallOutAnswer.yes({"probe_verdict": "run"}))
    run_tree(bridge, tree, actor_id=ACTOR_ID)
    assert peek.seen == {"probe_verdict": "run"}
    assert storage["/probe_verdict"] == "before"


@pytest.mark.spec("BT-17-020")
def test_the_written_keys_are_every_seams_outputs_and_refusal_ports() -> None:
    other = SynchronousCallOut(
        FixedAnswerBackend("Other", fixed=CallOutAnswer.yes())
    )
    tree = py_trees.composites.Sequence(
        name="TwoSeams",
        memory=False,
        children=[_seam(CallOutAnswer.yes({"probe_verdict": "v"})), other],
    )
    assert call_out_written_keys(tree) == sorted(
        {*_WRITTEN, *other.written_keys()}
    )
    assert other.written_keys() == ("call_out_refusal_reason",)
