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

"""Participant position statements: a participant's ``Read(CaseLedgerEntry)``.

The CASE_MANAGER answers an active participant's stated ledger position the
way it answers a ``Reject``: it records the position and replays the entries
after it, under the same rate bound and de-duplication (ADR-0155).
"""

import logging
from typing import cast
from unittest.mock import MagicMock

import pytest

from test.core.behaviors.sync.nodes._embargo_gate_support import (
    MANAGER_ID,
    NON_SIGNATORY_ID,
    SIGNATORY_ID,
    close,
    manager_datalayer,
    seed_case,
    seed_ledger,
)
from test.core.behaviors.sync.nodes.conftest import CASE_ID, _make_entry
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.sync import ReadLogEntryReceivedEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.received.sync import (
    ReadLedgerEntryReceivedUseCase,
)
from vultron.core.use_cases.triggers.sync import (
    state_ledger_positions_trigger,
)
from vultron.errors import VultronBTInternalError
from vultron.semantic_registry import find_matching_semantics
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.extractor import extract_intent
from vultron.wire.as2.factories import read_ledger_entry_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Read,
)

#: A third participant, removed from the case (CM-31-001).
REMOVED_ID = "https://example.org/actors/removed"

#: An actor the case roster does not list at all.
UNLISTED_ID = "https://example.org/actors/unlisted"


@pytest.fixture
def dl() -> SqliteDataLayer:
    """The CASE_MANAGER's store, with no active embargo."""
    store = manager_datalayer()
    seed_case(store, embargo_active=False)
    return store


def _read(entry: CaseLedgerEntry, sender: str) -> ReadLogEntryReceivedEvent:
    """*sender*'s ``Read(CaseLedgerEntry)`` naming *entry*, as delivered."""
    return cast(
        ReadLogEntryReceivedEvent,
        received_event(
            read_ledger_entry_activity(entry, actor=sender, to=[MANAGER_ID])
        ),
    )


def _answer(
    dl: SqliteDataLayer,
    event: ReadLogEntryReceivedEvent,
    sync_port: SyncActivityPort,
) -> HandlerResult:
    return ReadLedgerEntryReceivedUseCase(
        dl, event, sync_port=sync_port
    ).execute()


def _sync_port() -> MagicMock:
    port = MagicMock(spec=SyncActivityPort)
    port.send_announce_log_entry.return_value = True
    return port


def _sent_indices(port: MagicMock) -> list[int]:
    return [
        call.kwargs["entry"].log_index
        for call in port.send_announce_log_entry.call_args_list
    ]


def _state(dl: SqliteDataLayer, peer_id: str) -> object | None:
    return dl.read(
        VultronReplicationState(case_id=CASE_ID, peer_id=peer_id).id_
    )


def _ledger_ids(dl: SqliteDataLayer) -> list[str]:
    return sorted(e.id_ for e in dl.list_objects("CaseLedgerEntry"))


# ---------------------------------------------------------------------------
# SYNC-17-001: the message
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-17-001")
def test_factory_names_the_entry_by_reference() -> None:
    """The ``Read``'s object is the entry's id, its context the case."""
    entry = _make_entry(0)

    activity = read_ledger_entry_activity(
        entry, actor=SIGNATORY_ID, to=[MANAGER_ID]
    )

    assert isinstance(activity, as_Read)
    assert activity.type_ == "Read"
    assert activity.object_ == entry.id_
    assert activity.context == entry.case_id
    assert activity.ledger_position is not None
    assert activity.ledger_position.log_index == entry.log_index
    assert activity.ledger_position.entry_hash == entry.entry_hash
    body = activity.model_dump(by_alias=True, mode="json", exclude_none=True)
    assert body["object"] == entry.id_
    assert body["ledgerPosition"] == {
        "logIndex": entry.log_index,
        "entryHash": entry.entry_hash,
    }


@pytest.mark.spec("SYNC-17-001")
def test_read_case_ledger_entry_is_a_message_semantic() -> None:
    """A delivered ``Read(CaseLedgerEntry)`` has its own semantic type."""
    event = _read(_make_entry(0), SIGNATORY_ID)

    assert event.semantic_type is MessageSemantics.READ_CASE_LEDGER_ENTRY
    assert event.stated_entry_id == _make_entry(0).id_
    assert event.replay_case_id == CASE_ID
    assert event.last_accepted_hash == _make_entry(0).entry_hash


@pytest.mark.spec("SYNC-17-001")
def test_read_without_a_ledger_position_is_not_a_position_statement() -> None:
    """A ``Read`` of a bare reference with no position is not matched."""
    activity = as_Read(
        actor=SIGNATORY_ID, object_=_make_entry(0).id_, context=CASE_ID
    )

    assert find_matching_semantics(activity) is not (
        MessageSemantics.READ_CASE_LEDGER_ENTRY
    )


# ---------------------------------------------------------------------------
# SYNC-17-002: active senders only
# ---------------------------------------------------------------------------


def _assert_refused_with_nothing(
    dl: SqliteDataLayer, sender: str, result: HandlerResult, port: MagicMock
) -> None:
    assert result.disposition is HandlerDisposition.REFUSED
    assert "active participant" in (result.reason or "")
    assert _state(dl, sender) is None
    port.send_announce_log_entry.assert_not_called()


@pytest.mark.spec("SYNC-17-002")
@pytest.mark.spec("CM-10-004")
@pytest.mark.spec("CM-31-001")
def test_removed_participant_with_lagging_position_is_refused(dl) -> None:
    """A removed participant's lagging statement gets nothing (CM-31-001)."""
    entries = seed_ledger(dl, 3)
    removed = CaseParticipant(
        id_=f"{REMOVED_ID}/participant",
        attributed_to=REMOVED_ID,
        context=CASE_ID,
    )
    removed.record_removal("https://example.org/activities/remove-1")
    dl.create(removed)
    case = cast(VulnerabilityCase, dl.read(CASE_ID))
    case.add_participant(removed)
    dl.save(case)
    port = _sync_port()

    result = _answer(dl, _read(entries[0], REMOVED_ID), port)

    _assert_refused_with_nothing(dl, REMOVED_ID, result, port)


@pytest.mark.spec("SYNC-17-002")
@pytest.mark.spec("CM-10-005")
def test_unconsented_participant_with_lagging_position_is_refused() -> None:
    """With an embargo active, a participant that has not agreed gets nothing."""
    dl = manager_datalayer()
    seed_case(dl, embargo_active=True)
    entries = seed_ledger(dl, 3)
    port = _sync_port()

    result = _answer(dl, _read(entries[0], NON_SIGNATORY_ID), port)

    _assert_refused_with_nothing(dl, NON_SIGNATORY_ID, result, port)


@pytest.mark.spec("SYNC-17-002")
@pytest.mark.spec("CM-23-018")
def test_closed_participant_with_lagging_position_is_refused(dl) -> None:
    """A participant that has left the case may act on nothing further."""
    entries = seed_ledger(dl, 3)
    close(dl, SIGNATORY_ID)
    port = _sync_port()

    result = _answer(dl, _read(entries[0], SIGNATORY_ID), port)

    _assert_refused_with_nothing(dl, SIGNATORY_ID, result, port)


@pytest.mark.spec("SYNC-17-002")
@pytest.mark.spec("HP-01-005")
def test_replica_that_is_not_the_case_manager_refuses_a_read() -> None:
    """Only the CASE_MANAGER answers a ``Read``; a replica records nothing."""
    replica = SqliteDataLayer("sqlite:///:memory:", actor_id=SIGNATORY_ID)
    seed_case(replica, embargo_active=False)
    entries = seed_ledger(replica, 2)
    port = _sync_port()
    event = cast(
        ReadLogEntryReceivedEvent,
        received_event(
            read_ledger_entry_activity(
                entries[0],
                actor=NON_SIGNATORY_ID,
                to=[MANAGER_ID, SIGNATORY_ID],
            )
        ),
    )

    result = _answer(replica, event, port)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "not the CASE_MANAGER" in (result.reason or "")
    assert _state(replica, NON_SIGNATORY_ID) is None
    port.send_announce_log_entry.assert_not_called()


# ---------------------------------------------------------------------------
# SYNC-17-003, SYNC-17-004, SYNC-17-006: the answer
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-17-003")
@pytest.mark.spec("SYNC-17-004")
@pytest.mark.spec("SYNC-17-006")
def test_lagging_position_is_recorded_and_the_suffix_replayed(dl) -> None:
    """A position behind the tail: the hash is recorded, the rest is sent."""
    entries = seed_ledger(dl, 3)
    before = _ledger_ids(dl)
    port = _sync_port()

    result = _answer(dl, _read(entries[0], SIGNATORY_ID), port)

    assert result.disposition is HandlerDisposition.APPLIED
    state = _state(dl, SIGNATORY_ID)
    assert isinstance(state, VultronReplicationState)
    assert state.last_acknowledged_hash == entries[0].entry_hash
    assert _sent_indices(port) == [1, 2]
    assert all(
        call.kwargs["to"] == [SIGNATORY_ID]
        and call.kwargs["actor_id"] == MANAGER_ID
        for call in port.send_announce_log_entry.call_args_list
    )
    assert _ledger_ids(dl) == before


@pytest.mark.spec("SYNC-17-003")
@pytest.mark.spec("SYNC-17-004")
@pytest.mark.spec("SYNC-17-006")
def test_position_at_the_tail_is_recorded_and_sends_nothing(dl) -> None:
    entries = seed_ledger(dl, 3)
    before = _ledger_ids(dl)
    port = _sync_port()

    result = _answer(dl, _read(entries[-1], SIGNATORY_ID), port)

    assert result.disposition is HandlerDisposition.APPLIED
    state = _state(dl, SIGNATORY_ID)
    assert isinstance(state, VultronReplicationState)
    assert state.last_acknowledged_hash == entries[-1].entry_hash
    port.send_announce_log_entry.assert_not_called()
    assert _ledger_ids(dl) == before


@pytest.mark.spec("SYNC-17-004")
@pytest.mark.spec("SYNC-15-003")
@pytest.mark.spec("SYNC-15-013")
def test_second_lagging_position_inside_the_cooldown_replays_nothing(
    dl,
) -> None:
    """The replay rate bound covers a ``Read`` as it covers a ``Reject``."""
    entries = seed_ledger(dl, 3)
    port = _sync_port()
    _answer(dl, _read(entries[0], SIGNATORY_ID), port)
    port.send_announce_log_entry.reset_mock()

    result = _answer(dl, _read(entries[0], SIGNATORY_ID), port)

    assert result.disposition is HandlerDisposition.APPLIED
    port.send_announce_log_entry.assert_not_called()


@pytest.mark.spec("SYNC-17-004")
@pytest.mark.spec("SYNC-15-012")
def test_replay_counts_only_rows_the_outbox_queued(dl) -> None:
    """An entry already pending to the peer is not queued again (SYNC-15-012).

    The port reports it declined, so the replay records no position and a
    later statement from the same position still replays.
    """
    entries = seed_ledger(dl, 2)
    port = _sync_port()
    port.send_announce_log_entry.return_value = False
    _answer(dl, _read(entries[0], SIGNATORY_ID), port)
    port.send_announce_log_entry.return_value = True
    port.send_announce_log_entry.reset_mock()

    _answer(dl, _read(entries[0], SIGNATORY_ID), port)

    assert _sent_indices(port) == [1]


# ---------------------------------------------------------------------------
# SYNC-17-005: a position the ledger does not hold
# ---------------------------------------------------------------------------


def _assert_unknown_position(
    dl: SqliteDataLayer,
    event: ReadLogEntryReceivedEvent,
    caplog: pytest.LogCaptureFixture,
) -> None:
    before = _ledger_ids(dl)
    port = _sync_port()

    with caplog.at_level(logging.WARNING):
        result = _answer(dl, event, port)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "SYNC-17-005" in (result.reason or "")
    assert _state(dl, SIGNATORY_ID) is None
    port.send_announce_log_entry.assert_not_called()
    warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING
        and "SYNC-17-005" in record.getMessage()
    ]
    assert warnings, "expected a WARNING naming the stated position"
    message = warnings[0].getMessage()
    assert SIGNATORY_ID in message
    assert f"log_index={event.ledger_position.log_index}" in message
    assert _ledger_ids(dl) == before


@pytest.mark.spec("SYNC-17-005")
@pytest.mark.spec("SYNC-17-006")
def test_position_naming_an_entry_not_held_is_logged_and_answered_with_nothing(
    dl, caplog
) -> None:
    entries = seed_ledger(dl, 2)
    beyond = _make_entry(5, entries[-1].entry_hash)

    _assert_unknown_position(dl, _read(beyond, SIGNATORY_ID), caplog)


@pytest.mark.spec("SYNC-17-005")
def test_position_whose_index_holds_another_hash_is_answered_with_nothing(
    dl, caplog
) -> None:
    seed_ledger(dl, 3)
    other = _make_entry(1, "f" * 64)  # same index, another chain

    _assert_unknown_position(dl, _read(other, SIGNATORY_ID), caplog)


# ---------------------------------------------------------------------------
# SYNC-17-007: the participant states its positions
# ---------------------------------------------------------------------------


def _participant_store() -> SqliteDataLayer:
    """SIGNATORY_ID's replica of the case, holding two entries."""
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=SIGNATORY_ID)
    seed_case(store, embargo_active=False)
    seed_ledger(store, 2)
    return store


@pytest.mark.spec("SYNC-17-007")
@pytest.mark.spec("SYNC-17-001")
def test_participant_states_its_tail_to_the_case_manager() -> None:
    store = _participant_store()
    port = MagicMock(spec=SyncActivityPort)

    sent = state_ledger_positions_trigger(store, SIGNATORY_ID, port)

    assert sent == 1
    port.send_read_ledger_entry.assert_called_once()
    call = port.send_read_ledger_entry.call_args
    assert call.kwargs["case_id"] == CASE_ID
    tail = max(
        cast(list[CaseLedgerEntry], store.list_objects("CaseLedgerEntry")),
        key=lambda entry: entry.log_index,
    )
    assert call.kwargs["ledger_position"] == LedgerPosition(
        log_index=1, entry_hash=tail.entry_hash
    )
    assert call.kwargs["actor_id"] == SIGNATORY_ID
    assert call.kwargs["to"] == [MANAGER_ID]


@pytest.mark.spec("SYNC-17-001")
def test_participant_at_the_empty_ledger_position_states_nothing() -> None:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=SIGNATORY_ID)
    seed_case(store, embargo_active=False)
    port = MagicMock(spec=SyncActivityPort)

    assert state_ledger_positions_trigger(store, SIGNATORY_ID, port) == 0
    port.send_read_ledger_entry.assert_not_called()


@pytest.mark.spec("SYNC-17-007")
def test_case_manager_states_no_position_for_a_case_it_manages() -> None:
    store = manager_datalayer()
    seed_case(store, embargo_active=False)
    seed_ledger(store, 2)
    port = MagicMock(spec=SyncActivityPort)

    assert state_ledger_positions_trigger(store, MANAGER_ID, port) == 0
    port.send_read_ledger_entry.assert_not_called()


@pytest.mark.spec("SYNC-17-007")
@pytest.mark.spec("CM-23-018")
def test_closed_participant_states_no_position() -> None:
    """The CASE_MANAGER refuses a closed sender, so none is sent."""
    store = _participant_store()
    close(store, SIGNATORY_ID)
    port = MagicMock(spec=SyncActivityPort)

    assert state_ledger_positions_trigger(store, SIGNATORY_ID, port) == 0
    port.send_read_ledger_entry.assert_not_called()


@pytest.mark.spec("SYNC-17-007")
def test_case_naming_no_case_manager_gets_no_statement() -> None:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=SIGNATORY_ID)
    store.create(VulnerabilityCase(id_=CASE_ID, attributed_to=MANAGER_ID))
    store.save(_make_entry(0))
    port = MagicMock(spec=SyncActivityPort)

    assert state_ledger_positions_trigger(store, SIGNATORY_ID, port) == 0
    port.send_read_ledger_entry.assert_not_called()


@pytest.mark.spec("SYNC-17-005")
def test_position_whose_object_is_not_the_entry_at_its_index_is_refused(
    dl, caplog
) -> None:
    """The object names another entry than the one the index holds."""
    entries = seed_ledger(dl, 3)
    event = _read(entries[1], SIGNATORY_ID)
    other = CoreObject(id_=f"{CASE_ID}/log/elsewhere")

    _assert_unknown_position(
        dl, event.model_copy(update={"object_": other}), caplog
    )


@pytest.mark.spec("SYNC-17-002")
def test_read_naming_no_case_is_refused(dl) -> None:
    entries = seed_ledger(dl, 2)
    event = _read(entries[0], SIGNATORY_ID).model_copy(
        update={"context": None}
    )
    port = _sync_port()

    result = _answer(dl, event, port)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "names no case" in (result.reason or "")
    port.send_announce_log_entry.assert_not_called()


@pytest.mark.spec("SYNC-17-001")
def test_a_read_event_without_a_parsed_position_is_refused_at_the_edge() -> (
    None
):
    """The extractor never defaults a missing ``ledgerPosition``."""
    activity = as_Read(
        actor=SIGNATORY_ID, object_=_make_entry(0).id_, context=CASE_ID
    )

    with pytest.raises(VultronParseValidationError, match="ledgerPosition"):
        extract_intent(
            activity,
            MessageSemantics.READ_CASE_LEDGER_ENTRY,
            ReadLogEntryReceivedEvent,
        )


@pytest.mark.spec("SYNC-17-007")
def test_stating_positions_without_a_sync_port_is_a_wiring_fault() -> None:
    store = _participant_store()

    with pytest.raises(VultronBTInternalError, match="sync_port"):
        state_ledger_positions_trigger(
            store,
            SIGNATORY_ID,
            None,  # type: ignore[arg-type]
        )


@pytest.mark.spec("SYNC-17-007")
def test_actor_the_roster_does_not_list_states_no_position() -> None:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=UNLISTED_ID)
    seed_case(store, embargo_active=False)
    seed_ledger(store, 2)
    port = MagicMock(spec=SyncActivityPort)

    assert state_ledger_positions_trigger(store, UNLISTED_ID, port) == 0
    port.send_read_ledger_entry.assert_not_called()


@pytest.mark.spec("SYNC-17-007")
def test_removed_participant_still_states_its_position() -> None:
    """The entry that reinstated it may be the one its replica lost."""
    store = _participant_store()
    participant = cast(
        CaseParticipant, store.read(f"{SIGNATORY_ID}/participant")
    )
    participant.record_removal("https://example.org/activities/remove-2")
    store.save(participant)
    port = MagicMock(spec=SyncActivityPort)

    assert state_ledger_positions_trigger(store, SIGNATORY_ID, port) == 1
