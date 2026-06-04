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

"""Unit tests for report participant transition nodes."""

import pytest

from vultron.core.behaviors.report.nodes.participant import (
    TransitionParticipantRMtoAccepted,
    TransitionParticipantRMtoDeferred,
)
from vultron.core.models.case import VultronCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from test.core.behaviors.bt_harness import BTTestScenario


@pytest.fixture
def case_with_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> tuple[VultronCase, VultronParticipant]:
    """Create a case whose participant is already in RM.VALID."""
    case_id = "https://example.org/cases/case-001"
    participant = VultronParticipant(
        id_="https://example.org/participants/vendor-cp-001",
        attributed_to=actor.id_,
        context=case_id,
        participant_statuses=[
            ParticipantStatus(
                attributed_to=actor.id_,
                context=case_id,
                rm_state=RM.RECEIVED,
            ),
            ParticipantStatus(
                attributed_to=actor.id_,
                context=case_id,
                rm_state=RM.VALID,
            ),
        ],
    )
    case = VultronCase(
        id_=case_id,
        name="Participant Case",
        vulnerability_reports=[report.id_],
        case_participants=[participant.id_],
        attributed_to=actor.id_,
    )
    bt_scenario.seed(participant, case)
    return case, participant


@pytest.fixture
def case_without_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> VultronCase:
    """Create a case without a participant for the test actor."""
    case = VultronCase(
        id_="https://example.org/cases/case-002",
        name="Missing Participant Case",
        vulnerability_reports=[report.id_],
        attributed_to=actor.id_,
    )
    bt_scenario.seed(case)
    return case


def test_transition_participant_rm_to_accepted(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_participant: tuple[VultronCase, VultronParticipant],
) -> None:
    """TransitionParticipantRMtoAccepted appends RM.ACCEPTED."""
    case, participant = case_with_participant
    result = bt_scenario.run(
        TransitionParticipantRMtoAccepted(
            case_id=case.id_, actor_id=actor.id_
        ),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)

    updated_participant = bt_scenario.dl.read(participant.id_)
    assert updated_participant is not None
    assert updated_participant.participant_statuses[-1].rm_state == RM.ACCEPTED


def test_transition_participant_rm_to_accepted_is_idempotent(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_participant: tuple[VultronCase, VultronParticipant],
) -> None:
    """TransitionParticipantRMtoAccepted does not append duplicates."""
    case, participant = case_with_participant

    bt_scenario.assert_success(
        bt_scenario.run(
            TransitionParticipantRMtoAccepted(
                case_id=case.id_,
                actor_id=actor.id_,
            ),
            actor_id=actor.id_,
        )
    )
    bt_scenario.assert_success(
        bt_scenario.run(
            TransitionParticipantRMtoAccepted(
                case_id=case.id_,
                actor_id=actor.id_,
            ),
            actor_id=actor.id_,
        )
    )

    updated_participant = bt_scenario.dl.read(participant.id_)
    assert updated_participant is not None
    accepted_entries = [
        status
        for status in updated_participant.participant_statuses
        if status.rm_state == RM.ACCEPTED
    ]
    assert len(accepted_entries) == 1


def test_transition_participant_rm_to_accepted_fails_without_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_without_participant: VultronCase,
) -> None:
    """TransitionParticipantRMtoAccepted fails when actor has no participant."""
    result = bt_scenario.run(
        TransitionParticipantRMtoAccepted(
            case_id=case_without_participant.id_,
            actor_id=actor.id_,
        ),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_transition_participant_rm_to_deferred(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_participant: tuple[VultronCase, VultronParticipant],
) -> None:
    """TransitionParticipantRMtoDeferred appends RM.DEFERRED."""
    case, participant = case_with_participant
    result = bt_scenario.run(
        TransitionParticipantRMtoDeferred(
            case_id=case.id_, actor_id=actor.id_
        ),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)

    updated_participant = bt_scenario.dl.read(participant.id_)
    assert updated_participant is not None
    assert updated_participant.participant_statuses[-1].rm_state == RM.DEFERRED


def test_transition_participant_rm_to_deferred_is_idempotent(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_participant: tuple[VultronCase, VultronParticipant],
) -> None:
    """TransitionParticipantRMtoDeferred does not append duplicates."""
    case, participant = case_with_participant

    bt_scenario.assert_success(
        bt_scenario.run(
            TransitionParticipantRMtoDeferred(
                case_id=case.id_,
                actor_id=actor.id_,
            ),
            actor_id=actor.id_,
        )
    )
    bt_scenario.assert_success(
        bt_scenario.run(
            TransitionParticipantRMtoDeferred(
                case_id=case.id_,
                actor_id=actor.id_,
            ),
            actor_id=actor.id_,
        )
    )

    updated_participant = bt_scenario.dl.read(participant.id_)
    assert updated_participant is not None
    deferred_entries = [
        status
        for status in updated_participant.participant_statuses
        if status.rm_state == RM.DEFERRED
    ]
    assert len(deferred_entries) == 1


def test_transition_participant_rm_to_deferred_fails_without_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_without_participant: VultronCase,
) -> None:
    """TransitionParticipantRMtoDeferred fails when actor has no participant."""
    result = bt_scenario.run(
        TransitionParticipantRMtoDeferred(
            case_id=case_without_participant.id_,
            actor_id=actor.id_,
        ),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)
