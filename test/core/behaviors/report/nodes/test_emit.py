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

"""Unit tests for report emit nodes."""

import pytest
from typing import Any, cast

from vultron.core.behaviors.report.nodes.emit import (
    EmitDeferCaseActivity,
    EmitEngageCaseActivity,
)
from vultron.core.models.case import VultronCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.report import VultronReport
from test.core.behaviors.bt_harness import BTTestScenario


@pytest.fixture
def peer_actor(bt_scenario: BTTestScenario) -> VultronCaseActor:
    """Create a peer actor that should receive emitted activities."""
    obj = VultronCaseActor(
        id_="https://example.org/actors/reporter",
        name="Reporter Co",
    )
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def case_with_peer(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    peer_actor: VultronCaseActor,
    report: VultronReport,
) -> VultronCase:
    """Create a case whose actor_participant_index includes a peer recipient."""
    case_id = "https://example.org/cases/case-emit"
    sender_participant = VultronParticipant(
        id_="https://example.org/participants/vendor-cp-emit",
        attributed_to=actor.id_,
        context=case_id,
    )
    peer_participant = VultronParticipant(
        id_="https://example.org/participants/reporter-cp-emit",
        attributed_to=peer_actor.id_,
        context=case_id,
    )
    case = VultronCase(
        id_=case_id,
        name="Emit Case",
        vulnerability_reports=[report.id_],
        case_participants=[sender_participant.id_, peer_participant.id_],
        actor_participant_index={
            actor.id_: sender_participant.id_,
            peer_actor.id_: peer_participant.id_,
        },
        attributed_to=actor.id_,
    )
    bt_scenario.seed(sender_participant, peer_participant, case)
    return case


def test_emit_engage_case_activity(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    peer_actor: VultronCaseActor,
    case_with_peer: VultronCase,
) -> None:
    """EmitEngageCaseActivity persists a Join activity and queues it."""
    result = bt_scenario.run(
        EmitEngageCaseActivity(case_id=case_with_peer.id_, actor_id=actor.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)

    outbox_items = bt_scenario.dl.clone_for_actor(actor.id_).outbox_list()
    assert len(outbox_items) == 1

    activity_id = outbox_items[0]
    activity = cast(Any, bt_scenario.dl.read(activity_id))
    assert activity is not None
    assert str(getattr(activity, "type_", "")) == "Join"
    assert activity.to == [peer_actor.id_]
    assert (
        activity_id in bt_scenario.dl.clone_for_actor(actor.id_).outbox_list()
    )


def test_emit_defer_case_activity(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    peer_actor: VultronCaseActor,
    case_with_peer: VultronCase,
) -> None:
    """EmitDeferCaseActivity persists an Ignore activity and queues it."""
    result = bt_scenario.run(
        EmitDeferCaseActivity(case_id=case_with_peer.id_, actor_id=actor.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)

    outbox_items = bt_scenario.dl.clone_for_actor(actor.id_).outbox_list()
    assert len(outbox_items) == 1

    activity_id = outbox_items[0]
    activity = cast(Any, bt_scenario.dl.read(activity_id))
    assert activity is not None
    assert str(getattr(activity, "type_", "")) == "Ignore"
    assert activity.to == [peer_actor.id_]
    assert (
        activity_id in bt_scenario.dl.clone_for_actor(actor.id_).outbox_list()
    )
