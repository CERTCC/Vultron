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

"""Tests for received-report behavior trees and use-case integration.

Covers all four report-lifecycle BTs (issue #759 AC-1 through AC-5):
  - ``CreateReportReceivedBT``    — stores report + activity
  - ``AckReportReceivedBT``      — stores activity
  - ``CloseReportReceivedBT``    — stores activity + RM → CLOSED
  - ``InvalidateReportReceivedBT`` — stores activity + RM → INVALID

Each BT is tested at three levels:
  1. Node-level (individual storage / transition nodes)
  2. Tree-level (full factory via BTBridge)
  3. Use-case-level (``*ReceivedUseCase.execute()``)
"""

import logging
from typing import cast

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionCaseParticipantRMtoClosed,
    TransitionCaseParticipantRMtoInvalid,
)
from vultron.core.behaviors.report.nodes.storage import (
    StoreActivityNode,
    StoreReportNode,
)
from vultron.core.behaviors.report.received_report_trees import (
    create_ack_report_received_tree,
    create_close_report_received_tree,
    create_create_report_received_tree,
    create_invalidate_report_received_tree,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
)
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport as CoreReport
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.report import (
    AckReportReceivedUseCase,
    CloseReportReceivedUseCase,
    CreateReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTOR_ID = "https://example.org/actors/vendor"
FINDER_ID = "https://example.org/actors/finder"
REPORT_ID = "https://example.org/reports/rpt-bt-01"
ACTIVITY_ID = "https://example.org/activities/act-bt-01"
CASE_ID = "https://example.org/cases/case-bt-01"
PARTICIPANT_ID = "https://example.org/participants/p-bt-01"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _activity_stored(dl: SqliteDataLayer, activity_id: str) -> bool:
    """Return True if any activity with *activity_id* is in the DataLayer.

    Activities are stored in type-keyed collections (e.g. ``"Create"``),
    so ``dl.read(id)`` does not work for them.  This helper tries each
    known activity type used in these tests.
    """
    for type_key in ("Create", "Read", "Reject", "TentativeReject", "Offer"):
        for record in dl.get_all(type_key):
            if record.get("id_") == activity_id:
                return True
    return False


def _make_activity(
    id_: str = ACTIVITY_ID,
    type_: str = "Create",
    actor: str = ACTOR_ID,
) -> VultronActivity:
    """Build a minimal VultronActivity with sensible defaults."""
    return VultronActivity(id_=id_, type_=type_, actor=actor)


def _setup_case_with_participant(
    dl: SqliteDataLayer,
    report_id: str = REPORT_ID,
    actor_id: str = ACTOR_ID,
    initial_rm: RM = RM.RECEIVED,
) -> tuple[VulnerabilityCase, VultronParticipant]:
    """Create and persist a VulnerabilityCase linked to a report.

    Adds a CaseParticipant for *actor_id* so RM transition nodes can find
    the participant record.

    Returns:
        Tuple of (case, participant) as persisted in *dl*.
    """
    report = CoreReport(id_=report_id)
    dl.save(report)

    participant = VultronParticipant(
        id_=PARTICIPANT_ID,
        attributed_to=actor_id,
        context=CASE_ID,
        participant_statuses=[
            ParticipantStatus(
                rm_state=initial_rm,
                context=CASE_ID,
                attributed_to=actor_id,
            )
        ],
    )
    case = VulnerabilityCase(id_=CASE_ID, name="BT Test Case")
    case.vulnerability_reports.append(report_id)
    case.case_participants.append(participant.id_)
    case.actor_participant_index[actor_id] = participant.id_

    dl.save(participant)
    dl.save(case)
    return case, participant


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl: SqliteDataLayer) -> BTBridge:
    return BTBridge(datalayer=dl)


# ---------------------------------------------------------------------------
# StoreReportNode
# ---------------------------------------------------------------------------


class TestStoreReportNode:
    def test_stores_report_in_dl(self, dl, bridge):
        """StoreReportNode persists a VulnerabilityReport → SUCCESS."""
        report = CoreReport(id_=REPORT_ID)
        node = StoreReportNode(report_id=REPORT_ID, report_obj=report)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        stored = dl.read(REPORT_ID)
        assert stored is not None

    def test_idempotent_second_store(self, dl, bridge):
        """StoreReportNode is idempotent — second call is a no-op SUCCESS."""
        report = CoreReport(id_=REPORT_ID)
        dl.create(report)  # pre-store

        node = StoreReportNode(report_id=REPORT_ID, report_obj=report)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_no_report_obj_succeeds_with_warning(self, dl, bridge, caplog):
        """StoreReportNode with report_obj=None logs warning → SUCCESS."""
        node = StoreReportNode(report_id=REPORT_ID, report_obj=None)
        with caplog.at_level(logging.WARNING):
            result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        assert dl.read(REPORT_ID) is None

    def test_empty_report_id_is_no_op(self, bridge):
        """StoreReportNode with empty report_id is a no-op SUCCESS."""
        node = StoreReportNode(
            report_id="", report_obj=CoreReport(id_=REPORT_ID)
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# StoreActivityNode
# ---------------------------------------------------------------------------


class TestStoreActivityNode:
    def test_stores_activity_in_dl(self, dl, bridge):
        """StoreActivityNode persists an activity → SUCCESS."""
        activity = _make_activity()
        node = StoreActivityNode(
            activity_id=ACTIVITY_ID,
            activity_obj=activity,
            label="TestActivity",
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        # Activities are stored in type-keyed collections; dl.read() won't find them.
        stored = dl.get_all(activity.type_)
        assert any(r["id_"] == ACTIVITY_ID for r in stored)

    def test_idempotent_second_store(self, dl, bridge):
        """StoreActivityNode is idempotent — second call is a no-op SUCCESS."""
        activity = _make_activity()
        dl.create(activity)  # pre-store

        node = StoreActivityNode(
            activity_id=ACTIVITY_ID,
            activity_obj=activity,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_no_activity_obj_is_failure(self, dl, bridge, caplog):
        """StoreActivityNode with activity_obj=None and a set id → FAILURE."""
        node = StoreActivityNode(
            activity_id=ACTIVITY_ID,
            activity_obj=None,
        )
        with caplog.at_level(logging.ERROR):
            result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE
        assert dl.get_all("Create") == []

    def test_empty_activity_id_is_no_op(self, bridge):
        """StoreActivityNode with empty activity_id is a no-op SUCCESS."""
        node = StoreActivityNode(
            activity_id="",
            activity_obj=_make_activity(),
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# TransitionCaseParticipantRMtoClosed
# ---------------------------------------------------------------------------


class TestTransitionCaseParticipantRMtoClosed:
    def test_transitions_rm_to_closed(self, dl, bridge):
        """Participant RM → CLOSED when case found for report."""
        case, _ = _setup_case_with_participant(
            dl, REPORT_ID, ACTOR_ID, RM.INVALID
        )

        node = TransitionCaseParticipantRMtoClosed(report_id=REPORT_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        updated_case = cast(VulnerabilityCase, dl.read(CASE_ID))
        p_id = updated_case.actor_participant_index[ACTOR_ID]
        participant = cast(VultronParticipant, dl.read(p_id))
        assert participant.participant_statuses[-1].rm_state == RM.CLOSED

    def test_no_case_is_soft_pass(self, dl, bridge, caplog):
        """No case for report → WARNING logged, SUCCESS returned (soft pass)."""
        report = CoreReport(id_=REPORT_ID)
        dl.save(report)

        node = TransitionCaseParticipantRMtoClosed(report_id=REPORT_ID)
        with caplog.at_level(logging.WARNING):
            result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("no case found" in m.lower() for m in warn_msgs)

    def test_no_report_id_is_no_op(self, bridge):
        """report_id=None → no-op SUCCESS (debug only)."""
        node = TransitionCaseParticipantRMtoClosed(report_id=None)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# TransitionCaseParticipantRMtoInvalid
# ---------------------------------------------------------------------------


class TestTransitionCaseParticipantRMtoInvalid:
    def test_transitions_rm_to_invalid(self, dl, bridge):
        """Participant RM → INVALID when case found for report."""
        case, _ = _setup_case_with_participant(
            dl, REPORT_ID, ACTOR_ID, RM.RECEIVED
        )

        node = TransitionCaseParticipantRMtoInvalid(report_id=REPORT_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        updated_case = cast(VulnerabilityCase, dl.read(CASE_ID))
        p_id = updated_case.actor_participant_index[ACTOR_ID]
        participant = cast(VultronParticipant, dl.read(p_id))
        assert participant.participant_statuses[-1].rm_state == RM.INVALID

    def test_no_case_is_soft_pass(self, dl, bridge, caplog):
        """No case for report → WARNING logged, SUCCESS returned (soft pass)."""
        report = CoreReport(id_=REPORT_ID)
        dl.save(report)

        node = TransitionCaseParticipantRMtoInvalid(report_id=REPORT_ID)
        with caplog.at_level(logging.WARNING):
            result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("no case found" in m.lower() for m in warn_msgs)

    def test_no_report_id_is_no_op(self, bridge):
        """report_id=None → no-op SUCCESS (debug only)."""
        node = TransitionCaseParticipantRMtoInvalid(report_id=None)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Helpers: build events for tree / use-case tests
# ---------------------------------------------------------------------------


def _make_create_report_event() -> CreateReportReceivedEvent:
    # object_ IS the report for CreateReport (report_id = object_id)
    return CreateReportReceivedEvent(
        semantic_type=MessageSemantics.CREATE_REPORT,
        activity_id=ACTIVITY_ID,
        actor_id=ACTOR_ID,
        object_=CoreReport(id_=REPORT_ID),
        inner_object=CoreReport(id_=REPORT_ID),
        activity=_make_activity(type_="Create"),
    )


def _make_ack_report_event() -> AckReportReceivedEvent:
    return AckReportReceivedEvent(
        semantic_type=MessageSemantics.ACK_REPORT,
        activity_id=ACTIVITY_ID,
        actor_id=ACTOR_ID,
        object_=CoreReport(id_=ACTIVITY_ID),
        inner_object=CoreReport(id_=REPORT_ID),
        activity=_make_activity(type_="Read"),
    )


def _make_close_report_event() -> CloseReportReceivedEvent:
    return CloseReportReceivedEvent(
        semantic_type=MessageSemantics.CLOSE_REPORT,
        activity_id=ACTIVITY_ID,
        actor_id=ACTOR_ID,
        object_=CoreReport(id_=ACTIVITY_ID),
        inner_object=CoreReport(id_=REPORT_ID),
        activity=_make_activity(type_="Reject"),
    )


def _make_invalidate_report_event() -> InvalidateReportReceivedEvent:
    return InvalidateReportReceivedEvent(
        semantic_type=MessageSemantics.INVALIDATE_REPORT,
        activity_id=ACTIVITY_ID,
        actor_id=ACTOR_ID,
        object_=CoreReport(id_=ACTIVITY_ID),
        inner_object=CoreReport(id_=REPORT_ID),
        activity=_make_activity(type_="TentativeReject"),
    )


# ---------------------------------------------------------------------------
# CreateReportReceivedBT (tree factory + use case)
# ---------------------------------------------------------------------------


class TestCreateReportReceivedTree:
    def test_happy_path_stores_report_and_activity(self, dl):
        """Full BT stores both VulnerabilityReport and CreateReport activity."""
        event = _make_create_report_event()
        tree = create_create_report_received_tree(event)
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )

        assert result.status == Status.SUCCESS
        assert dl.read(REPORT_ID) is not None
        assert _activity_stored(dl, ACTIVITY_ID)

    def test_idempotent_run_succeeds(self, dl):
        """Second BT execution is idempotent — no-op SUCCESS."""
        event = _make_create_report_event()
        bridge = BTBridge(datalayer=dl)

        for _ in range(2):
            tree = create_create_report_received_tree(event)
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )
            assert result.status == Status.SUCCESS


class TestCreateReportReceivedUseCase:
    def test_use_case_stores_report_and_activity(self):
        """Use case delegates to BT; report and activity are persisted."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_create_report_event()
        CreateReportReceivedUseCase(dl, event).execute()

        assert dl.read(REPORT_ID) is not None
        assert _activity_stored(dl, ACTIVITY_ID)

    def test_use_case_is_idempotent(self):
        """Calling use case twice does not raise and stays consistent."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_create_report_event()
        CreateReportReceivedUseCase(dl, event).execute()
        CreateReportReceivedUseCase(dl, event).execute()

        assert dl.read(REPORT_ID) is not None
        assert _activity_stored(dl, ACTIVITY_ID)


# ---------------------------------------------------------------------------
# AckReportReceivedBT (tree factory + use case)
# ---------------------------------------------------------------------------


class TestAckReportReceivedTree:
    def test_happy_path_stores_activity(self, dl):
        """Full BT stores AckReport activity → SUCCESS."""
        event = _make_ack_report_event()
        tree = create_ack_report_received_tree(event)
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )

        assert result.status == Status.SUCCESS
        assert _activity_stored(dl, ACTIVITY_ID)

    def test_does_not_create_participant_status(self, dl):
        """AckReportReceivedBT must NOT create standalone ParticipantStatus."""
        event = _make_ack_report_event()
        tree = create_ack_report_received_tree(event)
        bridge = BTBridge(datalayer=dl)
        bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID, activity=event)

        all_statuses = dl.get_all("ParticipantStatus")
        assert all_statuses == [], (
            "AckReportReceivedBT must not create standalone "
            "ParticipantStatus records"
        )

    def test_idempotent_run_succeeds(self, dl):
        """Second BT execution is idempotent — no-op SUCCESS."""
        event = _make_ack_report_event()
        bridge = BTBridge(datalayer=dl)
        for _ in range(2):
            tree = create_ack_report_received_tree(event)
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )
            assert result.status == Status.SUCCESS


class TestAckReportReceivedUseCase:
    def test_use_case_stores_activity(self):
        """Use case delegates to BT; activity is persisted."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_ack_report_event()
        AckReportReceivedUseCase(dl, event).execute()

        assert _activity_stored(dl, ACTIVITY_ID)

    def test_use_case_does_not_create_participant_status(self):
        """Use case must NOT create standalone ParticipantStatus records."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_ack_report_event()
        AckReportReceivedUseCase(dl, event).execute()

        all_statuses = dl.get_all("ParticipantStatus")
        assert all_statuses == []


# ---------------------------------------------------------------------------
# CloseReportReceivedBT (tree factory + use case)
# ---------------------------------------------------------------------------


class TestCloseReportReceivedTree:
    def test_happy_path_stores_activity_and_transitions_rm(self, dl):
        """Full BT stores activity and transitions participant RM → CLOSED."""
        _setup_case_with_participant(dl, REPORT_ID, ACTOR_ID, RM.INVALID)
        event = _make_close_report_event()
        tree = create_close_report_received_tree(event)
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )

        assert result.status == Status.SUCCESS
        assert _activity_stored(dl, ACTIVITY_ID)

        updated_case = cast(VulnerabilityCase, dl.read(CASE_ID))
        p_id = updated_case.actor_participant_index[ACTOR_ID]
        participant = cast(VultronParticipant, dl.read(p_id))
        assert participant.participant_statuses[-1].rm_state == RM.CLOSED

    def test_no_case_soft_pass_with_warning(self, dl, caplog):
        """No case linked to report → WARNING, BT still SUCCESS."""
        event = _make_close_report_event()
        tree = create_close_report_received_tree(event)
        bridge = BTBridge(datalayer=dl)

        with caplog.at_level(logging.WARNING):
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )

        assert result.status == Status.SUCCESS
        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("no case found" in m.lower() for m in warn_msgs)

    def test_idempotent_rm_transition(self, dl):
        """Already-CLOSED participant stays CLOSED; BT still SUCCESS."""
        _setup_case_with_participant(dl, REPORT_ID, ACTOR_ID, RM.INVALID)
        event = _make_close_report_event()
        bridge = BTBridge(datalayer=dl)

        for _ in range(2):
            tree = create_close_report_received_tree(event)
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )
            assert result.status == Status.SUCCESS


class TestCloseReportReceivedUseCase:
    def test_use_case_stores_activity_and_transitions_rm(self):
        """Use case delegates to BT; activity stored + RM → CLOSED."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        _setup_case_with_participant(dl, REPORT_ID, ACTOR_ID, RM.INVALID)
        event = _make_close_report_event()
        CloseReportReceivedUseCase(dl, event).execute()

        assert _activity_stored(dl, ACTIVITY_ID)
        updated_case = cast(VulnerabilityCase, dl.read(CASE_ID))
        p_id = updated_case.actor_participant_index[ACTOR_ID]
        participant = cast(VultronParticipant, dl.read(p_id))
        assert participant.participant_statuses[-1].rm_state == RM.CLOSED

    def test_use_case_warns_when_no_case(self, caplog):
        """Use case logs WARNING when no case is found for the report."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_close_report_event()

        with caplog.at_level(logging.WARNING):
            CloseReportReceivedUseCase(dl, event).execute()

        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("no case found" in m.lower() for m in warn_msgs)


# ---------------------------------------------------------------------------
# InvalidateReportReceivedBT (tree factory + use case)
# ---------------------------------------------------------------------------


class TestInvalidateReportReceivedTree:
    def test_happy_path_stores_activity_and_transitions_rm(self, dl):
        """Full BT stores activity and transitions participant RM → INVALID."""
        _setup_case_with_participant(dl, REPORT_ID, ACTOR_ID, RM.RECEIVED)
        event = _make_invalidate_report_event()
        tree = create_invalidate_report_received_tree(event)
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )

        assert result.status == Status.SUCCESS
        assert _activity_stored(dl, ACTIVITY_ID)

        updated_case = cast(VulnerabilityCase, dl.read(CASE_ID))
        p_id = updated_case.actor_participant_index[ACTOR_ID]
        participant = cast(VultronParticipant, dl.read(p_id))
        assert participant.participant_statuses[-1].rm_state == RM.INVALID

    def test_no_case_soft_pass_with_warning(self, dl, caplog):
        """No case linked to report → WARNING, BT still SUCCESS."""
        event = _make_invalidate_report_event()
        tree = create_invalidate_report_received_tree(event)
        bridge = BTBridge(datalayer=dl)

        with caplog.at_level(logging.WARNING):
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )

        assert result.status == Status.SUCCESS
        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("no case found" in m.lower() for m in warn_msgs)

    def test_idempotent_rm_transition(self, dl):
        """Already-INVALID participant stays INVALID; BT still SUCCESS."""
        _setup_case_with_participant(dl, REPORT_ID, ACTOR_ID, RM.RECEIVED)
        event = _make_invalidate_report_event()
        bridge = BTBridge(datalayer=dl)

        for _ in range(2):
            tree = create_invalidate_report_received_tree(event)
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )
            assert result.status == Status.SUCCESS


class TestInvalidateReportReceivedUseCase:
    def test_use_case_stores_activity_and_transitions_rm(self):
        """Use case delegates to BT; activity stored + RM → INVALID."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        _setup_case_with_participant(dl, REPORT_ID, ACTOR_ID, RM.RECEIVED)
        event = _make_invalidate_report_event()
        InvalidateReportReceivedUseCase(dl, event).execute()

        assert _activity_stored(dl, ACTIVITY_ID)
        updated_case = cast(VulnerabilityCase, dl.read(CASE_ID))
        p_id = updated_case.actor_participant_index[ACTOR_ID]
        participant = cast(VultronParticipant, dl.read(p_id))
        assert participant.participant_statuses[-1].rm_state == RM.INVALID

    def test_use_case_warns_when_no_case(self, caplog):
        """Use case logs WARNING when no case is found for the report."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_invalidate_report_event()

        with caplog.at_level(logging.WARNING):
            InvalidateReportReceivedUseCase(dl, event).execute()

        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("no case found" in m.lower() for m in warn_msgs)
