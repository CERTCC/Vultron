#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see Contributors.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Tests for the report trigger BT factories (issue #849 AC-4, #1854 AC-1/AC-2).

Covers SUCCESS and FAILURE paths for:
  - ``InvalidateReportTriggerBT`` (create_invalidate_report_trigger_tree)
  - ``RejectReportTriggerBT``     (create_reject_report_trigger_tree)
  - ``CloseCaseTriggerBT``        (create_close_case_trigger_tree)
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.report.trigger_report_trees import (
    create_close_case_trigger_tree,
    create_invalidate_report_trigger_tree,
    create_reject_report_trigger_tree,
)
from vultron.core.models.activity import VultronOffer
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from vultron.core.models._helpers import _report_phase_status_id
from vultron.enums.roles import CVDRole
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)
from vultron.core.models.case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTOR_ID = "https://example.org/actors/vendor"
REPORTER_ID = "https://example.org/actors/reporter"
CASE_MANAGER_ID = "https://example.org/actors/case-manager"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scenario() -> BTTestScenario:
    return BTTestScenario(actor_id=ACTOR_ID)


@pytest.fixture
def actor(scenario: BTTestScenario) -> VultronCaseActor:
    obj = VultronCaseActor(id_=ACTOR_ID, name="Vendor Co")
    scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(scenario: BTTestScenario) -> VultronReport:
    obj = VultronReport(name="TEST-001", content="Test vuln")
    scenario.dl.create(obj)
    return obj


@pytest.fixture
def offer(
    scenario: BTTestScenario, report: VultronReport, actor: VultronCaseActor
) -> VultronOffer:
    obj = VultronOffer(actor=REPORTER_ID, object_=report.id_, target=ACTOR_ID)
    scenario.dl.create(obj)
    offer_record = VultronOfferRecord(
        offer_id=obj.id_,
        report_id=report.id_,
        offer_actor_id=REPORTER_ID,
        offer_to=[ACTOR_ID],
    )
    scenario.dl.create(offer_record)
    return obj


@pytest.fixture
def closed_status(
    scenario: BTTestScenario, report: VultronReport
) -> ParticipantStatus:
    """Pre-seed RM.CLOSED so the duplicate-close guard fires."""
    status = ParticipantStatus(
        id_=_report_phase_status_id(ACTOR_ID, report.id_, RM.CLOSED.value),
        context=report.id_,
        attributed_to=ACTOR_ID,
        rm=RmDimension(state=RM.CLOSED),
    )
    scenario.dl.create(status)
    return status


@pytest.fixture
def invalid_status(
    scenario: BTTestScenario, report: VultronReport
) -> ParticipantStatus:
    """Pre-seed RM.INVALID — valid predecessor for INVALID→CLOSED."""
    status = ParticipantStatus(
        id_=_report_phase_status_id(ACTOR_ID, report.id_, RM.INVALID.value),
        context=report.id_,
        attributed_to=ACTOR_ID,
        rm=RmDimension(state=RM.INVALID),
    )
    scenario.dl.create(status)
    return status


@pytest.fixture
def accepted_status(
    scenario: BTTestScenario, report: VultronReport
) -> ParticipantStatus:
    """Pre-seed RM.ACCEPTED — valid predecessor for ACCEPTED→CLOSED."""
    status = ParticipantStatus(
        id_=_report_phase_status_id(ACTOR_ID, report.id_, RM.ACCEPTED.value),
        context=report.id_,
        attributed_to=ACTOR_ID,
        rm=RmDimension(state=RM.ACCEPTED),
    )
    scenario.dl.create(status)
    return status


@pytest.fixture
def case_with_owner(
    scenario: BTTestScenario, report: VultronReport
) -> VulnerabilityCase:
    """Create a VulnerabilityCase where ACTOR_ID is CASE_OWNER and a separate CASE_MANAGER exists for routing."""
    owner_participant = CaseParticipant(
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )
    manager_actor = VultronCaseActor(id_=CASE_MANAGER_ID, name="Case Manager")
    manager_participant = CaseParticipant(
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case = VulnerabilityCase(name="Test Case")
    case.vulnerability_reports.append(report.id_)
    case.actor_participant_index[ACTOR_ID] = owner_participant.id_
    case.actor_participant_index[CASE_MANAGER_ID] = manager_participant.id_
    scenario.dl.create(manager_actor)
    scenario.dl.create(owner_participant)
    scenario.dl.create(manager_participant)
    scenario.dl.create(case)
    return case


@pytest.fixture
def case_with_non_owner(
    scenario: BTTestScenario, report: VultronReport
) -> VulnerabilityCase:
    """Create a VulnerabilityCase where ACTOR_ID is VENDOR (not CASE_OWNER) with a CASE_MANAGER for routing."""
    vendor_participant = CaseParticipant(
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.VENDOR],
    )
    manager_actor = VultronCaseActor(id_=CASE_MANAGER_ID, name="Case Manager")
    manager_participant = CaseParticipant(
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case = VulnerabilityCase(name="Test Case Non-Owner")
    case.vulnerability_reports.append(report.id_)
    case.actor_participant_index[ACTOR_ID] = vendor_participant.id_
    case.actor_participant_index[CASE_MANAGER_ID] = manager_participant.id_
    scenario.dl.create(manager_actor)
    scenario.dl.create(vendor_participant)
    scenario.dl.create(manager_participant)
    scenario.dl.create(case)
    return case


# ---------------------------------------------------------------------------
# InvalidateReportTriggerBT tests
# ---------------------------------------------------------------------------


class TestInvalidateReportTriggerTree:
    @pytest.mark.spec("RMB-11-001")
    @pytest.mark.spec("BT-15-002")
    @pytest.mark.spec("BT-03-004")
    def test_success_emits_activity_and_sets_rm_invalid(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """SUCCESS: emits activity and persists RM.INVALID ParticipantStatus."""
        tree = create_invalidate_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        result = scenario.run(tree)
        scenario.assert_success(result)
        scenario.assert_rm_state(report.id_, RM.INVALID)

    @pytest.mark.spec("RMB-11-001")
    def test_success_adds_to_outbox(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """SUCCESS: activity is added to the actor's outbox."""
        before = set(scenario.dl.outbox_list())
        tree = create_invalidate_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        scenario.run(tree)
        after = set(scenario.dl.outbox_list())
        assert len(after - before) >= 1

    @pytest.mark.spec("BT-15-002")
    def test_failure_no_trigger_activity_factory(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """FAILURE: no TriggerActivityPort on the blackboard → tree fails."""
        import py_trees

        from vultron.core.behaviors.bridge import BTBridge

        # Build a bridge without trigger_activity
        bridge_no_factory = BTBridge(datalayer=scenario.dl)
        tree = create_invalidate_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge_no_factory.execute_with_setup(tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    @pytest.mark.spec("BT-09-001")
    def test_idempotent_second_run(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """Running the tree twice must not raise — idempotent create guard."""
        for _ in range(2):
            py_trees_module = pytest.importorskip("py_trees")
            py_trees_module.blackboard.Blackboard.storage.clear()
            tree = create_invalidate_report_trigger_tree(
                offer_id=offer.id_, report_id=report.id_
            )
            result = scenario.run(tree)
        # Second run should succeed (idempotent) or at minimum not raise
        assert result.status in (Status.SUCCESS, Status.FAILURE)


# ---------------------------------------------------------------------------
# RejectReportTriggerBT tests
# ---------------------------------------------------------------------------


class TestRejectReportTriggerTree:
    @pytest.mark.spec("RMB-14-001")
    @pytest.mark.spec("BTND-10-001")
    @pytest.mark.spec("BT-03-004")
    def test_success_emits_activity_and_sets_rm_closed(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        invalid_status: ParticipantStatus,
    ):
        """SUCCESS: emits activity and persists RM.CLOSED ParticipantStatus.

        Requires RM.INVALID to be pre-seeded — BTND-10-001 forbids
        RECEIVED→CLOSED; the shortest valid path is RECEIVED→INVALID→CLOSED.
        """
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        result = scenario.run(tree)
        scenario.assert_success(result)
        scenario.assert_rm_state(report.id_, RM.CLOSED)

    @pytest.mark.spec("RMB-14-001")
    def test_success_adds_to_outbox(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        invalid_status: ParticipantStatus,
    ):
        """SUCCESS: activity is added to the actor's outbox."""
        before = set(scenario.dl.outbox_list())
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        scenario.run(tree)
        after = set(scenario.dl.outbox_list())
        assert len(after - before) >= 1

    @pytest.mark.spec("RMB-14-002")
    def test_no_pre_close_guard(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        closed_status: ParticipantStatus,
    ):
        """Reject does NOT guard against already-closed — hard-close always allowed."""
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        result = scenario.run(tree)
        # Should still succeed (idempotent create) — no guard node in this tree
        assert result.status == Status.SUCCESS

    @pytest.mark.spec("BT-15-002")
    def test_failure_no_trigger_activity_factory(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """FAILURE: no TriggerActivityPort on the blackboard → tree fails."""
        import py_trees

        from vultron.core.behaviors.bridge import BTBridge

        bridge_no_factory = BTBridge(datalayer=scenario.dl)
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge_no_factory.execute_with_setup(tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# CloseCaseTriggerBT tests
# ---------------------------------------------------------------------------


class TestCloseCaseTriggerTree:
    @pytest.mark.spec("RMB-14-001")
    @pytest.mark.spec("BTND-10-001")
    @pytest.mark.spec("BT-03-004")
    def test_success_emits_activity_and_sets_rm_closed(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        case_with_owner: VulnerabilityCase,
        accepted_status: ParticipantStatus,
    ):
        """SUCCESS: emits activity and persists RM.CLOSED ParticipantStatus.

        Requires RM.ACCEPTED to be pre-seeded — BTND-10-001 forbids
        RECEIVED→CLOSED; close-case follows ACCEPTED→CLOSED.
        """
        result_out: dict = {}
        tree = create_close_case_trigger_tree(
            actor_id=ACTOR_ID,
            case_id=case_with_owner.id_,
            offer_id=offer.id_,
            report_id=report.id_,
            result_out=result_out,
        )
        result = scenario.run(tree, case_id=case_with_owner.id_)
        scenario.assert_success(result)
        scenario.assert_rm_state(report.id_, RM.CLOSED)
        assert "error" not in result_out

    @pytest.mark.spec("RMB-14-001")
    def test_success_adds_to_outbox(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        case_with_owner: VulnerabilityCase,
        accepted_status: ParticipantStatus,
    ):
        """SUCCESS: activity is added to the actor's outbox."""
        before = set(scenario.dl.outbox_list())
        result_out: dict = {}
        tree = create_close_case_trigger_tree(
            actor_id=ACTOR_ID,
            case_id=case_with_owner.id_,
            offer_id=offer.id_,
            report_id=report.id_,
            result_out=result_out,
        )
        scenario.run(tree, case_id=case_with_owner.id_)
        after = set(scenario.dl.outbox_list())
        assert len(after - before) >= 1

    @pytest.mark.spec("BT-10-004")
    def test_failure_non_case_owner_blocked(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        case_with_non_owner: VulnerabilityCase,
    ):
        """FAILURE: actor is not CASE_OWNER — CheckCaseOwner guard blocks tree."""
        result_out: dict = {}
        tree = create_close_case_trigger_tree(
            actor_id=ACTOR_ID,
            case_id=case_with_non_owner.id_,
            offer_id=offer.id_,
            report_id=report.id_,
            result_out=result_out,
        )
        result = scenario.run(tree, case_id=case_with_non_owner.id_)
        scenario.assert_failure(result)

    @pytest.mark.spec("BTND-10-001")
    @pytest.mark.spec("RMB-14-002")
    def test_failure_already_closed_writes_error(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        case_with_owner: VulnerabilityCase,
        closed_status: ParticipantStatus,
    ):
        """FAILURE: already-closed report writes VultronInvalidStateTransitionError."""
        result_out: dict = {}
        tree = create_close_case_trigger_tree(
            actor_id=ACTOR_ID,
            case_id=case_with_owner.id_,
            offer_id=offer.id_,
            report_id=report.id_,
            result_out=result_out,
        )
        result = scenario.run(tree, case_id=case_with_owner.id_)
        scenario.assert_failure(result)
        assert "error" in result_out
        assert isinstance(
            result_out["error"], VultronInvalidStateTransitionError
        )

    @pytest.mark.spec("BTND-10-001")
    def test_failure_already_closed_error_message(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        case_with_owner: VulnerabilityCase,
        closed_status: ParticipantStatus,
    ):
        """The error message references the report ID."""
        result_out: dict = {}
        tree = create_close_case_trigger_tree(
            actor_id=ACTOR_ID,
            case_id=case_with_owner.id_,
            offer_id=offer.id_,
            report_id=report.id_,
            result_out=result_out,
        )
        scenario.run(tree, case_id=case_with_owner.id_)
        error = result_out.get("error")
        assert error is not None
        assert report.id_ in str(error)

    @pytest.mark.spec("BT-15-002")
    def test_failure_no_trigger_activity_factory(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        case_with_owner: VulnerabilityCase,
    ):
        """FAILURE: no TriggerActivityPort on the blackboard → tree fails."""
        import py_trees

        from vultron.core.behaviors.bridge import BTBridge

        bridge_no_factory = BTBridge(datalayer=scenario.dl)
        result_out: dict = {}
        tree = create_close_case_trigger_tree(
            actor_id=ACTOR_ID,
            case_id=case_with_owner.id_,
            offer_id=offer.id_,
            report_id=report.id_,
            result_out=result_out,
        )
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge_no_factory.execute_with_setup(
            tree, actor_id=ACTOR_ID, case_id=case_with_owner.id_
        )
        assert result.status == Status.FAILURE

    def test_custom_call_out_factory_is_used(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        case_with_owner: VulnerabilityCase,
        accepted_status: ParticipantStatus,
    ):
        """SUCCESS: a custom call_out bundle's pre_close_action_factory is invoked."""
        from vultron.core.behaviors.call_out.bundles.close_report import (
            CloseReportCallOutBundle,
        )

        invoked: list[str] = []

        def tracking_factory(name: str) -> py_trees.behaviour.Behaviour:
            invoked.append(name)
            return AlwaysSucceed(name)

        custom_bundle = CloseReportCallOutBundle(
            pre_close_action_factory=tracking_factory  # type: ignore[arg-type]
        )

        result_out: dict = {}
        tree = create_close_case_trigger_tree(
            actor_id=ACTOR_ID,
            case_id=case_with_owner.id_,
            offer_id=offer.id_,
            report_id=report.id_,
            result_out=result_out,
            call_out=custom_bundle,
        )
        result = scenario.run(tree, case_id=case_with_owner.id_)
        scenario.assert_success(result)
        assert invoked == [
            "PreCloseAction"
        ], "Custom pre_close_action_factory was not called"
