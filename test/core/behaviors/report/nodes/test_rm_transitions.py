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
    _ReportPhaseRMTransition,
    TransitionRMtoClosed,
    TransitionRMtoInvalid,
    TransitionRMtoValid,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.report import VultronReport
from vultron.core.models.activity import VultronOffer
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM
from test.core.behaviors.bt_harness import BTTestScenario


@pytest.mark.spec("RMB-15-001")
@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_valid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
    report_case_link: VultronReportCaseLink,
) -> None:
    """TransitionRMtoValid updates report status to VALID.

    ``RM.VALID`` is case-scoped, so the case replica must be in this actor's own
    store and ``/case_id`` must be published for it (ISSUE-2548).
    """
    result = bt_scenario.run(
        TransitionRMtoValid(
            report_id=report.id_,
            offer_id=offer.id_,
            sender_actor_id=actor.id_,
        ),
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
    report_case_link: VultronReportCaseLink,
) -> None:
    """TransitionRMtoInvalid updates report status to INVALID."""
    result = bt_scenario.run(
        TransitionRMtoInvalid(
            report_id=report.id_,
            offer_id=offer.id_,
            sender_actor_id=actor.id_,
        ),
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
    report_case_link: VultronReportCaseLink,
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
            TransitionRMtoValid(
                report_id=report.id_,
                offer_id=offer.id_,
                sender_actor_id=actor.id_,
            ),
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
# AC-2: RM transitions write the correct rm_state on VultronReportCaseLink
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_valid_sets_link_rm_state(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
    report_case_link: VultronReportCaseLink,
) -> None:
    """TransitionRMtoValid writes RM.VALID to VultronReportCaseLink.rm_state."""
    result = bt_scenario.run(
        TransitionRMtoValid(
            report_id=report.id_,
            offer_id=offer.id_,
            sender_actor_id=actor.id_,
        ),
        actor_id=actor.id_,
        case_id=case_with_participant.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.VALID)


@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_invalid_sets_link_rm_state(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    report_case_link: VultronReportCaseLink,
) -> None:
    """TransitionRMtoInvalid writes RM.INVALID to VultronReportCaseLink.rm_state."""
    result = bt_scenario.run(
        TransitionRMtoInvalid(
            report_id=report.id_,
            offer_id=offer.id_,
            sender_actor_id=actor.id_,
        ),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.INVALID)


@pytest.mark.spec("BTND-10-001")
@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_closed_sets_link_rm_state(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    report_case_link: VultronReportCaseLink,
) -> None:
    """TransitionRMtoClosed writes RM.CLOSED to VultronReportCaseLink.rm_state.

    Pre-seeds RM.INVALID so INVALID→CLOSED is a valid transition (BTND-10-001).
    """
    bt_scenario.dl.save(
        VultronReportCaseLink(report_id=report.id_, rm_state=RM.INVALID)
    )
    result = bt_scenario.run(
        TransitionRMtoClosed(
            report_id=report.id_,
            offer_id=offer.id_,
            sender_actor_id=actor.id_,
        ),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.CLOSED)


# ---------------------------------------------------------------------------
# AC-1: _ReportPhaseRMTransition base-class contract
# ---------------------------------------------------------------------------


def test_transition_rm_to_invalid_is_subclass_of_base() -> None:
    """TransitionRMtoInvalid inherits _ReportPhaseRMTransition."""
    assert issubclass(TransitionRMtoInvalid, _ReportPhaseRMTransition)


def test_transition_rm_to_closed_is_subclass_of_base() -> None:
    """TransitionRMtoClosed inherits _ReportPhaseRMTransition."""
    assert issubclass(TransitionRMtoClosed, _ReportPhaseRMTransition)


def test_transition_rm_to_valid_returns_sequence() -> None:
    """TransitionRMtoValid is a factory that returns a Sequence (ADR-0089 AC-5).

    After the sole-writer refactoring, TransitionRMtoValid produces a
    Sequence([CreateParticipantStatusNode, _ValidRMLatchNode]) so the
    case-scoped participant write is handled by the canonical writer.
    """
    import py_trees
    from vultron.core.behaviors.case.nodes.participant.status import (
        CreateParticipantStatusNode,
    )

    tree = TransitionRMtoValid(
        report_id="https://example.org/reports/r-001",
        offer_id="https://example.org/offers/o-001",
        sender_actor_id="https://example.org/actors/vendor-001",
    )
    assert isinstance(tree, py_trees.composites.Sequence)
    assert isinstance(tree.children[0], CreateParticipantStatusNode)
    assert isinstance(tree.children[1], _ReportPhaseRMTransition)


def test_transition_rm_to_invalid_target_rm() -> None:
    """TransitionRMtoInvalid._target_rm is RM.INVALID."""
    from vultron.core.states.rm import RM

    assert TransitionRMtoInvalid._target_rm is RM.INVALID


def test_transition_rm_to_closed_target_rm() -> None:
    """TransitionRMtoClosed._target_rm is RM.CLOSED."""
    from vultron.core.states.rm import RM

    assert TransitionRMtoClosed._target_rm is RM.CLOSED


@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_valid_without_case_fails_without_updating_link(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    report_case_link: VultronReportCaseLink,
) -> None:
    """No case in this actor's store ⇒ FAILURE, ReportCaseLink not updated.

    ISSUE-2548.  RM.VALID is case-scoped: when the case replica has not arrived
    yet, CreateParticipantStatusNode fails and the Sequence stops before
    _ValidRMLatchNode runs — so VultronReportCaseLink.rm_state must stay at
    RM.RECEIVED (ID-04-005, ARCH-15-001).
    """
    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)

    link_id = VultronReportCaseLink.build_id(report.id_)
    link = bt_scenario.dl.read(link_id)
    if isinstance(link, VultronReportCaseLink):
        assert link.rm_state != RM.VALID, (
            "TransitionRMtoValid updated ReportCaseLink.rm_state to RM.VALID even"
            " though the case-participant half of the transition never ran (ISSUE-2548)"
        )


def test_transition_rm_to_valid_without_participant_fails_without_updating_link(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case: VulnerabilityCase,
    report_case_link: VultronReportCaseLink,
) -> None:
    """Case present but actor not a participant ⇒ FAILURE, link not updated.

    ISSUE-2548, second half.  CreateParticipantStatusNode fails when the actor
    is absent from case.actor_participant_index; the Sequence stops and
    _ValidRMLatchNode never runs — ReportCaseLink.rm_state must stay at
    RM.RECEIVED.
    """
    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
        case_id=case.id_,
    )
    bt_scenario.assert_failure(result)

    link_id = VultronReportCaseLink.build_id(report.id_)
    link = bt_scenario.dl.read(link_id)
    if isinstance(link, VultronReportCaseLink):
        assert link.rm_state != RM.VALID, (
            "TransitionRMtoValid updated ReportCaseLink.rm_state to RM.VALID even"
            " though the case-participant RM update was blocked (ISSUE-2548)"
        )
