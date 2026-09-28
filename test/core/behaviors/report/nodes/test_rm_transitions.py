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
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.activity import VultronOffer
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario
from test.support.participant_status import advance_participant_rm


@pytest.mark.spec("RMB-15-001")
@pytest.mark.spec("BT-03-004")
def test_transition_rm_to_valid(
    bt_scenario: BTTestScenario,
    actor: CaseActor,
    report: VulnerabilityReport,
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
    actor: CaseActor,
    report: VulnerabilityReport,
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
    actor: CaseActor,
    report: VulnerabilityReport,
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
    actor: CaseActor,
    report: VulnerabilityReport,
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
    actor: CaseActor,
    report: VulnerabilityReport,
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
    actor: CaseActor,
    report: VulnerabilityReport,
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
    actor: CaseActor,
    report: VulnerabilityReport,
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
    actor: CaseActor,
    report: VulnerabilityReport,
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
def test_transition_rm_to_valid_absent_link_advances_without_latching(
    bt_scenario: BTTestScenario,
    actor: CaseActor,
    report: VulnerabilityReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
) -> None:
    """Absent ReportCaseLink: advance the participant, do NOT latch the link.

    Issue #3283.  The #3267 rewrite gated the participant advance behind a
    successful link read, so a store that reached the VALID transition without a
    prior link-seeding node (e.g. the CaseActor advancing a participant it
    tracks) was stranded at RM.RECEIVED.  The pre-#3267 design advanced the
    participant regardless.  But because the link is report-scoped *per store*,
    latching an absent link to VALID for one participant would make
    ``CheckRMStateValid`` short-circuit every sibling participant in a shared
    CaseActor store (the fcvcv/fvcv-handoff regression).  So the node advances
    the participant's own record while leaving the absent link unpersisted.
    This fixture omits the ``report_case_link`` fixture: no link exists, but the
    case + participant do.
    """
    from vultron.core.models.participant_status import (
        participant_status_rm_state,
    )

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

    # The participant's own record advanced to RM.VALID.
    participant_id = case_with_participant.actor_participant_index[actor.id_]
    participant = bt_scenario.dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    assert (
        participant_status_rm_state(participant.participant_status) == RM.VALID
    )

    # The absent report-scoped link was NOT latched to VALID — otherwise it
    # would short-circuit sibling participants' validate in a shared store.
    link = bt_scenario.dl.read(link_id)
    assert not (
        isinstance(link, VultronReportCaseLink) and link.rm_state == RM.VALID
    ), "an absent report link must not be latched to VALID (issue #3283)"


@pytest.mark.spec("BT-03-004")
def test_two_participants_one_report_both_reach_valid_in_shared_store(
    bt_scenario: BTTestScenario,
    actor: CaseActor,
    report: VulnerabilityReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
) -> None:
    """fcvcv-in-miniature: two participants on one report both reach RM.VALID.

    Issue #3283 / #3266.  The CaseActor's store holds every participant of the
    one report but only one report-scoped ``ReportCaseLink``.  If the first
    participant's validate latches that shared link to VALID, ``CheckRMStateValid``
    short-circuits the second participant's validate and it never advances — the
    fcvcv/fvcv-handoff regression.  With no link pre-seeded, advancing participant
    A must leave the shared link unlatched so participant B still advances.
    """
    from vultron.core.models.participant_status import (
        participant_status_rm_state,
    )

    case = case_with_participant
    actor_a = actor.id_  # already a participant at RECEIVED (the fixture)
    actor_b = "https://example.org/actors/second-participant"
    participant_b = CaseParticipant(
        id_=f"{case.id_}/participants/second",
        attributed_to=actor_b,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
    )
    advance_participant_rm(participant_b, RM.RECEIVED, actor_b, case.id_)
    case.add_participant(participant_b)
    bt_scenario.dl.create(participant_b)
    bt_scenario.dl.save(case)

    # No ReportCaseLink in the shared store (the CaseActor never received Offer).
    link_id = VultronReportCaseLink.build_id(report.id_)
    assert not isinstance(bt_scenario.dl.read(link_id), VultronReportCaseLink)

    # Participant A validates first.
    bt_scenario.assert_success(
        bt_scenario.run(
            TransitionRMtoValid(
                report_id=report.id_,
                offer_id=offer.id_,
                sender_actor_id=actor_a,
            ),
            actor_id=actor_a,
            case_id=case.id_,
        )
    )
    # The idempotency gate must NOT report the report valid yet — otherwise B
    # would be short-circuited.
    bt_scenario.assert_failure(
        bt_scenario.run(
            CheckRMStateValid(report_id=report.id_, sender_actor_id=actor_b),
            actor_id=actor_a,
        )
    )
    # Participant B validates and also advances.
    bt_scenario.assert_success(
        bt_scenario.run(
            TransitionRMtoValid(
                report_id=report.id_,
                offer_id=offer.id_,
                sender_actor_id=actor_b,
            ),
            actor_id=actor_a,
            case_id=case.id_,
        )
    )

    pa = bt_scenario.dl.read(case.actor_participant_index[actor_a])
    pb = bt_scenario.dl.read(case.actor_participant_index[actor_b])
    assert isinstance(pa, CaseParticipant) and isinstance(pb, CaseParticipant)
    assert participant_status_rm_state(pa.participant_status) == RM.VALID
    assert participant_status_rm_state(pb.participant_status) == RM.VALID
