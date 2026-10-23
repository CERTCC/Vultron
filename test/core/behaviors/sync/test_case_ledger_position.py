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

"""Each case stores the ledger position it is a projection of (SYNC-16-005).

Every case names a position: a new case starts at its empty ledger
(CLP-08-004), every commit and replica store moves it in the transaction
that stores the entry, and a stored or received case without the field is
refused rather than given one.
"""

import logging
from types import SimpleNamespace
from typing import Any

import pytest
from py_trees.common import Status
from pydantic import ValidationError

from test.adapters.driven.test_sqlite_core_roundtrip import _insert_raw_row
from test.support.ledger import (
    case_snapshot_position_violations,
    checking_each_commit,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.db_record import STORED_ROW_CONTEXT
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.nodes import (
    PersistLogEntryNode,
    PersistReceivedLogEntryNode,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
from vultron.core.sync_helpers import at_stored_position, store_ledger_entry
from vultron.errors import VultronNotFoundError
from vultron.metadata.wire_context.sync import vultron_property_terms
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.factories import create_case_activity
from vultron.wire.as2.parser import parse_activity

OWNER = "https://example.org/actors/vendor"
REPLICA = "https://example.org/actors/reporter"
CASE_ID = "https://example.org/cases/position"


def _case(**fields: Any) -> VulnerabilityCase:
    return VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER, **fields)


def _entry(
    case: VulnerabilityCase, log_index: int, prev: str
) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=case.id_,
            log_index=log_index,
            object_id=f"https://example.org/activities/{log_index}",
            semantic_type="test_event",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev,
        )
    )


def _position(entry: CaseLedgerEntry) -> LedgerPosition:
    return LedgerPosition(
        log_index=entry.log_index, entry_hash=entry.entry_hash
    )


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)


# ---------------------------------------------------------------------------
# The field and its validation (AC-1)
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-16-005")
@pytest.mark.spec("CLP-08-004")
def test_a_new_owned_case_starts_at_its_empty_ledger() -> None:
    case = _case()

    assert case.ledger_position == LedgerPosition(
        log_index=EMPTY_LEDGER_LOG_INDEX, entry_hash=case.genesis_hash
    )


@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize(
    "context", [None, STORED_ROW_CONTEXT], ids=["built", "loaded"]
)
def test_a_case_with_no_position_is_refused(
    context: dict[str, bool] | None,
) -> None:
    """Every case has an owner, so every case names a ledger position."""
    data = _case().model_dump(mode="json")
    data["ledger_position"] = None

    with pytest.raises(ValidationError, match="ledger_position"):
        VulnerabilityCase.model_validate(data, context=context)


@pytest.mark.spec("ARCH-10-001")
def test_clearing_the_position_of_a_case_is_refused() -> None:
    case = _case()

    with pytest.raises(ValidationError):
        case.ledger_position = None  # type: ignore[assignment]


@pytest.mark.spec("CLP-08-004")
def test_an_empty_ledger_position_must_name_the_genesis_hash() -> None:
    with pytest.raises(ValidationError, match="other than its genesis_hash"):
        _case(ledger_position={"log_index": -1, "entry_hash": "b" * 64})


@pytest.mark.spec("SYNC-16-005")
def test_the_position_travels_on_the_wire_form() -> None:
    case = _case(ledger_position={"log_index": 4, "entry_hash": "c" * 64})
    body = create_case_activity(case, actor=OWNER).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )

    assert body["object"]["ledgerPosition"] == {
        "logIndex": 4,
        "entryHash": "c" * 64,
    }
    received = getattr(parse_activity(body), "object_", None)
    assert isinstance(received, VulnerabilityCase)
    assert received.ledger_position == case.ledger_position
    assert (
        vultron_property_terms()["ledgerPosition"] == "vultron:ledgerPosition"
    )


@pytest.mark.spec("SYNC-16-005")
def test_a_received_case_without_a_position_is_refused() -> None:
    body = create_case_activity(_case(), actor=OWNER).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    del body["object"]["ledgerPosition"]

    with pytest.raises(VultronParseValidationError, match="ledgerPosition"):
        parse_activity(body)


# ---------------------------------------------------------------------------
# A stored case without the field is refused on load (AC-5)
# ---------------------------------------------------------------------------


def _old_shape_row() -> dict[str, Any]:
    data = _case().model_dump(mode="json")
    del data["ledger_position"]
    return data


@pytest.mark.spec("SYNC-16-005")
def test_building_a_case_without_the_field_starts_it_at_its_empty_ledger() -> (
    None
):
    """Construction and storage reads share the validator; only a read refuses."""
    case = VulnerabilityCase.model_validate(_old_shape_row())

    assert case.ledger_position == LedgerPosition(
        log_index=EMPTY_LEDGER_LOG_INDEX, entry_hash=case.genesis_hash
    )


@pytest.mark.spec("SYNC-16-005")
def test_a_stored_row_without_the_field_is_refused_naming_the_reset() -> None:
    with pytest.raises(ValidationError, match="must be reset"):
        VulnerabilityCase.model_validate(
            _old_shape_row(), context=STORED_ROW_CONTEXT
        )


@pytest.mark.spec("SYNC-16-005")
def test_the_store_reads_an_old_shape_case_as_absent_and_says_why(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
) -> None:
    _insert_raw_row(dl, CASE_ID, "VulnerabilityCase", _old_shape_row())

    with caplog.at_level(logging.WARNING):
        assert dl.read_case(CASE_ID) is None

    assert any("must be reset" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# Every commit and replica store moves it, with the entry (AC-2)
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-16-005")
def test_storing_an_entry_moves_the_case_to_it(dl: SqliteDataLayer) -> None:
    case = _case()
    dl.save(case)
    first = _entry(case, 0, case.genesis_hash)
    second = _entry(case, 1, first.entry_hash)

    store_ledger_entry(first, dl)
    moved = store_ledger_entry(second, dl)

    stored = dl.read_case(CASE_ID)
    assert stored is not None
    assert stored.ledger_position == _position(second) == moved.ledger_position
    assert dl.read(second.id_) is not None


@pytest.mark.spec("SYNC-16-005")
def test_the_entry_and_the_move_commit_together(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case()
    dl.save(case)
    entry = _entry(case, 0, case.genesis_hash)
    real_save = SqliteDataLayer.save

    def _save(self: SqliteDataLayer, obj: Any) -> None:
        if obj.type_ == "VulnerabilityCase":
            raise RuntimeError("case write failed")
        real_save(self, obj)

    monkeypatch.setattr(SqliteDataLayer, "save", _save)

    with pytest.raises(RuntimeError, match="case write failed"):
        store_ledger_entry(entry, dl)

    monkeypatch.undo()
    assert dl.read(entry.id_) is None
    assert dl.read_case(CASE_ID) == case


@pytest.mark.spec("SYNC-16-005")
def test_an_entry_for_a_case_the_store_does_not_hold_is_not_stored(
    dl: SqliteDataLayer,
) -> None:
    entry = _entry(_case(), 0, _case().genesis_hash)

    with pytest.raises(VultronNotFoundError):
        store_ledger_entry(entry, dl)

    assert dl.read(entry.id_) is None


@pytest.mark.spec("SYNC-16-005")
def test_the_case_manager_commit_moves_its_case(dl: SqliteDataLayer) -> None:
    case = _case()
    dl.save(case)
    entry = _entry(case, 0, case.genesis_hash)

    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=PersistLogEntryNode(name="PersistLogEntry"),
        actor_id=OWNER,
        log_entry=entry,
    )

    assert result.status == Status.SUCCESS
    stored = dl.read_case(CASE_ID)
    assert stored is not None
    assert stored.ledger_position == _position(entry)


@pytest.mark.spec("SYNC-16-005")
def test_a_replica_store_moves_its_case() -> None:
    replica = SqliteDataLayer("sqlite:///:memory:", actor_id=REPLICA)
    case = _case()
    replica.save(case)
    entry = _entry(case, 0, case.genesis_hash)

    result = BTBridge(datalayer=replica).execute_with_setup(
        tree=PersistReceivedLogEntryNode(name="PersistReceivedLogEntry"),
        actor_id=REPLICA,
        activity=SimpleNamespace(log_entry=entry),
    )

    assert result.status == Status.SUCCESS
    stored = replica.read_case(CASE_ID)
    assert stored is not None
    assert stored.ledger_position == _position(entry)


# ---------------------------------------------------------------------------
# A copy read before a commit is brought up to the stored position
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-16-005")
def test_a_copy_read_before_a_commit_takes_the_stored_position(
    dl: SqliteDataLayer,
) -> None:
    case = _case()
    dl.save(case)
    read_before = dl.read_case(CASE_ID)
    assert read_before is not None
    entry = _entry(case, 0, case.genesis_hash)
    store_ledger_entry(entry, dl)

    caught_up = at_stored_position(read_before, dl)

    assert caught_up.ledger_position == _position(entry)
    assert read_before.ledger_position == case.ledger_position
    assert at_stored_position(caught_up, dl) is caught_up


@pytest.mark.spec("SYNC-16-005")
def test_the_commit_check_catches_a_write_that_puts_the_position_back(
    dl: SqliteDataLayer,
) -> None:
    """The AC-4 invariant check is not vacuous: a stale save is reported."""
    case = _case()
    dl.save(case)
    failures: list[str] = []
    checked = checking_each_commit(store_ledger_entry, failures)
    first = _entry(case, 0, case.genesis_hash)
    checked(first, dl)
    assert failures == []

    dl.save(case)  # the copy read before the commit, saved after it
    checked(_entry(case, 1, first.entry_hash), dl)

    assert len(failures) == 1
    assert "before committing entry 1" in failures[0]


@pytest.mark.spec("SYNC-16-005")
@pytest.mark.parametrize("slot", ["object", "target"])
def test_the_snapshot_check_reads_a_case_in_either_slot(slot: str) -> None:
    """A case carried as the object or the target (full-case Invite) is checked.

    The entry carries the case at the entry's own position, which no snapshot
    may name, so the check reports it whichever member holds the case.
    """
    case = _case()
    genesis = _entry(case, 0, case.genesis_hash)
    ahead = case.model_copy(update={"ledger_position": _position(genesis)})
    carried = ahead.model_dump(by_alias=True, mode="json", exclude_none=True)
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=case.id_,
            log_index=0,
            object_id="https://example.org/activities/carrying",
            semantic_type="test_event",
            payload_snapshot={"actor": OWNER, slot: carried},
            prev_log_hash=case.genesis_hash,
        )
    )

    (violation,) = case_snapshot_position_violations([entry], OWNER)

    assert f"as its {slot} at its own or a later position" in violation


@pytest.mark.spec("SYNC-16-005")
def test_a_copy_of_a_case_the_store_does_not_hold_is_returned_as_is(
    dl: SqliteDataLayer,
) -> None:
    case = _case()

    assert at_stored_position(case, dl) is case


@pytest.mark.spec("SYNC-16-005")
def test_the_case_manager_commit_fails_without_its_case(
    dl: SqliteDataLayer,
) -> None:
    entry = _entry(_case(), 0, _case().genesis_hash)

    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=PersistLogEntryNode(name="PersistLogEntry"),
        actor_id=OWNER,
        log_entry=entry,
    )

    assert result.status == Status.FAILURE
    assert not result.internal_error
    assert "cannot commit log entry 0" in result.feedback_message
    assert dl.read(entry.id_) is None


@pytest.mark.spec("SYNC-16-005")
def test_a_replica_store_fails_without_its_case() -> None:
    replica = SqliteDataLayer("sqlite:///:memory:", actor_id=REPLICA)
    entry = _entry(_case(), 0, _case().genesis_hash)

    result = BTBridge(datalayer=replica).execute_with_setup(
        tree=PersistReceivedLogEntryNode(name="PersistReceivedLogEntry"),
        actor_id=REPLICA,
        activity=SimpleNamespace(log_entry=entry),
    )

    assert result.status == Status.FAILURE
    assert not result.internal_error
    assert "cannot store received log entry" in result.feedback_message
    assert replica.read(entry.id_) is None
