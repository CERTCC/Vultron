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

"""Tests for StoreDeadLetterRecordNode (dead_letter.py)."""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.inbox.nodes.dead_letter import (
    StoreDeadLetterRecordNode,
)
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.unknown import UnresolvableObjectReceivedEvent
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Accept

ACTOR_URI = "https://example.org/coordinator"
UNRESOLVABLE_URI = "urn:uuid:does-not-exist-dead-letter-node-test"


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def unresolvable_event() -> UnresolvableObjectReceivedEvent:
    accept = as_Accept(actor=ACTOR_URI, object_=UNRESOLVABLE_URI)
    event = extract_event(accept)
    assert event.semantic_type == MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    return event  # type: ignore[return-value]


class TestStoreDeadLetterRecordNode:
    """Unit tests for StoreDeadLetterRecordNode via BTBridge."""

    def test_stores_dead_letter_record(
        self, bridge, dl, unresolvable_event
    ) -> None:
        """Happy path: BT stores a DeadLetterRecord in the DataLayer."""
        tree = StoreDeadLetterRecordNode(request=unresolvable_event)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_URI, activity=unresolvable_event
        )
        assert result.status == Status.SUCCESS
        stored = dl.by_type("DeadLetterRecord")
        assert len(stored) == 1

    def test_stored_record_contains_unresolvable_uri(
        self, bridge, dl, unresolvable_event
    ) -> None:
        """The stored DeadLetterRecord includes the unresolvable URI."""
        tree = StoreDeadLetterRecordNode(request=unresolvable_event)
        bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_URI, activity=unresolvable_event
        )
        record_data = next(iter(dl.by_type("DeadLetterRecord").values()))
        assert record_data["unresolvable_uri"] == UNRESOLVABLE_URI

    def test_stored_record_contains_actor_id(
        self, bridge, dl, unresolvable_event
    ) -> None:
        """The stored DeadLetterRecord includes the actor ID."""
        tree = StoreDeadLetterRecordNode(request=unresolvable_event)
        bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_URI, activity=unresolvable_event
        )
        record_data = next(iter(dl.by_type("DeadLetterRecord").values()))
        assert record_data["actor_id"] == ACTOR_URI

    def test_node_returns_success_on_second_call(
        self, bridge, dl, unresolvable_event
    ) -> None:
        """StoreDeadLetterRecordNode can be called multiple times (no dedup)."""
        tree1 = StoreDeadLetterRecordNode(request=unresolvable_event)
        bridge.execute_with_setup(
            tree=tree1, actor_id=ACTOR_URI, activity=unresolvable_event
        )
        tree2 = StoreDeadLetterRecordNode(request=unresolvable_event)
        result = bridge.execute_with_setup(
            tree=tree2, actor_id=ACTOR_URI, activity=unresolvable_event
        )
        assert result.status == Status.SUCCESS
        # At least one record is stored
        assert len(dl.by_type("DeadLetterRecord")) >= 1
