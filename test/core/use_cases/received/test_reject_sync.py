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
"""Tests for SYNC-3: RejectLogEntryReceivedUseCase and replay trigger.

Spec: SYNC-03-001, SYNC-03-002, SYNC-04-001, SYNC-04-002.
"""

import pytest

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.models.case_log import GENESIS_HASH, CaseLogEntry
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.use_cases.triggers.sync import _to_persistable_entry
from vultron.core.models.events import MessageSemantics
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.use_cases.received.sync import (
    RejectLogEntryReceivedUseCase,
    _update_replication_state,
)
from vultron.core.use_cases.triggers.sync import replay_missing_entries_trigger
from typing import cast

from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.wire.as2.extractor import extract_intent
from vultron.wire.as2.vocab.activities.sync import RejectLogEntryActivity

CASE_ACTOR_URI = "https://example.org/actors/case-actor"
PARTICIPANT_URI = "https://example.org/actors/participant-1"
CASE_URI = "https://example.org/cases/case1"


def _make_entry(
    case_id: str, log_index: int, prev_hash: str
) -> VultronCaseLogEntry:
    chain = CaseLogEntry(
        case_id=case_id,
        log_index=log_index,
        object_id="https://example.org/activities/act1",
        event_type="test_event",
        payload_snapshot={"key": "value"},
        prev_log_hash=prev_hash,
    )
    return _to_persistable_entry(chain)


@pytest.fixture
def dl() -> TinyDbDataLayer:
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def entry0() -> VultronCaseLogEntry:
    return _make_entry(CASE_URI, 0, GENESIS_HASH)


@pytest.fixture
def entry1(entry0) -> VultronCaseLogEntry:
    return _make_entry(CASE_URI, 1, entry0.entry_hash)


def _make_reject_event(
    entry: VultronCaseLogEntry, last_accepted_hash: str, actor: str
) -> RejectLogEntryReceivedEvent:
    """Build a RejectLogEntryReceivedEvent via the extractor."""
    activity = RejectLogEntryActivity(
        actor=actor,
        object_=entry,  # type: ignore[arg-type]
        to=[CASE_ACTOR_URI],
        context=last_accepted_hash,
    )
    return cast(RejectLogEntryReceivedEvent, extract_intent(activity))


class TestRejectLogEntryPattern:
    """Pattern matching for REJECT_CASE_LOG_ENTRY (SYNC-03-001)."""

    def test_pattern_matches_reject_with_case_log_entry(self, entry0):
        activity = RejectLogEntryActivity(
            actor=PARTICIPANT_URI,
            object_=entry0,  # type: ignore[arg-type]
            context=GENESIS_HASH,
        )
        event = extract_intent(activity)
        assert event.semantic_type == MessageSemantics.REJECT_CASE_LOG_ENTRY

    def test_rejected_entry_accessible(self, entry0):
        event = _make_reject_event(entry0, GENESIS_HASH, PARTICIPANT_URI)
        assert event.semantic_type == MessageSemantics.REJECT_CASE_LOG_ENTRY
        from vultron.core.models.events.sync import RejectLogEntryReceivedEvent

        assert isinstance(event, RejectLogEntryReceivedEvent)
        assert event.rejected_entry is not None
        assert event.rejected_entry.case_id == CASE_URI

    def test_last_accepted_hash_from_context(self, entry0):
        """last_accepted_hash is extracted from the context field."""
        from vultron.core.models.events.sync import RejectLogEntryReceivedEvent

        event = _make_reject_event(entry0, entry0.entry_hash, PARTICIPANT_URI)
        assert isinstance(event, RejectLogEntryReceivedEvent)
        assert event.last_accepted_hash == entry0.entry_hash

    def test_last_accepted_hash_defaults_to_genesis(self, entry0):
        """When no context is set, last_accepted_hash falls back to GENESIS_HASH."""
        from vultron.core.models.events.sync import RejectLogEntryReceivedEvent

        # Activity with no context
        activity = RejectLogEntryActivity(
            actor=PARTICIPANT_URI,
            object_=entry0,  # type: ignore[arg-type]
        )
        event = extract_intent(activity)
        assert isinstance(event, RejectLogEntryReceivedEvent)
        assert event.last_accepted_hash == GENESIS_HASH


class TestUpdateReplicationState:
    """_update_replication_state creates and updates per-peer state (SYNC-04-001)."""

    def test_creates_new_state(self, dl, entry0):
        _update_replication_state(
            CASE_URI, PARTICIPANT_URI, entry0.entry_hash, dl
        )
        state_id = VultronReplicationState(
            case_id=CASE_URI, peer_id=PARTICIPANT_URI
        ).id_
        stored = dl.read(state_id)
        assert stored is not None

    def test_stores_hash(self, dl, entry0):
        _update_replication_state(
            CASE_URI, PARTICIPANT_URI, entry0.entry_hash, dl
        )
        state_id = VultronReplicationState(
            case_id=CASE_URI, peer_id=PARTICIPANT_URI
        ).id_
        stored = dl.read(state_id)
        assert (
            getattr(stored, "last_acknowledged_hash", None)
            == entry0.entry_hash
        )

    def test_updates_existing_state(self, dl, entry0, entry1):
        _update_replication_state(
            CASE_URI, PARTICIPANT_URI, entry0.entry_hash, dl
        )
        _update_replication_state(
            CASE_URI, PARTICIPANT_URI, entry1.entry_hash, dl
        )

        state_id = VultronReplicationState(
            case_id=CASE_URI, peer_id=PARTICIPANT_URI
        ).id_
        stored = dl.read(state_id)
        # Only one record should exist (upsert, not duplicate)
        all_states = dl.by_type("ReplicationState")
        assert len(all_states) == 1
        assert (
            getattr(stored, "last_acknowledged_hash", None)
            == entry1.entry_hash
        )


class TestReplayMissingEntriesTrigger:
    """replay_missing_entries_trigger queues Announce activities (SYNC-03-002)."""

    def test_replays_all_when_from_genesis(self, dl, entry0, entry1):
        dl.save(entry0)
        dl.save(entry1)

        replayed = replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash=GENESIS_HASH,
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
        )
        assert replayed == 2

    def test_replays_only_missing_entries(self, dl, entry0, entry1):
        dl.save(entry0)
        dl.save(entry1)

        replayed = replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash=entry0.entry_hash,
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
        )
        assert replayed == 1

    def test_returns_zero_when_up_to_date(self, dl, entry0):
        dl.save(entry0)

        replayed = replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash=entry0.entry_hash,
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
        )
        assert replayed == 0

    def test_returns_zero_when_no_entries(self, dl):
        replayed = replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash=GENESIS_HASH,
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
        )
        assert replayed == 0

    def test_announces_target_peer(self, dl, entry0):
        dl.save(entry0)
        replay_missing_entries_trigger(
            case_id=CASE_URI,
            peer_id=PARTICIPANT_URI,
            from_hash=GENESIS_HASH,
            case_actor_id=CASE_ACTOR_URI,
            dl=dl,
        )
        # Check the announce was saved to the DataLayer (outbox queue
        # goes to a per-actor table not accessible via the global dl.outbox_list())
        announces = dl.by_type("Announce")
        assert len(announces) == 1
        announce = next(iter(announces.values()))
        assert PARTICIPANT_URI in (announce.get("to") or [])


class TestRejectLogEntryReceivedUseCase:
    """RejectLogEntryReceivedUseCase updates state and triggers replay."""

    def _make_event(
        self, entry: VultronCaseLogEntry, last_accepted_hash: str
    ) -> RejectLogEntryReceivedEvent:
        return _make_reject_event(entry, last_accepted_hash, PARTICIPANT_URI)

    def test_updates_replication_state(self, dl, entry0, entry1):
        """Receiving a Reject updates ReplicationState (SYNC-04-001)."""
        dl.save(entry0)
        dl.save(entry1)

        event = self._make_event(entry1, entry0.entry_hash)
        uc = RejectLogEntryReceivedUseCase(dl, event)
        uc.execute()

        state_id = VultronReplicationState(
            case_id=CASE_URI, peer_id=PARTICIPANT_URI
        ).id_
        stored = dl.read(state_id)
        assert stored is not None
        assert (
            getattr(stored, "last_acknowledged_hash", None)
            == entry0.entry_hash
        )

    def test_ignores_reject_with_no_entry(self, dl):
        """Reject with no object_ is safely ignored."""
        from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
        from vultron.core.models.events.base import MessageSemantics

        event = RejectLogEntryReceivedEvent(
            semantic_type=MessageSemantics.REJECT_CASE_LOG_ENTRY,
            activity_id="https://example.org/activities/rej1",
            actor_id=PARTICIPANT_URI,
        )
        uc = RejectLogEntryReceivedUseCase(dl, event)
        uc.execute()  # should not raise

    def test_replay_triggered_when_case_actor_found(self, dl, entry0, entry1):
        """When a CaseActor (Service) exists for the case, missing entries are replayed."""
        from vultron.wire.as2.vocab.objects.case_actor import CaseActor

        # Save both entries
        dl.save(entry0)
        dl.save(entry1)

        # Register a CaseActor associated with the case
        case_actor = CaseActor(
            id_=CASE_ACTOR_URI,
            context=CASE_URI,
        )
        dl.save(case_actor)

        # Participant says they only have up to entry0
        event = self._make_event(entry1, entry0.entry_hash)
        RejectLogEntryReceivedUseCase(dl, event).execute()

        # Should have queued one replay Announce (for entry1).
        # announce saved to DataLayer; outbox queue uses actor-scoped table.
        announces = dl.by_type("Announce")
        assert len(announces) == 1
