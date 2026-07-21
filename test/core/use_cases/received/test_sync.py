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
"""Tests for SYNC-2/SYNC-3 received use cases."""

import pytest
from unittest.mock import MagicMock

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import (
    HashChainLedgerRecord,
)
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.events import MessageSemantics
from vultron.core.models.ledger_gap_buffer import LedgerGapBuffer
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
    _reconstruct_tail_hash,
)
from typing import cast

from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.semantic_registry import extract_event
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

ACTOR_URI = "https://example.org/actors/case-actor"
CASE_URI = "https://example.org/cases/case1"
_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains


def _to_persistable_entry(
    chain_entry: HashChainLedgerRecord,
) -> VultronCaseLedgerEntry:
    """Test helper: convert a HashChainLedgerRecord to a VultronCaseLedgerEntry."""
    return VultronCaseLedgerEntry(
        case_id=chain_entry.case_id,
        log_index=chain_entry.log_index,
        disposition=chain_entry.disposition,
        term=chain_entry.term,
        log_object_id=chain_entry.object_id,
        event_type=chain_entry.event_type,
        payload_snapshot=dict(chain_entry.payload_snapshot),
        prev_log_hash=chain_entry.prev_log_hash,
        entry_hash=chain_entry.entry_hash,
        reason_code=chain_entry.reason_code,
        reason_detail=chain_entry.reason_detail,
    )


def _make_entry(
    case_id: str, log_index: int, prev_hash: str
) -> VultronCaseLedgerEntry:
    chain = HashChainLedgerRecord(
        case_id=case_id,
        log_index=log_index,
        object_id="https://example.org/activities/act1",
        event_type="test_event",
        payload_snapshot={"key": "value"},
        prev_log_hash=prev_hash,
    )
    return _to_persistable_entry(chain)


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def first_entry() -> VultronCaseLedgerEntry:
    # Use _ZERO_HASH as prev_log_hash for chain tests that don't need
    # genesis validation. Tests that need genesis hash must build their own.
    return _make_entry(CASE_URI, 0, _ZERO_HASH)


@pytest.fixture
def case_with_genesis(dl) -> VulnerabilityCase:
    """Create and store a VulnerabilityCase so genesis hash is known."""
    case = _make_case()
    dl.save(case)
    return case


@pytest.fixture
def genesis_entry(case_with_genesis) -> VultronCaseLedgerEntry:
    """First entry whose prev_log_hash matches the per-case genesis hash."""
    return _make_entry(CASE_URI, 0, case_with_genesis.genesis_hash)


def _make_case(case_id: str = CASE_URI) -> VulnerabilityCase:
    """Create a VulnerabilityCase with genesis_hash for test DataLayer storage."""
    return VulnerabilityCase(
        id_=case_id,
        attributed_to=ACTOR_URI,
    )


class TestReconstructTailHash:
    def test_empty_log_returns_genesis(self, dl):
        case = _make_case()
        dl.save(case)
        tail_hash, tail_index = _reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == case.genesis_hash
        assert len(tail_hash) == 64
        assert tail_index == -1

    def test_empty_log_no_case_raises(self, dl):
        """Without a case in DataLayer, empty ledger raises VultronValidationError.

        Fail-closed: the ledger cannot be safely bootstrapped without a known
        genesis anchor (CLP-08-005).
        """
        import pytest
        from vultron.errors import VultronValidationError

        with pytest.raises(VultronValidationError, match="genesis hash"):
            _reconstruct_tail_hash(CASE_URI, dl)

    def test_one_entry_returns_its_hash(self, dl, first_entry):
        dl.save(first_entry)
        tail_hash, tail_index = _reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == first_entry.entry_hash
        assert tail_index == 0

    def test_two_entries_returns_last_hash(self, dl, first_entry):
        dl.save(first_entry)
        second = _make_entry(CASE_URI, 1, first_entry.entry_hash)
        dl.save(second)
        tail_hash, tail_index = _reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == second.entry_hash
        assert tail_index == 1

    def test_ignores_other_case_entries(self, dl, first_entry):
        dl.save(first_entry)
        other = _make_entry("https://example.org/cases/other", 0, _ZERO_HASH)
        dl.save(other)
        tail_hash, tail_index = _reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == first_entry.entry_hash
        assert tail_index == 0


RECEIVER_URI = "https://example.org/actors/reporter"


class TestAnnounceLedgerEntryReceivedUseCase:
    def _make_event(
        self, entry: VultronCaseLedgerEntry
    ) -> AnnounceLogEntryReceivedEvent:
        wire_entry = WireCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )
        activity = announce_log_entry_activity(wire_entry, actor=ACTOR_URI)
        event = cast(AnnounceLogEntryReceivedEvent, extract_event(activity))
        # The inbox adapter always sets receiving_actor_id in production; set
        # it here so the reject is enqueued against the receiving actor's
        # outbox (matching send_announce_log_entry's explicit-actor queueing).
        return event.model_copy(update={"receiving_actor_id": RECEIVER_URI})

    def test_inline_case_ledger_entry_round_trip(self, first_entry):
        """parse_activity must preserve inline as_CaseLedgerEntry fields (BUG-26041501).

        Simulates the Finder receiving an Announce activity with a full inline
        as_CaseLedgerEntry dict via HTTP, and verifies the event's log_entry has all
        domain fields intact after the parse → extract pipeline.
        """
        body = {
            "type": "Announce",
            "id": "urn:uuid:test-announce-rt",
            "actor": ACTOR_URI,
            "object": first_entry.model_dump(mode="json", by_alias=True),
        }
        parsed = parse_activity(body)
        event = cast(AnnounceLogEntryReceivedEvent, extract_event(parsed))
        assert (
            event.semantic_type == MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
        )
        assert event.log_entry is not None
        assert event.log_entry.case_id == CASE_URI

    def test_accepts_valid_first_entry(self, dl, genesis_entry):
        event = self._make_event(genesis_entry)
        assert (
            event.semantic_type == MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
        )

        uc = AnnounceLedgerEntryReceivedUseCase(dl, event)
        uc.execute()

        stored = dl.read(genesis_entry.id_)
        assert stored is not None

    def test_rejects_entry_with_wrong_prev_hash(self, dl, first_entry):
        """Entry whose prev_log_hash does not match local tail is rejected."""
        bad_entry = _make_entry(CASE_URI, 0, "deadbeef" * 8)
        event = self._make_event(bad_entry)
        sync_port = MagicMock(spec=SyncActivityPort)
        uc = AnnounceLedgerEntryReceivedUseCase(dl, event, sync_port=sync_port)
        uc.execute()
        # Entry not stored
        assert dl.read(bad_entry.id_) is None

    def test_mismatch_queues_reject_activity(self, dl, first_entry):
        """Hash mismatch causes a RejectLogEntryActivity to be queued (SYNC-03-001)."""
        # Pre-seed a good entry so tail_hash != the genesis hash
        dl.save(first_entry)
        # Send a second entry with wrong prev_hash
        bad_entry = _make_entry(CASE_URI, 1, "badbadbadbadbad0" * 4)
        event = self._make_event(bad_entry)
        sync_port = SyncActivityAdapter(dl)
        uc = AnnounceLedgerEntryReceivedUseCase(dl, event, sync_port=sync_port)
        uc.execute()

        # Bad entry still not stored
        assert dl.read(bad_entry.id_) is None

        # A Reject activity should be queued in the receiving actor's outbox
        queued = dl.outbox_list_for_actor(RECEIVER_URI)
        assert len(queued) == 1

        reject_obj = dl.read(queued[0])
        assert reject_obj is not None
        # DataLayer reconstructs as as_Reject (type_="Reject") via VOCABULARY
        from vultron.wire.as2.enums import as_TransitiveActivityType

        assert (
            getattr(reject_obj, "type_", None)
            == as_TransitiveActivityType.REJECT
        )

    def test_mismatch_reject_carries_tail_hash(self, dl, first_entry):
        """The queued Reject carries the local tail hash as context (SYNC-03-001)."""
        dl.save(first_entry)
        bad_entry = _make_entry(CASE_URI, 1, "badbadbadbadbad0" * 4)
        event = self._make_event(bad_entry)
        sync_port = SyncActivityAdapter(dl)
        AnnounceLedgerEntryReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        queued = dl.outbox_list_for_actor(RECEIVER_URI)
        reject_obj = dl.read(queued[0])
        assert getattr(reject_obj, "context", None) == first_entry.entry_hash

    def test_mismatch_reject_addressed_to_sender(self, dl, first_entry):
        """The queued Reject is addressed to the CaseActor who sent the Announce."""
        dl.save(first_entry)
        bad_entry = _make_entry(CASE_URI, 1, "badbadbadbadbad0" * 4)
        event = self._make_event(bad_entry)
        sync_port = SyncActivityAdapter(dl)
        AnnounceLedgerEntryReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        queued = dl.outbox_list_for_actor(RECEIVER_URI)
        reject_obj = dl.read(queued[0])
        to_field = getattr(reject_obj, "to", None) or []
        assert ACTOR_URI in to_field

    def test_idempotent_second_accept(self, dl, first_entry):
        """Calling execute twice with the same entry stores it only once."""
        dl.save(first_entry)  # pre-store
        event = self._make_event(first_entry)
        uc = AnnounceLedgerEntryReceivedUseCase(dl, event)
        uc.execute()  # should skip silently
        # Still exactly one entry for this case
        case_entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if getattr(obj, "case_id", None) == CASE_URI
        ]
        assert len(case_entries) == 1

    def test_sequential_chain(self, dl, genesis_entry):
        """Accept two sequential entries; chain is maintained."""
        event0 = self._make_event(genesis_entry)
        AnnounceLedgerEntryReceivedUseCase(dl, event0).execute()

        second = _make_entry(CASE_URI, 1, genesis_entry.entry_hash)
        event1 = self._make_event(second)
        AnnounceLedgerEntryReceivedUseCase(dl, event1).execute()

        assert dl.read(genesis_entry.id_) is not None
        assert dl.read(second.id_) is not None

    def test_semantic_type_is_correct(self, dl, first_entry):
        event = self._make_event(first_entry)
        assert (
            event.semantic_type == MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
        )
        assert event.log_entry is not None
        assert event.log_entry.case_id == CASE_URI


class TestOutOfOrderAnnounceBuffering:
    """Out-of-order ``Announce(CaseLedgerEntry)`` must not permanently drop
    entries; the replica converges to a contiguous prefix regardless of
    delivery order (issue #1556, SYNC-10-004).
    """

    @pytest.fixture
    def gap_buffer(self) -> LedgerGapBuffer:
        return LedgerGapBuffer()

    def _make_event(
        self, entry: VultronCaseLedgerEntry
    ) -> AnnounceLogEntryReceivedEvent:
        wire_entry = WireCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )
        activity = announce_log_entry_activity(wire_entry, actor=ACTOR_URI)
        return cast(AnnounceLogEntryReceivedEvent, extract_event(activity))

    def _chain(
        self, case: VulnerabilityCase, length: int
    ) -> list[VultronCaseLedgerEntry]:
        """Build a valid hash chain of *length* entries anchored on genesis."""
        entries: list[VultronCaseLedgerEntry] = []
        prev = case.genesis_hash
        for i in range(length):
            entry = _make_entry(CASE_URI, i, prev)
            entries.append(entry)
            prev = entry.entry_hash
        return entries

    def _present_indices(self, dl: SqliteDataLayer) -> set[int]:
        return {
            obj.log_index
            for obj in dl.list_objects("CaseLedgerEntry")
            if getattr(obj, "case_id", None) == CASE_URI
            and isinstance(obj, VultronCaseLedgerEntry)
        }

    def test_reversed_delivery_converges_to_contiguous_prefix(
        self, dl, case_with_genesis, gap_buffer
    ):
        """Delivering a 3-entry chain fully reversed (2, 1, 0) must leave all
        three entries stored — no entry is permanently dropped.
        """
        e0, e1, e2 = self._chain(case_with_genesis, 3)
        sync_port = MagicMock(spec=SyncActivityPort)

        # Reverse order: the two later entries arrive before their predecessor.
        for entry in (e2, e1, e0):
            AnnounceLedgerEntryReceivedUseCase(
                dl,
                self._make_event(entry),
                sync_port=sync_port,
                gap_buffer=gap_buffer,
            ).execute()

        assert self._present_indices(dl) == {0, 1, 2}

    def test_single_gap_then_predecessor_clicks_into_place(
        self, dl, case_with_genesis, gap_buffer
    ):
        """Index 1 arriving before index 0 must be buffered and applied once
        index 0 lands (the minimal out-of-order case).
        """
        e0, e1 = self._chain(case_with_genesis, 2)
        sync_port = MagicMock(spec=SyncActivityPort)

        AnnounceLedgerEntryReceivedUseCase(
            dl,
            self._make_event(e1),
            sync_port=sync_port,
            gap_buffer=gap_buffer,
        ).execute()
        # Before the predecessor arrives, nothing is stored but the entry is
        # held in the buffer (not dropped).
        assert self._present_indices(dl) == set()
        assert gap_buffer.depth(CASE_URI) == 1

        AnnounceLedgerEntryReceivedUseCase(
            dl,
            self._make_event(e0),
            sync_port=sync_port,
            gap_buffer=gap_buffer,
        ).execute()
        assert self._present_indices(dl) == {0, 1}
        assert gap_buffer.depth(CASE_URI) == 0

    def test_multi_gap_cascade_drains_all_successors(
        self, dl, case_with_genesis, gap_buffer
    ):
        """With 4, 5 and 6 buffered, delivering 3 must cascade-drain all of
        them once the gap at index 3 is closed.

        Mirrors the maintainer's zipper example: 0,1,2 present, later entries
        buffered, the predecessor arrives → the whole contiguous run clicks
        into place in one drain.
        """
        e0, e1, e2, e3, e4, e5, e6 = self._chain(case_with_genesis, 7)
        sync_port = MagicMock(spec=SyncActivityPort)

        # Establish a contiguous prefix 0,1,2.
        for entry in (e0, e1, e2):
            AnnounceLedgerEntryReceivedUseCase(
                dl,
                self._make_event(entry),
                sync_port=sync_port,
                gap_buffer=gap_buffer,
            ).execute()
        assert self._present_indices(dl) == {0, 1, 2}

        # 4, 5 and 6 arrive out of order (all forward gaps) and are buffered.
        for entry in (e4, e5, e6):
            AnnounceLedgerEntryReceivedUseCase(
                dl,
                self._make_event(entry),
                sync_port=sync_port,
                gap_buffer=gap_buffer,
            ).execute()
        assert self._present_indices(dl) == {0, 1, 2}
        assert gap_buffer.depth(CASE_URI) == 3

        # 3 lands → cascade should drain 4, 5, 6 as well.
        AnnounceLedgerEntryReceivedUseCase(
            dl,
            self._make_event(e3),
            sync_port=sync_port,
            gap_buffer=gap_buffer,
        ).execute()
        assert self._present_indices(dl) == {0, 1, 2, 3, 4, 5, 6}
        assert gap_buffer.depth(CASE_URI) == 0

    def test_replayed_entries_out_of_order_still_converge(
        self, dl, case_with_genesis, gap_buffer
    ):
        """The CaseActor replay path (SYNC-03-002) sends each missing entry as
        a separate ``Announce`` over an unordered transport.  Those replays flow
        through the *same* receive path, so out-of-order replays are buffered
        and drained just like normal fan-out — the participant converges
        regardless of replay delivery order (issue #1556 finding: replay was
        order-fragile before buffering).
        """
        # Participant is stuck at index 0; the CaseActor replays 1..4.
        entries = self._chain(case_with_genesis, 5)
        sync_port = MagicMock(spec=SyncActivityPort)
        AnnounceLedgerEntryReceivedUseCase(
            dl,
            self._make_event(entries[0]),
            sync_port=sync_port,
            gap_buffer=gap_buffer,
        ).execute()
        assert self._present_indices(dl) == {0}

        # Replayed entries arrive in a shuffled order (3, 1, 4, 2).
        for entry in (entries[3], entries[1], entries[4], entries[2]):
            AnnounceLedgerEntryReceivedUseCase(
                dl,
                self._make_event(entry),
                sync_port=sync_port,
                gap_buffer=gap_buffer,
            ).execute()

        assert self._present_indices(dl) == {0, 1, 2, 3, 4}
        assert gap_buffer.depth(CASE_URI) == 0
