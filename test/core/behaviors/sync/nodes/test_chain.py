#!/usr/bin/env python
"""Unit tests for sync chain nodes."""

import logging

import py_trees
import pytest

from vultron.core.models._helpers import _now_utc
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
    ReconstructChainTailNode,
)

_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains


def _canonical_note_snapshot(actor_id: str) -> dict[str, object]:
    return {
        "type": "Add",
        "actor": actor_id,
        # CLP-07-011: recorded snapshots carry the asserter's claimed timestamp.
        "published": _now_utc().isoformat(),
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
        "published": _now_utc().isoformat(),
        "object": {
            "type": "VulnerabilityCase",
            "id": CASE_ID,
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }


@pytest.mark.spec("CLP-02-001")
@pytest.mark.spec("SYNC-01-002")
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
        tail_hash=_ZERO_HASH,
        tail_index=-1,
    )

    assert result.status == Status.SUCCESS
    blackboard = py_trees.blackboard.Client(name="assert-log-entry")
    blackboard.register_key(
        key="log_entry", access=py_trees.common.Access.READ
    )
    assert blackboard.log_entry.case_id == CASE_ID
    assert blackboard.log_entry.log_index == 0


@pytest.mark.spec("CLP-07-011")
def test_create_log_entry_node_default_payload_snapshot_is_empty_dict():
    """Omitting payload_snapshot gives an empty dict on the node instance."""
    node = CreateLogEntryNode(
        case_id=CASE_ID,
        object_id="https://example.org/activities/act-2",
        event_type="note_added",
    )
    assert node.payload_snapshot == {}
    assert node.payload_snapshot is not None


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
@pytest.mark.spec("CLP-07-005")
@pytest.mark.spec("CLP-07-011")
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
        tail_hash=_ZERO_HASH,
        tail_index=-1,
    )

    assert result.status == Status.FAILURE
    assert message in result.feedback_message


@pytest.mark.spec("CLP-07-003")
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
        tail_hash=_ZERO_HASH,
        tail_index=-1,
    )

    assert result.status == Status.SUCCESS


class TestReconstructChainTailPreGenesisLogging:
    """Bug #2169: the pre-genesis bootstrap window (empty ledger + no per-case
    genesis hash) is an expected, self-healing condition, not a fault.

    ``ReconstructChainTailNode`` writes the replay-from-genesis sentinel
    (``tail_hash=""``, ``tail_index=-1``) so the downstream
    ``ReconstructOrRejectOnMissingCase`` selector fires a
    ``Reject(CaseLedgerEntry)`` and the CaseActor replays the chain
    (SYNC-15-001, CLP-08-005).  Because this recovery is by design, it MUST be
    logged at WARNING — not ERROR — so it does not surface as spurious error
    noise on replica containers (e.g. ``finder-1``) during the initial
    Announce/Create delivery race.
    """

    @pytest.mark.spec("SYNC-15-001")
    @pytest.mark.spec("CLP-08-005")
    def test_pre_genesis_logs_warning_not_error(
        self, bridge, caplog: pytest.LogCaptureFixture
    ):
        node_logger = "vultron.core.behaviors.sync.nodes.chain"
        with caplog.at_level(logging.DEBUG, logger=node_logger):
            result = bridge.execute_with_setup(
                tree=ReconstructChainTailNode(
                    case_id=CASE_ID, name="ReconstructChainTail"
                ),
                actor_id=OWNER_ACTOR_ID,
            )

        assert result.status == Status.FAILURE
        assert not any(r.levelno == logging.ERROR for r in caplog.records), (
            "pre-genesis bootstrap window must not log at ERROR — it is an "
            "expected, self-healing Reject/replay recovery (Bug #2169)"
        )
        assert any(
            r.levelno == logging.WARNING and "CLP-08-005" in r.message
            for r in caplog.records
        ), "expected a WARNING explaining the replay-from-genesis recovery"

    @pytest.mark.spec("SYNC-15-001")
    @pytest.mark.spec("CLP-08-005")
    def test_pre_genesis_writes_replay_sentinel(self, bridge):
        result = bridge.execute_with_setup(
            tree=ReconstructChainTailNode(
                case_id=CASE_ID, name="ReconstructChainTail"
            ),
            actor_id=OWNER_ACTOR_ID,
        )

        assert result.status == Status.FAILURE
        blackboard = py_trees.blackboard.Client(name="assert-sentinel")
        blackboard.register_key(
            key="tail_hash", access=py_trees.common.Access.READ
        )
        blackboard.register_key(
            key="tail_index", access=py_trees.common.Access.READ
        )
        assert blackboard.tail_hash == ""
        assert blackboard.tail_index == -1


class TestPersistLogEntryNodeLogging:
    """Verify INFO and DEBUG log emission from PersistLogEntryNode."""

    @pytest.fixture()
    def entry(self):
        return _make_entry(log_index=0, prev_hash=_ZERO_HASH)

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
