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
Tests for report validation behavior tree nodes.

Uses BTTestScenario (from ``test.core.behaviors.bt_harness``) as the single
execution path; no direct ``node.update()`` / ``node.blackboard.register_key()``
calls appear here.

Per GitHub issue #401 and specs/behavior-tree-node-design.yaml.
"""

import pytest
from py_trees.composites import Sequence
from typing import cast, Any

from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.core.models.vultron_types import (
    VultronOffer,
    VultronReport,
)
from vultron.core.behaviors.report.nodes import (
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    CreateCaseActivity,
    CreateCaseNode,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    TransitionRMtoInvalid,
    TransitionRMtoValid,
    UpdateActorOutbox,
)
from vultron.core.states.rm import RM
from test.core.behaviors.bt_harness import BTTestScenario

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def actor(bt_scenario: BTTestScenario) -> VultronCaseActor:
    """Create a test actor and persist it in the scenario DataLayer."""
    obj = VultronCaseActor(name="Test Actor")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(bt_scenario: BTTestScenario) -> VultronReport:
    """Create a test report and persist it in the scenario DataLayer."""
    obj = VultronReport(
        name="TEST-001",
        content="Test vulnerability report",
    )
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def offer(
    bt_scenario: BTTestScenario, report: VultronReport, actor: VultronCaseActor
) -> VultronOffer:
    """Create a test offer and persist it in the scenario DataLayer."""
    obj = VultronOffer(actor=actor.id_, object_=report.id_)
    bt_scenario.dl.create(obj)
    return obj


# ============================================================================
# Condition Node Tests
# ============================================================================


def test_check_rm_state_valid_when_valid(
    bt_scenario: BTTestScenario, actor: VultronCaseActor, report: VultronReport
) -> None:
    """CheckRMStateValid returns SUCCESS when report is VALID."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.VALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.VALID,
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateValid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result)


def test_check_rm_state_valid_when_received(
    bt_scenario: BTTestScenario, actor: VultronCaseActor, report: VultronReport
) -> None:
    """CheckRMStateValid returns FAILURE when report is RECEIVED (no VALID record)."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.RECEIVED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.RECEIVED,
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateValid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_failure(result)


def test_check_rm_state_valid_when_no_status(
    bt_scenario: BTTestScenario, actor: VultronCaseActor, report: VultronReport
) -> None:
    """CheckRMStateValid returns FAILURE when no status exists."""
    result = bt_scenario.run(
        CheckRMStateValid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_failure(result)


def test_check_rm_state_received_or_invalid_when_received(
    bt_scenario: BTTestScenario, actor: VultronCaseActor, report: VultronReport
) -> None:
    """CheckRMStateReceivedOrInvalid returns SUCCESS when RECEIVED."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.RECEIVED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.RECEIVED,
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateReceivedOrInvalid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result)


def test_check_rm_state_received_or_invalid_when_invalid(
    bt_scenario: BTTestScenario, actor: VultronCaseActor, report: VultronReport
) -> None:
    """CheckRMStateReceivedOrInvalid returns SUCCESS when INVALID."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.INVALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.INVALID,
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateReceivedOrInvalid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result)


def test_check_rm_state_received_or_invalid_when_valid(
    bt_scenario: BTTestScenario, actor: VultronCaseActor, report: VultronReport
) -> None:
    """CheckRMStateReceivedOrInvalid returns FAILURE when VALID."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.VALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.VALID,
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateReceivedOrInvalid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_failure(result)


def test_check_rm_state_received_or_invalid_when_no_status(
    bt_scenario: BTTestScenario, actor: VultronCaseActor, report: VultronReport
) -> None:
    """CheckRMStateReceivedOrInvalid returns SUCCESS when no status (default RECEIVED)."""
    result = bt_scenario.run(
        CheckRMStateReceivedOrInvalid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result)


# ============================================================================
# Action Node Tests
# ============================================================================


def test_transition_rm_to_valid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoValid updates statuses correctly."""
    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.VALID, actor_id=actor.id_)


def test_transition_rm_to_invalid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoInvalid updates report status to INVALID in DataLayer."""
    result = bt_scenario.run(
        TransitionRMtoInvalid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.INVALID, actor_id=actor.id_)


def test_create_case_node(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CreateCaseNode creates a VulnerabilityCase in the DataLayer."""
    result = bt_scenario.run(
        CreateCaseNode(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_case_count(1)

    case = bt_scenario.assert_case_exists()
    assert case.name == f"Case for Report {report.id_}"
    assert case.attributed_to == actor.id_


def test_create_case_node_idempotency(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CreateCaseNode handles duplicate case creation gracefully."""
    result1 = bt_scenario.run(
        CreateCaseNode(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result1)

    result2 = bt_scenario.run(
        CreateCaseNode(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result2)


def test_create_case_activity(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """CreateCaseActivity creates activity with recipients and embedded case."""
    finder = VultronCaseActor(name="Finder Actor")
    bt_scenario.dl.create(finder)

    # Set report.attributed_to so the finder appears in the addressees list.
    report.attributed_to = finder.id_
    bt_scenario.dl.save(report)

    chain = Sequence(
        "CreateAndNotify",
        memory=True,
        children=[
            CreateCaseNode(report_id=report.id_),
            CreateCaseActivity(report_id=report.id_, offer_id=offer.id_),
        ],
    )
    result = bt_scenario.run(chain, actor_id=actor.id_)
    bt_scenario.assert_success(result)

    create_activities = bt_scenario.dl.by_type("Create")
    assert len(create_activities) == 1, "Expected exactly one Create activity"
    activity_id = next(iter(create_activities))
    activity_data = create_activities[activity_id]

    assert activity_data.get("type_") == "Create"
    assert activity_data.get(
        "to"
    ), "CreateCaseActivity should have 'to' recipients"
    assert (
        actor.id_ not in activity_data["to"]
    ), "Sender actor should be excluded from 'to' recipients"
    assert (
        finder.id_ in activity_data["to"]
    ), "Finder (report.attributed_to) should be in 'to' recipients"
    assert isinstance(
        activity_data.get("object_"), str
    ), "CreateCaseActivity object_ should be stored as the case ID string"


def test_create_case_activity_missing_case_id(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """CreateCaseActivity fails if no preceding CreateCaseNode set case_id."""
    result = bt_scenario.run(
        CreateCaseActivity(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_update_actor_outbox(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """UpdateActorOutbox appends activity to actor's outbox."""
    chain = Sequence(
        "CreateAndPost",
        memory=True,
        children=[
            CreateCaseNode(report_id=report.id_),
            CreateCaseActivity(report_id=report.id_, offer_id=offer.id_),
            UpdateActorOutbox(),
        ],
    )
    result = bt_scenario.run(chain, actor_id=actor.id_)
    bt_scenario.assert_success(result)

    updated_actor = cast(
        Any, bt_scenario.dl.read(actor.id_, raise_on_missing=True)
    )
    create_activities = bt_scenario.dl.by_type("Create")
    assert (
        create_activities
    ), "Expected at least one Create activity in DataLayer"
    activity_id = next(iter(create_activities))
    assert activity_id in updated_actor.outbox.items


def test_update_actor_outbox_missing_activity_id(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
) -> None:
    """UpdateActorOutbox fails if no preceding node set activity_id."""
    result = bt_scenario.run(UpdateActorOutbox(), actor_id=actor.id_)
    bt_scenario.assert_failure(result)


# ============================================================================
# Policy Node Tests (Stubs)
# ============================================================================


def test_evaluate_report_credibility(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """EvaluateReportCredibility always returns SUCCESS (stub)."""
    result = bt_scenario.run(
        EvaluateReportCredibility(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result)


def test_evaluate_report_validity(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """EvaluateReportValidity always returns SUCCESS (stub)."""
    result = bt_scenario.run(
        EvaluateReportValidity(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result)


# ============================================================================
# Integration Test
# ============================================================================


def test_full_validation_workflow(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """Test full validation workflow using all nodes in sequence."""
    # 1. Check if already valid (should fail initially)
    bt_scenario.assert_failure(
        bt_scenario.run(
            CheckRMStateValid(report_id=report.id_), actor_id=actor.id_
        )
    )

    # 2. Check preconditions (should succeed — no status = default RECEIVED)
    bt_scenario.assert_success(
        bt_scenario.run(
            CheckRMStateReceivedOrInvalid(report_id=report.id_),
            actor_id=actor.id_,
        )
    )

    # 3. Evaluate credibility (stub: always succeeds)
    bt_scenario.assert_success(
        bt_scenario.run(
            EvaluateReportCredibility(report_id=report.id_), actor_id=actor.id_
        )
    )

    # 4. Evaluate validity (stub: always succeeds)
    bt_scenario.assert_success(
        bt_scenario.run(
            EvaluateReportValidity(report_id=report.id_), actor_id=actor.id_
        )
    )

    # 5. Transition to VALID
    bt_scenario.assert_success(
        bt_scenario.run(
            TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
            actor_id=actor.id_,
        )
    )

    # 6. Create case, activity, update outbox — share blackboard via Sequence
    actions = Sequence(
        "ValidationActions",
        memory=True,
        children=[
            CreateCaseNode(report_id=report.id_),
            CreateCaseActivity(report_id=report.id_, offer_id=offer.id_),
            UpdateActorOutbox(),
        ],
    )
    bt_scenario.assert_success(bt_scenario.run(actions, actor_id=actor.id_))

    # 7. Verify final state
    bt_scenario.assert_rm_state(report.id_, RM.VALID, actor_id=actor.id_)


# ============================================================================
# D5-6-LOGCTX: UpdateActorOutbox log content tests
# ============================================================================


def test_update_actor_outbox_logs_create_activity_type(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """UpdateActorOutbox MUST log 'Create' activity type (D5-6-LOGCTX)."""
    chain = Sequence(
        "CreateAndPost",
        memory=True,
        children=[
            CreateCaseNode(report_id=report.id_),
            CreateCaseActivity(report_id=report.id_, offer_id=offer.id_),
            UpdateActorOutbox(),
        ],
    )
    with caplog.at_level("INFO"):
        bt_scenario.run(chain, actor_id=actor.id_)

    assert "Create" in caplog.text


def test_update_actor_outbox_logs_case_id_in_message(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """UpdateActorOutbox MUST log the case ID in the outbox message (D5-6-LOGCTX)."""
    chain = Sequence(
        "CreateAndPost",
        memory=True,
        children=[
            CreateCaseNode(report_id=report.id_),
            CreateCaseActivity(report_id=report.id_, offer_id=offer.id_),
            UpdateActorOutbox(),
        ],
    )
    with caplog.at_level("INFO"):
        bt_scenario.run(chain, actor_id=actor.id_)

    cases = bt_scenario.dl.by_type("VulnerabilityCase")
    assert cases, "Expected VulnerabilityCase to be created"
    case_id = next(iter(cases))
    assert case_id in caplog.text
