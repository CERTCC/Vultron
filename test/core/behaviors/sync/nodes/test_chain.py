#!/usr/bin/env python
"""Unit tests for sync chain nodes."""

import logging

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    OWNER_ACTOR_ID,
    _make_entry,
)
from vultron.core.behaviors.sync.nodes import (
    CreateLogEntryNode,
    PersistLogEntryNode,
)
from vultron.core.models.case_ledger import GENESIS_HASH


def test_create_log_entry_node_writes_log_entry_to_blackboard(bridge):
    case_id = "https://example.org/cases/case-sync"
    result = bridge.execute_with_setup(
        tree=CreateLogEntryNode(
            case_id=case_id,
            object_id="https://example.org/activities/act-1",
            event_type="case_created",
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
    assert blackboard.log_entry.case_id == case_id
    assert blackboard.log_entry.log_index == 0


# ---------------------------------------------------------------------------
# PersistLogEntryNode — logging (SL-03-001, SL-04-001)
# ---------------------------------------------------------------------------


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
