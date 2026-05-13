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
Tests for case behavior tree nodes (P360-FIX-1, P360-FIX-2, P360-FIX-3).

Covers:
- UpdateActorOutbox re-export via case.nodes and report.nodes (P360-FIX-1)
- _create_and_attach_participant shared helper (P360-FIX-2)
- CreateCaseOwnerParticipant and CreateCaseParticipantNode use of helper
- RecordCaseCreationEvents blackboard key contract (P360-FIX-3)

Uses BTTestScenario (from ``test.core.behaviors.bt_harness``) as the single
execution path for BT node tests; no direct ``node.update()`` /
``node.blackboard.register_key()`` calls appear here.

Per specs/behavior-tree-node-design.yaml BTND-02-001, BTND-03-001, BTND-04-001
and GitHub issue #401.
"""

import logging
from typing import cast, Any
from unittest.mock import MagicMock

import pytest

from vultron.core.behaviors.case.nodes import (
    CreateCaseOwnerParticipant,
    CreateCaseParticipantNode,
    RecordCaseCreationEvents,
    UpdateActorOutbox,
    _create_and_attach_participant,
)
from vultron.core.behaviors.helpers import (
    UpdateActorOutbox as UpdateActorOutboxHelper,
)
from vultron.core.behaviors.report.nodes import (
    UpdateActorOutbox as UpdateActorOutboxReport,
)
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronParticipant,
    VultronReport,
)
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
    obj = VultronReport(
        name="TEST-001",
        content="Test vulnerability report",
    )
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
# P360-FIX-1: UpdateActorOutbox re-export tests
# ---------------------------------------------------------------------------


class TestUpdateActorOutboxReExport:
    """UpdateActorOutbox is the same object in all three modules (BTND-04-001)."""

    def test_case_nodes_re_exports_from_helpers(self) -> None:
        assert UpdateActorOutbox is UpdateActorOutboxHelper

    def test_report_nodes_re_exports_from_helpers(self) -> None:
        assert UpdateActorOutboxReport is UpdateActorOutboxHelper

    def test_shared_class_is_not_duplicate(self) -> None:
        """There is exactly one UpdateActorOutbox class definition."""
        assert (
            UpdateActorOutbox
            is UpdateActorOutboxReport
            is UpdateActorOutboxHelper
        )


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
        from typing import cast, Any

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
        from typing import cast, Any
        from vultron.core.models.actor_config import ActorConfig

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

        stored_actor = cast(Any, bt_scenario.dl.read(actor_id))
        outbox_ids = stored_actor.outbox.items if stored_actor else []
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


# ---------------------------------------------------------------------------
# P360-FIX-3: RecordCaseCreationEvents blackboard key contract
# ---------------------------------------------------------------------------


class TestRecordCaseCreationEvents:
    """Blackboard keys are declared; activity key is optional (BTND-03-001/02)."""

    def test_activity_key_optional_node_succeeds_without_it(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """Node runs successfully with no 'activity' on the blackboard.

        This behavioral test verifies BTND-03-001: if the 'activity' key were
        not properly registered by setup(), accessing it would raise
        AttributeError (unregistered) rather than being handled gracefully.
        Succeeding without an activity proves the key contract is correct.
        """
        result = bt_scenario.run(
            RecordCaseCreationEvents(case_obj=case_obj),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

    def test_records_case_created_event_without_activity(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """Without activity on blackboard, case_created event is recorded."""
        result = bt_scenario.run(
            RecordCaseCreationEvents(case_obj=case_obj),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        event_types = [e.event_type for e in stored_case.events]
        assert "case_created" in event_types

    def test_records_offer_received_event_when_activity_has_in_reply_to(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        report: VultronReport,
        actor_id: str,
    ) -> None:
        """With activity.in_reply_to set, offer_received event is backfilled."""
        offer_mock = MagicMock()
        offer_mock.id_ = "https://example.org/activities/offer-001"
        activity_mock = MagicMock()
        activity_mock.in_reply_to = offer_mock

        result = bt_scenario.run(
            RecordCaseCreationEvents(case_obj=case_obj),
            actor_id=actor_id,
            case_id=case_obj.id_,
            activity=activity_mock,
        )
        bt_scenario.assert_success(result)

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        event_types = [e.event_type for e in stored_case.events]
        assert "offer_received" in event_types
        assert "case_created" in event_types

    def test_no_offer_received_when_activity_lacks_in_reply_to(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """Activity without in_reply_to produces only case_created event."""
        activity_mock = MagicMock()
        activity_mock.in_reply_to = None

        result = bt_scenario.run(
            RecordCaseCreationEvents(case_obj=case_obj),
            actor_id=actor_id,
            case_id=case_obj.id_,
            activity=activity_mock,
        )
        bt_scenario.assert_success(result)

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        event_types = [e.event_type for e in stored_case.events]
        assert "offer_received" not in event_types
        assert "case_created" in event_types


# ---------------------------------------------------------------------------
# CreateCaseActorNode (blackboard variant) tests
# ---------------------------------------------------------------------------


class TestCreateCaseActorNodeBlackboard:
    """CreateCaseActorNode reads case_id from blackboard when not given at construction."""

    def test_creates_case_actor_from_blackboard_case_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """CreateCaseActorNode() (no args) succeeds and creates a CaseActor entity."""
        from vultron.core.behaviors.case.nodes import CreateCaseActorNode

        result = bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)

        # A Service (VultronCaseActor) should exist in the DataLayer.
        services = list(bt_scenario.dl.list_objects("Service"))
        case_actor_services = [
            s for s in services if getattr(s, "context", None) == case_obj.id_
        ]
        assert len(case_actor_services) >= 1

    def test_writes_case_actor_id_to_blackboard(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """CreateCaseActorNode() writes case_actor_id to the blackboard."""
        import py_trees
        from vultron.core.behaviors.case.nodes import CreateCaseActorNode

        bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        # py_trees stores global keys with a leading "/" prefix.
        stored = py_trees.blackboard.Blackboard.storage.get("/case_actor_id")
        assert stored is not None
        assert isinstance(stored, str)

    def test_registers_case_actor_participant(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """CreateCaseActorNode registers a CASE_MANAGER participant in the case."""
        from vultron.core.behaviors.case.nodes import CreateCaseActorNode

        bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        # Case Actor participant ID uses flat HTTP URL, not URN-based path.
        import hashlib

        case_id = case_obj.id_
        if case_id.startswith("urn:uuid:"):
            case_slug = case_id[len("urn:uuid:") :]
        else:
            case_slug = hashlib.sha256(case_id.encode()).hexdigest()[:12]

        from vultron.config import get_config

        base_url = get_config().server.base_url.rstrip("/")
        expected_participant_id = (
            f"{base_url}/actors/case-actor-{case_slug}/participant"
        )
        participant = bt_scenario.dl.read(expected_participant_id)
        assert participant is not None

    def test_fails_without_case_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        """CreateCaseActorNode() fails when case_id is not in blackboard."""
        import py_trees
        from vultron.core.behaviors.case.nodes import CreateCaseActorNode

        result = bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            # No case_id supplied
        )
        assert result.status == py_trees.common.Status.FAILURE


# ---------------------------------------------------------------------------
# SendOfferCaseManagerRoleNode tests
# ---------------------------------------------------------------------------


class TestSendOfferCaseManagerRoleNode:
    """SendOfferCaseManagerRoleNode queues Offer(CaseManagerRole) to Case Actor."""

    def test_queues_offer_and_writes_activity_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """SendOfferCaseManagerRoleNode writes activity_id to blackboard after Offer."""
        import py_trees
        from vultron.core.behaviors.case.nodes import (
            CreateCaseActorNode,
            SendOfferCaseManagerRoleNode,
        )

        # Run CreateCaseActorNode first to populate the DataLayer with the
        # Case Actor entity and participant.
        bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        # Retrieve the case_actor_id that was written to the blackboard.
        case_actor_id = py_trees.blackboard.Blackboard.storage.get(
            "/case_actor_id"
        )
        assert (
            case_actor_id is not None
        ), "CreateCaseActorNode must write case_actor_id"

        case_actor_participant_id = py_trees.blackboard.Blackboard.storage.get(
            "/case_actor_participant_id"
        )
        assert (
            case_actor_participant_id is not None
        ), "CreateCaseActorNode must write case_actor_participant_id"

        # Now run SendOfferCaseManagerRoleNode with the needed blackboard context.
        result = bt_scenario.run(
            SendOfferCaseManagerRoleNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            case_actor_id=case_actor_id,
            case_actor_participant_id=case_actor_participant_id,
        )
        bt_scenario.assert_success(result)

        activity_id = py_trees.blackboard.Blackboard.storage.get(
            "/activity_id"
        )
        assert activity_id is not None

    def test_fails_without_case_actor_id_in_blackboard(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """SendOfferCaseManagerRoleNode fails if case_actor_id is not in blackboard."""
        import py_trees
        from vultron.core.behaviors.case.nodes import (
            SendOfferCaseManagerRoleNode,
        )

        # Provide case_id but no case_actor_id — the participant exists in DL
        # but the blackboard is missing the case_actor_id key.
        result = bt_scenario.run(
            SendOfferCaseManagerRoleNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            # case_actor_id intentionally omitted
        )
        assert result.status == py_trees.common.Status.FAILURE
