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

"""Unit tests for report case creation nodes."""

import pytest
from py_trees.composites import Sequence

from vultron.core.behaviors.helpers import UpdateActorOutbox
from vultron.core.behaviors.report.nodes.case_creation import (
    CreateCaseActivity,
    CreateCaseNode,
)
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.report import VultronReport
from vultron.core.models.activity import VultronOffer
from test.core.behaviors.bt_harness import BTTestScenario


def test_create_case_node(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
) -> None:
    """CreateCaseNode creates a VulnerabilityCase in the DataLayer."""
    result = bt_scenario.run(
        CreateCaseNode(report_id=report.id_),
        actor_id=actor.id_,
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
        CreateCaseNode(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result1)

    result2 = bt_scenario.run(
        CreateCaseNode(report_id=report.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result2)


def test_create_case_activity(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """CreateCaseActivity creates activity with recipients and embedded case."""
    reporter = VultronCaseActor(
        id_="https://example.org/actors/reporter",
        name="Reporter Co",
    )
    bt_scenario.dl.create(reporter)

    report.attributed_to = reporter.id_
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
    assert activity_data.get("to"), "CreateCaseActivity should have recipients"
    assert actor.id_ not in activity_data["to"]
    assert reporter.id_ in activity_data["to"]
    assert isinstance(activity_data.get("object_"), str)


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

    outbox_items = bt_scenario.dl.clone_for_actor(actor.id_).outbox_list()
    create_activities = bt_scenario.dl.by_type("Create")
    assert create_activities, "Expected at least one Create activity"
    activity_id = next(iter(create_activities))
    assert activity_id in outbox_items


def test_update_actor_outbox_missing_activity_id(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
) -> None:
    """UpdateActorOutbox fails if no preceding node set activity_id."""
    result = bt_scenario.run(UpdateActorOutbox(), actor_id=actor.id_)
    bt_scenario.assert_failure(result)


def test_update_actor_outbox_logs_create_activity_type(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """UpdateActorOutbox MUST log 'Create' activity type."""
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
    """UpdateActorOutbox MUST log the case ID in the outbox message."""
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
