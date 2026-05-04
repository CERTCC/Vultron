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

Per specs/behavior-tree-integration.yaml BT-06, specs/case-management.yaml
CM-02, and specs/idempotency.yaml ID-04-004.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronReport,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.create_tree import create_create_case_tree


@pytest.fixture
def datalayer():
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
        id_="https://example.org/reports/CVE-2024-001",
        name="Test Vulnerability Report",
        content="Buffer overflow in component X",
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def case_obj(report):
    return VultronCase(
        id_="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report.id_],
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
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor.id_, activity=None
    )
    assert result.status == Status.SUCCESS


def test_create_case_tree_persists_case(datalayer, actor, case_obj, bridge):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)
    stored = datalayer.read(case_obj.id_)
    assert stored is not None
    assert stored.id_ == case_obj.id_


def test_create_case_tree_creates_case_actor(
    datalayer, actor, case_obj, bridge
):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)
    # Verify at least one actor-context record was created for this case.
    from sqlmodel import Session, select

    from vultron.adapters.driven.datalayer_sqlite import VultronObjectRecord

    found = False
    with Session(datalayer._engine) as session:
        rows = session.exec(select(VultronObjectRecord)).all()
        for row in rows:
            data = row.data or {}
            if data.get("context") == case_obj.id_:
                found = True
                break
    assert found, "CaseActor was not created in DataLayer"


def test_create_case_tree_emits_activity_to_outbox(
    datalayer, actor, case_obj, bridge
):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)
    updated_actor = datalayer.read(actor.id_)
    assert updated_actor is not None
    assert len(updated_actor.outbox.items) > 0


# ============================================================================
# Idempotency tests
# ============================================================================


def test_create_case_tree_idempotent(datalayer, actor, case_obj, bridge):
    """Running the tree twice succeeds and does not duplicate the case."""
    tree1 = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    result1 = bridge.execute_with_setup(
        tree=tree1, actor_id=actor.id_, activity=None
    )
    assert result1.status == Status.SUCCESS

    tree2 = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    result2 = bridge.execute_with_setup(
        tree=tree2, actor_id=actor.id_, activity=None
    )
    assert result2.status == Status.SUCCESS

    stored = datalayer.read(case_obj.id_)
    assert stored is not None
    assert stored.id_ == case_obj.id_


# ============================================================================
# CM-02-008 vendor initial participant tests (SC-1.3)
# ============================================================================


def test_create_case_tree_sets_attributed_to(
    datalayer, actor, case_obj, bridge
):
    """VulnerabilityCase.attributed_to MUST be set to the actor_id (CM-02-008)."""
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)
    stored = datalayer.read(case_obj.id_)
    assert stored is not None
    attributed = (
        stored.attributed_to.id_
        if hasattr(stored.attributed_to, "id_")
        else stored.attributed_to
    )
    assert attributed == actor.id_


def test_create_case_tree_creates_case_owner_participant(
    datalayer, actor, case_obj, bridge
):
    """A case-owner participant SHOULD be created and added to case_participants (CM-02-008)."""
    from vultron.core.states.roles import CVDRole

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)

    stored_case = datalayer.read(case_obj.id_)
    assert stored_case is not None
    assert len(stored_case.case_participants) >= 1

    found_owner = False
    from sqlmodel import Session, select

    from vultron.adapters.driven.datalayer_sqlite import VultronObjectRecord

    with Session(datalayer._engine) as session:
        rows = session.exec(select(VultronObjectRecord)).all()
        for row in rows:
            data = row.data or {}
            at = data.get("attributed_to")
            ctx = data.get("context")
            roles = data.get("case_roles", [])
            if (
                at == actor.id_
                and ctx == case_obj.id_
                and CVDRole.CASE_OWNER.value in roles
            ):
                found_owner = True
                break
    assert found_owner, "Case-owner participant was not found in DataLayer"


def test_create_case_tree_case_owner_participant_includes_config_roles(
    datalayer, actor, case_obj, bridge
):
    """CreateCaseOwnerParticipant includes config roles + CASE_OWNER (CFG-07-004)."""
    from vultron.core.models.actor_config import ActorConfig
    from vultron.core.states.roles import CVDRole

    config = ActorConfig(default_case_roles=[CVDRole.COORDINATOR])
    tree = create_create_case_tree(
        case_obj=case_obj, actor_id=actor.id_, actor_config=config
    )
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)

    from sqlmodel import Session, select

    from vultron.adapters.driven.datalayer_sqlite import VultronObjectRecord

    with Session(datalayer._engine) as session:
        rows = session.exec(select(VultronObjectRecord)).all()
        for row in rows:
            data = row.data or {}
            at = data.get("attributed_to")
            ctx = data.get("context")
            roles = data.get("case_roles", [])
            if at == actor.id_ and ctx == case_obj.id_:
                assert CVDRole.CASE_OWNER.value in roles
                assert CVDRole.COORDINATOR.value in roles
                return
    pytest.fail("No participant found for actor in case")


def test_create_case_tree_vendor_participant_seeded_with_rm_valid(
    datalayer, actor, case_obj, bridge
):
    """VendorParticipant MUST be seeded with rm_state=RM.VALID at case creation (ADR-0013)."""
    from vultron.core.states.rm import RM

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)

    stored_case = datalayer.read(case_obj.id_)
    assert stored_case is not None

    found_valid = False
    for p_ref in stored_case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
        participant = datalayer.read(p_id)
        if participant is None:
            continue
        p_actor = participant.attributed_to
        p_actor_id = p_actor if isinstance(p_actor, str) else p_actor.id_
        if p_actor_id != actor.id_:
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
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)

    stored = datalayer.read(case_obj.id_)
    assert stored is not None
    event_types = [e.event_type for e in stored.events]
    assert "case_created" in event_types


def test_create_case_tree_case_created_event_uses_case_id(
    datalayer, actor, case_obj, bridge
):
    """The case_created event MUST reference the case ID as object_id (CM-02-009)."""
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)

    stored = datalayer.read(case_obj.id_)
    assert stored is not None
    created_events = [
        e for e in stored.events if e.event_type == "case_created"
    ]
    assert len(created_events) == 1
    assert created_events[0].object_id == case_obj.id_


def test_create_case_tree_records_offer_received_event_when_present(
    datalayer, actor, actor_id, case_obj, bridge
):
    """If the triggering activity has in_reply_to, an offer_received event MUST be recorded (CM-02-009)."""
    from vultron.core.models.vultron_types import VultronOffer

    offer_id = "https://example.org/activities/offer-001"

    class FakeActivity:
        in_reply_to = VultronOffer(id_=offer_id, actor=actor_id)

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(
        tree=tree, actor_id=actor.id_, activity=FakeActivity()
    )

    stored = datalayer.read(case_obj.id_)
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
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)

    stored = datalayer.read(case_obj.id_)
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
        in_reply_to = VultronOffer(id_=offer_id, actor=actor_id)

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(
        tree=tree, actor_id=actor.id_, activity=FakeActivity()
    )

    stored = datalayer.read(case_obj.id_)
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

    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)

    stored = datalayer.read(case_obj.id_)
    assert stored is not None
    assert len(stored.events) >= 1
    for evt in stored.events:
        assert evt.received_at is not None
        assert evt.received_at.tzinfo is not None
        assert evt.received_at.tzinfo == timezone.utc


# ============================================================================
# D5-6-LOGCTX: outbox activity log content tests
# ============================================================================


def test_create_case_tree_logs_create_case_activity_type(
    datalayer, actor, case_obj, bridge, caplog
):
    """UpdateActorOutbox MUST log 'Create' activity type (D5-6-LOGCTX)."""
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    with caplog.at_level("INFO"):
        bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)
    assert "Create" in caplog.text


def test_create_case_tree_logs_case_id_in_outbox_message(
    datalayer, actor, case_obj, bridge, caplog
):
    """UpdateActorOutbox MUST log the case ID in the outbox message (D5-6-LOGCTX)."""
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.id_)
    with caplog.at_level("INFO"):
        bridge.execute_with_setup(tree=tree, actor_id=actor.id_, activity=None)
    assert case_obj.id_ in caplog.text
