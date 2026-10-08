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
"""Tests for LedgerReconciliation: RejectLedgerEntryReceivedUseCase and replay trigger.

Spec: SYNC-03-001, SYNC-03-002.
"""

from typing import cast
from unittest.mock import MagicMock

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.received.sync import (
    RejectLedgerEntryReceivedUseCase,
)
from vultron.core.use_cases.triggers.sync import replay_missing_entries_trigger
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import reject_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

CASE_ACTOR_URI = "https://example.org/actors/case-actor"
PARTICIPANT_URI = "https://example.org/actors/participant-1"
CASE_URI = "https://example.org/cases/case1"


def _to_persistable_entry(
    chain_entry: HashChainLedgerRecord,
) -> CaseLedgerEntry:
    """Test helper: convert a HashChainLedgerRecord to a CaseLedgerEntry."""
    return CaseLedgerEntry(
        case_id=chain_entry.case_id,
        log_index=chain_entry.log_index,
        term=chain_entry.term,
        log_object_id=chain_entry.object_id,
        event_type=chain_entry.event_type,
        payload_snapshot=dict(chain_entry.payload_snapshot),
        prev_log_hash=chain_entry.prev_log_hash,
        entry_hash=chain_entry.entry_hash,
    )


def _make_entry(
    case_id: str, log_index: int, prev_hash: str
) -> CaseLedgerEntry:
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
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


@pytest.fixture
def entry0() -> CaseLedgerEntry:
    _ZERO_HASH: str = "0" * 64
    return _make_entry(CASE_URI, 0, _ZERO_HASH)


@pytest.fixture
def entry1(entry0) -> CaseLedgerEntry:
    return _make_entry(CASE_URI, 1, entry0.entry_hash)


def _make_reject_event(
    entry: CaseLedgerEntry, last_accepted_hash: str, actor: str
) -> RejectLogEntryReceivedEvent:
    """Build a RejectLogEntryReceivedEvent via the extractor."""
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = reject_log_entry_activity(
        wire_entry,
        context=last_accepted_hash,
        actor=actor,
        to=[CASE_ACTOR_URI],
    )
    return cast(RejectLogEntryReceivedEvent, extract_event(activity))


class TestRejectLogEntryPattern:
    """Pattern matching for REJECT_CASE_LEDGER_ENTRY (SYNC-03-001)."""

    @pytest.mark.spec("SYNC-03-001")
    def test_pattern_matches_reject_with_case_ledger_entry(self, entry0):
        wire_entry = WireCaseLedgerEntry.model_validate(
            entry0.model_dump(mode="json")
        )
        activity = reject_log_entry_activity(
            wire_entry, context="a" * 64, actor=PARTICIPANT_URI
        )
        event = extract_event(activity)
        assert event.semantic_type == MessageSemantics.REJECT_CASE_LEDGER_ENTRY

    @pytest.mark.spec("SYNC-03-001")
    def test_rejected_entry_accessible(self, entry0):
        event = _make_reject_event(entry0, "a" * 64, PARTICIPANT_URI)
        assert event.semantic_type == MessageSemantics.REJECT_CASE_LEDGER_ENTRY
        from vultron.core.models.events.sync import RejectLogEntryReceivedEvent

        assert isinstance(event, RejectLogEntryReceivedEvent)
        assert event.rejected_entry is not None
        assert event.rejected_entry.case_id == CASE_URI

    @pytest.mark.spec("SYNC-03-001")
    @pytest.mark.spec("SYNC-03-004")
    def test_last_accepted_hash_from_context(self, entry0):
        """last_accepted_hash is extracted from the context field."""
        from vultron.core.models.events.sync import RejectLogEntryReceivedEvent

        event = _make_reject_event(entry0, entry0.entry_hash, PARTICIPANT_URI)
        assert isinstance(event, RejectLogEntryReceivedEvent)
        assert event.last_accepted_hash == entry0.entry_hash

    @pytest.mark.spec("CLP-08-005")
    def test_last_accepted_hash_defaults_to_empty_string(self, entry0):
        """When no context is set, last_accepted_hash falls back to '' (CLP-08-005)."""
        from vultron.core.models.events.sync import RejectLogEntryReceivedEvent

        wire_entry = WireCaseLedgerEntry.model_validate(
            entry0.model_dump(mode="json")
        )
        activity = reject_log_entry_activity(wire_entry, actor=PARTICIPANT_URI)
        event = extract_event(activity)
        assert isinstance(event, RejectLogEntryReceivedEvent)
        assert event.last_accepted_hash == ""


class TestReplayMissingEntriesTrigger:
    """replay_missing_entries_trigger queues Announce activities (SYNC-03-002)."""

    @pytest.mark.spec("SYNC-03-002")
    def test_replays_all_when_from_genesis(self, dl, entry0, entry1):
        dl.save(entry0)
        dl.save(entry1)

        sync_port = MagicMock(spec=SyncActivityPort)
        replayed = replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash="",
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
            sync_port=sync_port,
        )
        assert replayed == 2

    @pytest.mark.spec("SYNC-03-002")
    def test_replays_only_missing_entries(self, dl, entry0, entry1):
        dl.save(entry0)
        dl.save(entry1)

        sync_port = MagicMock(spec=SyncActivityPort)
        replayed = replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash=entry0.entry_hash,
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
            sync_port=sync_port,
        )
        assert replayed == 1

    @pytest.mark.spec("SYNC-03-002")
    def test_returns_zero_when_up_to_date(self, dl, entry0):
        dl.save(entry0)

        sync_port = MagicMock(spec=SyncActivityPort)
        replayed = replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash=entry0.entry_hash,
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
            sync_port=sync_port,
        )
        assert replayed == 0

    @pytest.mark.spec("SYNC-03-002")
    def test_returns_zero_when_no_entries(self, dl):
        sync_port = MagicMock(spec=SyncActivityPort)
        replayed = replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash="",
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
            sync_port=sync_port,
        )
        assert replayed == 0

    @pytest.mark.spec("SYNC-02-001")
    @pytest.mark.spec("SYNC-02-003")
    def test_announces_target_peer(self, dl, entry0):
        dl.save(entry0)
        sync_port = SyncActivityAdapter(dl)
        replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash="",
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
            sync_port=sync_port,
        )
        # Check the announce was saved to the DataLayer (outbox queue
        # goes to a per-actor table not accessible via the global dl.outbox_list())
        announces = dl.by_type("Announce")
        assert len(announces) == 1
        announce = next(iter(announces.values()))
        assert PARTICIPANT_URI in (announce.get("to") or [])


def _seed_case(dl: SqliteDataLayer) -> None:
    """Store the case, CASE_ACTOR_URI its CASE_MANAGER, in *dl*.

    PARTICIPANT_URI, the Reject's sender, is a joined participant, so the
    replay's active-participant gate admits it (CM-10-004).
    """
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
        attributed_to=CASE_ACTOR_URI,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(manager)
    peer = as_CaseParticipant(
        id_=f"{CASE_URI}/participants/peer",
        context=CASE_URI,
        attributed_to=PARTICIPANT_URI,
    )
    dl.create(peer)
    case = as_VulnerabilityCase(id_=CASE_URI, name="Reject Sync Case")
    case.case_participants.extend([manager.id_, peer.id_])
    case.actor_participant_index[CASE_ACTOR_URI] = manager.id_
    case.actor_participant_index[PARTICIPANT_URI] = peer.id_
    dl.create(case)


@pytest.fixture
def manager_dl() -> SqliteDataLayer:
    """The CASE_MANAGER's own store: only it answers a Reject (SYNC-03-005)."""
    return SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_ACTOR_URI)


class TestRejectLedgerEntryReceivedUseCase:
    """RejectLedgerEntryReceivedUseCase updates state and triggers replay."""

    def _make_event(
        self, entry: CaseLedgerEntry, last_accepted_hash: str
    ) -> RejectLogEntryReceivedEvent:
        return _make_reject_event(entry, last_accepted_hash, PARTICIPANT_URI)

    @pytest.mark.spec("SYNC-04-001")
    def test_updates_replication_state(self, manager_dl, entry0, entry1):
        """Receiving a Reject updates ReplicationState (SYNC-04-001)."""
        manager_dl.save(entry0)
        manager_dl.save(entry1)
        _seed_case(manager_dl)

        event = self._make_event(entry1, entry0.entry_hash)
        # SendMissingEntries raises VultronWiringError without a sync port
        # (#3776), so inject one as the replay test below does.
        uc = RejectLedgerEntryReceivedUseCase(
            manager_dl, event, sync_port=SyncActivityAdapter(manager_dl)
        )
        uc.execute()

        state_id = VultronReplicationState(
            case_id=CASE_URI, peer_id=PARTICIPANT_URI
        ).id_
        stored = manager_dl.read(state_id)
        assert stored is not None
        assert (
            getattr(stored, "last_acknowledged_hash", None)
            == entry0.entry_hash
        )

    @pytest.mark.spec("SYNC-03-005")
    @pytest.mark.spec("HP-01-005")
    def test_refused_at_an_actor_that_is_not_the_case_manager(
        self, dl, entry0, entry1
    ):
        """Only the CASE_MANAGER answers a Reject; elsewhere it is REFUSED.

        ``dl`` belongs to an actor other than CASE_ACTOR_URI: it holds a copy
        of the case and its ledger, but answering would replay entries and
        record replication state in another actor's name.
        """
        dl.save(entry0)
        dl.save(entry1)
        _seed_case(dl)
        sync_port = MagicMock(spec=SyncActivityPort)

        result = RejectLedgerEntryReceivedUseCase(
            dl,
            self._make_event(entry1, entry0.entry_hash),
            sync_port=sync_port,
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert "not the CASE_MANAGER" in (result.reason or "")
        sync_port.send_announce_log_entry.assert_not_called()
        state_id = VultronReplicationState(
            case_id=CASE_URI, peer_id=PARTICIPANT_URI
        ).id_
        assert dl.read(state_id) is None

    @pytest.mark.spec("SYNC-03-001")
    def test_ignores_reject_with_no_entry(self, dl):
        """Reject with no object_ is safely ignored."""
        from vultron.core.models.events.base import MessageSemantics
        from vultron.core.models.events.sync import RejectLogEntryReceivedEvent

        event = RejectLogEntryReceivedEvent(
            semantic_type=MessageSemantics.REJECT_CASE_LEDGER_ENTRY,
            activity_id="https://example.org/activities/rej1",
            actor_id=PARTICIPANT_URI,
        )
        uc = RejectLedgerEntryReceivedUseCase(dl, event)
        result = uc.execute()  # should not raise

        # HP-01-003: a Reject naming no entry is malformed, not a no-op.
        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("SYNC-03-002")
    @pytest.mark.spec("CM-02-011")
    def test_replay_triggered_when_the_case_manager_is_resolvable(
        self, manager_dl, entry0, entry1
    ):
        """Missing entries are replayed once the case's CASE_MANAGER resolves.

        The sender address comes from the role (ADR-0088, ARCH-24-004). This
        used to be satisfied by an ``as_CaseActor`` whose ``context`` was the
        case id — a hosting signal that no longer answers.
        """
        manager_dl.save(entry0)
        manager_dl.save(entry1)
        _seed_case(manager_dl)

        # Participant says they only have up to entry0
        event = self._make_event(entry1, entry0.entry_hash)
        sync_port = SyncActivityAdapter(manager_dl)
        result = RejectLedgerEntryReceivedUseCase(
            manager_dl, event, sync_port=sync_port
        ).execute()
        assert result.disposition == HandlerDisposition.APPLIED

        # Should have queued one replay Announce (for entry1).
        # announce saved to DataLayer; outbox queue uses actor-scoped table.
        announces = manager_dl.by_type("Announce")
        assert len(announces) == 1
        # Only the CASE_MANAGER answers a Reject (SYNC-03-005), so the
        # executing actor and the resolved role holder are one id here.  The
        # discrimination between "the role was resolved" and "the executing
        # actor was echoed" lives in the FindCaseActorNode unit tests
        # (test/core/behaviors/sync/nodes/test_replay.py).
        queued = list(
            announces.values() if isinstance(announces, dict) else announces
        )
        record = queued[0]
        sender = (
            record.get("actor")
            if isinstance(record, dict)
            else getattr(record, "actor", None)
        )
        assert _as_id(sender) == CASE_ACTOR_URI
