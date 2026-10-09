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

"""``SyncActivityAdapter.send_announce_log_entry`` does not queue a row it holds.

SYNC-15-012: an ``Announce(CaseLedgerEntry)`` for an (entry, peer) pair that is
still pending in this actor's outbox is not queued a second time, and the
caller is told so.  A row already popped for delivery is no longer pending, so
a later request for the same pair queues again — the guard is against
duplicates *in the queue*, not against ever re-sending.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry

OWNER = "https://example.org/actors/owner"
PEER_A = "https://example.org/actors/a"
PEER_B = "https://example.org/actors/b"
CASE = "https://example.org/cases/c"


def _entry(index: int) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE,
            log_index=index,
            object_id=f"urn:test:activity-{index}",
            event_type="add_note",
            payload_snapshot={"log_index": index},
            prev_log_hash="0" * 64,
        )
    )


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)


@pytest.mark.spec("SYNC-15-012")
def test_same_entry_same_peer_is_queued_once_while_pending(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(1)

    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_A]) is True
    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_A]) is False

    assert len(dl.outbox_list()) == 1


@pytest.mark.spec("SYNC-15-012")
def test_same_entry_to_another_peer_is_still_queued(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(1)

    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_A]) is True
    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_B]) is True

    assert len(dl.outbox_list()) == 2


@pytest.mark.spec("SYNC-15-012")
def test_once_popped_for_delivery_the_pair_can_be_queued_again(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(1)
    adapter.send_announce_log_entry(entry, OWNER, [PEER_A])
    assert dl.outbox_pop() is not None  # the drain took it

    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_A]) is True
    assert len(dl.outbox_list()) == 1


@pytest.mark.spec("ID-04-004")
def test_same_mismatching_entry_is_rejected_under_one_id(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(2)

    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])
    (first,) = dl.outbox_list()
    assert dl.outbox_pop() == first  # the drain took it
    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])
    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])

    # Queued again under the same id (the receiver deduplicates), once.
    assert dl.outbox_list() == [first]


@pytest.mark.spec("ID-04-005")
def test_a_sealed_reject_that_was_never_queued_is_queued_on_redelivery(dl):
    from vultron.adapters.outbox_sealed_body import (
        derived_activity_id,
        is_sealed,
    )

    adapter = SyncActivityAdapter(dl)
    entry = _entry(2)
    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])
    (reject_id,) = dl.outbox_list()
    assert reject_id == derived_activity_id(
        "reject-log-entry", OWNER, entry.id_, "a" * 64, PEER_A
    )
    # A crash between sealing and queueing: sealed, nothing queued.
    dl.outbox_pop()
    assert is_sealed(dl, reject_id) and dl.outbox_list() == []

    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])

    assert dl.outbox_list() == [reject_id]


@pytest.mark.spec("ID-04-004")
def test_a_different_tail_hash_is_a_new_rejection(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(2)

    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])
    adapter.send_reject_log_entry(entry, "b" * 64, OWNER, [PEER_A])

    assert len(dl.outbox_list()) == 2
