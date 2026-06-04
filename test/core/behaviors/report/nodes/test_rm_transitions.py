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
    TransitionRMtoInvalid,
    TransitionRMtoValid,
)
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.report import VultronReport
from vultron.core.models.activity import VultronOffer
from vultron.core.states.rm import RM
from test.core.behaviors.bt_harness import BTTestScenario


def test_transition_rm_to_valid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoValid updates report status to VALID."""
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
    """TransitionRMtoInvalid updates report status to INVALID."""
    result = bt_scenario.run(
        TransitionRMtoInvalid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.INVALID, actor_id=actor.id_)


def test_full_validation_workflow(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
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
