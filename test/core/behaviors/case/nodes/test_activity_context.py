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
"""The activity-context guard of Add(ParticipantStatus) (HP-08-015)."""

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.activity_context import (
    ActivityContextMatchesObjectNode,
)

CASE_A = "https://example.org/cases/a"
CASE_B = "https://example.org/cases/b"
STATUS_ID = f"{CASE_A}/statuses/s1"


def _run(
    activity: str | None, obj: str | None
) -> ActivityContextMatchesObjectNode:
    node = ActivityContextMatchesObjectNode(
        activity_context_id=activity,
        object_context_id=obj,
        object_id=STATUS_ID,
    )
    BTTestScenario().run(node)
    return node


@pytest.mark.spec("HP-08-015")
@pytest.mark.parametrize(
    "activity, obj",
    [(CASE_A, CASE_A), (None, CASE_A), (CASE_A, None), (None, None)],
    ids=["same", "no-activity-context", "no-object-context", "neither"],
)
def test_contexts_that_do_not_disagree_pass(activity, obj) -> None:
    assert _run(activity, obj).status == Status.SUCCESS


@pytest.mark.spec("HP-08-015")
def test_differing_contexts_are_refused_naming_both_cases() -> None:
    node = _run(CASE_B, CASE_A)

    assert node.status == Status.FAILURE
    assert node.feedback_message == (
        f"the activity's context names case '{CASE_B}' but '{STATUS_ID}'"
        f" names case '{CASE_A}' — REFUSED (HP-08-015)"
    )
