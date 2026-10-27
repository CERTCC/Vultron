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
"""Tests for LedgerFanout/LedgerReconciliation received use cases."""

from typing import cast
from unittest.mock import MagicMock

import pytest

from test.support.case_manager import add_case_manager_participant
from test.support.case_owner import CASE_OWNER_ID
from test.support.inbox_replay import (
    RecordingInboxReplay,
    deliver_replayed,
    held_depth,
    hold_received,
    ledger_announce_event,
    replayed_event,
)
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import (
    HashChainLedgerRecord,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.models.pending_assertion import PendingAssertionStore
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.services.held_ledger_announces import (
    held_ledger_announces,
    hold_ledger_announce,
)
from vultron.core.sync_helpers import reconstruct_tail_hash
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
)
from vultron.errors import VultronBTInternalError, VultronWiringError
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

ACTOR_URI = "https://example.org/actors/case-actor"
CASE_URI = "https://example.org/cases/case1"
_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains


def _make_entry(
    case_id: str, log_index: int, prev_hash: str
) -> CaseLedgerEntry:
    chain = HashChainLedgerRecord(
        case_id=case_id,
        log_index=log_index,
        object_id="https://example.org/activities/act1",
        semantic_type="test_event",
        payload_snapshot={"key": "value"},
        prev_log_hash=prev_hash,
    )
    return chain.to_ledger_entry()


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=RECEIVER_URI,
    )


@pytest.fixture
def first_entry() -> CaseLedgerEntry:
    # Use _ZERO_HASH as prev_log_hash for chain tests that don't need
    # genesis validation. Tests that need genesis hash must build their own.
    return _make_entry(CASE_URI, 0, _ZERO_HASH)


@pytest.fixture
def case_with_genesis(dl) -> VulnerabilityCase:
    """Create and store a VulnerabilityCase so genesis hash is known.

    Its roster names ``ACTOR_URI`` as CASE_MANAGER, the sender whose
    Announces the replica applies (SYNC-13-006).
    """
    case = _make_case()
    add_case_manager_participant(dl, case, ACTOR_URI)
    return case


@pytest.fixture
def genesis_entry(case_with_genesis) -> CaseLedgerEntry:
    """First entry whose prev_log_hash matches the per-case genesis hash."""
    return _make_entry(CASE_URI, 0, case_with_genesis.genesis_hash)


def _make_case(case_id: str = CASE_URI) -> VulnerabilityCase:
    """Create a VulnerabilityCase with genesis_hash for test DataLayer storage."""
    return VulnerabilityCase(
        id_=case_id,
        attributed_to=ACTOR_URI,
    )


class TestReconstructTailHash:
    @pytest.mark.spec("CLP-08-004")
    def test_empty_log_returns_genesis(self, dl):
        case = _make_case()
        dl.save(case)
        tail_hash, tail_index = reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == case.genesis_hash
        assert len(tail_hash) == 64
        assert tail_index == -1

    @pytest.mark.spec("CLP-08-005")
    def test_empty_log_no_case_raises(self, dl):
        """Without a case in DataLayer, empty ledger raises VultronValidationError.

        Fail-closed: the ledger cannot be safely bootstrapped without a known
        genesis anchor (CLP-08-005).
        """
        import pytest

        from vultron.errors import VultronValidationError

        with pytest.raises(VultronValidationError, match="genesis hash"):
            reconstruct_tail_hash(CASE_URI, dl)

    @pytest.mark.spec("SYNC-01-002")
    def test_one_entry_returns_its_hash(self, dl, first_entry):
        dl.save(first_entry)
        tail_hash, tail_index = reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == first_entry.entry_hash
        assert tail_index == 0

    @pytest.mark.spec("SYNC-01-002")
    def test_two_entries_returns_last_hash(self, dl, first_entry):
        dl.save(first_entry)
        second = _make_entry(CASE_URI, 1, first_entry.entry_hash)
        dl.save(second)
        tail_hash, tail_index = reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == second.entry_hash
        assert tail_index == 1

    @pytest.mark.spec("SYNC-01-002")
    def test_ignores_other_case_entries(self, dl, first_entry):
        dl.save(first_entry)
        other = _make_entry("https://example.org/cases/other", 0, _ZERO_HASH)
        dl.save(other)
        tail_hash, tail_index = reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == first_entry.entry_hash
        assert tail_index == 0


RECEIVER_URI = "https://example.org/actors/reporter"


class TestAnnounceLedgerEntryReceivedUseCase:
    def _make_event(
        self, entry: CaseLedgerEntry
    ) -> AnnounceLogEntryReceivedEvent:
        wire_entry = WireCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )
        activity = announce_log_entry_activity(
            wire_entry, actor=ACTOR_URI, to=[RECEIVER_URI]
        )
        event = cast(AnnounceLogEntryReceivedEvent, received_event(activity))
        # The inbox adapter always sets receiving_actor_id in production; set
        # it here so the reject is enqueued against the receiving actor's
        # outbox (matching send_announce_log_entry's explicit-actor queueing).
        return event.model_copy(update={"receiving_actor_id": RECEIVER_URI})

    @pytest.mark.spec("SYNC-02-005")
    @pytest.mark.spec("CLP-02-002")
    @pytest.mark.spec("SYNC-02-004")
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
            # Required on every inbound activity: the parser refuses one
            # without a sender-supplied claimed time (ISSUE-3149).
            "published": "2026-03-04T05:06:07+00:00",
            "object": first_entry.model_dump(mode="json", by_alias=True),
        }
        parsed = parse_activity(body)
        event = cast(AnnounceLogEntryReceivedEvent, received_event(parsed))
        assert (
            event.semantic_type == MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
        )
        assert event.log_entry is not None
        assert event.log_entry.case_id == CASE_URI

    @pytest.mark.spec("SYNC-01-001")
    @pytest.mark.spec("SYNC-01-002")
    def test_accepts_valid_first_entry(self, dl, genesis_entry):
        event = self._make_event(genesis_entry)
        assert (
            event.semantic_type == MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
        )

        uc = AnnounceLedgerEntryReceivedUseCase(dl, event)
        uc.execute()

        stored = dl.read(genesis_entry.id_)
        assert stored is not None

    @pytest.mark.spec("SYNC-03-001")
    def test_rejects_entry_with_wrong_prev_hash(self, dl, first_entry):
        """Entry whose prev_log_hash does not match local tail is rejected."""
        bad_entry = _make_entry(CASE_URI, 0, "deadbeef" * 8)
        event = self._make_event(bad_entry)
        sync_port = MagicMock(spec=SyncActivityPort)
        uc = AnnounceLedgerEntryReceivedUseCase(dl, event, sync_port=sync_port)
        uc.execute()
        # Entry not stored
        assert dl.read(bad_entry.id_) is None

    @pytest.mark.spec("SYNC-03-001")
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
        queued = dl.outbox_list()
        assert len(queued) == 1

        reject_obj = dl.read(queued[0])
        assert reject_obj is not None
        # DataLayer reconstructs as as_Reject (type_="Reject") via VOCABULARY
        from vultron.wire.as2.enums import as_TransitiveActivityType

        assert (
            getattr(reject_obj, "type_", None)
            == as_TransitiveActivityType.REJECT
        )

    @pytest.mark.spec("SYNC-03-001")
    @pytest.mark.spec("SYNC-18-001")
    def test_mismatch_reject_carries_tail_hash(self, dl, first_entry):
        """The queued Reject states the local tail as its position (SYNC-18-001)."""
        dl.save(first_entry)
        bad_entry = _make_entry(CASE_URI, 1, "badbadbadbadbad0" * 4)
        event = self._make_event(bad_entry)
        sync_port = SyncActivityAdapter(dl)
        AnnounceLedgerEntryReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        queued = dl.outbox_list()
        reject_obj = dl.read(queued[0])
        position = getattr(reject_obj, "ledger_position", None)
        assert position is not None
        assert position.entry_hash == first_entry.entry_hash
        assert position.log_index == first_entry.log_index

    @pytest.mark.spec("SYNC-03-001")
    def test_mismatch_reject_addressed_to_sender(self, dl, first_entry):
        """The queued Reject is addressed to the CaseActor who sent the Announce."""
        dl.save(first_entry)
        bad_entry = _make_entry(CASE_URI, 1, "badbadbadbadbad0" * 4)
        event = self._make_event(bad_entry)
        sync_port = SyncActivityAdapter(dl)
        AnnounceLedgerEntryReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        queued = dl.outbox_list()
        reject_obj = dl.read(queued[0])
        to_field = getattr(reject_obj, "to", None) or []
        assert ACTOR_URI in to_field

    @pytest.mark.spec("SYNC-15-001")
    @pytest.mark.spec("SYNC-15-002")
    @pytest.mark.spec("CLP-08-005")
    def test_missing_case_queues_reject_with_empty_tail_hash(self, dl):
        """Announce before VulnerabilityCase is seeded MUST send Reject (SYNC-15-001).

        When no VulnerabilityCase exists in the DataLayer, ReconstructChainTailNode
        cannot derive the per-case genesis hash (CLP-08-005) and the entry cannot
        be accepted.  A Reject with last_accepted_hash="" MUST be sent so the
        CaseActor replays all entries from the beginning once the case is delivered.
        Without this Reject the dropped entry is permanently lost (issue #1873).
        """
        entry = _make_entry(CASE_URI, 0, "any_hash" * 8)
        event = self._make_event(entry)
        event = event.model_copy(update={"receiving_actor_id": RECEIVER_URI})
        sync_port = SyncActivityAdapter(dl)
        AnnounceLedgerEntryReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        # Entry must NOT be stored (no case → cannot validate genesis)
        assert dl.read(entry.id_) is None

        # A Reject MUST be queued so CaseActor retries delivery (SYNC-15-001)
        queued = dl.outbox_list()
        assert len(queued) == 1, (
            "Expected a Reject activity — missing case silently dropped the entry "
            "(regression for issue #1873)"
        )
        reject_obj = dl.read(queued[0])
        from vultron.wire.as2.enums import as_TransitiveActivityType

        assert (
            getattr(reject_obj, "type_", None)
            == as_TransitiveActivityType.REJECT
        )
        # No case, no ledger to state: the Reject states no position, which
        # the CASE_MANAGER reads as last_accepted_hash="" (SYNC-18-001).
        assert getattr(reject_obj, "ledger_position", None) is None

    @pytest.mark.spec("SYNC-03-003")
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

    @pytest.mark.spec("SYNC-01-002")
    @pytest.mark.spec("SYNC-01-003")
    def test_sequential_chain(self, dl, genesis_entry):
        """Accept two sequential entries; chain is maintained."""
        event0 = self._make_event(genesis_entry)
        AnnounceLedgerEntryReceivedUseCase(dl, event0).execute()

        second = _make_entry(CASE_URI, 1, genesis_entry.entry_hash)
        event1 = self._make_event(second)
        AnnounceLedgerEntryReceivedUseCase(dl, event1).execute()

        assert dl.read(genesis_entry.id_) is not None
        assert dl.read(second.id_) is not None

    @pytest.mark.spec("SYNC-13-007")
    @pytest.mark.spec("SYNC-13-004")
    def test_semantic_type_is_correct(self, dl, first_entry):
        event = self._make_event(first_entry)
        assert (
            event.semantic_type == MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
        )
        assert event.log_entry is not None
        assert event.log_entry.case_id == CASE_URI


def _announce_event(
    entry: CaseLedgerEntry, actor: str = ACTOR_URI, to: str = RECEIVER_URI
) -> AnnounceLogEntryReceivedEvent:
    """The received ``Announce`` of *entry* from *actor*, as delivered."""
    event = ledger_announce_event(entry, actor=actor, to=to)
    return event.model_copy(update={"receiving_actor_id": RECEIVER_URI})


class TestOutOfOrderAnnounceBuffering:
    """Out-of-order ``Announce(CaseLedgerEntry)`` must not permanently drop
    entries; the replica converges to a contiguous prefix regardless of
    delivery order (issue #1556, SYNC-10-004).  What is held and replayed is
    the ``Announce`` that was received (SYNC-14-009).
    """

    def _chain(
        self, case: VulnerabilityCase, length: int
    ) -> list[CaseLedgerEntry]:
        """Build a valid hash chain of *length* entries anchored on genesis."""
        entries: list[CaseLedgerEntry] = []
        prev = case.genesis_hash
        for i in range(length):
            entry = _make_entry(CASE_URI, i, prev)
            entries.append(entry)
            prev = entry.entry_hash
        return entries

    def _deliver(
        self,
        dl: SqliteDataLayer,
        entry: CaseLedgerEntry,
        sync_port: SyncActivityPort,
        replay: RecordingInboxReplay,
    ) -> None:
        """Deliver *entry*, then each held Announce its tree replays."""

        def run(event: AnnounceLogEntryReceivedEvent) -> None:
            AnnounceLedgerEntryReceivedUseCase(
                dl, event, sync_port=sync_port, inbox_replay=replay
            ).execute()

        run(_announce_event(entry))
        deliver_replayed(replay, dl, RECEIVER_URI, run)

    def _present_indices(self, dl: SqliteDataLayer) -> set[int]:
        return {
            obj.log_index
            for obj in dl.list_objects("CaseLedgerEntry")
            if getattr(obj, "case_id", None) == CASE_URI
            and isinstance(obj, CaseLedgerEntry)
        }

    @pytest.mark.spec("SYNC-14-001")
    @pytest.mark.spec("SYNC-14-005")
    def test_forward_gap_holds_the_received_announce(
        self, dl, case_with_genesis
    ):
        """A forward-gap entry is held as the ``Announce`` that arrived, its
        body as intake archived it, and no ledger entry is stored."""
        _, e1 = self._chain(case_with_genesis, 2)
        event = _announce_event(e1)

        AnnounceLedgerEntryReceivedUseCase(
            dl, event, sync_port=MagicMock(spec=SyncActivityPort)
        ).execute()

        held = held_ledger_announces(dl, CASE_URI)
        assert [h.activity_id for h in held] == [event.activity_id]
        body = dl.read(DeferredInboxActivity.build_id(event.activity_id))
        assert isinstance(body, DeferredInboxActivity)
        assert body.received_body == event.received_evidence
        assert self._present_indices(dl) == set()

    @pytest.mark.spec("SYNC-14-009")
    def test_commit_replays_the_held_announce_without_running_it(
        self, dl, case_with_genesis
    ):
        """Committing e0 with e1's Announce held replays that Announce, by
        its own id, and runs no second tree in the same ``execute()``
        (SYNC-14-009, CLP-10-005)."""
        e0, e1 = self._chain(case_with_genesis, 2)
        e1_event = _announce_event(e1)
        hold_received(dl, e1_event)
        replay = RecordingInboxReplay()

        result = AnnounceLedgerEntryReceivedUseCase(
            dl,
            _announce_event(e0),
            sync_port=MagicMock(spec=SyncActivityPort),
            inbox_replay=replay,
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        assert replay.replayed == [e1_event.activity_id]
        # The index row is gone, the body waits for the replay, and this
        # delivery did not apply e1.
        assert held_depth(dl, CASE_URI) == 0
        assert isinstance(
            dl.read(DeferredInboxActivity.build_id(e1_event.activity_id)),
            DeferredInboxActivity,
        )
        assert self._present_indices(dl) == {0}

    @pytest.mark.spec("SYNC-14-008")
    @pytest.mark.spec("SYNC-14-009")
    @pytest.mark.spec("VM-08-002")
    def test_the_replay_is_the_announce_that_was_received(
        self, dl, case_with_genesis
    ):
        """The replayed delivery is the received Announce: same id, same
        sender, and the first delivery's body as its evidence.  Nothing is
        built or attributed to the CASE_MANAGER."""
        e0, e1 = self._chain(case_with_genesis, 2)
        e1_event = _announce_event(e1)
        hold_received(dl, e1_event)
        replay = RecordingInboxReplay()
        AnnounceLedgerEntryReceivedUseCase(
            dl,
            _announce_event(e0),
            sync_port=MagicMock(spec=SyncActivityPort),
            inbox_replay=replay,
        ).execute()

        replayed = replayed_event(dl, replay.replayed[0], RECEIVER_URI)

        assert replayed.activity_id == e1_event.activity_id
        assert replayed.actor_id == e1_event.actor_id
        assert replayed.received_evidence == e1_event.received_evidence

    @pytest.mark.spec("SYNC-14-009")
    def test_only_the_next_successor_is_replayed(self, dl, case_with_genesis):
        """With e1 and e2 held, committing e0 replays e1 alone: e1's own
        delivery replays e2, so the use case has no drain loop."""
        e0, e1, e2 = self._chain(case_with_genesis, 3)
        e1_event, e2_event = _announce_event(e1), _announce_event(e2)
        hold_received(dl, e1_event)
        hold_received(dl, e2_event)
        replay = RecordingInboxReplay()

        AnnounceLedgerEntryReceivedUseCase(
            dl,
            _announce_event(e0),
            sync_port=MagicMock(spec=SyncActivityPort),
            inbox_replay=replay,
        ).execute()

        assert replay.replayed == [e1_event.activity_id]
        assert [
            h.activity_id for h in held_ledger_announces(dl, CASE_URI)
        ] == [e2_event.activity_id]

    @pytest.mark.spec("SYNC-14-009")
    def test_missing_replay_port_is_a_wiring_error(
        self, dl, case_with_genesis
    ):
        """No port with a successor waiting is a composition fault: the
        handler raises and the Announce stays held, never applied inline."""
        e0, e1 = self._chain(case_with_genesis, 2)
        hold_received(dl, _announce_event(e1))

        with pytest.raises(VultronBTInternalError, match="inbox_replay"):
            AnnounceLedgerEntryReceivedUseCase(
                dl,
                _announce_event(e0),
                sync_port=MagicMock(spec=SyncActivityPort),
            ).execute()

        assert dl.read(e1.id_) is None
        assert held_depth(dl, CASE_URI) == 1

    @pytest.mark.spec("CSB-19-001")
    @pytest.mark.spec("CSB-19-003")
    def test_cascade_replays_in_log_index_order(self, dl, case_with_genesis):
        """A held run replays one Announce at a time, in ``log_index`` order,
        whatever order it arrived in, so CS guards see the entries in causal
        order (CSB-19-001) and a P-state entry precedes the ET entry after it
        (CSB-19-003)."""
        entries = self._chain(case_with_genesis, 5)
        events = {entry.log_index: _announce_event(entry) for entry in entries}
        for index in (4, 2, 3, 1):
            hold_received(dl, events[index])
        replay = RecordingInboxReplay()

        self._deliver(dl, entries[0], MagicMock(spec=SyncActivityPort), replay)

        assert replay.replayed == [events[i].activity_id for i in (1, 2, 3, 4)]
        assert self._present_indices(dl) == {0, 1, 2, 3, 4}

    @pytest.mark.spec("CSB-19-002")
    def test_holding_evaluates_no_cs_invariant(self, dl, case_with_genesis):
        """An out-of-order CS entry is held, not checked: a status entry whose
        payload would fail its apply is DEFERRED, not refused, at receipt."""
        e0 = _make_entry(CASE_URI, 0, case_with_genesis.genesis_hash)
        status_entry = HashChainLedgerRecord(
            case_id=CASE_URI,
            log_index=2,
            object_id="https://example.org/activities/status-2",
            semantic_type="add_case_status_to_case",
            payload_snapshot={"not": "a case status"},
            prev_log_hash=e0.entry_hash,
        ).to_ledger_entry()

        result = AnnounceLedgerEntryReceivedUseCase(
            dl,
            _announce_event(status_entry),
            sync_port=MagicMock(spec=SyncActivityPort),
        ).execute()

        assert result.disposition is HandlerDisposition.DEFERRED
        assert held_depth(dl, CASE_URI) == 1

    @pytest.mark.spec("SYNC-14-001")
    @pytest.mark.spec("SYNC-14-003")
    def test_reversed_delivery_converges_to_contiguous_prefix(
        self, dl, case_with_genesis
    ):
        """Delivering a 3-entry chain fully reversed (2, 1, 0) must leave all
        three entries stored — no entry is permanently dropped.
        """
        e0, e1, e2 = self._chain(case_with_genesis, 3)
        sync_port = MagicMock(spec=SyncActivityPort)
        replay = RecordingInboxReplay()

        # Reverse order: the two later entries arrive before their predecessor.
        for entry in (e2, e1, e0):
            self._deliver(dl, entry, sync_port, replay)

        assert self._present_indices(dl) == {0, 1, 2}

    @pytest.mark.spec("SYNC-14-001")
    @pytest.mark.spec("SYNC-14-003")
    def test_single_gap_then_predecessor_clicks_into_place(
        self, dl, case_with_genesis
    ):
        """Index 1 arriving before index 0 must be held and applied once
        index 0 lands (the minimal out-of-order case).
        """
        e0, e1 = self._chain(case_with_genesis, 2)
        sync_port = MagicMock(spec=SyncActivityPort)
        replay = RecordingInboxReplay()

        self._deliver(dl, e1, sync_port, replay)
        # Before the predecessor arrives, nothing is stored but the Announce
        # is held (not dropped).
        assert self._present_indices(dl) == set()
        assert held_depth(dl, CASE_URI) == 1

        self._deliver(dl, e0, sync_port, replay)
        assert self._present_indices(dl) == {0, 1}
        assert held_depth(dl, CASE_URI) == 0
        # The replay consumed the held body (IO-03-004).
        assert dl.list_objects("DeferredInboxActivity") == []

    @pytest.mark.spec("SYNC-14-003")
    def test_multi_gap_cascade_drains_all_successors(
        self, dl, case_with_genesis
    ):
        """With 4, 5 and 6 held, delivering 3 must cascade-drain all of
        them once the gap at index 3 is closed.

        Mirrors the maintainer's zipper example: 0,1,2 present, later entries
        held, the predecessor arrives → the whole contiguous run clicks
        into place.
        """
        e0, e1, e2, e3, e4, e5, e6 = self._chain(case_with_genesis, 7)
        sync_port = MagicMock(spec=SyncActivityPort)
        replay = RecordingInboxReplay()

        # Establish a contiguous prefix 0,1,2.
        for entry in (e0, e1, e2):
            self._deliver(dl, entry, sync_port, replay)
        assert self._present_indices(dl) == {0, 1, 2}

        # 4, 5 and 6 arrive out of order (all forward gaps) and are held.
        for entry in (e4, e5, e6):
            self._deliver(dl, entry, sync_port, replay)
        assert self._present_indices(dl) == {0, 1, 2}
        assert held_depth(dl, CASE_URI) == 3

        # 3 lands → cascade should drain 4, 5, 6 as well.
        self._deliver(dl, e3, sync_port, replay)
        assert self._present_indices(dl) == {0, 1, 2, 3, 4, 5, 6}
        assert held_depth(dl, CASE_URI) == 0

    @pytest.mark.spec("SYNC-14-003")
    @pytest.mark.spec("SYNC-03-002")
    def test_replayed_entries_out_of_order_still_converge(
        self, dl, case_with_genesis
    ):
        """The CaseActor replay path (SYNC-03-002) sends each missing entry as
        a separate ``Announce`` over an unordered transport.  Those replays flow
        through the *same* receive path, so out-of-order replays are held
        and drained just like normal fan-out — the participant converges
        regardless of replay delivery order (issue #1556 finding: replay was
        order-fragile before buffering).
        """
        # Participant is stuck at index 0; the CaseActor replays 1..4.
        entries = self._chain(case_with_genesis, 5)
        sync_port = MagicMock(spec=SyncActivityPort)
        replay = RecordingInboxReplay()
        self._deliver(dl, entries[0], sync_port, replay)
        assert self._present_indices(dl) == {0}

        # Replayed entries arrive in a shuffled order (3, 1, 4, 2).
        for entry in (entries[3], entries[1], entries[4], entries[2]):
            self._deliver(dl, entry, sync_port, replay)

        assert self._present_indices(dl) == {0, 1, 2, 3, 4}


class TestHeldAnnounceBound:
    """The holding area is bounded per case (SYNC-14-006)."""

    def _held_event(self, index: int) -> AnnounceLogEntryReceivedEvent:
        return _announce_event(_make_entry(CASE_URI, index, f"{index:064x}"))

    @pytest.mark.spec("SYNC-14-006")
    def test_full_area_drops_the_farthest_ahead_announce(
        self, dl, case_with_genesis, caplog
    ):
        near, far = (
            self._held_event(3),
            self._held_event(9),
        )
        hold_received(dl, near)
        hold_received(dl, far)
        middle = self._held_event(5)
        dl.save(
            ReceivedActivityRecord(
                activity_id=middle.activity_id,
                received_body=cast(str, middle.received_evidence),
            )
        )
        entry = middle.log_entry
        assert entry is not None

        with caplog.at_level("WARNING"):
            assert hold_ledger_announce(
                dl, entry, middle.activity_id, max_per_case=2
            )

        assert [h.log_index for h in held_ledger_announces(dl, CASE_URI)] == [
            3,
            5,
        ]
        # The dropped Announce's body goes with it.
        assert dl.read(DeferredInboxActivity.build_id(far.activity_id)) is None
        assert "dropped the Announce" in caplog.text

    @pytest.mark.spec("SYNC-14-006")
    def test_full_area_does_not_hold_a_farther_announce(
        self, dl, case_with_genesis
    ):
        for index in (3, 5):
            hold_received(dl, self._held_event(index))
        farther = self._held_event(9)
        dl.save(
            ReceivedActivityRecord(
                activity_id=farther.activity_id,
                received_body=cast(str, farther.received_evidence),
            )
        )
        entry = farther.log_entry
        assert entry is not None

        assert not hold_ledger_announce(
            dl, entry, farther.activity_id, max_per_case=2
        )
        assert [h.log_index for h in held_ledger_announces(dl, CASE_URI)] == [
            3,
            5,
        ]
        assert (
            dl.read(DeferredInboxActivity.build_id(farther.activity_id))
            is None
        )

    @pytest.mark.spec("SYNC-14-001")
    def test_a_second_announce_of_a_held_entry_is_not_held_again(
        self, dl, case_with_genesis
    ):
        """A redelivered entry under another Announce id leaves the first
        Announce held, alone."""
        entry = _make_entry(CASE_URI, 4, "4" * 64)
        first, second = _announce_event(entry), _announce_event(entry)
        hold_received(dl, first)
        hold_received(dl, second)

        assert [
            h.activity_id for h in held_ledger_announces(dl, CASE_URI)
        ] == [first.activity_id]
        assert (
            dl.read(DeferredInboxActivity.build_id(second.activity_id)) is None
        )

    @pytest.mark.spec("SYNC-14-001")
    def test_a_fork_replaces_the_held_announce(self, dl, case_with_genesis):
        """A different entry under the same predecessor replaces the held
        Announce, body included."""
        entry = _make_entry(CASE_URI, 4, "4" * 64)
        fork = HashChainLedgerRecord(
            case_id=CASE_URI,
            log_index=4,
            object_id="https://example.org/activities/fork",
            semantic_type="test_event",
            payload_snapshot={"fork": True},
            prev_log_hash="4" * 64,
        ).to_ledger_entry()
        first, forked = _announce_event(entry), _announce_event(fork)
        hold_received(dl, first)
        hold_received(dl, forked)

        assert [
            h.activity_id for h in held_ledger_announces(dl, CASE_URI)
        ] == [forked.activity_id]
        assert (
            dl.read(DeferredInboxActivity.build_id(first.activity_id)) is None
        )

    @pytest.mark.spec("CLP-10-017")
    def test_holding_an_unarchived_announce_is_a_wiring_error(self, dl):
        """Intake archives every received activity first; holding one it did
        not archive would hold nothing."""
        entry = _make_entry(CASE_URI, 4, "4" * 64)
        event = _announce_event(entry)

        with pytest.raises(VultronWiringError, match="not archived"):
            hold_ledger_announce(dl, entry, event.activity_id)
        assert held_depth(dl, CASE_URI) == 0


class TestPreGenesisAnnounceBuffering:
    """A pre-genesis ``Announce(CaseLedgerEntry)`` — one that arrives before the
    ``VulnerabilityCase`` is seeded, so the per-case genesis hash is unavailable
    (CLP-08-005) — MUST be held rather than permanently dropped, and MUST
    drain into the local ledger once the case is seeded (issue #2186, #2180,
    SYNC-15-004, SYNC-15-005).

    This closes the pre-genesis race without relying on the reject/replay
    round-trip: the forward-gap hold (SYNC-14) only covers entries for a case
    whose genesis anchor is already known, so a distinct pre-genesis hold is
    required.
    """

    @pytest.mark.spec("SYNC-15-001")
    @pytest.mark.spec("SYNC-15-004")
    def test_pre_genesis_entry_is_held_not_dropped(self, dl):
        """With no case seeded, the Announce is held (not dropped) and a
        Reject is still sent as the loss backstop (SYNC-15-001)."""
        case = _make_case()  # deliberately NOT saved — pre-genesis window
        entry = _make_entry(CASE_URI, 0, case.genesis_hash)
        sync_port = SyncActivityAdapter(dl)

        AnnounceLedgerEntryReceivedUseCase(
            dl, _announce_event(entry), sync_port=sync_port
        ).execute()

        # Not stored — cannot validate genesis (SYNC-15-002).
        assert dl.read(entry.id_) is None
        # Held, not dropped — the #2186 fix.
        assert held_depth(dl, CASE_URI) == 1
        # Reject still queued as the backstop (SYNC-15-001).
        assert len(dl.outbox_list()) == 1

    @pytest.mark.spec("SYNC-03-006")
    @pytest.mark.spec("SYNC-15-004")
    def test_pre_genesis_entry_with_bad_hash_is_not_held(self, dl):
        """A tampered entry for an unseeded case is refused, not held."""
        case = _make_case()  # deliberately NOT saved — pre-genesis window
        entry = _make_entry(CASE_URI, 0, case.genesis_hash).model_copy(
            update={"payload_snapshot": {"tampered": True}}
        )

        result = AnnounceLedgerEntryReceivedUseCase(
            dl,
            _announce_event(entry),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert dl.read(entry.id_) is None
        assert held_depth(dl, CASE_URI) == 0
        # Refused without a Reject (SYNC-03-006), and without a fault: this
        # store knows no CASE_MANAGER to verify the sender against
        # (SYNC-03-007, ASK-07-002).
        assert dl.outbox_list() == []


class TestAnnounceLedgerEntryDisposition:
    """Each ``Announce(CaseLedgerEntry)`` exit reports what happened (#2255).

    APPLIED reads as "processed" in the InboxOutcome.  A duplicate or a
    self-echo is a no-op (SKIPPED), a held entry is DEFERRED, and an entry
    this replica answered with a ``Reject`` is REFUSED (HP-01-003).
    """

    _IMPOSTER_URI = "https://example.org/actors/imposter"

    def _make_event(
        self, entry: CaseLedgerEntry, actor: str = ACTOR_URI
    ) -> AnnounceLogEntryReceivedEvent:
        return _announce_event(entry, actor=actor)

    def _seed_case_managed_by(self, dl, manager_id: str) -> None:
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        manager = as_CaseParticipant(
            id_=f"{CASE_URI}/participants/case-manager",
            context=CASE_URI,
            attributed_to=manager_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(manager)
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, id_=CASE_URI, name="Disposition Case"
        )
        case.case_participants.append(manager.id_)
        case.actor_participant_index[manager_id] = manager.id_
        dl.create(case)

    def _run(self, dl, event, replay=None):
        return AnnounceLedgerEntryReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
            inbox_replay=replay,
        ).execute()

    @pytest.mark.spec("HP-01-003")
    def test_missing_log_entry_is_refused(self, dl):
        event = AnnounceLogEntryReceivedEvent(
            activity_id="urn:uuid:no-entry",
            actor_id=ACTOR_URI,
            receiving_actor_id=RECEIVER_URI,
        )

        result = self._run(dl, event)

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    def test_chain_extending_entry_is_applied(self, dl, genesis_entry):
        result = self._run(dl, self._make_event(genesis_entry))

        assert result.disposition == HandlerDisposition.APPLIED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("SYNC-03-003")
    def test_already_stored_entry_is_skipped(self, dl, genesis_entry):
        dl.save(genesis_entry)

        result = self._run(dl, self._make_event(genesis_entry))

        assert result.disposition == HandlerDisposition.SKIPPED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("SYNC-03-001")
    def test_hash_mismatch_is_refused(self, dl, first_entry):
        """A stale or forked entry is answered with Reject, so it is REFUSED."""
        dl.save(first_entry)
        bad_entry = _make_entry(CASE_URI, 1, "badbadbadbadbad0" * 4)

        result = self._run(dl, self._make_event(bad_entry))

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "SYNC-03-001" in result.reason
        assert held_depth(dl, CASE_URI) == 0

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("SYNC-03-006")
    def test_entry_failing_its_own_hash_is_refused(self, dl, genesis_entry):
        """A tampered entry is REFUSED with the integrity reason, not stored."""
        tampered = genesis_entry.model_copy(
            update={"payload_snapshot": {"tampered": True}}
        )

        result = self._run(dl, self._make_event(tampered))

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "SYNC-03-006" in result.reason
        assert dl.read(tampered.id_) is None

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("SYNC-03-006")
    def test_tampered_copy_of_stored_entry_is_refused_not_skipped(
        self, dl, genesis_entry
    ):
        """The already-stored shortcut does not hide a failed hash check."""
        dl.save(genesis_entry)
        tampered = genesis_entry.model_copy(
            update={"payload_snapshot": {"tampered": True}}
        )

        result = self._run(dl, self._make_event(tampered))

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "SYNC-03-006" in result.reason
        stored = dl.read(genesis_entry.id_)
        assert stored is not None
        assert stored.payload_snapshot == genesis_entry.payload_snapshot

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("SYNC-14-001")
    def test_forward_gap_entry_is_deferred(self, dl, case_with_genesis):
        e0 = _make_entry(CASE_URI, 0, case_with_genesis.genesis_hash)
        e1 = _make_entry(CASE_URI, 1, e0.entry_hash)

        result = self._run(dl, self._make_event(e1))

        assert result.disposition == HandlerDisposition.DEFERRED
        assert held_depth(dl, CASE_URI) == 1

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("SYNC-14-003")
    def test_entry_that_closes_a_gap_is_applied(self, dl, case_with_genesis):
        e0 = _make_entry(CASE_URI, 0, case_with_genesis.genesis_hash)
        e1 = _make_entry(CASE_URI, 1, e0.entry_hash)
        replay = RecordingInboxReplay()
        self._run(dl, self._make_event(e1), replay)

        result = self._run(dl, self._make_event(e0), replay)

        assert result.disposition == HandlerDisposition.APPLIED
        # e1's Announce is its own delivery, replayed (SYNC-14-009).
        assert dl.read(e1.id_) is None
        deliver_replayed(
            replay, dl, RECEIVER_URI, lambda ev: self._run(dl, ev, replay)
        )
        assert dl.read(e1.id_) is not None

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("SYNC-15-004")
    def test_pre_genesis_entry_is_deferred(self, dl):
        case = _make_case()  # deliberately NOT saved — pre-genesis window
        entry = _make_entry(CASE_URI, 0, case.genesis_hash)

        result = self._run(dl, self._make_event(entry))

        assert result.disposition == HandlerDisposition.DEFERRED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("SYNC-15-001")
    @pytest.mark.spec("SYNC-14-006")
    def test_unheld_pre_genesis_entry_is_refused(self, dl, monkeypatch):
        """With the holding area full and the entry the farthest ahead, the
        entry is only answered with Reject."""
        from vultron.core.services import held_ledger_announces as held_mod

        monkeypatch.setattr(held_mod, "DEFAULT_HELD_LEDGER_ANNOUNCES_MAX", 0)
        case = _make_case()
        entry = _make_entry(CASE_URI, 0, case.genesis_hash)

        result = self._run(dl, self._make_event(entry))

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("SYNC-13-006")
    def test_announce_from_non_case_actor_is_refused(self, dl, first_entry):
        self._seed_case_managed_by(dl, ACTOR_URI)

        result = self._run(
            dl, self._make_event(first_entry, self._IMPOSTER_URI)
        )

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None
        assert self._IMPOSTER_URI in result.reason
        assert "SYNC-13-006" in result.reason
        assert dl.read(first_entry.id_) is None

    @pytest.mark.spec("HP-01-003")
    def test_case_manager_self_echo_is_skipped(self, dl, first_entry):
        """The CaseActor's own fan-out echoing back is a delivery receipt."""
        self._seed_case_managed_by(dl, RECEIVER_URI)

        result = self._run(dl, self._make_event(first_entry, RECEIVER_URI))

        assert result.disposition == HandlerDisposition.SKIPPED

    @pytest.mark.spec("HP-01-003")
    def test_case_manager_refuses_announce_from_another_actor(
        self, dl, first_entry
    ):
        self._seed_case_managed_by(dl, RECEIVER_URI)

        result = self._run(
            dl, self._make_event(first_entry, self._IMPOSTER_URI)
        )

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None
        assert self._IMPOSTER_URI in result.reason
        assert "is not the CASE_MANAGER" in result.reason


class TestUnaddressedAnnounceActsOnNothing:
    """A copy the addressee door guard refuses replays nothing and leaves
    the receiver's pending assertion pending (HP-01-005, #4832)."""

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.spec("HP-01-012")
    def test_refused_copy_replays_nothing_and_clears_no_assertion(
        self, dl, case_with_genesis
    ):
        """The same delivery addressed to the receiver commits e0 and replays
        e1 (``test_commit_replays_the_held_announce_without_running_it``);
        unaddressed, the door refuses it before either happens."""
        genesis = _make_entry(CASE_URI, 0, case_with_genesis.genesis_hash)
        successor = _make_entry(CASE_URI, 1, genesis.entry_hash)
        # The successor's Announce waits for the genesis entry the copy
        # announces, so an admitted copy would replay it.
        hold_received(dl, _announce_event(successor))
        pending = PendingAssertionStore()
        pending.add(CASE_URI, genesis.semantic_type, genesis.log_object_id)
        replay = RecordingInboxReplay()
        sync_port = MagicMock(spec=SyncActivityPort)
        copy = _announce_event(
            genesis, to="https://example.org/actors/someone-else"
        )

        result = AnnounceLedgerEntryReceivedUseCase(
            dl,
            copy,
            sync_port=sync_port,
            pending_assertions=pending,
            inbox_replay=replay,
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert replay.replayed == []
        assert "unaddressed copy is refused (HP-01-005)" in (
            result.reason or ""
        )
        assert held_depth(dl, CASE_URI) == 1
        assert pending.is_suppressed(
            CASE_URI, genesis.semantic_type, genesis.log_object_id
        )
        assert sync_port.mock_calls == []
        assert dl.list_objects("CaseLedgerEntry") == []
