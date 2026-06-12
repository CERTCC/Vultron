#!/usr/bin/env python
"""Unit tests for sync chain nodes."""

import py_trees
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import OWNER_ACTOR_ID
from vultron.core.behaviors.sync.nodes import CreateLogEntryNode
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
