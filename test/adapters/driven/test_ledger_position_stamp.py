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

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.ledger_position_stamp import (
    with_sender_ledger_position,
)
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
        as_Note(id_=f"{_CASE}/notes/1", content="n", context=_CASE),
        target=_CASE,
        actor=_ACTOR,
    )


def _entry(log_index: int, prev: str, entry_hash: str) -> CaseLedgerEntry:
    return CaseLedgerEntry(
        case_id=_CASE,
        log_index=log_index,
        log_object_id=f"{_CASE}/activities/{log_index}",
        semantic_type="add_note_to_case",
        payload_snapshot={},
        prev_log_hash=prev,
        entry_hash=entry_hash,
    )


@pytest.mark.spec("SYNC-18-001")
def test_a_store_holding_the_case_stamps_its_empty_ledger(dl) -> None:
    case = VulnerabilityCase(id_=_CASE, attributed_to=_ACTOR)
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


@pytest.mark.spec("SYNC-18-001")
def test_a_store_holding_no_ledger_for_the_case_stamps_nothing(dl) -> None:
    note = _note()

    assert with_sender_ledger_position(dl, note) is note


@pytest.mark.spec("SYNC-18-001")
def test_something_that_is_no_activity_passes_through(dl) -> None:
    dl.create(VulnerabilityCase(id_=_CASE, attributed_to=_ACTOR))
    note = as_Note(id_=f"{_CASE}/notes/2", content="n", context=_CASE)

    assert with_sender_ledger_position(dl, note) is note


@pytest.mark.spec("SYNC-18-001")
def test_a_processing_fault_from_a_case_holder_carries_no_position(
    dl,
) -> None:
    dl.create(VulnerabilityCase(id_=_CASE, attributed_to=_ACTOR))

    fault_id = TriggerActivityAdapter(dl).emit_processing_fault(
        actor=_ACTOR,
        failed_activity_id=f"{_CASE}/activities/9",
        failure_class="https://example.org/faults/x",
        to=["https://example.org/users/manager"],
        case_id=_CASE,
    )

    body = read_sealed_body_dict(dl, fault_id)
    assert body is not None
    assert "ledgerPosition" not in body


@pytest.mark.spec("SYNC-18-002")
def test_the_stored_activity_and_its_sealed_body_carry_one_position(
    dl,
) -> None:
    dl.create(VulnerabilityCase(id_=_CASE, attributed_to=_ACTOR))
    dl.create(as_Note(id_=f"{_CASE}/notes/3", content="n", context=_CASE))

    activity_id, _ = TriggerActivityAdapter(dl).add_note_to_case(
        note_id=f"{_CASE}/notes/3", case_id=_CASE, actor=_ACTOR
    )

    body = read_sealed_body_dict(dl, activity_id)
    stored = dl.read(activity_id)
    assert body is not None and "ledgerPosition" in body
    assert getattr(stored, "ledger_position", None) == LedgerPosition(
        **body["ledgerPosition"]
    )
