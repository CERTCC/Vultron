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

"""Unit tests for DeferCheckNode (pipeline.py) — deferral guards.

Two regressions are covered:

1. Non-URI context_id: when a Reject(CaseLedgerEntry) carries a genesis hash
   as context, DeferCheckNode must skip deferral (no colon in context_id).
2. Bootstrap self-deferral deadlock: every semantic in
   ``CASE_BOOTSTRAP_SEMANTICS`` establishes the local case replica, so it must
   never be deferred — nothing else could ever make its case known locally.
   ``CREATE_CASE`` in particular used to defer itself because its AS2
   ``context`` is the Accept(CaseProposal) URI (CP-05-003), not the case URI.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.inbox.nodes.pipeline import DeferCheckNode
from vultron.core.models.events import (
    CASE_BOOTSTRAP_SEMANTICS,
    MessageSemantics,
    VultronEvent,
)
from vultron.core.models.events.base import VultronObject

CASE_ID = "https://example.org/cases/case-defer-test"
ACTOR_ID = "https://example.org/actors/actor-1"
ACTIVITY_ID = "https://example.org/activities/act-1"

# 64-char hex string — typical genesis hash format
_GENESIS_HASH = "a" * 64


class _StubQueuePort:
    def __init__(self, case_known: bool = False) -> None:
        self._case_known = case_known
        self.queued: list[tuple] = []

    def is_case_known(self, case_id: str) -> bool:
        return self._case_known

    def check_and_expire(self, case_id: str) -> bool:
        return False

    def queue(
        self, activity_id: str, case_id: str, case_actor_id=None
    ) -> None:
        self.queued.append((activity_id, case_id, case_actor_id))


def _make_event(semantic_type=MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY):
    """Return a minimal VultronEvent stub for DeferCheckNode."""
    obj = VultronObject(id_=ACTIVITY_ID, type_=None)
    return VultronEvent(
        activity_id=ACTIVITY_ID,
        actor_id=ACTOR_ID,
        semantic_type=semantic_type,
        object_=obj,
        context=None,
    )


@pytest.fixture(autouse=True)
def _clear_blackboard():
    """Reset the py_trees blackboard between tests."""
    yield
    py_trees.blackboard.Blackboard.enable_activity_stream()
    py_trees.blackboard.Blackboard.storage.clear()


def _run_node(
    context_id: str,
    queue_port: _StubQueuePort | None,
    semantic_type: MessageSemantics = MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY,
) -> Status:
    """Set up the blackboard and tick DeferCheckNode once."""
    setup_bb = py_trees.blackboard.Client(name="_setup")
    setup_bb.register_key("inbox_event", access=py_trees.common.Access.WRITE)
    setup_bb.register_key(
        "inbox_context_id", access=py_trees.common.Access.WRITE
    )
    setup_bb.register_key("inbox_queue", access=py_trees.common.Access.WRITE)
    setup_bb.inbox_event = _make_event(semantic_type)
    setup_bb.inbox_context_id = context_id
    if queue_port is not None:
        setup_bb.inbox_queue = queue_port

    node = DeferCheckNode(name="TestDeferCheck")
    tree = py_trees.trees.BehaviourTree(root=node)
    tree.setup()
    tree.tick()
    return node.status


class TestDeferCheckNodeNonUriContextId:
    def test_genesis_hash_skips_deferral(self):
        """Non-URI context_id (genesis hash) must not be queued for deferral.

        Regression: Reject(CaseLedgerEntry) carries context=tail_hash which is
        a 64-char hex string.  Without the guard, queue.queue() would have been
        called with case_id=genesis_hash causing a pydantic ValidationError.
        """
        queue = _StubQueuePort(case_known=False)
        status = _run_node(_GENESIS_HASH, queue)

        assert status == Status.SUCCESS
        assert len(queue.queued) == 0, "genesis hash must not be queued"

    def test_uri_context_id_is_still_deferred(self):
        """Normal URI context_id for unknown case is still deferred."""
        queue = _StubQueuePort(case_known=False)
        status = _run_node("https://example.org/cases/unknown-case", queue)

        assert status == Status.FAILURE
        assert len(queue.queued) == 1

    def test_no_queue_port_skips_deferral(self):
        """Without a queue port, deferral is skipped regardless of context_id."""
        status = _run_node("https://example.org/cases/unknown-case", None)

        assert status == Status.SUCCESS


class TestDeferCheckNodeBootstrapNeverDeferred:
    """Bootstrap activities must never be deferred (deadlock regression)."""

    @pytest.mark.parametrize("semantic_type", sorted(CASE_BOOTSTRAP_SEMANTICS))
    def test_bootstrap_semantic_not_deferred_for_unknown_case(
        self, semantic_type
    ):
        """A bootstrap activity for an unknown case dispatches, not defers.

        Deferring here would deadlock: the bootstrap activity is the only
        thing that can make the case known locally, so queuing it means it
        is never replayed and the case replica is never created.
        """
        queue = _StubQueuePort(case_known=False)
        status = _run_node(
            "https://example.org/cases/not-yet-known",
            queue,
            semantic_type=semantic_type,
        )

        assert status == Status.SUCCESS
        assert queue.queued == [], f"{semantic_type} must not be deferred"

    def test_create_case_is_a_bootstrap_semantic(self):
        """CREATE_CASE carries the case inline, so it bootstraps the replica.

        Guards against a regression where only ANNOUNCE_VULNERABILITY_CASE
        was treated as bootstrap, leaving Create(VulnerabilityCase) to defer
        itself against its Accept(CaseProposal) context URI (CP-05-003).
        """
        assert MessageSemantics.CREATE_CASE in CASE_BOOTSTRAP_SEMANTICS

    def test_non_bootstrap_case_semantic_is_still_deferred(self):
        """Semantics that presuppose the case are still deferred."""
        queue = _StubQueuePort(case_known=False)
        status = _run_node(
            "https://example.org/cases/not-yet-known",
            queue,
            semantic_type=MessageSemantics.ENGAGE_CASE,
        )

        assert status == Status.FAILURE
        assert len(queue.queued) == 1
