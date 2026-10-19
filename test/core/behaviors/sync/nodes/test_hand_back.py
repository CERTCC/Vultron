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

"""Direct tests for ``HandBackBufferedSuccessorNode`` (SYNC-14-009).

The use-case tests reach the node through the announce trees; these pin the
branches those trees never reach: a buffered entry for a case with no genesis
anchor, and a successor with no executing actor to hand it to.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
)
from test.support.case_manager import (
    CASE_MANAGER_ID,
    add_case_manager_participant,
)
from test.support.inbox_hand_back import RecordingInboxHandBack
from vultron.core.behaviors.sync.nodes import HandBackBufferedSuccessorNode
from vultron.core.models.ledger_gap_buffer import LedgerGapBuffer


@pytest.fixture
def gap_buffer() -> LedgerGapBuffer:
    return LedgerGapBuffer()


@pytest.fixture
def hand_back() -> RecordingInboxHandBack:
    return RecordingInboxHandBack()


def _run(bridge, gap_buffer, hand_back, actor_id=PARTICIPANT_ACTOR_ID):
    return bridge.execute_with_setup(
        tree=HandBackBufferedSuccessorNode(case_id=CASE_ID),
        actor_id=actor_id,
        gap_buffer=gap_buffer,
        inbox_hand_back=hand_back,
    )


@pytest.mark.spec("SYNC-14-009")
def test_no_genesis_anchor_hands_nothing_back(bridge, gap_buffer, hand_back):
    """With the case not stored, no buffered entry can extend the chain."""
    entry = _make_entry(0)
    gap_buffer.buffer(entry)

    result = _run(bridge, gap_buffer, hand_back)

    assert result.status == Status.SUCCESS
    assert hand_back.handed_back == []
    assert gap_buffer.depth(CASE_ID) == 1


@pytest.mark.spec("SYNC-14-009")
def test_successor_with_no_executing_actor_is_a_wiring_error(
    bridge, datalayer, case_obj, gap_buffer, hand_back
):
    """A successor with nobody to hand it to is a composition fault."""
    add_case_manager_participant(datalayer, case_obj, CASE_MANAGER_ID)
    gap_buffer.buffer(_make_entry(0, prev_hash=case_obj.genesis_hash))

    result = _run(bridge, gap_buffer, hand_back, actor_id="")

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "no executing actor" in (result.feedback_message or "")
    assert hand_back.handed_back == []
    assert gap_buffer.depth(CASE_ID) == 1


@pytest.mark.spec("SYNC-14-009")
def test_successor_is_handed_back_then_taken(
    bridge, datalayer, case_obj, gap_buffer, hand_back
):
    """The node hands the successor to the port, then removes it."""
    add_case_manager_participant(datalayer, case_obj, CASE_MANAGER_ID)
    entry = _make_entry(0, prev_hash=case_obj.genesis_hash)
    gap_buffer.buffer(entry)

    result = _run(bridge, gap_buffer, hand_back)

    assert result.status == Status.SUCCESS
    [handed] = hand_back.handed_back
    assert handed.entry == entry
    assert handed.case_manager_id == CASE_MANAGER_ID
    assert handed.receiving_actor_id == PARTICIPANT_ACTOR_ID
    assert gap_buffer.depth(CASE_ID) == 0
