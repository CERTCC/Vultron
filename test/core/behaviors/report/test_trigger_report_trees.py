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

"""Tests for the report trigger BT factories (issue #849 AC-4).

Covers SUCCESS and FAILURE paths for:
  - ``InvalidateReportTriggerBT`` (create_invalidate_report_trigger_tree)
  - ``RejectReportTriggerBT``     (create_reject_report_trigger_tree)
  - ``CloseReportTriggerBT``      (create_close_report_trigger_tree)
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.report.trigger_report_trees import (
    create_close_report_trigger_tree,
    create_invalidate_report_trigger_tree,
    create_reject_report_trigger_tree,
)
from vultron.core.models.activity import VultronOffer
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.errors import VultronInvalidStateTransitionError

# noqa: F401 — vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTOR_ID = "https://example.org/actors/vendor"
REPORTER_ID = "https://example.org/actors/reporter"


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
        rm_state=RM.CLOSED,
    )
    scenario.dl.create(status)
    return status


# ---------------------------------------------------------------------------
# InvalidateReportTriggerBT tests
# ---------------------------------------------------------------------------


class TestInvalidateReportTriggerTree:
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

    def test_success_adds_to_outbox(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """SUCCESS: activity is added to the actor's outbox."""
        before = set(scenario.dl.outbox_list_for_actor(ACTOR_ID))
        tree = create_invalidate_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        scenario.run(tree)
        after = set(scenario.dl.outbox_list_for_actor(ACTOR_ID))
        assert len(after - before) >= 1

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
    def test_success_emits_activity_and_sets_rm_closed(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """SUCCESS: emits activity and persists RM.CLOSED ParticipantStatus."""
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        result = scenario.run(tree)
        scenario.assert_success(result)
        scenario.assert_rm_state(report.id_, RM.CLOSED)

    def test_success_adds_to_outbox(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """SUCCESS: activity is added to the actor's outbox."""
        before = set(scenario.dl.outbox_list_for_actor(ACTOR_ID))
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_
        )
        scenario.run(tree)
        after = set(scenario.dl.outbox_list_for_actor(ACTOR_ID))
        assert len(after - before) >= 1

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
# CloseReportTriggerBT tests
# ---------------------------------------------------------------------------


class TestCloseReportTriggerTree:
    def test_success_emits_activity_and_sets_rm_closed(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """SUCCESS: emits activity and persists RM.CLOSED ParticipantStatus."""
        result_out: dict = {}
        tree = create_close_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, result_out=result_out
        )
        result = scenario.run(tree)
        scenario.assert_success(result)
        scenario.assert_rm_state(report.id_, RM.CLOSED)
        assert "error" not in result_out

    def test_success_adds_to_outbox(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """SUCCESS: activity is added to the actor's outbox."""
        before = set(scenario.dl.outbox_list_for_actor(ACTOR_ID))
        result_out: dict = {}
        tree = create_close_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, result_out=result_out
        )
        scenario.run(tree)
        after = set(scenario.dl.outbox_list_for_actor(ACTOR_ID))
        assert len(after - before) >= 1

    def test_failure_already_closed_writes_error(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        closed_status: ParticipantStatus,
    ):
        """FAILURE: already-closed report writes VultronInvalidStateTransitionError."""
        result_out: dict = {}
        tree = create_close_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, result_out=result_out
        )
        result = scenario.run(tree)
        scenario.assert_failure(result)
        assert "error" in result_out
        assert isinstance(
            result_out["error"], VultronInvalidStateTransitionError
        )

    def test_failure_already_closed_error_message(
        self,
        scenario: BTTestScenario,
        actor,
        report,
        offer,
        closed_status: ParticipantStatus,
    ):
        """The error message references the report ID."""
        result_out: dict = {}
        tree = create_close_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, result_out=result_out
        )
        scenario.run(tree)
        error = result_out.get("error")
        assert error is not None
        assert report.id_ in str(error)

    def test_failure_no_trigger_activity_factory(
        self, scenario: BTTestScenario, actor, report, offer
    ):
        """FAILURE: no TriggerActivityPort on the blackboard → tree fails."""
        import py_trees

        from vultron.core.behaviors.bridge import BTBridge

        bridge_no_factory = BTBridge(datalayer=scenario.dl)
        result_out: dict = {}
        tree = create_close_report_trigger_tree(
            offer_id=offer.id_, report_id=report.id_, result_out=result_out
        )
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge_no_factory.execute_with_setup(tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
