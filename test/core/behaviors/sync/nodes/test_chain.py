#!/usr/bin/env python
"""Unit tests for sync chain nodes."""

import logging

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    CASE_ID,
    _make_entry,
)
from vultron.core.behaviors.sync.nodes import (
    CreateLogEntryNode,
    PersistLogEntryNode,
)
from vultron.core.models.case_ledger import GENESIS_HASH
from vultron.core.behaviors.sync.nodes.chain import (
    _validate_canonical_entry,
)
from vultron.errors import VultronCanonicalEntryError


def _canonical_note_snapshot(actor_id: str) -> dict[str, object]:
    return {
        "type": "Add",
        "actor": actor_id,
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/note-1",
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }


def _canonical_case_announce_snapshot() -> dict[str, object]:
    return {
        "type": "Announce",
        "actor": OWNER_ACTOR_ID,
        "object": {
            "type": "VulnerabilityCase",
            "id": CASE_ID,
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }


def test_create_log_entry_node_writes_log_entry_to_blackboard(bridge):
    result = bridge.execute_with_setup(
        tree=CreateLogEntryNode(
            case_id=CASE_ID,
            object_id="https://example.org/activities/act-1",
            event_type="note_added",
            payload_snapshot=_canonical_note_snapshot(PARTICIPANT_ACTOR_ID),
            name="CreateLogEntry",
        ),
        actor_id=OWNER_ACTOR_ID,
        tail_hash=GENESIS_HASH,
        tail_index=-1,
    )

    assert result.status == Status.SUCCESS
    blackboard = py_trees.blackboard.Client(name="assert-log-entry")
    blackboard.register_key(
        key="log_entry", access=py_trees.common.Access.READ
    )
    assert blackboard.log_entry.case_id == CASE_ID
    assert blackboard.log_entry.log_index == 0


def test_validate_canonical_entry_rejects_empty_snapshot():
    with pytest.raises(VultronCanonicalEntryError):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=OWNER_ACTOR_ID,
            disposition="recorded",
            payload_snapshot={},
            event_type="note_added",
        )


@pytest.mark.parametrize(
    ("snapshot", "message"),
    [
        (
            {
                "type": "Read",
                "actor": PARTICIPANT_ACTOR_ID,
                "object": {
                    "type": "Note",
                    "id": "https://example.org/notes/note-2",
                    "context": CASE_ID,
                },
                "context": CASE_ID,
            },
            "type/object pair",
        ),
        (
            {
                "type": "Add",
                "actor": "",
                "object": {
                    "type": "Note",
                    "id": "https://example.org/notes/note-3",
                    "context": CASE_ID,
                },
                "context": CASE_ID,
            },
            "non-empty URI",
        ),
        (
            {
                "type": "Add",
                "actor": PARTICIPANT_ACTOR_ID,
                "object": "https://example.org/notes/note-4",
                "context": CASE_ID,
            },
            "inline object",
        ),
        (
            {
                "type": "Add",
                "actor": PARTICIPANT_ACTOR_ID,
                "object": {
                    "type": "Note",
                    "id": "https://example.org/notes/note-5",
                    "context": CASE_ID,
                },
                "context": "https://example.org/cases/other",
            },
            "case URI",
        ),
    ],
)
def test_create_log_entry_node_rejects_non_canonical_snapshots(
    bridge, snapshot, message
):
    result = bridge.execute_with_setup(
        tree=CreateLogEntryNode(
            case_id=CASE_ID,
            object_id="https://example.org/activities/act-invalid",
            event_type="note_added",
            payload_snapshot=snapshot,
            name="CreateLogEntry",
        ),
        actor_id=OWNER_ACTOR_ID,
        tail_hash=GENESIS_HASH,
        tail_index=-1,
    )

    assert result.status == Status.FAILURE
    assert message in result.feedback_message


def test_create_log_entry_node_allows_case_authored_announce(bridge):
    result = bridge.execute_with_setup(
        tree=CreateLogEntryNode(
            case_id=CASE_ID,
            object_id=CASE_ID,
            event_type="case_announced",
            payload_snapshot=_canonical_case_announce_snapshot(),
            name="CreateLogEntry",
        ),
        actor_id=OWNER_ACTOR_ID,
        tail_hash=GENESIS_HASH,
        tail_index=-1,
    )

    assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Actor provenance checks (CLP-07-003)
# ---------------------------------------------------------------------------

CASE_ACTOR_ID = "https://example.org/actors/case-actor"


def _note_snapshot_with_actor(actor_id: str) -> dict[str, object]:
    return {
        "type": "Add",
        "actor": actor_id,
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/note-prov",
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }


def test_validate_canonical_entry_rejects_case_actor_as_snapshot_actor_for_non_case_authored():
    """CLP-07-003: non-CaseActor-authored signatures must not have case_actor as actor."""
    with pytest.raises(
        VultronCanonicalEntryError, match="must not be the CaseActor"
    ):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=CASE_ACTOR_ID,
            case_actor_id=CASE_ACTOR_ID,
            disposition="recorded",
            payload_snapshot=_note_snapshot_with_actor(CASE_ACTOR_ID),
            event_type="note_added",
        )


def test_validate_canonical_entry_allows_participant_actor_for_non_case_authored():
    """CLP-07-003: participant actor is valid for non-CaseActor-authored signatures."""
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=OWNER_ACTOR_ID,
        case_actor_id=CASE_ACTOR_ID,
        disposition="recorded",
        payload_snapshot=_note_snapshot_with_actor(PARTICIPANT_ACTOR_ID),
        event_type="note_added",
    )


def test_validate_canonical_entry_allows_case_actor_for_case_authored_signature():
    """CLP-07-003: CaseActor is the expected actor for Announce(VulnerabilityCase)."""
    snapshot = {
        "type": "Announce",
        "actor": CASE_ACTOR_ID,
        "object": {
            "type": "VulnerabilityCase",
            "id": CASE_ID,
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=CASE_ACTOR_ID,
        case_actor_id=CASE_ACTOR_ID,
        disposition="recorded",
        payload_snapshot=snapshot,
        event_type="case_announced",
    )


def test_validate_canonical_entry_provenance_skipped_when_no_case_actor_id():
    """Provenance check is skipped when case_actor_id is not provided."""
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=OWNER_ACTOR_ID,
        case_actor_id=None,
        disposition="recorded",
        payload_snapshot=_note_snapshot_with_actor(OWNER_ACTOR_ID),
        event_type="note_added",
    )


class TestPersistLogEntryNodeLogging:
    """Verify INFO and DEBUG log emission from PersistLogEntryNode."""

    @pytest.fixture()
    def entry(self):
        return _make_entry(log_index=0, prev_hash=GENESIS_HASH)

    def test_info_log_emitted_on_persist(
        self, bridge, entry, caplog: pytest.LogCaptureFixture
    ):
        node_logger = "vultron.core.behaviors.sync.nodes.chain"
        with caplog.at_level(logging.INFO, logger=node_logger):
            result = bridge.execute_with_setup(
                tree=PersistLogEntryNode(name="PersistLogEntry"),
                actor_id=OWNER_ACTOR_ID,
                log_entry=entry,
            )
        assert result.status == Status.SUCCESS
        assert any(r.levelno == logging.INFO for r in caplog.records)

    def test_info_log_contains_event_type(
        self, bridge, entry, caplog: pytest.LogCaptureFixture
    ):
        node_logger = "vultron.core.behaviors.sync.nodes.chain"
        with caplog.at_level(logging.INFO, logger=node_logger):
            bridge.execute_with_setup(
                tree=PersistLogEntryNode(name="PersistLogEntry"),
                actor_id=OWNER_ACTOR_ID,
                log_entry=entry,
            )
        assert any(
            r.levelno == logging.INFO and "test_event" in r.message
            for r in caplog.records
        )

    def test_info_log_contains_log_index(
        self, bridge, entry, caplog: pytest.LogCaptureFixture
    ):
        node_logger = "vultron.core.behaviors.sync.nodes.chain"
        with caplog.at_level(logging.INFO, logger=node_logger):
            bridge.execute_with_setup(
                tree=PersistLogEntryNode(name="PersistLogEntry"),
                actor_id=OWNER_ACTOR_ID,
                log_entry=entry,
            )
        assert any(
            r.levelno == logging.INFO and "log_index=0" in r.message
            for r in caplog.records
        )

    def test_info_log_contains_actor_id(
        self, bridge, entry, caplog: pytest.LogCaptureFixture
    ):
        node_logger = "vultron.core.behaviors.sync.nodes.chain"
        with caplog.at_level(logging.INFO, logger=node_logger):
            bridge.execute_with_setup(
                tree=PersistLogEntryNode(name="PersistLogEntry"),
                actor_id=OWNER_ACTOR_ID,
                log_entry=entry,
            )
        assert any(
            r.levelno == logging.INFO and OWNER_ACTOR_ID in r.message
            for r in caplog.records
        )

    def test_debug_log_contains_entry_hash_prefix(
        self, bridge, entry, caplog: pytest.LogCaptureFixture
    ):
        node_logger = "vultron.core.behaviors.sync.nodes.chain"
        with caplog.at_level(logging.DEBUG, logger=node_logger):
            bridge.execute_with_setup(
                tree=PersistLogEntryNode(name="PersistLogEntry"),
                actor_id=OWNER_ACTOR_ID,
                log_entry=entry,
            )
        expected_prefix = entry.entry_hash[:16]
        assert any(
            r.levelno == logging.DEBUG and expected_prefix in r.message
            for r in caplog.records
        )
