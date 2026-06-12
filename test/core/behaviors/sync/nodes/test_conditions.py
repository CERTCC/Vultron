#!/usr/bin/env python
"""Unit tests for sync conditions nodes."""

from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    OWNER_ACTOR_ID,
    _make_entry,
    _make_event,
)
from vultron.core.behaviors.sync.nodes import CheckIsOwnCaseActorNode
from vultron.core.models.case_ledger import GENESIS_HASH


def test_check_is_own_case_actor_succeeds_for_case_owner(bridge, case_actor):
    entry = _make_entry(0, GENESIS_HASH)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=CheckIsOwnCaseActorNode(name="CheckIsOwnCaseActor"),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
