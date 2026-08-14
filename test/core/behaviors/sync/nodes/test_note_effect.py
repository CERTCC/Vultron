#!/usr/bin/env python
"""Tests for ApplyNoteFromLedgerNode.

Covers add_note_to_case ledger event application to the local case replica.
Per SYNC-02-002, ADR-0022.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from vultron.core.behaviors.sync.nodes.note_effect import (
    ApplyNoteFromLedgerNode,
)
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

NOTE_ID = "https://example.org/notes/note-01"


def _make_note_entry(note_id: str = NOTE_ID):
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/add-note",
            event_type="add_note_to_case",
            payload_snapshot={"object": {"id": note_id}},
            prev_log_hash="0" * 64,
        )
    )


@pytest.fixture
def case_with_notes(datalayer):
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=OWNER_ACTOR_ID
    )
    datalayer.save(case)
    return case


def test_apply_note_adds_to_case(
    bridge, datalayer, case_actor, case_with_notes
):
    """Note ID is appended to the case's notes list."""
    assert case_with_notes is not None
    entry = _make_note_entry(NOTE_ID)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyNoteFromLedgerNode(name="ApplyNote"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
    updated = datalayer.read(CASE_ID)
    assert updated is not None
    note_ids = [
        n if isinstance(n, str) else getattr(n, "id_", str(n))
        for n in updated.notes
    ]
    assert NOTE_ID in note_ids


def test_apply_note_idempotent(bridge, datalayer, case_actor, case_with_notes):
    """Applying the same note twice does not duplicate it."""
    assert case_with_notes is not None
    entry = _make_note_entry(NOTE_ID)
    event = _make_event(entry, actor_id=case_actor.id_)

    for _ in range(2):
        result = bridge.execute_with_setup(
            tree=ApplyNoteFromLedgerNode(name="ApplyNote"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )
        assert result.status == Status.SUCCESS

    updated = datalayer.read(CASE_ID)
    note_ids = [
        n if isinstance(n, str) else getattr(n, "id_", str(n))
        for n in updated.notes
    ]
    assert note_ids.count(NOTE_ID) == 1


def test_apply_note_skips_missing_case(bridge, case_actor):
    """Node returns SUCCESS when the case is not in the local DataLayer."""
    entry = _make_note_entry(NOTE_ID)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyNoteFromLedgerNode(name="ApplyNote"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
