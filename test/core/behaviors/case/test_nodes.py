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

Per specs/behavior-tree-node-design.md BTND-02-001, BTND-03-001, BTND-04-001.
"""

import logging

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
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
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def datalayer():
    """In-memory DataLayer for testing."""
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def actor_id():
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(datalayer, actor_id):
    obj = VultronCaseActor(id_=actor_id, name="Vendor Co")
    datalayer.create(obj)
    return obj


@pytest.fixture
def report(datalayer):
    obj = VultronReport(
        name="TEST-001",
        content="Test vulnerability report",
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def case_obj(datalayer, report):
    case = VultronCase(
        id_="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report.id_],
    )
    datalayer.create(case)
    return case


def setup_node_blackboard(node, datalayer, actor_id, extra_keys=None):
    """Set up a node's blackboard with DataLayer and actor_id."""
    node.setup()
    node.blackboard.register_key(
        key="datalayer", access=py_trees.common.Access.WRITE
    )
    node.blackboard.register_key(
        key="actor_id", access=py_trees.common.Access.WRITE
    )
    node.blackboard.datalayer = datalayer
    node.blackboard.actor_id = actor_id
    if extra_keys:
        for key, value in extra_keys.items():
            node.blackboard.register_key(
                key=key, access=py_trees.common.Access.WRITE
            )
            node.blackboard.set(key, value, overwrite=True)
    node.initialise()


# ---------------------------------------------------------------------------
# P360-FIX-1: UpdateActorOutbox re-export tests
# ---------------------------------------------------------------------------


class TestUpdateActorOutboxReExport:
    """UpdateActorOutbox is the same object in all three modules (BTND-04-001)."""

    def test_case_nodes_re_exports_from_helpers(self):
        assert UpdateActorOutbox is UpdateActorOutboxHelper

    def test_report_nodes_re_exports_from_helpers(self):
        assert UpdateActorOutboxReport is UpdateActorOutboxHelper

    def test_shared_class_is_not_duplicate(self):
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
        self, datalayer, case_obj, actor_id
    ):
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRoles.VENDOR],
        )
        result = _create_and_attach_participant(
            datalayer,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        assert datalayer.read(participant.id_) is not None

    def test_attaches_participant_to_case(self, datalayer, case_obj, actor_id):
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRoles.VENDOR],
        )
        result = _create_and_attach_participant(
            datalayer,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        assert participant.id_ in result.case_participants

    def test_updates_actor_participant_index(
        self, datalayer, case_obj, actor_id
    ):
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRoles.VENDOR],
        )
        result = _create_and_attach_participant(
            datalayer,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        assert result.actor_participant_index.get(actor_id) == participant.id_

    def test_returns_unsaved_case(self, datalayer, case_obj, actor_id):
        """The returned case is unsaved; the caller controls the final save."""
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRoles.VENDOR],
        )
        result = _create_and_attach_participant(
            datalayer,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        # Before the caller saves, the persisted version has no participant yet
        persisted = datalayer.read(case_obj.id_)
        assert participant.id_ not in persisted.case_participants

    def test_idempotent_participant_creation(
        self, datalayer, case_obj, actor_id
    ):
        """Calling twice does not create a duplicate participant."""
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRoles.VENDOR],
        )
        node_logger = logging.getLogger("test")
        _create_and_attach_participant(
            datalayer, participant, case_obj.id_, actor_id, node_logger
        )
        datalayer.save(datalayer.read(case_obj.id_))  # simulate caller save

        result2 = _create_and_attach_participant(
            datalayer, participant, case_obj.id_, actor_id, node_logger
        )
        assert result2 is not None
        # Still only one entry for this participant
        assert result2.case_participants.count(participant.id_) == 1

    def test_returns_none_when_case_not_found(self, datalayer, actor_id):
        participant = VultronParticipant(
            attributed_to=actor_id,
            context="https://example.org/cases/missing",
            case_roles=[CVDRoles.VENDOR],
        )
        result = _create_and_attach_participant(
            datalayer,
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
        self, datalayer, actor, case_obj
    ):
        node = CreateInitialVendorParticipant()
        setup_node_blackboard(
            node,
            datalayer,
            actor.id_,
            extra_keys={"case_id": case_obj.id_},
        )
        result = node.update()
        assert result == Status.SUCCESS

        stored_case = datalayer.read(case_obj.id_)
        assert any(
            p == stored_case.actor_participant_index.get(actor.id_)
            for p in stored_case.case_participants
        )

    def test_idempotent(self, datalayer, actor, case_obj):
        """Running twice does not error."""
        node1 = CreateInitialVendorParticipant()
        setup_node_blackboard(
            node1, datalayer, actor.id_, extra_keys={"case_id": case_obj.id_}
        )
        assert node1.update() == Status.SUCCESS

        node2 = CreateInitialVendorParticipant()
        setup_node_blackboard(
            node2, datalayer, actor.id_, extra_keys={"case_id": case_obj.id_}
        )
        assert node2.update() == Status.SUCCESS

    def test_fails_when_case_not_found(self, datalayer, actor):
        node = CreateInitialVendorParticipant()
        setup_node_blackboard(
            node,
            datalayer,
            actor.id_,
            extra_keys={"case_id": "https://example.org/cases/missing"},
        )
        result = node.update()
        assert result == Status.FAILURE


# ---------------------------------------------------------------------------
# P360-FIX-2: CreateCaseParticipantNode uses shared helper
# ---------------------------------------------------------------------------


class TestCreateCaseParticipantNode:
    """CreateCaseParticipantNode preserves its distinct semantics after refactor."""

    @pytest.fixture
    def finder_actor_id(self):
        return "https://example.org/actors/finder"

    def test_creates_and_attaches_participant(
        self, datalayer, actor, case_obj, finder_actor_id
    ):
        node = CreateCaseParticipantNode(
            actor_id=finder_actor_id, roles=[CVDRoles.FINDER]
        )
        setup_node_blackboard(
            node,
            datalayer,
            actor.id_,
            extra_keys={"case_id": case_obj.id_},
        )
        result = node.update()
        assert result == Status.SUCCESS

        stored_case = datalayer.read(case_obj.id_)
        assert finder_actor_id in stored_case.actor_participant_index

    def test_records_participant_added_event(
        self, datalayer, actor, case_obj, finder_actor_id
    ):
        """CreateCaseParticipantNode records 'participant_added' on the case."""
        node = CreateCaseParticipantNode(
            actor_id=finder_actor_id, roles=[CVDRoles.FINDER]
        )
        setup_node_blackboard(
            node,
            datalayer,
            actor.id_,
            extra_keys={"case_id": case_obj.id_},
        )
        node.update()

        stored_case = datalayer.read(case_obj.id_)
        event_types = [e.event_type for e in stored_case.events]
        assert "participant_added" in event_types

    def test_emits_add_participant_activity(
        self, datalayer, actor, case_obj, finder_actor_id
    ):
        """CreateCaseParticipantNode queues AddParticipantToCaseActivity."""
        node = CreateCaseParticipantNode(
            actor_id=finder_actor_id, roles=[CVDRoles.FINDER]
        )
        setup_node_blackboard(
            node,
            datalayer,
            actor.id_,
            extra_keys={"case_id": case_obj.id_},
        )
        node.update()

        stored_actor = datalayer.read(actor.id_)
        outbox_ids = stored_actor.outbox.items if stored_actor else []
        found = any(
            isinstance(datalayer.read(oid), AddParticipantToCaseActivity)
            for oid in outbox_ids
        )
        assert found

    def test_does_not_record_participant_added_event_for_vendor(
        self, datalayer, actor, case_obj
    ):
        """CreateInitialVendorParticipant does NOT record 'participant_added'."""
        node = CreateInitialVendorParticipant()
        setup_node_blackboard(
            node, datalayer, actor.id_, extra_keys={"case_id": case_obj.id_}
        )
        node.update()

        stored_case = datalayer.read(case_obj.id_)
        event_types = [e.event_type for e in stored_case.events]
        assert "participant_added" not in event_types


# ---------------------------------------------------------------------------
# P360-FIX-3: RecordCaseCreationEvents blackboard key contract
# ---------------------------------------------------------------------------


class TestRecordCaseCreationEvents:
    """Blackboard keys are declared; activity key is optional (BTND-03-001/02)."""

    def test_registers_activity_key_in_setup(self, datalayer, actor, case_obj):
        """setup() must register 'activity' as a READ key (BTND-03-001).

        Verify that accessing the 'activity' key via the blackboard client
        raises KeyError (unset) rather than AttributeError (unregistered),
        confirming the key was properly declared in setup().
        """
        node = RecordCaseCreationEvents(case_obj=case_obj)
        setup_node_blackboard(
            node, datalayer, actor.id_, extra_keys={"case_id": case_obj.id_}
        )
        # The key is registered READ; accessing an unset registered key
        # raises KeyError, NOT AttributeError.
        with pytest.raises(KeyError):
            node.blackboard.get("activity")

    def test_records_case_created_event_without_activity(
        self, datalayer, actor, case_obj
    ):
        """Without activity on blackboard, case_created event is recorded."""
        node = RecordCaseCreationEvents(case_obj=case_obj)
        setup_node_blackboard(
            node,
            datalayer,
            actor.id_,
            extra_keys={"case_id": case_obj.id_},
        )
        result = node.update()
        assert result == Status.SUCCESS

        stored_case = datalayer.read(case_obj.id_)
        event_types = [e.event_type for e in stored_case.events]
        assert "case_created" in event_types

    def test_records_offer_received_event_when_activity_has_in_reply_to(
        self, datalayer, actor, case_obj, report
    ):
        """With activity.in_reply_to set, offer_received event is backfilled."""
        from unittest.mock import MagicMock

        offer_mock = MagicMock()
        offer_mock.id_ = "https://example.org/activities/offer-001"
        activity_mock = MagicMock()
        activity_mock.in_reply_to = offer_mock

        node = RecordCaseCreationEvents(case_obj=case_obj)
        setup_node_blackboard(
            node,
            datalayer,
            actor.id_,
            extra_keys={
                "case_id": case_obj.id_,
                "activity": activity_mock,
            },
        )
        result = node.update()
        assert result == Status.SUCCESS

        stored_case = datalayer.read(case_obj.id_)
        event_types = [e.event_type for e in stored_case.events]
        assert "offer_received" in event_types
        assert "case_created" in event_types

    def test_no_offer_received_when_activity_lacks_in_reply_to(
        self, datalayer, actor, case_obj
    ):
        """Activity without in_reply_to produces only case_created event."""
        from unittest.mock import MagicMock

        activity_mock = MagicMock()
        activity_mock.in_reply_to = None

        node = RecordCaseCreationEvents(case_obj=case_obj)
        setup_node_blackboard(
            node,
            datalayer,
            actor.id_,
            extra_keys={
                "case_id": case_obj.id_,
                "activity": activity_mock,
            },
        )
        result = node.update()
        assert result == Status.SUCCESS

        stored_case = datalayer.read(case_obj.id_)
        event_types = [e.event_type for e in stored_case.events]
        assert "offer_received" not in event_types
        assert "case_created" in event_types
