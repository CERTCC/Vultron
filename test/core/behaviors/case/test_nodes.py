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
- CreateInitialVendorParticipant and CreateCaseParticipantNode use of helper
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
    CreateCaseParticipantNode,
    CreateInitialVendorParticipant,
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
from vultron.core.states.roles import CVDRoles
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
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
            case_roles=[CVDRoles.VENDOR],
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
            case_roles=[CVDRoles.VENDOR],
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
            case_roles=[CVDRoles.VENDOR],
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
            case_roles=[CVDRoles.VENDOR],
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
            case_roles=[CVDRoles.VENDOR],
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
            case_roles=[CVDRoles.VENDOR],
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
# P360-FIX-2: CreateInitialVendorParticipant uses shared helper
# ---------------------------------------------------------------------------


class TestCreateInitialVendorParticipant:
    """CreateInitialVendorParticipant preserves semantics after refactor."""

    def test_creates_and_attaches_vendor_participant(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            CreateInitialVendorParticipant(),
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
            CreateInitialVendorParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result1)

        result2 = bt_scenario.run(
            CreateInitialVendorParticipant(),
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
            CreateInitialVendorParticipant(),
            actor_id=actor_id,
            case_id="https://example.org/cases/missing",
        )
        bt_scenario.assert_failure(result)


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
                actor_id=finder_actor_id, roles=[CVDRoles.FINDER]
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
                actor_id=finder_actor_id, roles=[CVDRoles.FINDER]
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
                actor_id=finder_actor_id, roles=[CVDRoles.FINDER]
            ),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        stored_actor = cast(Any, bt_scenario.dl.read(actor_id))
        outbox_ids = stored_actor.outbox.items if stored_actor else []
        found = any(
            isinstance(bt_scenario.dl.read(oid), as_Add) for oid in outbox_ids
        )
        assert found

    def test_does_not_record_participant_added_event_for_vendor(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """CreateInitialVendorParticipant does NOT record 'participant_added'."""
        bt_scenario.run(
            CreateInitialVendorParticipant(),
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
