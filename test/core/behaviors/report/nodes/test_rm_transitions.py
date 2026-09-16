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


def test_transition_rm_to_valid_is_single_atomic_node() -> None:
    """TransitionRMtoValid is one node, not a Sequence (issue #3267).

    It performs the case-scoped participant write (through the sole writer,
    CreateParticipantStatusNode) and the ReportCaseLink latch in a single
    execution, so a partial failure cannot leave the two records disagreeing.
    The writer is pre-built in __init__ (BTND-10-004), never constructed inside
    update().
    """
    import py_trees
    from vultron.core.behaviors.case.nodes.participant.status import (
        CreateParticipantStatusNode,
    )

    node = TransitionRMtoValid(
        report_id="https://example.org/reports/r-001",
        offer_id="https://example.org/offers/o-001",
        sender_actor_id="https://example.org/actors/vendor-001",
    )
    assert not isinstance(node, py_trees.composites.Sequence)
    assert isinstance(node, py_trees.behaviour.Behaviour)
    assert isinstance(node._status_node, CreateParticipantStatusNode)


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
    yet, the node fails at the case-scoped write and never reaches the link
    latch — so VultronReportCaseLink.rm_state must stay at RM.RECEIVED
    (ID-04-005, ARCH-15-001).
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

    ISSUE-2548, second half.  The case-scoped write fails when the actor is
    absent from case.actor_participant_index; the node never reaches the link
    latch — ReportCaseLink.rm_state must stay at RM.RECEIVED.
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


@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_valid_seeds_absent_link_and_advances(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
) -> None:
    """Absent ReportCaseLink is seeded, not fatal — participant still reaches VALID.

    Issue #3283.  The #3267 rewrite gated the participant advance behind a
    successful link read, so a store that reached the VALID transition without a
    prior link-seeding node (e.g. the CaseActor advancing a participant it
    tracks) was stranded at RM.RECEIVED — the fcvcv/fvcv-handoff demo
    regression.  The pre-#3267 design advanced the participant regardless.  This
    fixture deliberately omits the ``report_case_link`` fixture: no link exists
    in the store, but the case + participant do.  The node must seed the link at
    RM.RECEIVED, advance the participant, and latch the link to RM.VALID.
    """
    # Precondition: no link in the store.
    link_id = VultronReportCaseLink.build_id(report.id_)
    assert not isinstance(
        bt_scenario.dl.read(link_id), VultronReportCaseLink
    ), "test setup error: a ReportCaseLink was seeded despite omitting the fixture"

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

    # The link was seeded and latched to VALID in the same execution.
    link = bt_scenario.dl.read(link_id)
    assert isinstance(link, VultronReportCaseLink)
    assert link.rm_state is RM.VALID
