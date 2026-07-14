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

"""Tests for case-owner participant subtree composition and behavior."""

from typing import Any, cast

import py_trees
import pytest

from vultron.core.behaviors.case.nodes import CreateCaseOwnerParticipant
from vultron.core.behaviors.case.nodes.participant import (
    AdvanceOwnerRmToAcceptedNode,
    AttachOwnerParticipantToCaseNode,
    CreateOwnerParticipantNode,
    PersistOwnerCaseNode,
    RecordOwnerJoinedEventNode,
    ResolveOwnerInitialStatusNode,
    ShouldAdvanceOwnerToAcceptedNode,
)
from vultron.config.actor import ActorConfig
from vultron.core.models.vultron_types import VultronCase, VultronCaseActor
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario


class TestCreateCaseOwnerParticipant:
    """CreateCaseOwnerParticipant preserves semantics after refactor."""

    def test_creates_and_attaches_case_owner_participant(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)
        bt_scenario.assert_participant_in_case(actor_id, case_obj.id_)

    def test_idempotent(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """Running twice does not error."""
        result1 = bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result1)

        result2 = bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result2)

    def test_fails_when_case_not_found(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id="https://example.org/cases/missing",
        )
        bt_scenario.assert_failure(result)

    def test_default_role_is_case_owner(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """Default (no actor_config) assigns only CASE_OWNER role."""
        bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        for p_ref in stored_case.case_participants:
            p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
            participant = cast(Any, bt_scenario.dl.read(p_id))
            if participant is None:
                continue
            p_actor = participant.attributed_to
            p_actor_id = (
                p_actor
                if isinstance(p_actor, str)
                else getattr(p_actor, "id_", p_actor)
            )
            if p_actor_id == actor_id:
                assert CVDRole.CASE_OWNER in participant.case_roles
                return
        pytest.fail("No case-owner participant found")

    def test_config_roles_combined_with_case_owner(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """config roles + CASE_OWNER appear in participant roles."""
        config = ActorConfig(default_case_roles=[CVDRole.COORDINATOR])
        bt_scenario.run(
            CreateCaseOwnerParticipant(actor_config=config),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        for p_ref in stored_case.case_participants:
            p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
            participant = cast(Any, bt_scenario.dl.read(p_id))
            if participant is None:
                continue
            p_actor = participant.attributed_to
            p_actor_id = (
                p_actor
                if isinstance(p_actor, str)
                else getattr(p_actor, "id_", p_actor)
            )
            if p_actor_id == actor_id:
                assert CVDRole.CASE_OWNER in participant.case_roles
                assert CVDRole.COORDINATOR in participant.case_roles
                return
        pytest.fail("No participant found for actor")

    def test_is_composed_subtree_of_named_leaf_nodes(self) -> None:
        node = CreateCaseOwnerParticipant()
        assert isinstance(node, py_trees.composites.Sequence)
        assert [type(child) for child in node.children[:5]] == [
            ResolveOwnerInitialStatusNode,
            CreateOwnerParticipantNode,
            AttachOwnerParticipantToCaseNode,
            PersistOwnerCaseNode,
            RecordOwnerJoinedEventNode,
        ]
        assert isinstance(node.children[5], py_trees.composites.Selector)

        conditional_selector = node.children[5]
        assert isinstance(
            conditional_selector.children[0], py_trees.composites.Sequence
        )
        assert [
            type(child) for child in conditional_selector.children[0].children
        ] == [
            ShouldAdvanceOwnerToAcceptedNode,
            AdvanceOwnerRmToAcceptedNode,
        ]
        assert isinstance(
            conditional_selector.children[1], py_trees.behaviours.Success
        )

    def test_records_owner_joined_event(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """CreateCaseOwnerParticipant registers owner as a case participant.

        record_event('owner_joined') was removed in #789; the behavioral
        outcome — owner registered in actor_participant_index — is the
        authoritative check now.
        """
        result = bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert actor_id in stored_case.actor_participant_index

    def test_advances_owner_rm_to_accepted_when_configured(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            CreateCaseOwnerParticipant(advance_to_accepted=True),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        participant_id = stored_case.actor_participant_index[actor_id]
        participant = cast(Any, bt_scenario.dl.read(participant_id))
        rm_states = [
            status.rm_state for status in participant.participant_statuses
        ]
        assert RM.ACCEPTED in rm_states
