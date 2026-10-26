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
"""Every CASE_MANAGER send path holds back an entry it cannot verify (SYNC-03-009).

One case per send site: the ``Reject``/``Read`` replay
(``SendMissingEntriesNode``), the fan-out of a new entry and its admission
backfill (``SendLogEntryToEachNode``), the admission backfill node
(``BackfillAdmittedParticipantsNode``) and the join-time backfill
(``BackfillCanonicalLedgerToInviteeNode``).  Each runs with an intact ledger,
one with a tampered entry and one with an entry that states no hash: the
entries before the broken one are queued, it and every later one are not,
the hold-back is logged at ERROR, and the node returns ``FAILURE``
(BT-14-001).
"""

import logging
from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import CASE_ID
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.invite_ledger_backfill import (
    BackfillCanonicalLedgerToInviteeNode,
)
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    record_embargo_pause,
)
from vultron.core.behaviors.sync.nodes.fanout import FanOutLogEntryNode
from vultron.core.behaviors.sync.nodes.replay_guard import _read_state
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.sync_activity import SyncActivityPort

from ._embargo_gate_support import (
    MANAGER_ID,
    NON_SIGNATORY_ID,
    SIGNATORY_ID,
    accept_embargo,
    manager_datalayer,
    paused_from,
    replay,
    seed_case,
    seed_ledger,
    sends,
)

_INVITEE_ID = "https://example.org/actors/invitee"

BreakEntry = Callable[[CaseLedgerEntry], CaseLedgerEntry]


def _tampered(entry: CaseLedgerEntry) -> CaseLedgerEntry:
    """Content no longer reproduces the stated hash."""
    return entry.model_copy(
        update={"payload_snapshot": {"log_index": "tampered"}}
    )


def _hashless(entry: CaseLedgerEntry) -> CaseLedgerEntry:
    """The entry states no hash, so there is nothing to check."""
    return entry.model_copy(update={"entry_hash": ""})


_BROKEN = pytest.mark.parametrize(
    "break_entry", [_tampered, _hashless], ids=["tampered", "hashless"]
)


@pytest.fixture
def datalayer():
    """The CASE_MANAGER's store, shadowing the package's participant store."""
    return manager_datalayer()


def _break_stored(datalayer, entries: list, index: int, break_entry) -> None:
    entries[index] = break_entry(entries[index])
    datalayer.save(entries[index])


def _assert_held_back(
    caplog: pytest.LogCaptureFixture, entry: CaseLedgerEntry, peer_id: str
) -> None:
    """One ERROR names the case, the entry, its log_index and the recipient."""
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.ERROR
    ]
    assert any(
        entry.case_id in message
        and entry.id_ in message
        and f"log_index={entry.log_index}" in message
        and peer_id in message
        for message in messages
    ), messages


# --- Reject / Read replay ---------------------------------------------------


@pytest.mark.spec("SYNC-03-002")
def test_replay_of_an_intact_ledger_sends_every_entry(
    bridge: BTBridge, datalayer
) -> None:
    seed_case(datalayer, embargo_active=False)
    entries = seed_ledger(datalayer, 4)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = replay(
        bridge,
        entries,
        peer_id=SIGNATORY_ID,
        from_index=-1,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    assert [index for index, _ in sends(sync_port)] == [0, 1, 2, 3]


@pytest.mark.spec("SYNC-03-009")
@pytest.mark.spec("SYNC-15-011")
@_BROKEN
def test_replay_stops_at_a_broken_entry_and_fails(
    bridge: BTBridge,
    datalayer,
    break_entry: BreakEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Entries before it go out and the cooldown records that replay."""
    seed_case(datalayer, embargo_active=False)
    entries = seed_ledger(datalayer, 4)
    entries[2] = break_entry(entries[2])
    sync_port = MagicMock(spec=SyncActivityPort)

    with caplog.at_level(logging.ERROR):
        result = replay(
            bridge,
            entries,
            peer_id=SIGNATORY_ID,
            from_index=-1,
            sync_port=sync_port,
        )

    assert result.status == Status.FAILURE
    assert sends(sync_port) == [(0, [SIGNATORY_ID]), (1, [SIGNATORY_ID])]
    _assert_held_back(caplog, entries[2], SIGNATORY_ID)
    state = _read_state(datalayer, case_id=CASE_ID, peer_id=SIGNATORY_ID)
    assert state is not None
    assert state.last_replayed_from_hash is not None


@pytest.mark.spec("SYNC-03-009")
@pytest.mark.spec("SYNC-15-011")
@_BROKEN
def test_replay_held_back_at_its_first_entry_records_no_cooldown(
    bridge: BTBridge, datalayer, break_entry: BreakEntry
) -> None:
    """A replay that queues nothing records no position (SYNC-15-011)."""
    seed_case(datalayer, embargo_active=False)
    entries = seed_ledger(datalayer, 4)
    entries[2] = break_entry(entries[2])
    sync_port = MagicMock(spec=SyncActivityPort)

    result = replay(
        bridge,
        entries,
        peer_id=SIGNATORY_ID,
        from_index=1,
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    assert sends(sync_port) == []
    state = _read_state(datalayer, case_id=CASE_ID, peer_id=SIGNATORY_ID)
    assert state is None or state.last_replayed_from_hash is None


# --- Fan-out ----------------------------------------------------------------


def _fan_out(bridge: BTBridge, entry: CaseLedgerEntry, sync_port):
    return bridge.execute_with_setup(
        tree=FanOutLogEntryNode(case_id=CASE_ID),
        actor_id=MANAGER_ID,
        log_entry=entry,
        sync_port=sync_port,
    )


@pytest.mark.spec("SYNC-03-009")
@_BROKEN
def test_fanout_holds_back_a_new_entry_that_does_not_verify(
    bridge: BTBridge,
    datalayer,
    break_entry: BreakEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    seed_case(datalayer, embargo_active=False)
    entries = seed_ledger(datalayer, 2)
    _break_stored(datalayer, entries, 1, break_entry)
    sync_port = MagicMock(spec=SyncActivityPort)

    with caplog.at_level(logging.ERROR):
        result = _fan_out(bridge, entries[1], sync_port)

    assert result.status == Status.FAILURE
    assert sends(sync_port) == []
    _assert_held_back(caplog, entries[1], SIGNATORY_ID)
    _assert_held_back(caplog, entries[1], NON_SIGNATORY_ID)


def _paused_from_one_then_admitted(datalayer) -> list:
    """The finder was paused from entry 1 and has since accepted."""
    seed_case(datalayer, embargo_active=True)
    entries = seed_ledger(datalayer, 4)
    record_embargo_pause(
        datalayer, case_id=CASE_ID, peer_id=NON_SIGNATORY_ID, from_index=1
    )
    accept_embargo(datalayer, NON_SIGNATORY_ID)
    return entries


@pytest.mark.spec("CM-10-006")
def test_fanout_backfill_of_an_intact_ledger_sends_it_all(
    bridge: BTBridge, datalayer
) -> None:
    entries = _paused_from_one_then_admitted(datalayer)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = _fan_out(bridge, entries[3], sync_port)

    assert result.status == Status.SUCCESS
    to_finder = [i for i, to in sends(sync_port) if to == [NON_SIGNATORY_ID]]
    assert to_finder == [1, 2, 3]
    assert paused_from(datalayer) is None


@pytest.mark.spec("SYNC-03-009")
@pytest.mark.spec("CM-10-006")
@_BROKEN
def test_fanout_backfill_stops_at_a_broken_entry_and_sends_no_new_entry(
    bridge: BTBridge,
    datalayer,
    break_entry: BreakEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The new entry would reach the backfilled peer as a forward gap."""
    entries = _paused_from_one_then_admitted(datalayer)
    _break_stored(datalayer, entries, 2, break_entry)
    sync_port = MagicMock(spec=SyncActivityPort)

    with caplog.at_level(logging.ERROR):
        result = _fan_out(bridge, entries[3], sync_port)

    assert result.status == Status.FAILURE
    assert sends(sync_port) == [(1, [NON_SIGNATORY_ID])]
    _assert_held_back(caplog, entries[2], NON_SIGNATORY_ID)
    assert paused_from(datalayer) == 1


# --- Admission backfill node --------------------------------------------------


def _admission_backfill(bridge: BTBridge, sync_port):
    return bridge.execute_with_setup(
        tree=BackfillAdmittedParticipantsNode(case_id=CASE_ID),
        actor_id=MANAGER_ID,
        sync_port=sync_port,
    )


@pytest.mark.spec("CM-10-006")
def test_admission_backfill_of_an_intact_ledger_sends_it_all(
    bridge: BTBridge, datalayer
) -> None:
    _paused_from_one_then_admitted(datalayer)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = _admission_backfill(bridge, sync_port)

    assert result.status == Status.SUCCESS
    assert [i for i, _ in sends(sync_port)] == [1, 2, 3]
    assert paused_from(datalayer) is None


@pytest.mark.spec("SYNC-03-009")
@pytest.mark.spec("CM-10-006")
@_BROKEN
def test_admission_backfill_stops_at_a_broken_entry_and_keeps_the_pause(
    bridge: BTBridge,
    datalayer,
    break_entry: BreakEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entries = _paused_from_one_then_admitted(datalayer)
    _break_stored(datalayer, entries, 2, break_entry)
    sync_port = MagicMock(spec=SyncActivityPort)

    with caplog.at_level(logging.ERROR):
        result = _admission_backfill(bridge, sync_port)

    assert result.status == Status.FAILURE
    assert sends(sync_port) == [(1, [NON_SIGNATORY_ID])]
    _assert_held_back(caplog, entries[2], NON_SIGNATORY_ID)
    assert paused_from(datalayer) == 1


# --- Join-time backfill ---------------------------------------------------------


def _join_backfill(bridge: BTBridge, sync_port):
    return bridge.execute_with_setup(
        tree=BackfillCanonicalLedgerToInviteeNode(
            case_id=CASE_ID, invitee_id=_INVITEE_ID
        ),
        actor_id=MANAGER_ID,
        sync_port=sync_port,
    )


@pytest.mark.spec("CM-17-004")
def test_join_backfill_of_an_intact_ledger_sends_it_all(
    bridge: BTBridge, datalayer
) -> None:
    seed_ledger(datalayer, 3)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = _join_backfill(bridge, sync_port)

    assert result.status == Status.SUCCESS
    assert [i for i, _ in sends(sync_port)] == [0, 1, 2]


@pytest.mark.spec("SYNC-03-009")
@pytest.mark.spec("CM-17-004")
@_BROKEN
def test_join_backfill_stops_at_a_broken_entry_and_fails(
    bridge: BTBridge,
    datalayer,
    break_entry: BreakEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entries = seed_ledger(datalayer, 3)
    _break_stored(datalayer, entries, 1, break_entry)
    sync_port = MagicMock(spec=SyncActivityPort)

    with caplog.at_level(logging.ERROR):
        result = _join_backfill(bridge, sync_port)

    assert result.status == Status.FAILURE
    assert sends(sync_port) == [(0, [_INVITEE_ID])]
    _assert_held_back(caplog, entries[1], _INVITEE_ID)
