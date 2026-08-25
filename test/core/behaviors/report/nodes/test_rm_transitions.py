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

"""Unit tests for report RM transition nodes."""

from typing import Any

import pytest
from py_trees.composites import Sequence

from vultron.core.behaviors.helpers import UpdateActorOutbox
from vultron.core.behaviors.report.nodes.case_creation import (
    CreateCaseActivity,
    CreateCaseNode,
)
from vultron.core.behaviors.report.nodes.conditions import (
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    EvaluateReportCredibility,
    EvaluateReportValidity,
)
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionRMtoClosed,
    TransitionRMtoInvalid,
    TransitionRMtoValid,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.models.activity import VultronOffer
from vultron.core.states.rm import RM
from vultron.core.models._helpers import _report_phase_status_id
from test.core.behaviors.bt_harness import BTTestScenario


@pytest.mark.spec("RMB-15-001")
@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_valid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
) -> None:
    """TransitionRMtoValid updates report status to VALID.

    ``RM.VALID`` is case-scoped, so the case replica must be in this actor's own
    store and ``/case_id`` must be published for it (ISSUE-2548).
    """
    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
        case_id=case_with_participant.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.VALID, actor_id=actor.id_)


@pytest.mark.spec("RMB-15-001")
@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_invalid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoInvalid updates report status to INVALID."""
    result = bt_scenario.run(
        TransitionRMtoInvalid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.INVALID, actor_id=actor.id_)


@pytest.mark.spec("BT-10-001")
@pytest.mark.spec("BT-03-004")
def test_full_validation_workflow(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
) -> None:
    """Test full validation workflow using all nodes in sequence."""
    bt_scenario.assert_failure(
        bt_scenario.run(
            CheckRMStateValid(report_id=report.id_),
            actor_id=actor.id_,
        )
    )

    bt_scenario.assert_success(
        bt_scenario.run(
            CheckRMStateReceivedOrInvalid(report_id=report.id_),
            actor_id=actor.id_,
        )
    )

    bt_scenario.assert_success(
        bt_scenario.run(
            EvaluateReportCredibility(report_id=report.id_),
            actor_id=actor.id_,
        )
    )

    bt_scenario.assert_success(
        bt_scenario.run(
            EvaluateReportValidity(report_id=report.id_),
            actor_id=actor.id_,
        )
    )

    bt_scenario.assert_success(
        bt_scenario.run(
            TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
            actor_id=actor.id_,
            case_id=case_with_participant.id_,
        )
    )

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

    bt_scenario.assert_rm_state(report.id_, RM.VALID, actor_id=actor.id_)


# ---------------------------------------------------------------------------
# AC-2: ParticipantStatus.context uses case URI when case exists (CLP-07-007)
# ---------------------------------------------------------------------------


def _read_status(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    rm_state: RM,
) -> Any:
    """Read a report-phase ParticipantStatus and assert it exists."""
    status_id = _report_phase_status_id(actor.id_, report.id_, rm_state.value)
    obj = bt_scenario.dl.read(status_id)
    assert (
        obj is not None
    ), f"No ParticipantStatus found at {status_id!r} in DataLayer"
    # Two ParticipantStatus classes exist (core + wire). Check by type_ string.
    assert (
        getattr(obj, "type_", None) == "ParticipantStatus"
    ), f"Expected ParticipantStatus at {status_id!r}, got {type(obj).__name__}"
    return obj


@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_valid_context_is_case_uri(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
) -> None:
    """TransitionRMtoValid sets ParticipantStatus.context to the case URI."""
    case = case_with_participant
    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
        case_id=case.id_,
    )
    bt_scenario.assert_success(result)

    status = _read_status(bt_scenario, actor, report, RM.VALID)
    ctx = getattr(status, "context", None)
    assert ctx == case.id_, (
        f"Expected context={case.id_!r}, got {ctx!r} "
        "(report URI must not appear in ParticipantStatus.context, CLP-07-007)"
    )
    assert (
        ctx != report.id_
    ), "ParticipantStatus.context must not be the report URI (CLP-07-007)"


@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_invalid_context_is_case_uri(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case: VulnerabilityCase,
) -> None:
    """TransitionRMtoInvalid sets ParticipantStatus.context to the case URI."""
    result = bt_scenario.run(
        TransitionRMtoInvalid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)

    status = _read_status(bt_scenario, actor, report, RM.INVALID)
    ctx = getattr(status, "context", None)
    assert ctx == case.id_, (
        f"Expected context={case.id_!r}, got {ctx!r} "
        "(report URI must not appear in ParticipantStatus.context, CLP-07-007)"
    )


@pytest.mark.spec("BTND-10-001")
@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_closed_context_is_case_uri(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case: VulnerabilityCase,
) -> None:
    """TransitionRMtoClosed sets ParticipantStatus.context to the case URI."""
    # Pre-seed RM.INVALID so INVALID→CLOSED is a valid transition (BTND-10-001).
    bt_scenario.seed(
        ParticipantStatus(
            id_=_report_phase_status_id(
                actor.id_, report.id_, RM.INVALID.value
            ),
            context=case.id_,
            attributed_to=actor.id_,
            rm=RmDimension(state=RM.INVALID),
        )
    )
    result = bt_scenario.run(
        TransitionRMtoClosed(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)

    status = _read_status(bt_scenario, actor, report, RM.CLOSED)
    ctx = getattr(status, "context", None)
    assert ctx == case.id_, (
        f"Expected context={case.id_!r}, got {ctx!r} "
        "(report URI must not appear in ParticipantStatus.context, CLP-07-007)"
    )


@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_valid_without_case_fails_without_writing_status(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """No case in this actor's store ⇒ FAILURE, and no RM.VALID record written.

    ISSUE-2548.  RM.VALID is a *case-scoped* transition: DUR-07-004 requires an
    established embargo, and the participant's RM state lives on the case.  When
    the case has not been delivered to this actor's store yet (ADR-0072 gives
    every actor its own store; co-located actors still exchange state only by
    protocol message, PCR-01-003), neither half can be performed — so the node
    MUST return FAILURE (ARCH-15-001) and MUST NOT write the report-phase
    RM.VALID record, because that record is the idempotency latch that
    ``CheckRMStateValid`` reads (ID-04-005).  Writing it for a transition that
    did not happen latches the actor out of ever retrying.
    """
    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)

    status_id = _report_phase_status_id(actor.id_, report.id_, RM.VALID.value)
    assert bt_scenario.dl.read(status_id) is None, (
        "TransitionRMtoValid wrote the report-phase RM.VALID latch even though"
        " the case-participant half of the transition never ran (ISSUE-2548)"
    )


def test_transition_rm_to_valid_without_participant_fails_without_writing_status(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case: VulnerabilityCase,
) -> None:
    """Case present but actor not a participant ⇒ FAILURE, no latch written.

    ISSUE-2548, second half.  ``update_participant_rm_state`` returns ``False``
    when the acting actor is absent from the case's ``actor_participant_index``
    — the case replica arrived dehydrated.  The report-phase latch must not be
    written on that path either.
    """
    # The bare ``case`` fixture has no participants, so the participant half
    # cannot run.
    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
        case_id=case.id_,
    )
    bt_scenario.assert_failure(result)

    status_id = _report_phase_status_id(actor.id_, report.id_, RM.VALID.value)
    assert bt_scenario.dl.read(status_id) is None, (
        "TransitionRMtoValid wrote the report-phase RM.VALID latch even though"
        " the case-participant RM update was blocked (ISSUE-2548)"
    )
