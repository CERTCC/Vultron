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

"""Tests for sender.nodes.actions."""

import pytest
import py_trees
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sender.nodes.actions import (
    ConstructActivitiesNode,
    QueueToOutboxNode,
    ResolveCaseManagerNode,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/finder"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
ACTIVITY_ID = "https://example.org/activities/act-01"


@pytest.fixture
def dl():
    actor = as_Service(name="finder")
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
    case_actor_id: str,
) -> tuple[as_VulnerabilityCase, VendorParticipant]:
    case = as_VulnerabilityCase(name="Test Case")
    finder_participant = FinderParticipant(
        attributed_to=actor_id,
        context=case.id_,
    )
    case_manager_participant = VendorParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
    )
    case_manager_participant.add_role(CVDRole.CASE_MANAGER)
    case.case_participants = [
        finder_participant.id_,
        case_manager_participant.id_,
    ]
    case.actor_participant_index = {
        actor_id: finder_participant.id_,
        case_actor_id: case_manager_participant.id_,
    }
    store.create(case)
    store.create(finder_participant)
    store.create(case_manager_participant)
    return case, case_manager_participant


class TestResolveCaseManagerNode:
    def test_success_when_case_manager_found(self, dl, bridge):
        store, actor = dl
        case, _ = _make_case_with_case_manager(store, actor.id_, CASE_ACTOR_ID)
        node = ResolveCaseManagerNode(case_id=case.id_)
        result = bridge.execute_with_setup(tree=node, actor_id=actor.id_)
        assert result.status == Status.SUCCESS

    def test_writes_case_manager_id_to_blackboard(self, dl, bridge):
        store, actor = dl
        case, _ = _make_case_with_case_manager(store, actor.id_, CASE_ACTOR_ID)
        node = ResolveCaseManagerNode(case_id=case.id_)
        bridge.execute_with_setup(tree=node, actor_id=actor.id_)
        reader = py_trees.blackboard.Client(name="test-reader")
        reader.register_key(
            key="case_manager_id", access=py_trees.common.Access.READ
        )
        assert reader.case_manager_id == CASE_ACTOR_ID

    def test_failure_when_case_not_found(self, dl, bridge):
        _, actor = dl
        node = ResolveCaseManagerNode(case_id="https://missing.example/case")
        result = bridge.execute_with_setup(tree=node, actor_id=actor.id_)
        assert result.status == Status.FAILURE

    def test_failure_when_no_case_manager(self, dl, bridge):
        store, actor = dl
        case = as_VulnerabilityCase(name="No Manager Case")
        participant = FinderParticipant(
            attributed_to=actor.id_,
            context=case.id_,
        )
        case.case_participants = [participant.id_]
        case.actor_participant_index = {actor.id_: participant.id_}
        store.create(case)
        store.create(participant)
        node = ResolveCaseManagerNode(case_id=case.id_)
        result = bridge.execute_with_setup(tree=node, actor_id=actor.id_)
        assert result.status == Status.FAILURE
        assert "CASE_MANAGER" in node.feedback_message


class TestConstructActivitiesNode:
    def test_success_calls_builder_with_case_manager_id(self, dl, bridge):
        store, actor = dl
        case, _ = _make_case_with_case_manager(store, actor.id_, CASE_ACTOR_ID)
        received_ids: list[str] = []

        def _builder(case_manager_id: str) -> list[str]:
            received_ids.append(case_manager_id)
            return [ACTIVITY_ID]

        seq = py_trees.composites.Sequence(
            name="test-seq",
            memory=False,
            children=[
                ResolveCaseManagerNode(case_id=case.id_),
                ConstructActivitiesNode(activity_builder=_builder),
            ],
        )
        result = bridge.execute_with_setup(tree=seq, actor_id=actor.id_)
        assert result.status == Status.SUCCESS
        assert received_ids == [CASE_ACTOR_ID]

    def test_failure_when_builder_raises(self, dl, bridge):
        store, actor = dl
        case, _ = _make_case_with_case_manager(store, actor.id_, CASE_ACTOR_ID)

        def _failing_builder(case_manager_id: str) -> list[str]:
            raise ValueError("build error")

        seq = py_trees.composites.Sequence(
            name="test-seq",
            memory=False,
            children=[
                ResolveCaseManagerNode(case_id=case.id_),
                ConstructActivitiesNode(activity_builder=_failing_builder),
            ],
        )
        result = bridge.execute_with_setup(tree=seq, actor_id=actor.id_)
        assert result.status == Status.FAILURE

    def test_failure_without_resolve_first(self, dl, bridge):
        _, actor = dl
        node = ConstructActivitiesNode(activity_builder=lambda _: [])
        result = bridge.execute_with_setup(tree=node, actor_id=actor.id_)
        assert result.status == Status.FAILURE


class TestQueueToOutboxNode:
    def test_queues_activities_to_outbox(self, dl, bridge):
        store, actor = dl
        case, _ = _make_case_with_case_manager(store, actor.id_, CASE_ACTOR_ID)

        def _builder(case_manager_id: str) -> list[str]:
            return [ACTIVITY_ID]

        seq = py_trees.composites.Sequence(
            name="test-seq",
            memory=False,
            children=[
                ResolveCaseManagerNode(case_id=case.id_),
                ConstructActivitiesNode(activity_builder=_builder),
                QueueToOutboxNode(),
            ],
        )
        result = bridge.execute_with_setup(tree=seq, actor_id=actor.id_)
        assert result.status == Status.SUCCESS
        outbox_items = store.clone_for_actor(actor.id_).outbox_list()
        assert ACTIVITY_ID in outbox_items
