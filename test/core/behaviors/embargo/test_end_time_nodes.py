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

"""The end-time guard nodes fail closed on an embargo they cannot read.

``TerminationIsTimelyNode`` and ``EmbargoEndTimePassedNode`` compare a
claimed time with the end time of the embargo in force (ADR-0122,
EMB-13-003).
"""

from datetime import datetime, timedelta
from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import setup_blackboard
from test.support.act_runner import in_act
from test.support.embargo_register import activate
from test.support.future_dates import days_from_now
from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors import act_keys
from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.embargo.end_time_tree import (
    EmbargoEndTimePassedNode,
)
from vultron.core.behaviors.embargo.nodes.teardown_guards import (
    TerminationIsTimelyNode,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.errors import VultronMissingActInstantError
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

ACTOR = "https://example.org/actors/manager"


def _store(end_time=None) -> tuple[SqliteDataLayer, VulnerabilityCase]:
    """A case whose register holds its embargo in force, ending *end_time*.

    With no *end_time* the embargo ends far ahead.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR)
    case = make(VulnerabilityCase, name="End-time nodes", attributed_to=ACTOR)
    embargo = make(
        as_EmbargoEvent,
        id_=f"{case.id_}/embargo_events/e1",
        context=case.id_,
        end_time=end_time or days_from_now(90),
    )
    dl.create(embargo)
    activate(case, embargo)
    dl.create(case)
    return dl, case


def _tick(node, dl, at: datetime | None = None) -> Status:
    setup_blackboard(dl, actor_id=ACTOR)
    tree = py_trees.trees.BehaviourTree(root=node)
    tree.setup()
    with in_act(at):
        tree.tick()
    return cast(Status, node.status)


def test_timely_guard_has_nothing_to_check_for_an_early_termination() -> None:
    dl, case = _store()
    node = TerminationIsTimelyNode(termination=EmbargoTermination.other())

    assert _tick(with_case_id(node, case.id_), dl) == Status.SUCCESS


@pytest.mark.spec("EMB-13-003")
def test_end_time_passed_node_counts_the_end_time_itself() -> None:
    end = now_utc() - timedelta(minutes=1)
    dl, case = _store(end_time=end)

    assert (
        _tick(with_case_id(EmbargoEndTimePassedNode(), case.id_), dl, at=end)
        == Status.SUCCESS
    )
    assert (
        _tick(
            with_case_id(EmbargoEndTimePassedNode(), case.id_),
            dl,
            at=end - timedelta(seconds=1),
        )
        == Status.FAILURE
    )


@pytest.mark.spec("CS-13-002")
def test_end_time_passed_node_refuses_a_run_with_no_act_instant() -> None:
    """The node reads the act's instant when it ticks, never the clock."""
    dl, case = _store(end_time=now_utc() - timedelta(minutes=1))
    setup_blackboard(dl, actor_id=ACTOR)
    node = EmbargoEndTimePassedNode()
    tree = py_trees.trees.BehaviourTree(root=with_case_id(node, case.id_))
    tree.setup()

    with pytest.raises(VultronMissingActInstantError):
        tree.tick()


@pytest.mark.spec("CLP-10-006")
@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize("trial_refuses", [False, True])
@pytest.mark.spec("CLP-07-023")
@pytest.mark.spec("CLP-07-025")
def test_timely_guard_trial_applies_the_step_the_remove_names(
    trial_refuses: bool,
) -> None:
    """With the named embargo in force, the guard runs the ``TERMINATE``
    step through the one apply function before the guarded commit (ADR-0124):
    a refused step refuses the act."""
    from unittest.mock import patch

    from vultron.core.behaviors.embargo.nodes import teardown_guards
    from vultron.errors import VultronEntryRefusedError

    dl, case = _store(end_time=now_utc() + timedelta(days=1))
    node = with_act_keys(
        TerminationIsTimelyNode(termination=EmbargoTermination.other()),
        {
            act_keys.CASE_ID: case.id_,
            act_keys.EMBARGO_ID: f"{case.id_}/embargo_events/e1",
        },
    )

    with patch.object(
        teardown_guards,
        "trial_apply",
        wraps=teardown_guards.trial_apply,
        side_effect=(
            VultronEntryRefusedError("does not apply")
            if trial_refuses
            else None
        ),
    ) as trial:
        status = _tick(node, dl)

    trial.assert_called_once()
    assert status == (Status.FAILURE if trial_refuses else Status.SUCCESS)
    assert cast(VulnerabilityCase, dl.read(case.id_)).em_state.name == "ACTIVE"
