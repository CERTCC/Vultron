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

"""Send-side hash check: the CASE_MANAGER holds back an entry it cannot verify.

Covers the shared pieces every send path uses: ``send_verified_log_entry``,
the one ``send_announce_log_entry`` call, and ``send_ledger_suffix``, the
loop the replays and backfills share (SYNC-03-009).  Each send site has its
own test in ``nodes/test_send_side_hash_check_sites.py``.
"""

import logging
from datetime import UTC, datetime
from typing import cast

import pytest

from test.support.broken_ledger_entry import BreakEntry, broken_entries
from vultron.core.behaviors.sync.nodes.embargo_pause import send_ledger_suffix
from vultron.core.behaviors.sync.nodes.verified_send import (
    send_verified_log_entry,
)
from vultron.core.models.case_ledger import (
    CaseLedgerEntry,
    HashChainLedgerRecord,
    compute_genesis_hash,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronUnverifiedLedgerEntryError

_CASE_ID = "https://example.org/cases/case-send-side-hash-001"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_PEER_ID = "https://example.org/actors/vendor"


class _RecordingSyncPort:
    """Records each ``Announce(CaseLedgerEntry)`` it is asked to queue."""

    def __init__(self) -> None:
        self.sent: list[int] = []

    def send_announce_log_entry(
        self, entry: CaseLedgerEntry, actor_id: str, to: list[str]
    ) -> bool:
        self.sent.append(entry.log_index)
        return True


def _chain(length: int) -> list[CaseLedgerEntry]:
    entries: list[CaseLedgerEntry] = []
    prev = compute_genesis_hash(
        _CASE_ID, datetime(2026, 1, 1, tzinfo=UTC), _CASE_ACTOR_ID
    )
    for log_index in range(length):
        entry = HashChainLedgerRecord(
            case_id=_CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/{log_index}",
            semantic_type="test_event",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev,
        ).to_ledger_entry()
        entries.append(entry)
        prev = entry.entry_hash
    return entries


@pytest.mark.spec("SYNC-03-009")
@broken_entries
def test_replay_stops_at_an_entry_that_does_not_verify(
    break_entry: BreakEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Entries before the broken one go out; it and everything after do not."""
    entries = _chain(4)
    entries[2] = break_entry(entries[2])
    port = _RecordingSyncPort()

    with caplog.at_level(logging.ERROR):
        result = send_ledger_suffix(
            cast(SyncActivityPort, port),
            entries,
            after_index=-1,
            actor_id=_CASE_ACTOR_ID,
            peer_id=_PEER_ID,
        )

    assert port.sent == [0, 1]
    assert any(
        record.levelno == logging.ERROR and _PEER_ID in record.getMessage()
        for record in caplog.records
    )
    assert result.sent == 2
    assert result.held_back is not None
    assert result.held_back.log_index == 2


@pytest.mark.spec("SYNC-03-009")
def test_an_intact_suffix_is_sent_unchanged() -> None:
    entries = _chain(4)
    port = _RecordingSyncPort()

    result = send_ledger_suffix(
        cast(SyncActivityPort, port),
        entries,
        after_index=-1,
        actor_id=_CASE_ACTOR_ID,
        peer_id=_PEER_ID,
    )

    assert port.sent == [0, 1, 2, 3]
    assert result == (4, 0, None)


@pytest.mark.spec("SYNC-03-009")
@broken_entries
def test_the_verified_send_raises_and_queues_nothing(
    break_entry: BreakEntry,
) -> None:
    """The error names the case, the entry, its log_index and the recipients."""
    entry = break_entry(_chain(1)[0])
    port = _RecordingSyncPort()

    with pytest.raises(VultronUnverifiedLedgerEntryError) as excinfo:
        send_verified_log_entry(
            cast(SyncActivityPort, port),
            entry,
            actor_id=_CASE_ACTOR_ID,
            to=[_PEER_ID],
        )

    assert port.sent == []
    error = excinfo.value
    assert (error.case_id, error.entry_id, error.log_index) == (
        _CASE_ID,
        entry.id_,
        0,
    )
    assert error.recipients == [_PEER_ID]
    for part in (_CASE_ID, entry.id_, "log_index=0", _PEER_ID):
        assert part in str(error)


@pytest.mark.spec("SYNC-03-009")
def test_the_verified_send_passes_an_intact_entry_through() -> None:
    entry = _chain(1)[0]
    port = _RecordingSyncPort()

    assert send_verified_log_entry(
        cast(SyncActivityPort, port),
        entry,
        actor_id=_CASE_ACTOR_ID,
        to=[_PEER_ID],
    )
    assert port.sent == [0]
