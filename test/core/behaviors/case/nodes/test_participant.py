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

"""
Tests for participant management behavior tree nodes.

Covers:
- _create_and_attach_participant shared helper (P360-FIX-2)
- CreateCaseOwnerParticipant uses shared helper
- CreateCaseParticipantNode uses shared helper

Per specs/behavior-tree-node-design.yaml BTND-05-002 and GitHub issue #401.
"""

import logging
from typing import Any, cast

import pytest
import py_trees

from vultron.core.behaviors.case.nodes import (
    CreateCaseOwnerParticipant,
    CreateCaseParticipantNode,
    _create_and_attach_participant,
)
from vultron.core.behaviors.case.nodes.participant import (
    AdvanceOwnerRmToAcceptedNode,
    AttachOwnerParticipantToCaseNode,
    AttachParticipantToCaseNode,
    CaseHasActiveEmbargoNode,
    CaseHasNoActiveEmbargoNode,
    CreateParticipantNode,
    CreateOwnerParticipantNode,
    PersistOwnerCaseNode,
    QueueAddParticipantNotificationNode,
    RecordOwnerJoinedEventNode,
    RecordParticipantAddedEventNode,
    ResolveParticipantAcceptedStatusNode,
    ResolveOwnerInitialStatusNode,
    SeedParticipantAsSignatoryIfEmbargoActiveNode,
    SeedParticipantAsSignatoryNode,
    ShouldAdvanceOwnerToAcceptedNode,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.actor_config import ActorConfig
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronParticipant,
    VultronReport,
)
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from test.core.behaviors.bt_harness import BTTestScenario

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def actor_id() -> str:
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(bt_scenario: BTTestScenario, actor_id: str) -> VultronCaseActor:
    obj = VultronCaseActor(id_=actor_id, name="Vendor Co")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(bt_scenario: BTTestScenario) -> VultronReport:
    obj = VultronReport(name="TEST-001", content="Test vulnerability report")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def case_obj(
    bt_scenario: BTTestScenario, report: VultronReport
) -> VultronCase:
    case = VultronCase(
        id_="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report.id_],
    )
    bt_scenario.dl.create(case)
    return case


# ---------------------------------------------------------------------------
# P360-FIX-2: _create_and_attach_participant helper tests
# ---------------------------------------------------------------------------


class TestCreateAndAttachParticipant:
    """Unit tests for the shared _create_and_attach_participant helper."""

    def test_creates_participant_in_datalayer(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        assert bt_scenario.dl.read(participant.id_) is not None

    def test_attaches_participant_to_case(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        assert participant.id_ in result.case_participants

    def test_updates_actor_participant_index(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        assert result.actor_participant_index.get(actor_id) == participant.id_

    def test_returns_unsaved_case(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """The returned case is unsaved; the caller controls the final save."""
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        persisted = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert participant.id_ not in persisted.case_participants

    def test_idempotent_participant_creation(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """Calling twice does not create a duplicate participant."""
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        node_logger = logging.getLogger("test")
        _create_and_attach_participant(
            bt_scenario.dl, participant, case_obj.id_, actor_id, node_logger
        )
        bt_scenario.dl.save(cast(Any, bt_scenario.dl.read(case_obj.id_)))

        result2 = _create_and_attach_participant(
            bt_scenario.dl, participant, case_obj.id_, actor_id, node_logger
        )
        assert result2 is not None
        assert result2.case_participants.count(participant.id_) == 1

    def test_returns_none_when_case_not_found(
        self, bt_scenario: BTTestScenario, actor_id: str
    ) -> None:
        participant = VultronParticipant(
            attributed_to=actor_id,
            context="https://example.org/cases/missing",
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            "https://example.org/cases/missing",
            actor_id,
            logging.getLogger("test"),
        )
        assert result is None


# ---------------------------------------------------------------------------
# P360-FIX-2: CreateCaseOwnerParticipant uses shared helper
# ---------------------------------------------------------------------------


class TestCreateCaseOwnerParticipant:
    """CreateCaseOwnerParticipant preserves semantics after refactor (BTND-05-002)."""

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
        """Default (no actor_config) assigns only CASE_OWNER role (CFG-07-002)."""
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
        """config roles + CASE_OWNER appear in participant roles (CFG-07-004)."""
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
        """CreateCaseOwnerParticipant records 'owner_joined' on the case."""
        result = bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        event_types = [e.event_type for e in stored_case.events]
        assert "owner_joined" in event_types

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


# ---------------------------------------------------------------------------
# P360-FIX-2: CreateCaseParticipantNode uses shared helper
# ---------------------------------------------------------------------------


class TestCreateCaseParticipantNode:
    """CreateCaseParticipantNode preserves its distinct semantics after refactor."""

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
        """CreateCaseParticipantNode records 'participant_added' on the case."""
        bt_scenario.run(
            CreateCaseParticipantNode(
                actor_id=finder_actor_id, roles=[CVDRole.FINDER]
            ),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        event_types = [e.event_type for e in stored_case.events]
        assert "participant_added" in event_types

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
        """CreateCaseOwnerParticipant does NOT record 'participant_added'."""
        bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        event_types = [e.event_type for e in stored_case.events]
        assert "participant_added" not in event_types
