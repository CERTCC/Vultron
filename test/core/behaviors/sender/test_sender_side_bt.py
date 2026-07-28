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

import pytest
import py_trees
from py_trees.common import Status

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
    FinderParticipant,
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
) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(name="Test Case")
    finder_participant = FinderParticipant(
        attributed_to=actor_id,
        context=case.id_,
    )
    case_manager_participant = VendorParticipant(
        attributed_to=CASE_ACTOR_ID,
        context=case.id_,
    )
    case_manager_participant.add_role(CVDRole.CASE_MANAGER)
    case.case_participants = [
        finder_participant.id_,
        case_manager_participant.id_,
    ]
    case.actor_participant_index = {
        actor_id: finder_participant.id_,
        CASE_ACTOR_ID: case_manager_participant.id_,
    }
    store.create(case)
    store.create(finder_participant)
    store.create(case_manager_participant)
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
        result = bridge.execute_with_setup(tree=tree, actor_id=actor.id_)
        assert result.status == Status.SUCCESS
        assert addressed_to == [CASE_ACTOR_ID]

    def test_bt_failure_when_case_manager_absent(self, dl, bridge):
        store, actor = dl
        case = as_VulnerabilityCase(name="No Manager")
        participant = FinderParticipant(
            attributed_to=actor.id_,
            context=case.id_,
        )
        case.case_participants = [participant.id_]
        case.actor_participant_index = {actor.id_: participant.id_}
        store.create(case)
        store.create(participant)
        tree = sender_side_bt(
            case_id=case.id_,
            activity_builder=lambda _: [ACTIVITY_ID],
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=actor.id_)
        assert result.status == Status.FAILURE
        reason = BTBridge.get_failure_reason(tree)
        assert "CASE_MANAGER" in reason
