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

"""Direct tests for ``ReplayHeldSuccessorNode`` (SYNC-14-009).

The use-case tests reach the node through the announce trees; these pin the
branches those trees never reach: a held ``Announce`` for a case with no
genesis anchor, and a successor with no replay port.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
    _make_event,
)
from test.support.case_manager import CASE_MANAGER_ID
from test.support.inbox_replay import (
    RecordingInboxReplay,
    held_depth,
    hold_received,
)
from vultron.core.behaviors.sync.nodes import ReplayHeldSuccessorNode
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity


@pytest.fixture
def replay() -> RecordingInboxReplay:
    return RecordingInboxReplay()


def _run(bridge, replay):
    return bridge.execute_with_setup(
        tree=ReplayHeldSuccessorNode(case_id=CASE_ID),
        actor_id=PARTICIPANT_ACTOR_ID,
        inbox_replay=replay,
    )


@pytest.mark.spec("SYNC-14-009")
def test_no_genesis_anchor_replays_nothing(bridge, datalayer, replay):
    """With the case not stored, no held Announce can extend the chain."""
    hold_received(datalayer, _make_event(_make_entry(0), CASE_MANAGER_ID))

    result = _run(bridge, replay)

    assert result.status == Status.SUCCESS
    assert replay.replayed == []
    assert held_depth(datalayer, CASE_ID) == 1


@pytest.mark.spec("SYNC-14-009")
def test_nothing_held_replays_nothing(bridge, case_obj, replay):
    result = _run(bridge, replay)

    assert result.status == Status.SUCCESS
    assert replay.replayed == []


@pytest.mark.spec("SYNC-14-009")
def test_no_successor_of_the_tail_replays_nothing(
    bridge, datalayer, case_obj, replay
):
    """A held Announce that does not extend the tail stays held."""
    hold_received(
        datalayer, _make_event(_make_entry(3, "ab" * 32), CASE_MANAGER_ID)
    )

    result = _run(bridge, replay)

    assert result.status == Status.SUCCESS
    assert replay.replayed == []
    assert held_depth(datalayer, CASE_ID) == 1


@pytest.mark.spec("SYNC-14-009")
def test_successor_with_no_replay_port_is_a_wiring_error(
    bridge, datalayer, case_obj
):
    """A successor with no port to replay it is a composition fault, and the
    Announce stays held."""
    hold_received(
        datalayer,
        _make_event(
            _make_entry(0, prev_hash=case_obj.genesis_hash), CASE_MANAGER_ID
        ),
    )

    result = bridge.execute_with_setup(
        tree=ReplayHeldSuccessorNode(case_id=CASE_ID),
        actor_id=PARTICIPANT_ACTOR_ID,
    )

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "inbox_replay" in (result.feedback_message or "")
    assert held_depth(datalayer, CASE_ID) == 1


@pytest.mark.spec("SYNC-14-009")
def test_successor_is_replayed_then_released(
    bridge, datalayer, case_obj, replay
):
    """The node replays the held Announce by its own id, then drops the
    index row."""
    event = _make_event(
        _make_entry(0, prev_hash=case_obj.genesis_hash), CASE_MANAGER_ID
    )
    hold_received(datalayer, event)

    result = _run(bridge, replay)

    assert result.status == Status.SUCCESS
    assert replay.replayed == [event.activity_id]
    assert held_depth(datalayer, CASE_ID) == 0


@pytest.mark.spec("SYNC-14-002")
@pytest.mark.spec("SYNC-14-009")
def test_successor_with_no_held_body_is_dropped_not_wedged(
    bridge, datalayer, case_obj, replay, caplog
):
    """An index row whose body is gone can never replay: the node drops it
    with a warning instead of failing every later drain of the case."""
    event = _make_event(
        _make_entry(0, prev_hash=case_obj.genesis_hash), CASE_MANAGER_ID
    )
    hold_received(datalayer, event)
    datalayer.delete(
        "DeferredInboxActivity",
        DeferredInboxActivity.build_id(event.activity_id),
    )

    with caplog.at_level("WARNING"):
        result = _run(bridge, replay)

    assert result.status == Status.SUCCESS
    assert replay.replayed == []
    assert held_depth(datalayer, CASE_ID) == 0
    assert "has no held body" in caplog.text
