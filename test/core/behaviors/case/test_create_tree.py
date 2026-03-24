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
Tests for case creation behavior tree composition (BT-3.1).

Verifies that CreateCaseBT correctly orchestrates case persistence,
CaseActor creation, and outbox update. Also verifies idempotency.

Per specs/behavior-tree-integration.md BT-06, specs/case-management.md
CM-02, and specs/idempotency.md ID-04-004.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronReport,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.create_tree import create_create_case_tree


@pytest.fixture
def datalayer():
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def actor_id():
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(datalayer, actor_id):
    obj = VultronCaseActor(as_id=actor_id, name="Vendor Co")
    datalayer.create(obj)
    return obj


@pytest.fixture
def report(datalayer):
    obj = VultronReport(
        as_id="https://example.org/reports/CVE-2024-001",
        name="Test Vulnerability Report",
        content="Buffer overflow in component X",
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def case_obj(report):
    return VultronCase(
        as_id="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report.as_id],
    )


@pytest.fixture
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


# ============================================================================
# Tree structure tests
# ============================================================================


def test_create_create_case_tree_returns_selector(case_obj, actor_id):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor_id)
    assert tree is not None
    assert tree.name == "CreateCaseBT"
    assert hasattr(tree, "children")
    assert len(tree.children) == 2


def test_create_case_tree_first_child_is_idempotency_check(case_obj, actor_id):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor_id)
    from vultron.core.behaviors.case.nodes import CheckCaseAlreadyExists

    assert isinstance(tree.children[0], CheckCaseAlreadyExists)


def test_create_case_tree_second_child_is_sequence(case_obj, actor_id):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor_id)
    import py_trees

    assert isinstance(tree.children[1], py_trees.composites.Sequence)


# ============================================================================
# Execution tests
# ============================================================================


def test_create_case_tree_succeeds(datalayer, actor, case_obj, bridge):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor.as_id, activity=None
    )
    assert result.status == Status.SUCCESS


def test_create_case_tree_persists_case(datalayer, actor, case_obj, bridge):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)
    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    assert stored.as_id == case_obj.as_id


def test_create_case_tree_creates_case_actor(
    datalayer, actor, case_obj, bridge
):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)
    # Verify at least one CaseActor exists for this case
    # (also checking via read fallback if stored under different table)
    found = False
    for table_name in datalayer._db.tables():
        for rec in datalayer._db.table(table_name).all():
            data = rec.get("data_", {})
            if data.get("context") == case_obj.as_id:
                found = True
                break
        if found:
            break
    assert found, "CaseActor was not created in DataLayer"


def test_create_case_tree_emits_activity_to_outbox(
    datalayer, actor, case_obj, bridge
):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)
    updated_actor = datalayer.read(actor.as_id)
    assert updated_actor is not None
    assert len(updated_actor.outbox.items) > 0


# ============================================================================
# Idempotency tests
# ============================================================================


def test_create_case_tree_idempotent(datalayer, actor, case_obj, bridge):
    """Running the tree twice succeeds and does not duplicate the case."""
    tree1 = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    result1 = bridge.execute_with_setup(
        tree=tree1, actor_id=actor.as_id, activity=None
    )
    assert result1.status == Status.SUCCESS

    tree2 = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    result2 = bridge.execute_with_setup(
        tree=tree2, actor_id=actor.as_id, activity=None
    )
    assert result2.status == Status.SUCCESS

    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    assert stored.as_id == case_obj.as_id


# ============================================================================
# CM-02-008 vendor initial participant tests (SC-1.3)
# ============================================================================


def test_create_case_tree_sets_attributed_to(
    datalayer, actor, case_obj, bridge
):
    """VulnerabilityCase.attributed_to MUST be set to the actor_id (CM-02-008)."""
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)
    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    attributed = (
        stored.attributed_to.as_id
        if hasattr(stored.attributed_to, "as_id")
        else stored.attributed_to
    )
    assert attributed == actor.as_id


def test_create_case_tree_creates_vendor_participant(
    datalayer, actor, case_obj, bridge
):
    """A VendorParticipant SHOULD be created and added to case_participants (CM-02-008)."""
    from vultron.core.states.roles import CVDRoles as CVDRole

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)

    stored_case = datalayer.read(case_obj.as_id)
    assert stored_case is not None
    assert len(stored_case.case_participants) >= 1

    found_vendor = False
    for table_name in datalayer._db.tables():
        for rec in datalayer._db.table(table_name).all():
            data = rec.get("data_", {})
            at = data.get("attributed_to")
            ctx = data.get("context")
            roles = data.get("case_roles", [])
            if (
                at == actor.as_id
                and ctx == case_obj.as_id
                and CVDRole.VENDOR.name in roles
            ):
                found_vendor = True
                break
        if found_vendor:
            break
    assert found_vendor, "VendorParticipant was not found in DataLayer"


def test_create_case_tree_vendor_participant_seeded_with_rm_valid(
    datalayer, actor, case_obj, bridge
):
    """VendorParticipant MUST be seeded with rm_state=RM.VALID at case creation (ADR-0013)."""
    from vultron.core.states.rm import RM

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)

    stored_case = datalayer.read(case_obj.as_id)
    assert stored_case is not None

    found_valid = False
    for p_ref in stored_case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.as_id
        participant = datalayer.read(p_id)
        if participant is None:
            continue
        p_actor = participant.attributed_to
        p_actor_id = p_actor if isinstance(p_actor, str) else p_actor.as_id
        if p_actor_id != actor.as_id:
            continue
        statuses = participant.participant_statuses
        assert statuses, "Participant has no status history"
        latest_rm = getattr(statuses[-1], "rm_state", None)
        assert (
            latest_rm == RM.VALID
        ), f"Expected initial rm_state=RM.VALID, got {latest_rm}"
        found_valid = True

    assert found_valid, "No vendor participant found for actor in case"


# ============================================================================
# CM-02-009 event log backfill tests (TECHDEBT-10)
# ============================================================================


def test_create_case_tree_records_case_created_event(
    datalayer, actor, case_obj, bridge
):
    """A case_created event MUST be recorded in the case event log (CM-02-009)."""
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)

    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    event_types = [e.event_type for e in stored.events]
    assert "case_created" in event_types


def test_create_case_tree_case_created_event_uses_case_id(
    datalayer, actor, case_obj, bridge
):
    """The case_created event MUST reference the case ID as object_id (CM-02-009)."""
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)

    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    created_events = [
        e for e in stored.events if e.event_type == "case_created"
    ]
    assert len(created_events) == 1
    assert created_events[0].object_id == case_obj.as_id


def test_create_case_tree_records_offer_received_event_when_present(
    datalayer, actor, actor_id, case_obj, bridge
):
    """If the triggering activity has in_reply_to, an offer_received event MUST be recorded (CM-02-009)."""
    from vultron.core.models.vultron_types import VultronOffer

    offer_id = "https://example.org/activities/offer-001"

    class FakeActivity:
        in_reply_to = VultronOffer(as_id=offer_id, actor=actor_id)

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(
        tree=tree, actor_id=actor.as_id, activity=FakeActivity()
    )

    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    event_types = [e.event_type for e in stored.events]
    assert "offer_received" in event_types

    offer_events = [
        e for e in stored.events if e.event_type == "offer_received"
    ]
    assert len(offer_events) == 1
    assert offer_events[0].object_id == offer_id


def test_create_case_tree_no_offer_received_event_without_in_reply_to(
    datalayer, actor, case_obj, bridge
):
    """If the triggering activity has no in_reply_to, no offer_received event is recorded."""
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)

    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    event_types = [e.event_type for e in stored.events]
    assert "offer_received" not in event_types


def test_create_case_tree_offer_received_before_case_created(
    datalayer, actor, actor_id, case_obj, bridge
):
    """offer_received event MUST appear before case_created in the event log."""
    from vultron.core.models.vultron_types import VultronOffer

    offer_id = "https://example.org/activities/offer-002"

    class FakeActivity:
        in_reply_to = VultronOffer(as_id=offer_id, actor=actor_id)

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(
        tree=tree, actor_id=actor.as_id, activity=FakeActivity()
    )

    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    event_types = [e.event_type for e in stored.events]
    assert event_types.index("offer_received") < event_types.index(
        "case_created"
    )


def test_create_case_tree_events_have_trusted_timestamps(
    datalayer, actor, case_obj, bridge
):
    """Case event timestamps MUST be server-generated (CM-02-009)."""
    from datetime import timezone

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)

    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    assert len(stored.events) >= 1
    for evt in stored.events:
        assert evt.received_at is not None
        assert evt.received_at.tzinfo is not None
        assert evt.received_at.tzinfo == timezone.utc
