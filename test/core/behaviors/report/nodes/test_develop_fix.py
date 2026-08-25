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

"""Unit tests for develop_fix and deploy_fix participant-RM guard nodes."""

import pytest

from vultron.core.behaviors.report.nodes.deploy_fix import RMinStateDeferred
from vultron.core.behaviors.report.nodes.develop_fix import (
    _CheckParticipantRMStateBase,
    CheckRMStateAccepted,
)
from vultron.core.models.case import VultronCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from test.core.behaviors.bt_harness import BTTestScenario

# ---------------------------------------------------------------------------
# AC-3: _CheckParticipantRMStateBase base-class contract
# ---------------------------------------------------------------------------


def test_check_rm_state_accepted_is_subclass_of_base() -> None:
    """CheckRMStateAccepted inherits _CheckParticipantRMStateBase."""
    assert issubclass(CheckRMStateAccepted, _CheckParticipantRMStateBase)


def test_rm_in_state_deferred_is_subclass_of_base() -> None:
    """RMinStateDeferred inherits _CheckParticipantRMStateBase."""
    assert issubclass(RMinStateDeferred, _CheckParticipantRMStateBase)


def test_check_rm_state_accepted_target_rm() -> None:
    """CheckRMStateAccepted._target_rm is RM.ACCEPTED."""
    assert CheckRMStateAccepted._target_rm is RM.ACCEPTED


def test_rm_in_state_deferred_target_rm() -> None:
    """RMinStateDeferred._target_rm is RM.DEFERRED."""
    assert RMinStateDeferred._target_rm is RM.DEFERRED


# ---------------------------------------------------------------------------
# Behavioural tests for _CheckParticipantRMStateBase via CheckRMStateAccepted
# ---------------------------------------------------------------------------


@pytest.fixture
def case_with_accepted_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> tuple[VultronCase, VultronParticipant]:
    """Case whose participant is in RM.ACCEPTED."""
    case_id = "https://example.org/cases/case-accepted-001"
    participant = VultronParticipant(
        id_="https://example.org/participants/vendor-accepted-001",
        attributed_to=actor.id_,
        context=case_id,
        participant_statuses=[
            ParticipantStatus(
                attributed_to=actor.id_,
                context=case_id,
                rm=RmDimension(state=RM.RECEIVED),
            ),
            ParticipantStatus(
                attributed_to=actor.id_,
                context=case_id,
                rm=RmDimension(state=RM.VALID),
            ),
            ParticipantStatus(
                attributed_to=actor.id_,
                context=case_id,
                rm=RmDimension(state=RM.ACCEPTED),
            ),
        ],
    )
    case = VultronCase(
        id_=case_id,
        name="Accepted Participant Case",
        vulnerability_reports=[report.id_],
        case_participants=[participant.id_],
        actor_participant_index={actor.id_: participant.id_},
        attributed_to=actor.id_,
    )
    bt_scenario.seed(participant, case)
    return case, participant


@pytest.fixture
def case_with_deferred_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> tuple[VultronCase, VultronParticipant]:
    """Case whose participant is in RM.DEFERRED."""
    case_id = "https://example.org/cases/case-deferred-001"
    participant = VultronParticipant(
        id_="https://example.org/participants/vendor-deferred-001",
        attributed_to=actor.id_,
        context=case_id,
        participant_statuses=[
            ParticipantStatus(
                attributed_to=actor.id_,
                context=case_id,
                rm=RmDimension(state=RM.RECEIVED),
            ),
            ParticipantStatus(
                attributed_to=actor.id_,
                context=case_id,
                rm=RmDimension(state=RM.VALID),
            ),
            ParticipantStatus(
                attributed_to=actor.id_,
                context=case_id,
                rm=RmDimension(state=RM.DEFERRED),
            ),
        ],
    )
    case = VultronCase(
        id_=case_id,
        name="Deferred Participant Case",
        vulnerability_reports=[report.id_],
        case_participants=[participant.id_],
        actor_participant_index={actor.id_: participant.id_},
        attributed_to=actor.id_,
    )
    bt_scenario.seed(participant, case)
    return case, participant


def test_check_rm_state_accepted_succeeds_when_accepted(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_accepted_participant: tuple[VultronCase, VultronParticipant],
) -> None:
    """CheckRMStateAccepted returns SUCCESS when actor RM is ACCEPTED."""
    case, _ = case_with_accepted_participant
    result = bt_scenario.run(
        CheckRMStateAccepted(case_id=case.id_, actor_id=actor.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_check_rm_state_accepted_fails_when_deferred(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_deferred_participant: tuple[VultronCase, VultronParticipant],
) -> None:
    """CheckRMStateAccepted returns FAILURE when actor RM is DEFERRED."""
    case, _ = case_with_deferred_participant
    result = bt_scenario.run(
        CheckRMStateAccepted(case_id=case.id_, actor_id=actor.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_rm_in_state_deferred_succeeds_when_deferred(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_deferred_participant: tuple[VultronCase, VultronParticipant],
) -> None:
    """RMinStateDeferred returns SUCCESS when actor RM is DEFERRED."""
    case, _ = case_with_deferred_participant
    result = bt_scenario.run(
        RMinStateDeferred(case_id=case.id_, actor_id=actor.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_rm_in_state_deferred_fails_when_accepted(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_accepted_participant: tuple[VultronCase, VultronParticipant],
) -> None:
    """RMinStateDeferred returns FAILURE when actor RM is ACCEPTED."""
    case, _ = case_with_accepted_participant
    result = bt_scenario.run(
        RMinStateDeferred(case_id=case.id_, actor_id=actor.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_check_rm_state_accepted_fails_without_case(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
) -> None:
    """CheckRMStateAccepted returns FAILURE when case is not found."""
    result = bt_scenario.run(
        CheckRMStateAccepted(
            case_id="https://example.org/cases/missing",
            actor_id=actor.id_,
        ),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_check_rm_state_accepted_fails_without_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CheckRMStateAccepted returns FAILURE when actor has no participant."""
    case = VultronCase(
        id_="https://example.org/cases/no-participant",
        name="No Participant Case",
        vulnerability_reports=[report.id_],
        attributed_to=actor.id_,
    )
    bt_scenario.seed(case)
    result = bt_scenario.run(
        CheckRMStateAccepted(case_id=case.id_, actor_id=actor.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)
