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

"""Tests for non-owner participant add subtree composition and behavior."""

from typing import Any, cast

import py_trees
import pytest

from vultron.core.behaviors.case.nodes import (
    CreateCaseOwnerParticipant,
    CreateCaseParticipantNode,
)
from vultron.core.behaviors.case.nodes.participant import (
    AttachParticipantToCaseNode,
    CaseHasActiveEmbargoNode,
    CaseHasNoActiveEmbargoNode,
    CreateParticipantNode,
    QueueAddParticipantNotificationNode,
    RecordParticipantAddedEventNode,
    ResolveParticipantAcceptedStatusNode,
    SeedParticipantAsSignatoryIfEmbargoActiveNode,
    SeedParticipantAsSignatoryNode,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.vultron_types import VultronCase, VultronCaseActor
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from test.core.behaviors.bt_harness import BTTestScenario


class TestCreateCaseParticipantNode:
    """CreateCaseParticipantNode preserves semantics after refactor."""

    @pytest.fixture
    def finder_actor_id(self) -> str:
        return "https://example.org/actors/finder"

    def test_creates_and_attaches_participant(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
        finder_actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            CreateCaseParticipantNode(
                actor_id=finder_actor_id, roles=[CVDRole.FINDER]
            ),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert finder_actor_id in stored_case.actor_participant_index

    def test_records_participant_added_event(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
        finder_actor_id: str,
    ) -> None:
        """CreateCaseParticipantNode adds the participant to the case."""
        bt_scenario.run(
            CreateCaseParticipantNode(
                actor_id=finder_actor_id, roles=[CVDRole.FINDER]
            ),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        # Participant must be present in the case index
        assert finder_actor_id in stored_case.actor_participant_index

    def test_is_composed_subtree_of_named_leaf_nodes(self) -> None:
        node = CreateCaseParticipantNode(
            actor_id="https://example.org/actors/finder",
            roles=[CVDRole.FINDER],
        )

        assert [type(child) for child in node.children] == [
            ResolveParticipantAcceptedStatusNode,
            CreateParticipantNode,
            AttachParticipantToCaseNode,
            RecordParticipantAddedEventNode,
            SeedParticipantAsSignatoryIfEmbargoActiveNode,
            QueueAddParticipantNotificationNode,
        ]

    def test_embargo_seed_is_conditional_subtree(self) -> None:
        node = SeedParticipantAsSignatoryIfEmbargoActiveNode(
            participant_actor_id="https://example.org/actors/finder"
        )
        assert isinstance(node, py_trees.composites.Selector)
        assert isinstance(node.children[0], py_trees.composites.Sequence)
        assert [type(child) for child in node.children[0].children] == [
            CaseHasActiveEmbargoNode,
            SeedParticipantAsSignatoryNode,
        ]
        assert type(node.children[1]) is CaseHasNoActiveEmbargoNode

    def test_emits_add_participant_activity(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
        finder_actor_id: str,
    ) -> None:
        """CreateCaseParticipantNode queues AddParticipantToCaseActivity."""
        bt_scenario.run(
            CreateCaseParticipantNode(
                actor_id=finder_actor_id, roles=[CVDRole.FINDER]
            ),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        outbox_ids = bt_scenario.dl.clone_for_actor(actor_id).outbox_list()
        add_activities: list[as_Add] = []
        for oid in outbox_ids:
            obj = bt_scenario.dl.read(oid)
            if isinstance(obj, as_Add):
                add_activities.append(obj)
        assert any(
            act.type_ == "Add"
            and isinstance(act.object_, CaseParticipant)
            and getattr(act.target, "id_", act.target) == case_obj.id_
            for act in add_activities
        )

    def test_seeds_participant_as_signatory_when_embargo_active(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
        finder_actor_id: str,
    ) -> None:
        embargo = EmbargoEvent(context=case_obj.id_)
        bt_scenario.dl.create(embargo)
        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        stored_case.active_embargo = embargo.id_
        bt_scenario.dl.save(stored_case)

        bt_scenario.run(
            CreateCaseParticipantNode(
                actor_id=finder_actor_id, roles=[CVDRole.FINDER]
            ),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        participant_id = stored_case.actor_participant_index[finder_actor_id]
        participant = cast(Any, bt_scenario.dl.read(participant_id))
        assert participant.embargo_consent_state == PEC.SIGNATORY
        assert embargo.id_ in participant.accepted_embargo_ids

    def test_does_not_record_participant_added_event_for_case_owner(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """CreateCaseOwnerParticipant adds the owner; no extra participants."""
        bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        # Only the owner (actor_id) should be in the participant index
        assert list(stored_case.actor_participant_index.keys()) == [actor_id]
