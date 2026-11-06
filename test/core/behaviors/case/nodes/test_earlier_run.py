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

"""A re-run is told from a first run by the record alone (ADR-0154).

``began_in_an_earlier_run`` answers from the message's record, and
:class:`FirstRunOfMessageNode` is the condition the refusal stages ask it
through.  Each record a message can have is checked from both sides of
intake: before intake a record owed no replay in holding means a run left
it; after intake only ``HANDLED`` does, because intake writes a new message
``HELD`` and moves the record a run left to ``HANDLED``.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.case.nodes.test_seen_before import (
    ACTIVITY_ID,
    RECEIVER,
    _event,
)
from test.support.received import body_of
from vultron.core.behaviors.case.nodes.earlier_run import (
    FirstRunOfMessageNode,
)
from vultron.core.behaviors.helpers import ACTIVITY_UNAVAILABLE
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.services.received_activity import began_in_an_earlier_run


@pytest.fixture
def scenario() -> BTTestScenario:
    return BTTestScenario(actor_id=RECEIVER)


def _hold(scenario: BTTestScenario, **fields) -> None:
    scenario.dl.create(
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID,
            received_body=body_of(_event().activity),
            **fields,
        )
    )


#: (record, began in an earlier run: before intake, after intake)
_CASES = {
    "no record": (None, False, False),
    "intake's record": (
        {"stage": ReceivedStage.HELD, "replay_owed": False},
        True,
        False,
    ),
    "handled again": (
        {"stage": ReceivedStage.HANDLED, "replay_owed": False},
        True,
        True,
    ),
    "waiting": (
        {"stage": ReceivedStage.HELD, "replay_owed": True},
        False,
        False,
    ),
    "archived": ({"stage": ReceivedStage.ARCHIVED}, False, False),
}


@pytest.mark.spec("CLP-10-074")
@pytest.mark.spec("CLP-10-044")
@pytest.mark.parametrize(
    ("fields", "before", "after"), _CASES.values(), ids=list(_CASES)
)
def test_the_record_tells_a_rerun_on_each_side_of_intake(
    scenario, fields, before, after
):
    if fields is not None:
        _hold(scenario, **fields)

    assert (
        began_in_an_earlier_run(scenario.dl, ACTIVITY_ID, intake_ran=False)
        is before
    )
    assert (
        began_in_an_earlier_run(scenario.dl, ACTIVITY_ID, intake_ran=True)
        is after
    )


@pytest.mark.spec("CLP-10-044")
@pytest.mark.parametrize("intake_ran", [False, True])
def test_the_condition_fails_on_a_rerun_and_passes_a_first_run(
    scenario, intake_ran
):
    first = scenario.run(
        FirstRunOfMessageNode(intake_ran=intake_ran), activity=_event()
    )
    _hold(scenario, stage=ReceivedStage.HANDLED)
    rerun = scenario.run(
        FirstRunOfMessageNode(intake_ran=intake_ran), activity=_event()
    )

    assert first.status == Status.SUCCESS
    assert rerun.status == Status.FAILURE


@pytest.mark.spec("ARCH-15-001")
def test_the_condition_fails_closed_without_a_received_event(scenario):
    node = FirstRunOfMessageNode(intake_ran=True)

    result = scenario.run(node, activity="not-an-event")

    assert result.status == Status.FAILURE
    assert node.feedback_message == ACTIVITY_UNAVAILABLE
