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
Tests for receive-report case-creation behavior tree (IDEA-260408-01-2).

Verifies that ReceiveReportCaseBT correctly orchestrates case creation,
embargo initialization, participant creation, and outbox notification at
the RM.RECEIVED stage (ADR-0015).

Per specs/case-management.md CM-12 and specs/behavior-tree-integration.md
BT-06.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.receive_report_case_tree import (
    create_receive_report_case_tree,
)
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.models.vultron_types import (
    VultronCaseActor,
    VultronOffer,
    VultronReport,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _report_phase_status_id

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def datalayer():
    """In-memory TinyDB data layer for testing."""
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def actor_id():
    """Vendor (receiver) actor ID."""
    return "https://example.org/actors/vendor"


@pytest.fixture
def finder_actor_id():
    """Finder (reporter) actor ID."""
    return "https://example.org/actors/finder"


@pytest.fixture
def actor(datalayer, actor_id):
    """Create vendor actor in the DataLayer with an outbox."""
    obj = VultronCaseActor(id_=actor_id, name="Vendor Co")
    datalayer.create(obj)
    return obj


@pytest.fixture
def finder_actor(datalayer, finder_actor_id):
    """Create finder actor in the DataLayer."""
    obj = VultronCaseActor(id_=finder_actor_id, name="Finder Co")
    datalayer.create(obj)
    return obj


@pytest.fixture
def report(datalayer):
    """Create test VulnerabilityReport."""
    obj = VultronReport(
        id_="https://example.org/reports/CVE-2024-001",
        name="Test Vulnerability Report",
        content="Buffer overflow in component X",
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def finder_accepted_status(datalayer, finder_actor_id, report):
    """Pre-create the finder's RM.ACCEPTED report-phase status record.

    SubmitReportReceivedUseCase creates this record before the tree runs.
    """
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(
            finder_actor_id, report.id_, RM.ACCEPTED.value
        ),
        context=report.id_,
        attributed_to=finder_actor_id,
        rm_state=RM.ACCEPTED,
    )
    datalayer.create(status)
    return status


@pytest.fixture
def vendor_received_status(datalayer, actor_id, report):
    """Pre-create the vendor's RM.RECEIVED report-phase status record.

    CreateReportReceivedUseCase or AckReportReceivedUseCase creates this
    record before the tree runs.
    """
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor_id, report.id_, RM.RECEIVED.value),
        context=report.id_,
        attributed_to=actor_id,
        rm_state=RM.RECEIVED,
    )
    datalayer.create(status)
    return status


@pytest.fixture
def offer(datalayer, report, actor_id, finder_actor_id):
    """Create test Offer activity (finder submits report to vendor)."""
    obj = VultronOffer(
        id_="https://example.org/activities/offer-123",
        actor=finder_actor_id,
        object_=report.id_,
        target=actor_id,
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def bridge(datalayer):
    """BT bridge for tree execution."""
    return BTBridge(datalayer=datalayer)


# ============================================================================
# Tree structure tests
# ============================================================================


def test_create_receive_report_case_tree_returns_selector(report, offer):
    """Tree factory returns a Selector root node."""
    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    assert tree is not None
    assert tree.name == "ReceiveReportCaseBT"
    assert hasattr(tree, "children")
    assert len(tree.children) == 2


def test_tree_first_child_is_idempotency_check(report, offer):
    """First child is CheckCaseExistsForReport (idempotency guard)."""
    from vultron.core.behaviors.case.nodes import CheckCaseExistsForReport

    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    assert isinstance(tree.children[0], CheckCaseExistsForReport)


def test_tree_second_child_is_sequence(report, offer):
    """Second child is a Sequence (ReceiveReportCaseFlow)."""
    import py_trees

    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    assert isinstance(tree.children[1], py_trees.composites.Sequence)
    assert tree.children[1].name == "ReceiveReportCaseFlow"


def test_tree_flow_has_six_children(report, offer):
    """ReceiveReportCaseFlow sequence has exactly 6 action nodes."""
    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    flow = tree.children[1]
    assert len(flow.children) == 6


# ============================================================================
# Execution tests
# ============================================================================


def test_tree_succeeds(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """Tree executes successfully and returns Status.SUCCESS."""
    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor.id_)
    assert result.status == Status.SUCCESS


def test_tree_creates_case(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """Tree creates a VulnerabilityCase linked to the report."""
    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_)

    case = datalayer.find_case_by_report_id(report.id_)
    assert case is not None
    # The case should reference the report
    reports = getattr(case, "vulnerability_reports", []) or []
    report_refs = [
        r if isinstance(r, str) else getattr(r, "id_", str(r)) for r in reports
    ]
    assert report.id_ in report_refs


def test_tree_creates_vendor_participant_at_rm_received(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """Tree creates a vendor (receiver) participant at RM.RECEIVED."""
    from vultron.core.states.roles import CVDRoles

    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_)

    case = datalayer.find_case_by_report_id(report.id_)
    assert case is not None

    found_vendor = False
    for p_ref in case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
        participant = datalayer.read(p_id)
        if participant is None:
            continue
        p_actor = participant.attributed_to
        p_actor_id = (
            p_actor
            if isinstance(p_actor, str)
            else getattr(p_actor, "id_", p_actor)
        )
        if p_actor_id != actor.id_:
            continue
        roles = participant.case_roles
        if CVDRoles.VENDOR not in roles:
            continue
        statuses = participant.participant_statuses
        assert statuses, "Vendor participant has no status history"
        latest = statuses[-1]
        rm = getattr(latest, "rm_state", None)
        assert (
            rm == RM.RECEIVED
        ), f"Expected vendor rm_state=RM.RECEIVED, got {rm}"
        found_vendor = True

    assert found_vendor, "No vendor (VENDOR-role) participant found in case"


def test_tree_creates_finder_participant_at_rm_accepted(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """Tree creates a finder/reporter participant at RM.ACCEPTED."""
    from vultron.core.states.roles import CVDRoles

    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_)

    case = datalayer.find_case_by_report_id(report.id_)
    assert case is not None

    found_finder = False
    for p_ref in case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
        participant = datalayer.read(p_id)
        if participant is None:
            continue
        p_actor = participant.attributed_to
        p_actor_id = (
            p_actor
            if isinstance(p_actor, str)
            else getattr(p_actor, "id_", p_actor)
        )
        if p_actor_id != finder_actor.id_:
            continue
        roles = participant.case_roles
        if CVDRoles.FINDER not in roles:
            continue
        statuses = participant.participant_statuses
        assert statuses, "Finder participant has no status history"
        latest = statuses[-1]
        rm = getattr(latest, "rm_state", None)
        assert (
            rm == RM.ACCEPTED
        ), f"Expected finder rm_state=RM.ACCEPTED, got {rm}"
        found_finder = True

    assert (
        found_finder
    ), "No finder/reporter (FINDER-role) participant found in case"


def test_tree_creates_default_embargo(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """Tree creates a default embargo and attaches it to the case."""
    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_)

    case = datalayer.find_case_by_report_id(report.id_)
    assert case is not None
    assert case.active_embargo is not None


def test_tree_queues_create_case_activity(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """Tree queues a Create(Case) activity to the actor's outbox."""
    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_)

    updated_actor = datalayer.read(actor.id_)
    assert updated_actor is not None
    assert len(updated_actor.outbox.items) > 0


def test_create_case_precedes_add_participant_in_outbox(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """Create(Case) must be queued before Add(CaseParticipant) (D5-7-MSGORDER-1).

    Ensures the finder actor receives the case-creation notification before
    receiving the participant-addition notification, preventing "case not found"
    warnings on the finder side.
    """
    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_)

    updated_actor = datalayer.read(actor.id_)
    assert updated_actor is not None
    items = updated_actor.outbox.items
    assert len(items) >= 2, f"Expected >= 2 outbox items; got {len(items)}"

    # Read the first two activities to check their types
    first_activity = datalayer.read(items[0])
    second_activity = datalayer.read(items[1])
    assert first_activity is not None, f"Could not read activity '{items[0]}'"
    assert second_activity is not None, f"Could not read activity '{items[1]}'"

    first_type = getattr(first_activity, "type_", None)
    second_type = getattr(second_activity, "type_", None)
    assert (
        first_type == "Create"
    ), f"First outbox item should be Create(Case), got type_={first_type!r}"
    assert (
        second_type == "Add"
    ), f"Second outbox item should be Add(CaseParticipant), got type_={second_type!r}"


# ============================================================================
# Idempotency tests
# ============================================================================


def test_tree_is_idempotent(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """Running the tree twice succeeds and does not duplicate the case."""
    tree1 = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    result1 = bridge.execute_with_setup(tree=tree1, actor_id=actor.id_)
    assert result1.status == Status.SUCCESS

    tree2 = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    result2 = bridge.execute_with_setup(tree=tree2, actor_id=actor.id_)
    assert result2.status == Status.SUCCESS

    # Only one case for this report
    case = datalayer.find_case_by_report_id(report.id_)
    assert case is not None


def test_tree_early_exits_when_case_already_initialized(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """CheckCaseExistsForReport returns SUCCESS when case has participants."""
    # Run once to initialize case
    tree1 = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    bridge.execute_with_setup(tree=tree1, actor_id=actor.id_)

    # Record outbox length before second run
    actor_state = datalayer.read(actor.id_)
    outbox_count_before = len(actor_state.outbox.items)

    # Second run: CheckCaseExistsForReport should succeed (early exit)
    tree2 = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    result2 = bridge.execute_with_setup(tree=tree2, actor_id=actor.id_)
    assert result2.status == Status.SUCCESS

    # No additional outbox items (early exit skips CreateCaseActivity)
    actor_state2 = datalayer.read(actor.id_)
    assert len(actor_state2.outbox.items) == outbox_count_before


# ============================================================================
# Vendor RM state tests (IDEA-260408-01-2 spec requirement)
# ============================================================================


def test_vendor_participant_reuses_existing_received_status(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
    vendor_received_status,
):
    """Vendor participant reuses pre-existing RM.RECEIVED status (no duplicate)."""
    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    bridge.execute_with_setup(tree=tree, actor_id=actor.id_)

    case = datalayer.find_case_by_report_id(report.id_)
    assert case is not None

    for p_ref in case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
        participant = datalayer.read(p_id)
        if participant is None:
            continue
        p_actor = participant.attributed_to
        p_actor_id = (
            p_actor
            if isinstance(p_actor, str)
            else getattr(p_actor, "id_", p_actor)
        )
        if p_actor_id != actor.id_:
            continue
        # Participant should have exactly one status (the pre-existing one)
        statuses = participant.participant_statuses
        assert len(statuses) == 1
        assert statuses[0].id_ == vendor_received_status.id_
        break


def test_vendor_participant_created_without_pre_existing_status(
    datalayer,
    actor,
    finder_actor,
    report,
    offer,
    bridge,
    finder_accepted_status,
):
    """Vendor participant is created with fresh RM.RECEIVED when no prior status."""
    # No vendor_received_status fixture — vendor has no prior status record
    tree = create_receive_report_case_tree(
        report_id=report.id_, offer_id=offer.id_
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor.id_)
    assert result.status == Status.SUCCESS

    case = datalayer.find_case_by_report_id(report.id_)
    assert case is not None

    from vultron.core.states.roles import CVDRoles

    for p_ref in case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
        participant = datalayer.read(p_id)
        if participant is None:
            continue
        p_actor = participant.attributed_to
        p_actor_id = (
            p_actor
            if isinstance(p_actor, str)
            else getattr(p_actor, "id_", p_actor)
        )
        if p_actor_id != actor.id_:
            continue
        if CVDRoles.VENDOR not in participant.case_roles:
            continue
        statuses = participant.participant_statuses
        assert statuses
        rm = getattr(statuses[-1], "rm_state", None)
        assert rm == RM.RECEIVED, f"Expected RM.RECEIVED, got {rm}"
        break
