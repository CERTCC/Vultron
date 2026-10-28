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
"""The CASE_MANAGER's answer to a stamped ledger position (SYNC-18).

The stage the received-tree factory places in every tree that names its case
and sender, run here on its own against the CASE_MANAGER's store: a held
position from an active participant is recorded and the entries after it
replayed, a split one is logged at ERROR and an active participant
re-seeded, and an inert sender's position is neither recorded nor answered.
``test/core/use_cases/received/test_activity_ledger_tail.py`` runs the same
answer end to end through a received tree.
"""

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes._embargo_gate_support import (
    MANAGER_ID,
    NON_SIGNATORY_ID,
    SIGNATORY_ID,
    manager_datalayer,
    seed_case,
    seed_ledger,
)
from test.core.behaviors.sync.nodes.conftest import CASE_ID, _make_entry
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.ledger_position_stage import (
    create_ledger_position_stage,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.events.note import AddNoteToCaseReceivedEvent
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort

_COPY_ID = "https://example.org/activities/case-copy"
_STAGE_LOGGERS = "vultron.core.behaviors.sync.nodes.ledger_position"


@pytest.fixture
def dl() -> SqliteDataLayer:
    """The CASE_MANAGER's store, with the embargo active.

    ``SIGNATORY_ID`` agreed to it and is active; ``NON_SIGNATORY_ID`` has
    not, so it is inert (CM-10-004).
    """
    store = manager_datalayer()
    seed_case(store, embargo_active=True)
    return store


def _position(entry: CaseLedgerEntry) -> LedgerPosition:
    return LedgerPosition(
        log_index=entry.log_index, entry_hash=entry.entry_hash
    )


def _note(sender: str, position: LedgerPosition) -> AddNoteToCaseReceivedEvent:
    """*sender*'s ``Add(Note)`` to the case, stamped at *position*."""
    return AddNoteToCaseReceivedEvent(
        activity_id="https://example.org/activities/add-note",
        actor_id=sender,
        ledger_position=position,
    )


def _ports() -> tuple[MagicMock, MagicMock]:
    sync_port = MagicMock(spec=SyncActivityPort)
    sync_port.send_announce_log_entry.return_value = True
    trigger = MagicMock(spec=TriggerActivityPort)
    trigger.announce_vulnerability_case.return_value = _COPY_ID
    return sync_port, trigger


def _answer(
    dl: SqliteDataLayer,
    activity: VultronEvent,
    sync_port: MagicMock,
    trigger: MagicMock,
    *,
    sender: str = SIGNATORY_ID,
) -> Any:
    return BTBridge(
        datalayer=dl, sync_port=sync_port, trigger_activity=trigger
    ).execute_with_setup(
        tree=create_ledger_position_stage(CASE_ID, sender),
        actor_id=MANAGER_ID,
        activity=activity,
    )


def _state(
    dl: SqliteDataLayer, peer_id: str
) -> VultronReplicationState | None:
    state = dl.read(
        VultronReplicationState(case_id=CASE_ID, peer_id=peer_id).id_
    )
    assert state is None or isinstance(state, VultronReplicationState)
    return state


def _sent_indices(sync_port: MagicMock) -> list[int]:
    return [
        call.kwargs["entry"].log_index
        for call in sync_port.send_announce_log_entry.call_args_list
    ]


def _reseeded(trigger: MagicMock) -> list[list[str]]:
    return [
        call.kwargs["to"]
        for call in trigger.announce_vulnerability_case.call_args_list
    ]


# ---------------------------------------------------------------------------
# SYNC-18-004, SYNC-18-007: a held position
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-18-004")
@pytest.mark.spec("SYNC-18-007")
def test_a_lag_is_logged_recorded_and_the_suffix_replayed(dl, caplog) -> None:
    entries = seed_ledger(dl, 3)
    sync_port, trigger = _ports()

    with caplog.at_level(logging.DEBUG, logger=_STAGE_LOGGERS):
        result = _answer(
            dl, _note(SIGNATORY_ID, _position(entries[0])), sync_port, trigger
        )

    assert result.status == Status.SUCCESS
    state = _state(dl, SIGNATORY_ID)
    assert state is not None
    assert state.last_acknowledged_hash == entries[0].entry_hash
    assert _sent_indices(sync_port) == [1, 2]
    assert _reseeded(trigger) == []
    assert any(
        record.levelno == logging.DEBUG
        and "behind" in record.getMessage()
        and SIGNATORY_ID in record.getMessage()
        for record in caplog.records
    )
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.spec("SYNC-18-007")
def test_a_stamp_at_the_tail_is_recorded_and_sends_nothing(dl, caplog) -> None:
    entries = seed_ledger(dl, 3)
    sync_port, trigger = _ports()

    with caplog.at_level(logging.DEBUG, logger=_STAGE_LOGGERS):
        result = _answer(
            dl, _note(SIGNATORY_ID, _position(entries[-1])), sync_port, trigger
        )

    assert result.status == Status.SUCCESS
    state = _state(dl, SIGNATORY_ID)
    assert state is not None
    assert state.last_acknowledged_hash == entries[-1].entry_hash
    sync_port.send_announce_log_entry.assert_not_called()
    assert _reseeded(trigger) == []
    assert not any("behind" in r.getMessage() for r in caplog.records)


@pytest.mark.spec("SYNC-18-007")
@pytest.mark.spec("CM-10-004")
def test_an_inert_senders_lag_is_neither_recorded_nor_answered(dl) -> None:
    entries = seed_ledger(dl, 3)
    sync_port, trigger = _ports()

    result = _answer(
        dl,
        _note(NON_SIGNATORY_ID, _position(entries[0])),
        sync_port,
        trigger,
        sender=NON_SIGNATORY_ID,
    )

    assert result.status == Status.SUCCESS
    assert _state(dl, NON_SIGNATORY_ID) is None
    sync_port.send_announce_log_entry.assert_not_called()
    assert dl.outbox_list() == []


@pytest.mark.spec("SYNC-18-007")
@pytest.mark.spec("BT-14-001")
def test_a_replay_held_back_is_logged_and_never_fails_the_stage(
    dl, caplog
) -> None:
    """A replay that stops at an entry that does not verify fails (BT-14-001),
    and the stage reports that failure at WARNING without deciding the act."""
    first, second = seed_ledger(dl, 2)
    broken = _make_entry(2, second.entry_hash).model_copy(
        update={"entry_hash": "f" * 64}
    )
    dl.save(broken)
    sync_port, trigger = _ports()

    with caplog.at_level(logging.WARNING):
        result = _answer(
            dl, _note(SIGNATORY_ID, _position(first)), sync_port, trigger
        )

    assert result.status == Status.SUCCESS
    assert _sent_indices(sync_port) == [1]
    assert any(
        record.levelno == logging.WARNING
        and "answer to the sender's ledger position failed"
        in record.getMessage()
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# SYNC-18-005: a split position
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-18-005")
@pytest.mark.spec("SYNC-16-003")
@pytest.mark.parametrize("past_tail", [False, True], ids=["hash", "index"])
def test_a_split_is_logged_at_error_and_the_sender_reseeded(
    dl, caplog, past_tail
) -> None:
    entries = seed_ledger(dl, 3)
    split = LedgerPosition(
        log_index=entries[-1].log_index + 4 if past_tail else 1,
        entry_hash="0" * 64,
    )
    sync_port, trigger = _ports()

    with caplog.at_level(logging.ERROR):
        result = _answer(dl, _note(SIGNATORY_ID, split), sync_port, trigger)

    assert result.status == Status.SUCCESS
    assert any(
        record.levelno == logging.ERROR
        and "split" in record.getMessage()
        and SIGNATORY_ID in record.getMessage()
        for record in caplog.records
    )
    assert _reseeded(trigger) == [[SIGNATORY_ID]]
    assert dl.outbox_list() == [_COPY_ID]
    sync_port.send_announce_log_entry.assert_not_called()
    state = _state(dl, SIGNATORY_ID)
    assert state is not None
    assert state.last_acknowledged_hash == ""


@pytest.mark.spec("SYNC-18-005")
@pytest.mark.spec("SYNC-16-004")
def test_a_second_split_inside_the_cooldown_reseeds_nothing(dl) -> None:
    seed_ledger(dl, 2)
    split = LedgerPosition(log_index=1, entry_hash="0" * 64)
    sync_port, trigger = _ports()
    _answer(dl, _note(SIGNATORY_ID, split), sync_port, trigger)

    result = _answer(dl, _note(SIGNATORY_ID, split), sync_port, trigger)

    assert result.status == Status.SUCCESS
    assert _reseeded(trigger) == [[SIGNATORY_ID]]


@pytest.mark.spec("SYNC-18-005")
@pytest.mark.spec("CM-10-004")
def test_an_inert_senders_split_is_logged_and_reseeds_nothing(
    dl, caplog
) -> None:
    seed_ledger(dl, 2)
    split = LedgerPosition(log_index=1, entry_hash="0" * 64)
    sync_port, trigger = _ports()

    with caplog.at_level(logging.ERROR):
        result = _answer(
            dl,
            _note(NON_SIGNATORY_ID, split),
            sync_port,
            trigger,
            sender=NON_SIGNATORY_ID,
        )

    assert result.status == Status.SUCCESS
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert _reseeded(trigger) == []
    assert dl.outbox_list() == []
    assert _state(dl, NON_SIGNATORY_ID) is None


# ---------------------------------------------------------------------------
# What the stage leaves alone
# ---------------------------------------------------------------------------


def _untouched(
    dl: SqliteDataLayer, sync_port: MagicMock, trigger: MagicMock
) -> None:
    sync_port.send_announce_log_entry.assert_not_called()
    assert _reseeded(trigger) == []
    assert list(dl.list_objects("ReplicationState")) == []


@pytest.mark.spec("SYNC-18-001")
def test_an_activity_outside_the_scope_states_nothing_to_answer(dl) -> None:
    """A ``Reject(CaseLedgerEntry)`` is no ``LedgerPositionedEvent``: its
    own tree answers the position it reports (SYNC-03-002)."""
    seed_ledger(dl, 2)
    sync_port, trigger = _ports()
    reject = RejectLogEntryReceivedEvent(
        activity_id="https://example.org/activities/reject",
        actor_id=SIGNATORY_ID,
        ledger_position=LedgerPosition(log_index=1, entry_hash="0" * 64),
    )

    result = _answer(dl, reject, sync_port, trigger)

    assert result.status == Status.SUCCESS
    _untouched(dl, sync_port, trigger)


@pytest.mark.spec("SYNC-18-005")
def test_an_activity_from_another_sender_is_not_answered(dl) -> None:
    """The stage answers the sender its tree names, and no one else."""
    seed_ledger(dl, 2)
    sync_port, trigger = _ports()
    split = LedgerPosition(log_index=1, entry_hash="0" * 64)

    result = _answer(
        dl,
        _note(SIGNATORY_ID, split),
        sync_port,
        trigger,
        sender=NON_SIGNATORY_ID,
    )

    assert result.status == Status.SUCCESS
    _untouched(dl, sync_port, trigger)


@pytest.mark.spec("SYNC-18-005")
def test_the_case_managers_own_activity_is_not_answered(dl) -> None:
    seed_ledger(dl, 2)
    sync_port, trigger = _ports()
    split = LedgerPosition(log_index=1, entry_hash="0" * 64)

    result = _answer(
        dl, _note(MANAGER_ID, split), sync_port, trigger, sender=MANAGER_ID
    )

    assert result.status == Status.SUCCESS
    _untouched(dl, sync_port, trigger)


@pytest.mark.spec("SYNC-18-005")
@pytest.mark.spec("BT-17-001")
def test_a_store_that_is_not_the_case_manager_answers_nothing(caplog) -> None:
    """A replica holds no authority to replay or re-seed (BT-17-001).

    The sender is an active participant, so only the gate keeps the replica
    from answering: no split is logged and nothing is recorded or sent.
    """
    replica = SqliteDataLayer("sqlite:///:memory:", actor_id=NON_SIGNATORY_ID)
    seed_case(replica, embargo_active=True)
    seed_ledger(replica, 2)
    sync_port, trigger = _ports()
    split = LedgerPosition(log_index=1, entry_hash="0" * 64)

    with caplog.at_level(logging.DEBUG, logger=_STAGE_LOGGERS):
        result = BTBridge(
            datalayer=replica, sync_port=sync_port, trigger_activity=trigger
        ).execute_with_setup(
            tree=create_ledger_position_stage(CASE_ID, SIGNATORY_ID),
            actor_id=NON_SIGNATORY_ID,
            activity=_note(SIGNATORY_ID, split),
        )

    assert result.status == Status.SUCCESS
    _untouched(replica, sync_port, trigger)
    assert not any("split" in r.getMessage() for r in caplog.records)


@pytest.mark.spec("SYNC-18-007")
def test_a_stamp_at_the_tail_needs_no_sync_port(dl) -> None:
    """Nothing is replayed at the tail, so no send port is asked for."""
    entries = seed_ledger(dl, 2)

    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=create_ledger_position_stage(CASE_ID, SIGNATORY_ID),
        actor_id=MANAGER_ID,
        activity=_note(SIGNATORY_ID, _position(entries[-1])),
    )

    assert result.status == Status.SUCCESS
    assert not result.internal_error
    state = _state(dl, SIGNATORY_ID)
    assert state is not None
    assert state.last_acknowledged_hash == entries[-1].entry_hash


@pytest.mark.spec("SYNC-18-007")
@pytest.mark.spec("SYNC-16-007")
def test_an_empty_replicas_stamp_is_recorded_and_replayed_from_genesis(
    dl,
) -> None:
    """A sender holding no entry stamps index -1 and the case's genesis hash:
    a lag the ledger holds, so nothing is acknowledged and every entry is
    replayed (CLP-08-005)."""
    seed_ledger(dl, 2)
    case = dl.read_case(CASE_ID)
    assert case is not None
    genesis = LedgerPosition(log_index=-1, entry_hash=case.genesis_hash)
    sync_port, trigger = _ports()

    result = _answer(dl, _note(SIGNATORY_ID, genesis), sync_port, trigger)

    assert result.status == Status.SUCCESS
    state = _state(dl, SIGNATORY_ID)
    assert state is not None
    assert state.last_acknowledged_hash == ""
    assert _sent_indices(sync_port) == [0, 1]
    assert _reseeded(trigger) == []


@pytest.mark.spec("SYNC-18-004")
@pytest.mark.spec("CLP-10-005")
def test_a_replay_leaves_the_acts_case_key_alone(dl) -> None:
    """The answer runs ahead of the act's own nodes, several of which read
    ``/case_id``; its replay context stays in its own scope.  (``/case_actor_id``
    is the CASE_MANAGER gate's own output, written by every gate.)"""
    import py_trees

    entries = seed_ledger(dl, 3)
    sync_port, trigger = _ports()
    storage = py_trees.blackboard.Blackboard.storage
    before = storage.get("/case_id")

    _answer(dl, _note(SIGNATORY_ID, _position(entries[0])), sync_port, trigger)

    assert _sent_indices(sync_port) == [1, 2]
    assert storage.get("/case_id") == before
    assert storage.get("/ledger_position/case_id") == CASE_ID
