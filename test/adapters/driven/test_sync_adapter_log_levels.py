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

"""Per-recipient sync-queue lines are DEBUG, not INFO (SL-04-007).

``send_announce_log_entry`` fires once per recipient per ledger entry, so at
INFO it scales with participant count and buries the protocol story.
"""

import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry

_CASE_ACTOR = "https://example.org/actors/case-actor"
_PARTICIPANT = "https://example.org/actors/vendor"
_CASE_URI = "https://example.org/cases/case-sync-log"
_ZERO_HASH = "0" * 64
_ADAPTER_LOGGER = "vultron.adapters.driven.sync_activity_adapter"


@pytest.fixture()
def dl():
    datalayer = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR)
    yield datalayer
    datalayer.close()


@pytest.fixture()
def entry() -> VultronCaseLedgerEntry:
    chain = HashChainLedgerRecord(
        case_id=_CASE_URI,
        log_index=0,
        object_id="https://example.org/activities/act-sync-log",
        event_type="test_event",
        payload_snapshot={"key": "value"},
        prev_log_hash=_ZERO_HASH,
    )
    return VultronCaseLedgerEntry(
        case_id=chain.case_id,
        log_index=chain.log_index,
        disposition=chain.disposition,
        term=chain.term,
        log_object_id=chain.object_id,
        event_type=chain.event_type,
        payload_snapshot=dict(chain.payload_snapshot),
        prev_log_hash=chain.prev_log_hash,
        entry_hash=chain.entry_hash,
    )


def _queued_records(caplog) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if "sync adapter: queued Announce(CaseLedgerEntry)" in r.getMessage()
    ]


def test_queued_announce_line_is_debug(dl, entry, caplog):
    """The per-recipient Announce queue line is emitted at DEBUG."""
    adapter = SyncActivityAdapter(dl)

    with caplog.at_level(logging.DEBUG, logger=_ADAPTER_LOGGER):
        adapter.send_announce_log_entry(
            entry=entry, actor_id=_CASE_ACTOR, to=[_PARTICIPANT]
        )

    records = _queued_records(caplog)
    assert records, "Expected the queued-Announce log entry"
    assert all(r.levelno == logging.DEBUG for r in records)


def test_queued_announce_line_not_emitted_at_info(dl, entry, caplog):
    """No queued-Announce record reaches an INFO-only handler."""
    adapter = SyncActivityAdapter(dl)

    with caplog.at_level(logging.INFO, logger=_ADAPTER_LOGGER):
        adapter.send_announce_log_entry(
            entry=entry, actor_id=_CASE_ACTOR, to=[_PARTICIPANT]
        )

    assert not _queued_records(caplog)


def test_announce_is_still_queued_to_the_outbox(dl, entry):
    """Demoting the log level does not change delivery behaviour."""
    adapter = SyncActivityAdapter(dl)

    adapter.send_announce_log_entry(
        entry=entry, actor_id=_CASE_ACTOR, to=[_PARTICIPANT]
    )

    assert dl.outbox_list_for_actor(_CASE_ACTOR)
