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

"""Unit tests for participant RM transition behavior via CreateParticipantStatusNode.

Per ADR-0089 AC-4: TransitionParticipantRMtoAccepted and
TransitionParticipantRMtoDeferred bypass nodes were deleted; their behavior is
now provided directly by CreateParticipantStatusNode.
"""

import pytest
from typing import Any, cast

from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from test.core.behaviors.bt_harness import BTTestScenario


@pytest.fixture
def case_with_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> tuple[VulnerabilityCase, VultronParticipant]:
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
                rm=RmDimension(state=RM.RECEIVED),
            ),
            ParticipantStatus(
                attributed_to=actor.id_,
                context=case_id,
                rm=RmDimension(state=RM.VALID),
            ),
        ],
    )
    case = VulnerabilityCase(
        id_=case_id,
        name="Participant Case",
        vulnerability_reports=[report.id_],
        case_participants=[participant.id_],
        actor_participant_index={actor.id_: participant.id_},
        attributed_to=actor.id_,
    )
    bt_scenario.seed(participant, case)
    return case, participant


@pytest.fixture
def case_without_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> VulnerabilityCase:
    """Create a case without a participant for the test actor."""
    case = VulnerabilityCase(
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
    case_with_participant: tuple[VulnerabilityCase, VultronParticipant],
) -> None:
    """CreateParticipantStatusNode(rm_state=ACCEPTED) appends RM.ACCEPTED."""
    case, participant = case_with_participant
    result = bt_scenario.run(
        CreateParticipantStatusNode(
            actor_id=actor.id_,
            rm_state=RM.ACCEPTED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        ),
        actor_id=actor.id_,
        case_id=case.id_,
    )
    bt_scenario.assert_success(result)

    updated_participant = cast(Any, bt_scenario.dl.read(participant.id_))
    assert updated_participant is not None
    assert updated_participant.participant_statuses[-1].rm.state == RM.ACCEPTED


def test_transition_participant_rm_to_accepted_same_state_persists_confirmation(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_participant: tuple[VulnerabilityCase, VultronParticipant],
) -> None:
    """CreateParticipantStatusNode(rm_state=ACCEPTED) called twice appends two records.

    AC-4 (issue #3204): same-state writes are valid confirmation records and
    MUST be persisted.  ``CreateParticipantStatusNode`` is the sole writer; it
    does not suppress duplicate writes — callers that need idempotency must add
    their own guard (e.g. the ``IdempotentTransitionRMtoAccepted`` Selector in
    ``create_engage_case_tree``).
    """
    case, participant = case_with_participant

    bt_scenario.assert_success(
        bt_scenario.run(
            CreateParticipantStatusNode(
                actor_id=actor.id_,
                rm_state=RM.ACCEPTED,
                vf_state=None,
                d_state=None,
                pxa_state=None,
            ),
            actor_id=actor.id_,
            case_id=case.id_,
        )
    )
    bt_scenario.assert_success(
        bt_scenario.run(
            CreateParticipantStatusNode(
                actor_id=actor.id_,
                rm_state=RM.ACCEPTED,
                vf_state=None,
                d_state=None,
                pxa_state=None,
            ),
            actor_id=actor.id_,
            case_id=case.id_,
        )
    )

    updated_participant = cast(Any, bt_scenario.dl.read(participant.id_))
    assert updated_participant is not None
    accepted_entries = [
        status
        for status in updated_participant.participant_statuses
        if status.rm.state == RM.ACCEPTED
    ]
    # Both writes persisted: first is the transition, second is an AC-4 confirmation.
    assert len(accepted_entries) == 2


def test_transition_participant_rm_to_accepted_fails_without_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_without_participant: VulnerabilityCase,
) -> None:
    """CreateParticipantStatusNode(rm_state=ACCEPTED) fails when actor has no participant."""
    result = bt_scenario.run(
        CreateParticipantStatusNode(
            actor_id=actor.id_,
            rm_state=RM.ACCEPTED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        ),
        actor_id=actor.id_,
        case_id=case_without_participant.id_,
    )
    bt_scenario.assert_failure(result)


def test_transition_participant_rm_to_deferred(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_participant: tuple[VulnerabilityCase, VultronParticipant],
) -> None:
    """CreateParticipantStatusNode(rm_state=DEFERRED) appends RM.DEFERRED."""
    case, participant = case_with_participant
    result = bt_scenario.run(
        CreateParticipantStatusNode(
            actor_id=actor.id_,
            rm_state=RM.DEFERRED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        ),
        actor_id=actor.id_,
        case_id=case.id_,
    )
    bt_scenario.assert_success(result)

    updated_participant = cast(Any, bt_scenario.dl.read(participant.id_))
    assert updated_participant is not None
    assert updated_participant.participant_statuses[-1].rm.state == RM.DEFERRED


def test_transition_participant_rm_to_deferred_same_state_persists_confirmation(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_with_participant: tuple[VulnerabilityCase, VultronParticipant],
) -> None:
    """CreateParticipantStatusNode(rm_state=DEFERRED) called twice appends two records.

    AC-4 (issue #3204): same-state writes are valid confirmation records and
    MUST be persisted.  ``CreateParticipantStatusNode`` is the sole writer; it
    does not suppress duplicate writes — callers that need idempotency must add
    their own guard (e.g. the ``IdempotentTransitionRMtoDeferred`` Selector in
    ``create_defer_case_tree``).
    """
    case, participant = case_with_participant

    bt_scenario.assert_success(
        bt_scenario.run(
            CreateParticipantStatusNode(
                actor_id=actor.id_,
                rm_state=RM.DEFERRED,
                vf_state=None,
                d_state=None,
                pxa_state=None,
            ),
            actor_id=actor.id_,
            case_id=case.id_,
        )
    )
    bt_scenario.assert_success(
        bt_scenario.run(
            CreateParticipantStatusNode(
                actor_id=actor.id_,
                rm_state=RM.DEFERRED,
                vf_state=None,
                d_state=None,
                pxa_state=None,
            ),
            actor_id=actor.id_,
            case_id=case.id_,
        )
    )

    updated_participant = cast(Any, bt_scenario.dl.read(participant.id_))
    assert updated_participant is not None
    deferred_entries = [
        status
        for status in updated_participant.participant_statuses
        if status.rm.state == RM.DEFERRED
    ]
    # Both writes persisted: first is the transition, second is an AC-4 confirmation.
    assert len(deferred_entries) == 2


def test_transition_participant_rm_to_deferred_fails_without_participant(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    case_without_participant: VulnerabilityCase,
) -> None:
    """CreateParticipantStatusNode(rm_state=DEFERRED) fails when actor has no participant."""
    result = bt_scenario.run(
        CreateParticipantStatusNode(
            actor_id=actor.id_,
            rm_state=RM.DEFERRED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        ),
        actor_id=actor.id_,
        case_id=case_without_participant.id_,
    )
    bt_scenario.assert_failure(result)
