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
  - ``CloseCaseTriggerBT``        (create_close_case_trigger_tree), which
    fails closed on any case that holds the report (CM-23-019)
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
from vultron.core.models.actor import VultronService
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

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
def actor(scenario: BTTestScenario) -> VultronService:
    obj = VultronService(id_=ACTOR_ID, name="Vendor Co")
    scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(scenario: BTTestScenario) -> VulnerabilityReport:
    obj = VulnerabilityReport(name="TEST-001", content="Test vuln")
    scenario.dl.create(obj)
    return obj


@pytest.fixture
def offer(
    scenario: BTTestScenario,
    report: VulnerabilityReport,
    actor: VultronService,
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
    scenario: BTTestScenario, report: VulnerabilityReport
) -> VultronReportCaseLink:
    """Pre-seed RM.CLOSED so the duplicate-close guard fires."""
    link = VultronReportCaseLink(report_id=report.id_, rm_state=RM.CLOSED)
    scenario.dl.create(link)
    return link


@pytest.fixture
def invalid_status(
    scenario: BTTestScenario, report: VulnerabilityReport
) -> VultronReportCaseLink:
    """Pre-seed RM.INVALID — valid predecessor for INVALID→CLOSED."""
    link = VultronReportCaseLink(report_id=report.id_, rm_state=RM.INVALID)
    scenario.dl.create(link)
    return link


@pytest.fixture
def accepted_status(
    scenario: BTTestScenario, report: VulnerabilityReport
) -> VultronReportCaseLink:
    """Pre-seed RM.ACCEPTED — valid predecessor for ACCEPTED→CLOSED."""
    link = VultronReportCaseLink(report_id=report.id_, rm_state=RM.ACCEPTED)
    scenario.dl.create(link)
    return link


@pytest.fixture
def report_case_link(
    scenario: BTTestScenario, report: VulnerabilityReport
) -> VultronReportCaseLink:
    """Pre-seed RM.RECEIVED so transition nodes can find the ReportCaseLink."""
    link = VultronReportCaseLink(report_id=report.id_, rm_state=RM.RECEIVED)
    scenario.dl.create(link)
    return link


@pytest.fixture
def case_with_owner(
    scenario: BTTestScenario, report: VulnerabilityReport
) -> VulnerabilityCase:
    """Create a VulnerabilityCase where ACTOR_ID is CASE_OWNER and a separate CASE_MANAGER exists for routing."""
    owner_participant = CaseParticipant(
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )
    manager_actor = VultronService(id_=CASE_MANAGER_ID, name="Case Manager")
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
    scenario: BTTestScenario, report: VulnerabilityReport
) -> VulnerabilityCase:
    """Create a VulnerabilityCase where ACTOR_ID is VENDOR (not CASE_OWNER) with a CASE_MANAGER for routing."""
    vendor_participant = CaseParticipant(
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.VENDOR],
    )
    manager_actor = VultronService(id_=CASE_MANAGER_ID, name="Case Manager")
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
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        report_case_link: VultronReportCaseLink,
    ):
        """SUCCESS: emits activity and persists RM.INVALID ParticipantStatus."""
        tree = create_invalidate_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, sender_actor_id=ACTOR_ID
        )
        result = scenario.run(tree)
        scenario.assert_success(result)
        scenario.assert_rm_state(report.id_, RM.INVALID)

    @pytest.mark.spec("RMB-11-001")
    def test_success_adds_to_outbox(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        report_case_link: VultronReportCaseLink,
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
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        report_case_link: VultronReportCaseLink,
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
        invalid_status: VultronReportCaseLink,
    ):
        """SUCCESS: emits activity and persists RM.CLOSED from RM.INVALID."""
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, sender_actor_id=ACTOR_ID
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
        invalid_status: VultronReportCaseLink,
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
        closed_status: VultronReportCaseLink,
    ):
        """Reject does NOT guard against already-closed — hard-close always allowed."""
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, sender_actor_id=ACTOR_ID
        )
        result = scenario.run(tree)
        # Should still succeed (idempotent create) — no guard node in this tree
        assert result.status == Status.SUCCESS

    @pytest.mark.spec("RMB-14-004")
    def test_success_from_received_is_an_ordinary_transition(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        report_case_link: VultronReportCaseLink,
    ):
        """A hard reject from RM.RECEIVED is the ``R → C`` transition.

        No INVALID detour is needed: ``R → C`` is in the RM table (ADR-0114),
        so the Reject is sent and RM.CLOSED is recorded.
        """
        before = set(scenario.dl.outbox_list())
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, sender_actor_id=ACTOR_ID
        )
        result = scenario.run(tree)
        scenario.assert_success(result)
        scenario.assert_rm_state(report.id_, RM.CLOSED)
        assert len(set(scenario.dl.outbox_list()) - before) == 1

    @pytest.mark.spec("RMB-14-004")
    @pytest.mark.spec("VP-02-004")
    def test_reject_from_valid_is_refused_before_emit(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
    ):
        """A hard reject from RM.VALID is refused and sends nothing.

        *Valid* has no close edge, so ``CheckReportClosable`` fails the tree
        before ``EmitCloseReportActivity`` runs: no Reject goes out for a
        transition that is not recorded.
        """
        scenario.seed(
            VultronReportCaseLink(report_id=report.id_, rm_state=RM.VALID)
        )
        before = set(scenario.dl.outbox_list())
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, sender_actor_id=ACTOR_ID
        )
        result = scenario.run(tree)
        scenario.assert_failure(result)
        scenario.assert_rm_state(report.id_, RM.VALID)
        assert set(scenario.dl.outbox_list()) == before

    @pytest.mark.spec("BT-15-002")
    def test_failure_no_trigger_activity_factory(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """FAILURE: no TriggerActivityPort on the blackboard → tree fails."""

        from vultron.core.behaviors.bridge import BTBridge

        bridge_no_factory = BTBridge(datalayer=scenario.dl)
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge_no_factory.execute_with_setup(tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


def _assert_failed_closed(
    scenario: BTTestScenario,
    result,
    result_out: dict,
    report_id: str,
    rm_before: RM,
    outbox_before: set[str],
) -> None:
    """The trigger failed before any RM write or emit (CM-23-019)."""
    scenario.assert_failure(result)
    error = result_out.get("error")
    assert isinstance(error, VultronInvalidStateTransitionError)
    assert "Leave(VulnerabilityCase)" in str(error)
    assert report_id in str(error)
    scenario.assert_rm_state(report_id, rm_before)
    assert set(scenario.dl.outbox_list()) == outbox_before


class TestRejectReportOnACase:
    @pytest.mark.spec("CM-23-019")
    def test_reject_of_a_report_a_case_holds_fails_closed(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        case_with_owner: VulnerabilityCase,
        report_case_link: VultronReportCaseLink,
    ):
        """Once a case holds the report, no Close(Report) is sent for it."""
        before = set(scenario.dl.outbox_list())
        result_out: dict = {}
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_,
            report_id=report.id_,
            sender_actor_id=ACTOR_ID,
            result_out=result_out,
        )
        result = scenario.run(tree)
        _assert_failed_closed(
            scenario, result, result_out, report.id_, RM.RECEIVED, before
        )


# ---------------------------------------------------------------------------
# CloseCaseTriggerBT tests
# ---------------------------------------------------------------------------


class TestCloseCaseTriggerTree:
    """The close-report trigger emits ``Close(Report)``, so it fails closed on
    any case that holds the report: the Case Owner closes by ``Leave``
    (CM-23-019).  Before this rule its success moved the owner to RM
    ``CLOSED`` while the case stayed open (#4746)."""

    @pytest.mark.spec("CM-23-019")
    @pytest.mark.parametrize(
        "owner", [True, False], ids=["owner", "non-owner"]
    )
    def test_close_report_on_a_case_fails_closed(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        accepted_status: VultronReportCaseLink,
        request,
        owner: bool,
    ):
        """Owner or not, nothing is written or sent, and the error names Leave."""
        case = request.getfixturevalue(
            "case_with_owner" if owner else "case_with_non_owner"
        )
        before = set(scenario.dl.outbox_list())
        result_out: dict = {}
        tree = create_close_case_trigger_tree(
            actor_id=ACTOR_ID,
            case_id=case.id_,
            offer_id=offer.id_,
            report_id=report.id_,
            result_out=result_out,
        )
        result = scenario.run(tree, case_id=case.id_)
        _assert_failed_closed(
            scenario, result, result_out, report.id_, RM.ACCEPTED, before
        )

    @pytest.mark.spec("CM-23-019")
    def test_pre_close_action_does_not_run_on_a_case(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        case_with_owner: VulnerabilityCase,
        accepted_status: VultronReportCaseLink,
    ):
        """The refusal comes before the ``PreCloseAction`` call-out."""
        from vultron.core.behaviors.call_out.bundles.close_report import (
            CloseReportCallOutBundle,
        )

        ran: list[str] = []

        class _Recording(AlwaysSucceed):
            def update(self) -> Status:
                ran.append(self.name)
                return super().update()

        custom_bundle = CloseReportCallOutBundle(
            pre_close_action_factory=_Recording  # type: ignore[arg-type]
        )
        tree = create_close_case_trigger_tree(
            actor_id=ACTOR_ID,
            case_id=case_with_owner.id_,
            offer_id=offer.id_,
            report_id=report.id_,
            result_out={},
            call_out=custom_bundle,
        )
        result = scenario.run(tree, case_id=case_with_owner.id_)
        scenario.assert_failure(result)
        assert ran == [], "PreCloseAction never runs on a case"
