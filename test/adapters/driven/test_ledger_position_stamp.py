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
"""The sender's adapter stamps its own ledger tail (SYNC-18-001, SYNC-18-002)."""

from collections.abc import Iterator

import pytest

from test.support.act_clock import ACT_AT
from test.support.objects import authored_at, make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.ledger_position_stamp import (
    with_sender_ledger_position,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
from vultron.errors import VultronValidationError
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_ACTOR = "https://example.org/users/vendor"
_CASE = "https://example.org/cases/adapter-stamp"


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    yield store
    store.clear_all()
    store.close()


def _note():
    return add_note_to_case_activity(
        make(as_Note, id_=f"{_CASE}/notes/1", content="n", context=_CASE),
        target=_CASE,
        actor=_ACTOR,
        at=authored_at(),
    )


def _entry(log_index: int, prev: str, entry_hash: str) -> CaseLedgerEntry:
    return make(
        CaseLedgerEntry,
        case_id=_CASE,
        log_index=log_index,
        log_object_id=f"{_CASE}/activities/{log_index}",
        semantic_type="add_note_to_case",
        payload_snapshot={},
        prev_log_hash=prev,
        entry_hash=entry_hash,
        received_at=ACT_AT,
        published=ACT_AT,
    )


@pytest.mark.spec("SYNC-18-001")
def test_a_store_holding_the_case_stamps_its_empty_ledger(dl) -> None:
    case = make(VulnerabilityCase, id_=_CASE, attributed_to=_ACTOR)
    dl.create(case)

    stamped = with_sender_ledger_position(dl, _note())

    assert stamped.ledger_position == LedgerPosition(
        log_index=EMPTY_LEDGER_LOG_INDEX, entry_hash=case.genesis_hash
    )


@pytest.mark.spec("SYNC-18-001")
def test_a_store_holding_entries_stamps_its_last_entry(dl) -> None:
    dl.save(_entry(0, "00" * 32, "aa" * 32))
    dl.save(_entry(1, "aa" * 32, "bb" * 32))

    stamped = with_sender_ledger_position(dl, _note())

    assert stamped.ledger_position == LedgerPosition(
        log_index=1, entry_hash="bb" * 32
    )


@pytest.mark.spec("SYNC-18-001", "SYNC-18-017")
def test_a_store_holding_no_ledger_for_the_case_stamps_nothing(dl) -> None:
    note = _note()

    assert with_sender_ledger_position(dl, note) is note


@pytest.mark.spec("SYNC-18-001")
def test_something_that_is_no_activity_passes_through(dl) -> None:
    dl.create(make(VulnerabilityCase, id_=_CASE, attributed_to=_ACTOR))
    note = make(as_Note, id_=f"{_CASE}/notes/2", content="n", context=_CASE)

    assert with_sender_ledger_position(dl, note) is note


@pytest.mark.spec("SYNC-18-017")
def test_a_processing_fault_from_a_case_holder_carries_no_position(
    dl,
) -> None:
    dl.create(make(VulnerabilityCase, id_=_CASE, attributed_to=_ACTOR))

    fault_id = TriggerActivityAdapter(dl).emit_processing_fault(
        actor=_ACTOR,
        failed_activity_id=f"{_CASE}/activities/9",
        failure_class="https://example.org/faults/x",
        to=["https://example.org/users/manager"],
        case_id=_CASE,
        at=authored_at(),
    )

    body = read_sealed_body_dict(dl, fault_id)
    assert body is not None
    assert "ledgerPosition" not in body


@pytest.mark.spec("SYNC-18-002")
def test_the_stored_activity_and_its_sealed_body_carry_one_position(
    dl,
) -> None:
    dl.create(make(VulnerabilityCase, id_=_CASE, attributed_to=_ACTOR))
    dl.create(
        make(as_Note, id_=f"{_CASE}/notes/3", content="n", context=_CASE)
    )

    activity_id, _ = TriggerActivityAdapter(dl).add_note_to_case(
        note_id=f"{_CASE}/notes/3",
        case_id=_CASE,
        actor=_ACTOR,
        at=authored_at(),
    )

    body = read_sealed_body_dict(dl, activity_id)
    stored = dl.read(activity_id)
    assert body is not None and "ledgerPosition" in body
    assert getattr(stored, "ledger_position", None) == LedgerPosition(
        **body["ledgerPosition"]
    )


@pytest.mark.spec("SYNC-16-027")
def test_a_read_at_the_empty_chain_states_index_minus_one(dl) -> None:
    """A replica that holds no entry states the empty ledger's position in a
    ``Read`` of the case's ledger, naming what prompted it (ADR-0204)."""
    case = make(VulnerabilityCase, id_=_CASE, attributed_to=_ACTOR)
    dl.create(case)
    announce = "https://example.org/activities/prompting-announce"

    SyncActivityAdapter(dl).send_empty_chain_read(
        case_id=_CASE,
        copy_tail_hash="ef" * 32,
        actor_id=_ACTOR,
        to=["https://example.org/users/manager"],
        in_reply_to=announce,
        at=authored_at(),
    )

    (read_id,) = dl.outbox_list()
    body = read_sealed_body_dict(dl, read_id)
    assert body is not None
    assert body["type"] == "Read"
    assert body["object"] == {
        "id": f"{_CASE}/ledger",
        "type": "OrderedCollection",
    }
    assert body["context"] == _CASE
    assert body["inReplyTo"] == announce
    assert body["ledgerPosition"] == {
        "logIndex": EMPTY_LEDGER_LOG_INDEX,
        "entryHash": case.genesis_hash,
    }


@pytest.mark.spec("SYNC-16-027")
def test_an_empty_chain_read_repeat_under_another_announce_names_the_first(
    dl,
) -> None:
    """The ``Read`` answering a copy takes its id from the case and the
    copy's position, not from the Announce: a repeat for the same copy under
    another Announce queues the stored body, which names the first one, and
    a later copy's request is its own (ID-04-004)."""
    dl.create(make(VulnerabilityCase, id_=_CASE, attributed_to=_ACTOR))
    adapter = SyncActivityAdapter(dl)
    first = "https://example.org/activities/first-announce"

    def ask(copy_tail_hash: str, announce: str) -> None:
        adapter.send_empty_chain_read(
            case_id=_CASE,
            copy_tail_hash=copy_tail_hash,
            actor_id=_ACTOR,
            to=["https://example.org/users/manager"],
            in_reply_to=announce,
            at=authored_at(),
        )

    ask("ef" * 32, first)
    ask("ef" * 32, "https://example.org/activities/second-announce")

    (read_id,) = dl.outbox_list()
    body = read_sealed_body_dict(dl, read_id)
    assert body is not None and body["inReplyTo"] == first

    ask("cd" * 32, "https://example.org/activities/later-announce")

    assert len(set(dl.outbox_list())) == 2


@pytest.mark.spec("SYNC-16-027")
def test_an_empty_chain_read_needs_the_case_it_names(dl) -> None:
    """Its position is read from the stored case: a store that does not hold
    it raises before it writes or queues anything (SYNC-18-001)."""
    with pytest.raises(VultronValidationError):
        SyncActivityAdapter(dl).send_empty_chain_read(
            case_id=_CASE,
            copy_tail_hash="ef" * 32,
            actor_id=_ACTOR,
            to=["https://example.org/users/manager"],
            in_reply_to="https://example.org/activities/prompting-announce",
            at=authored_at(),
        )

    assert dl.outbox_list() == []


@pytest.mark.spec("SYNC-17-001")
def test_a_read_of_its_own_accord_names_no_cause(dl) -> None:
    dl.create(make(VulnerabilityCase, id_=_CASE, attributed_to=_ACTOR))

    SyncActivityAdapter(dl).send_read_ledger(
        case_id=_CASE,
        ledger_position=LedgerPosition(log_index=0, entry_hash="ab" * 32),
        actor_id=_ACTOR,
        to=["https://example.org/users/manager"],
        at=authored_at(),
    )

    (read_id,) = dl.outbox_list()
    body = read_sealed_body_dict(dl, read_id)
    assert body is not None
    assert "inReplyTo" not in body
