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

"""Unit tests for report condition nodes."""

from vultron.core.behaviors.report.nodes.conditions import (
    CheckParticipantExists,
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    EnsureEmbargoExists,
    EvaluateCasePriority,
    EvaluateReportCredibility,
    EvaluateReportValidity,
)
from vultron.core.models.case import VultronCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from vultron.core.models._helpers import _report_phase_status_id
from test.core.behaviors.bt_harness import BTTestScenario


def test_check_rm_state_valid_when_valid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckRMStateValid returns SUCCESS when report is VALID."""
    status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.VALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.VALID),
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateValid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_success(result)


def test_check_rm_state_valid_when_received(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckRMStateValid returns FAILURE when report is RECEIVED."""
    status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.RECEIVED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.RECEIVED),
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateValid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_failure(result)


def test_check_rm_state_valid_when_no_status(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckRMStateValid returns FAILURE when no status exists."""
    result = bt_scenario.run(
        CheckRMStateValid(report_id=report.id_), actor_id=actor.id_
    )
    bt_scenario.assert_failure(result)


def test_check_rm_state_received_or_invalid_when_received(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckRMStateReceivedOrInvalid returns SUCCESS when RECEIVED."""
    status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.RECEIVED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.RECEIVED),
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateReceivedOrInvalid(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_check_rm_state_received_or_invalid_when_invalid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckRMStateReceivedOrInvalid returns SUCCESS when INVALID."""
    status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.INVALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.INVALID),
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateReceivedOrInvalid(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_check_rm_state_received_or_invalid_when_valid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckRMStateReceivedOrInvalid returns FAILURE when VALID."""
    status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.VALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.VALID),
    )
    bt_scenario.seed(status)

    result = bt_scenario.run(
        CheckRMStateReceivedOrInvalid(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_check_rm_state_received_or_invalid_when_no_status(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckRMStateReceivedOrInvalid returns SUCCESS when no status exists."""
    result = bt_scenario.run(
        CheckRMStateReceivedOrInvalid(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_ensure_embargo_exists_when_case_has_active_embargo(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """EnsureEmbargoExists returns SUCCESS when the linked case has embargo."""
    case = VultronCase(
        name="Embargoed Case",
        vulnerability_reports=[report.id_],
        active_embargo="https://example.org/embargoes/embargo-001",
        attributed_to=actor.id_,
    )
    bt_scenario.seed(case)

    result = bt_scenario.run(
        EnsureEmbargoExists(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_ensure_embargo_exists_fails_without_case(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """EnsureEmbargoExists returns FAILURE when no linked case exists."""
    result = bt_scenario.run(
        EnsureEmbargoExists(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_ensure_embargo_exists_fails_without_active_embargo(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """EnsureEmbargoExists returns FAILURE when linked case has no embargo."""
    case = VultronCase(
        name="No Embargo Case",
        vulnerability_reports=[report.id_],
        attributed_to=actor.id_,
    )
    bt_scenario.seed(case)

    result = bt_scenario.run(
        EnsureEmbargoExists(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_evaluate_report_credibility(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """EvaluateReportCredibility always returns SUCCESS."""
    result = bt_scenario.run(
        EvaluateReportCredibility(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_evaluate_report_validity(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """EvaluateReportValidity always returns SUCCESS."""
    result = bt_scenario.run(
        EvaluateReportValidity(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_evaluate_case_priority(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
) -> None:
    """EvaluateCasePriority always returns SUCCESS."""
    case = VultronCase(
        id_="https://example.org/cases/case-priority",
        name="Priority Case",
        attributed_to=actor.id_,
    )
    bt_scenario.seed(case)

    result = bt_scenario.run(
        EvaluateCasePriority(case_id=case.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_check_participant_exists_when_participant_is_present(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckParticipantExists returns SUCCESS when actor has participant."""
    participant = VultronParticipant(
        id_="https://example.org/participants/vendor-cp-001",
        attributed_to=actor.id_,
        context="https://example.org/cases/case-001",
    )
    case = VultronCase(
        id_="https://example.org/cases/case-001",
        name="Participant Case",
        vulnerability_reports=[report.id_],
        case_participants=[participant.id_],
        attributed_to=actor.id_,
    )
    bt_scenario.seed(participant, case)

    result = bt_scenario.run(
        CheckParticipantExists(case_id=case.id_, actor_id=actor.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_check_participant_exists_fails_without_case(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
) -> None:
    """CheckParticipantExists returns FAILURE when case is missing."""
    result = bt_scenario.run(
        CheckParticipantExists(
            case_id="https://example.org/cases/missing",
            actor_id=actor.id_,
        ),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_check_participant_exists_fails_without_matching_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckParticipantExists returns FAILURE when actor has no participant."""
    other_participant = VultronParticipant(
        id_="https://example.org/participants/other-cp-001",
        attributed_to="https://example.org/actors/other",
        context="https://example.org/cases/case-002",
    )
    case = VultronCase(
        id_="https://example.org/cases/case-002",
        name="Other Participant Case",
        vulnerability_reports=[report.id_],
        case_participants=[other_participant.id_],
        attributed_to=actor.id_,
    )
    bt_scenario.seed(other_participant, case)

    result = bt_scenario.run(
        CheckParticipantExists(case_id=case.id_, actor_id=actor.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)
