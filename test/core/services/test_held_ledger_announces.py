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
"""Direct tests for the held ledger Announce service (SYNC-14-001, SYNC-14-006).

The use-case tests in ``test/core/use_cases/received/test_sync.py`` reach
these through the announce tree; these pin each operation on its own.
"""

import pytest

from test.support.inbox_replay import (
    archive_event,
    held_depth,
    hold_received,
    ledger_announce_event,
)
from test.support.received import received_record
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.received_activity_record import ReceivedStage
from vultron.core.services.held_ledger_announces import (
    discard_held,
    held_ledger_announces,
    held_successor,
    hold_ledger_announce,
    holds_held_body,
    release_held,
)
from vultron.core.services.received_holding import discard_holding

_CASE = "https://example.org/cases/held-service"
_OTHER_CASE = "https://example.org/cases/held-service-other"
_MANAGER = "https://example.org/actors/case-manager"
_RECEIVER = "https://example.org/actors/receiver"


@pytest.fixture
def dl():
    db = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    yield db
    db.close()


def _entry(
    index: int, prev: str, case_id: str = _CASE, marker: str = "x"
) -> CaseLedgerEntry:
    return HashChainLedgerRecord(
        case_id=case_id,
        log_index=index,
        object_id=f"https://example.org/activities/{marker}-{index}",
        semantic_type="test_event",
        payload_snapshot={"index": index, "marker": marker},
        prev_log_hash=prev,
    ).to_ledger_entry()


def _event(entry: CaseLedgerEntry):
    return ledger_announce_event(entry, actor=_MANAGER, to=_RECEIVER)


def _replay_is_owed(dl, activity_id: str) -> bool:
    """Whether the one record for *activity_id* still owes a replay.

    Read off the record rather than through the service, so the assertion
    names the field the hold writes (ADR-0154).
    """
    record = received_record(dl, activity_id)
    assert record is not None, f"{activity_id!r} has no ReceivedActivityRecord"
    return record.replay_owed


@pytest.mark.spec("SYNC-14-001")
def test_holds_the_received_body_and_finds_it_by_predecessor(dl):
    event = _event(_entry(2, "a" * 64))
    hold_received(dl, event)

    held = held_successor(dl, _CASE, "a" * 64)
    assert held is not None and held.activity_id == event.activity_id
    # A buffered Announce stays in holding, owing a replay: it has not been
    # applied, so it is not archived (ADR-0154).
    record = received_record(dl, event.activity_id)
    assert record is not None
    assert record.received_body == event.received_evidence
    assert record.stage is ReceivedStage.HELD
    assert record.replay_owed is True
    assert holds_held_body(dl, held)
    assert held_successor(dl, _CASE, "b" * 64) is None


def test_held_announces_are_per_case_and_in_index_order(dl):
    for index, prev in ((5, "5" * 64), (2, "2" * 64)):
        hold_received(dl, _event(_entry(index, prev)))
    hold_received(dl, _event(_entry(3, "3" * 64, case_id=_OTHER_CASE)))

    assert [h.log_index for h in held_ledger_announces(dl, _CASE)] == [2, 5]
    assert held_depth(dl, _OTHER_CASE) == 1


@pytest.mark.spec("SYNC-14-009")
def test_release_drops_the_index_row_and_keeps_the_body(dl):
    event = _event(_entry(2, "a" * 64))
    hold_received(dl, event)
    held = held_successor(dl, _CASE, "a" * 64)
    assert held is not None

    release_held(dl, held)

    assert held_depth(dl, _CASE) == 0
    assert _replay_is_owed(dl, event.activity_id)


@pytest.mark.spec("SYNC-14-006")
@pytest.mark.spec("SYNC-14-013")
def test_discard_drops_the_index_row_and_the_held_announce(dl):
    """Discarding drops the never-applied Announce, body and all
    (SYNC-14-013); it leaves no archive, because it was not applied."""
    event = _event(_entry(2, "a" * 64))
    hold_received(dl, event)
    held = held_successor(dl, _CASE, "a" * 64)
    assert held is not None

    discard_held(dl, held)

    assert held_depth(dl, _CASE) == 0
    assert received_record(dl, event.activity_id) is None


@pytest.mark.spec("SYNC-14-001")
def test_a_failed_fork_replacement_keeps_the_old_hold(dl, monkeypatch):
    """The fork's removal of the old hold and the new hold commit together:
    a failure claiming the new body's replay leaves the old Announce held."""
    old = _event(_entry(4, "4" * 64, marker="old"))
    hold_received(dl, old)
    fork = _event(_entry(4, "4" * 64, marker="fork"))
    archive_event(dl, fork)
    real_save = dl.save

    def failing_save(obj):
        if getattr(obj, "type_", None) == "ReceivedActivityRecord":
            raise RuntimeError("store unavailable")
        real_save(obj)

    monkeypatch.setattr(dl, "save", failing_save)
    entry = fork.log_entry
    assert entry is not None

    with pytest.raises(RuntimeError):
        hold_ledger_announce(dl, entry, fork.activity_id)

    held = held_successor(dl, _CASE, "4" * 64)
    assert held is not None and held.activity_id == old.activity_id
    assert _replay_is_owed(dl, old.activity_id)
    assert _replay_is_owed(dl, fork.activity_id) is False


@pytest.mark.spec("SYNC-14-006")
def test_a_failed_eviction_keeps_the_farthest_hold(dl, monkeypatch):
    far = _event(_entry(9, "9" * 64))
    hold_received(dl, far)
    near = _event(_entry(3, "3" * 64))
    archive_event(dl, near)
    real_save = dl.save

    def failing_save(obj):
        if getattr(obj, "type_", None) == "HeldLedgerAnnounce":
            raise RuntimeError("store unavailable")
        real_save(obj)

    monkeypatch.setattr(dl, "save", failing_save)
    entry = near.log_entry
    assert entry is not None

    with pytest.raises(RuntimeError):
        hold_ledger_announce(dl, entry, near.activity_id, max_per_case=1)

    assert [h.activity_id for h in held_ledger_announces(dl, _CASE)] == [
        far.activity_id
    ]
    assert _replay_is_owed(dl, far.activity_id)


@pytest.mark.spec("SYNC-14-001")
def test_a_redelivery_reholds_a_held_entry_that_owes_no_replay(dl):
    """A held row whose body was dropped can never replay; another Announce
    of the same entry takes its place, replay claim and all."""
    entry = _entry(4, "4" * 64)
    first, second = _event(entry), _event(entry)
    hold_received(dl, first)
    discard_holding(dl, first.activity_id)
    assert received_record(dl, first.activity_id) is None

    hold_received(dl, second)

    held = held_successor(dl, _CASE, "4" * 64)
    assert held is not None and held.activity_id == second.activity_id
    assert holds_held_body(dl, held)
