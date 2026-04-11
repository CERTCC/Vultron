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
"""Tests for SYNC-2 received use case (AnnounceLogEntryReceivedUseCase)."""

import pytest

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.models.case_log import GENESIS_HASH
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.events import MessageSemantics
from vultron.core.use_cases.received.sync import (
    AnnounceLogEntryReceivedUseCase,
    _reconstruct_tail_hash,
)
from vultron.wire.as2.extractor import extract_intent
from vultron.wire.as2.vocab.activities.sync import AnnounceLogEntryActivity

ACTOR_URI = "https://example.org/actors/case-actor"
CASE_URI = "https://example.org/cases/case1"


def _make_entry(
    case_id: str, log_index: int, prev_hash: str
) -> VultronCaseLogEntry:
    return VultronCaseLogEntry(
        case_id=case_id,
        log_index=log_index,
        log_object_id="https://example.org/activities/act1",
        event_type="test_event",
        payload_snapshot={"key": "value"},
        prev_log_hash=prev_hash,
    )


@pytest.fixture
def dl() -> TinyDbDataLayer:
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def first_entry() -> VultronCaseLogEntry:
    return _make_entry(CASE_URI, 0, GENESIS_HASH)


class TestReconstructTailHash:
    def test_empty_log_returns_genesis(self, dl):
        tail_hash, tail_index = _reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == GENESIS_HASH
        assert tail_index == -1

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
        other = _make_entry("https://example.org/cases/other", 0, GENESIS_HASH)
        dl.save(other)
        tail_hash, tail_index = _reconstruct_tail_hash(CASE_URI, dl)
        assert tail_hash == first_entry.entry_hash
        assert tail_index == 0


class TestAnnounceLogEntryReceivedUseCase:
    def _make_event(self, entry: VultronCaseLogEntry):
        activity = AnnounceLogEntryActivity(
            actor=ACTOR_URI,
            object_=entry,  # type: ignore[arg-type]
        )
        return extract_intent(activity)

    def test_accepts_valid_first_entry(self, dl, first_entry):
        event = self._make_event(first_entry)
        assert event.semantic_type == MessageSemantics.ANNOUNCE_CASE_LOG_ENTRY

        uc = AnnounceLogEntryReceivedUseCase(dl, event)
        uc.execute()

        stored = dl.read(first_entry.id_)
        assert stored is not None

    def test_rejects_entry_with_wrong_prev_hash(self, dl, first_entry):
        """Entry whose prev_log_hash does not match local tail is discarded."""
        bad_entry = _make_entry(CASE_URI, 0, "deadbeef" * 8)
        event = self._make_event(bad_entry)
        uc = AnnounceLogEntryReceivedUseCase(dl, event)
        uc.execute()
        assert dl.read(bad_entry.id_) is None

    def test_idempotent_second_accept(self, dl, first_entry):
        """Calling execute twice with the same entry stores it only once."""
        dl.save(first_entry)  # pre-store
        event = self._make_event(first_entry)
        uc = AnnounceLogEntryReceivedUseCase(dl, event)
        uc.execute()  # should skip silently
        # Still exactly one entry for this case
        raw = dl.by_type("CaseLogEntry")
        case_entries = [
            v for v in raw.values() if v.get("case_id") == CASE_URI
        ]
        assert len(case_entries) == 1

    def test_sequential_chain(self, dl, first_entry):
        """Accept two sequential entries; chain is maintained."""
        event0 = self._make_event(first_entry)
        AnnounceLogEntryReceivedUseCase(dl, event0).execute()

        second = _make_entry(CASE_URI, 1, first_entry.entry_hash)
        event1 = self._make_event(second)
        AnnounceLogEntryReceivedUseCase(dl, event1).execute()

        assert dl.read(first_entry.id_) is not None
        assert dl.read(second.id_) is not None

    def test_semantic_type_is_correct(self, dl, first_entry):
        event = self._make_event(first_entry)
        assert event.semantic_type == MessageSemantics.ANNOUNCE_CASE_LOG_ENTRY
        assert event.log_entry is not None
        assert event.log_entry.case_id == CASE_URI
