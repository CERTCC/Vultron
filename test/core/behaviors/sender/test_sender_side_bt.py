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

"""Tests for sender.send_tree factory."""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BlackboardKeyProbe
from test.support.act_runner import run_tree
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sender.nodes import (
    ConstructActivitiesNode,
    QueueToOutboxNode,
    ResolveCaseManagerNode,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    ReporterParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ACTOR_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/test-case"
ACTIVITY_ID = "https://example.org/activities/act-01"


@pytest.fixture
def dl():
    actor = make(as_Service, name="finder")
    reset_datalayer(actor.id_)
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    store.clear_all()
    store.create(actor)
    return store, actor


@pytest.fixture
def bridge(dl):
    store, _ = dl
    return BTBridge(datalayer=store)


def _make_case_with_case_manager(
    store: SqliteDataLayer,
    actor_id: str,
) -> as_VulnerabilityCase:
    case = make(
        as_VulnerabilityCase, attributed_to=CASE_OWNER_ID, name="Test Case"
    )
    finder_participant = make(
        ReporterParticipant,
        attributed_to=actor_id,
        context=case.id_,
    )
    case_manager_participant = make(
        VendorParticipant,
        attributed_to=CASE_ACTOR_ID,
        context=case.id_,
    )
    case_manager_participant.add_role(CVDRole.CASE_MANAGER)
    object.__setattr__(
        case,
        "case_participants",
        [
            finder_participant.id_,
            case_manager_participant.id_,
        ],
    )
    object.__setattr__(
        case,
        "actor_participant_index",
        {
            actor_id: finder_participant.id_,
            CASE_ACTOR_ID: case_manager_participant.id_,
        },
    )
    store.create(case)
    store.create(finder_participant)
    store.create(case_manager_participant)
    return case


def _make_case_without_case_manager(
    store: SqliteDataLayer,
    actor_id: str,
) -> as_VulnerabilityCase:
    """A stored case whose only participant is *actor_id*, a reporter."""
    case = make(
        as_VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
        name="No Manager Case",
    )
    participant = make(
        ReporterParticipant, attributed_to=actor_id, context=case.id_
    )
    object.__setattr__(case, "case_participants", [participant.id_])
    object.__setattr__(
        case, "actor_participant_index", {actor_id: participant.id_}
    )
    store.create(case)
    store.create(participant)
    return case


class TestSenderSideBT:
    def test_tree_structure_has_three_expected_nodes(self):
        tree = sender_side_bt(
            case_id=CASE_ID,
            activity_builder=lambda _: [],
        )
        assert tree.name == "SenderSideBT"
        assert isinstance(tree, py_trees.composites.Sequence)
        children = tree.children
        assert len(children) == 3
        assert isinstance(children[0], ResolveCaseManagerNode)
        assert isinstance(children[1], ConstructActivitiesNode)
        assert isinstance(children[2], QueueToOutboxNode)

    @pytest.mark.spec("CM-24-001")
    def test_bt_success_routes_to_case_manager(self, dl, bridge):
        store, actor = dl
        case = _make_case_with_case_manager(store, actor.id_)
        addressed_to: list[str] = []

        def _builder(case_manager_id: str) -> list[str]:
            addressed_to.append(case_manager_id)
            return [ACTIVITY_ID]

        tree = sender_side_bt(
            case_id=case.id_,
            activity_builder=_builder,
        )
        result = run_tree(bridge, tree=tree, actor_id=actor.id_)
        assert result.status == Status.SUCCESS
        assert addressed_to == [CASE_ACTOR_ID]

    @pytest.mark.spec("CM-24-014")
    def test_bt_failure_when_case_manager_absent(self, dl, bridge):
        store, actor = dl
        case = make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            name="No Manager",
        )
        participant = make(
            ReporterParticipant,
            attributed_to=actor.id_,
            context=case.id_,
        )
        object.__setattr__(case, "case_participants", [participant.id_])
        object.__setattr__(
            case, "actor_participant_index", {actor.id_: participant.id_}
        )
        store.create(case)
        store.create(participant)
        tree = sender_side_bt(
            case_id=case.id_,
            activity_builder=lambda _: [ACTIVITY_ID],
        )
        result = run_tree(bridge, tree=tree, actor_id=actor.id_)
        assert result.status == Status.FAILURE
        reason = BTBridge.get_failure_reason(tree)
        assert "CASE_MANAGER" in reason


@pytest.mark.spec("BT-17-003")
class TestSenderSideStaleKeyRegression:
    """Back-to-back runs on the same blackboard must not observe stale keys."""

    def test_stale_case_manager_id_not_present_after_execution(
        self, dl, bridge
    ):
        """``/case_manager_id`` is absent after a successful and a failed
        run alike: the bridge scopes it to its execution (#5803).
        """
        store, actor = dl
        storage = py_trees.blackboard.Blackboard.storage

        # Run 1: succeeds — /case_manager_id is cleaned up afterwards.
        case1 = _make_case_with_case_manager(store, actor.id_)
        tree1 = sender_side_bt(
            case_id=case1.id_,
            activity_builder=lambda _: [ACTIVITY_ID],
        )
        result1 = run_tree(bridge, tree=tree1, actor_id=actor.id_)
        assert result1.status == Status.SUCCESS
        assert "/case_manager_id" not in storage

        # Run 2 (no blackboard clear between runs): fails — case has no
        # CASE_MANAGER participant.  The key is still absent afterwards.
        case2 = _make_case_without_case_manager(store, actor.id_)

        tree2 = sender_side_bt(
            case_id=case2.id_,
            activity_builder=lambda _: [ACTIVITY_ID],
        )
        result2 = run_tree(bridge, tree=tree2, actor_id=actor.id_)
        assert result2.status == Status.FAILURE
        assert "/case_manager_id" not in storage

    @pytest.mark.parametrize("case_kind", ["missing", "no_case_manager"])
    def test_resolve_failure_overwrites_a_stale_case_manager_id_with_none(
        self, dl, bridge, case_kind
    ):
        """Each failure arm of ``ResolveCaseManagerNode`` writes ``None``.

        The bridge's restore removes a value only once the execution ends,
        so within one execution a node later than the failed resolve, as in
        a Selector, must see no manager rather than a value written before
        it ticked (BT-17-003).
        """
        store, actor = dl
        storage = py_trees.blackboard.Blackboard.storage
        case_id = (
            CASE_ID
            if case_kind == "missing"
            else _make_case_without_case_manager(store, actor.id_).id_
        )
        probe = BlackboardKeyProbe("case_manager_id")
        tree = py_trees.composites.Selector(
            name="ResolveOrProbe",
            memory=False,
            children=[ResolveCaseManagerNode(case_id=case_id), probe],
        )
        storage["/case_manager_id"] = "https://example.org/actors/stale"
        try:
            run_tree(bridge, tree=tree, actor_id=actor.id_)
        finally:
            storage.pop("/case_manager_id", None)

        assert probe.ran
        assert probe.value is None

    def test_stale_activity_ids_cleared_on_construct_failure(self, dl, bridge):
        store, actor = dl
        storage = py_trees.blackboard.Blackboard.storage

        # Run 1: succeeds — writes /activity_ids to the global blackboard
        case1 = _make_case_with_case_manager(store, actor.id_)
        tree1 = sender_side_bt(
            case_id=case1.id_,
            activity_builder=lambda _: [ACTIVITY_ID],
        )
        result1 = run_tree(bridge, tree=tree1, actor_id=actor.id_)
        assert result1.status == Status.SUCCESS
        assert storage.get("/activity_ids") is not None

        # Run 2 (no blackboard clear between runs): ResolveCaseManagerNode
        # succeeds but ConstructActivitiesNode fails (builder raises).
        # BT-17-003 requires ConstructActivitiesNode to clear /activity_ids.
        def _failing_builder(case_manager_id: str) -> list[str]:
            raise RuntimeError("simulated build failure")

        tree2 = sender_side_bt(
            case_id=case1.id_,
            activity_builder=_failing_builder,
        )
        result2 = run_tree(bridge, tree=tree2, actor_id=actor.id_)
        assert result2.status == Status.FAILURE

        assert storage.get("/activity_ids") is None
