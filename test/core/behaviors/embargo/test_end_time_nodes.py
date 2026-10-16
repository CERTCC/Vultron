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

import logging
from datetime import timedelta
from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import setup_blackboard
from test.support.embargo_register import activate
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.end_time_tree import (
    EmbargoEndTimePassedNode,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    TerminationIsTimelyNode,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

ACTOR = "https://example.org/actors/manager"


def _store(end_time=None) -> tuple[SqliteDataLayer, VulnerabilityCase]:
    """A case whose register names its embargo in force by id.

    With *end_time* the embargo is stored; without, it cannot be read.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR)
    case = VulnerabilityCase(name="End-time nodes", attributed_to=ACTOR)
    embargo_id = f"{case.id_}/embargo_events/e1"
    if end_time is not None:
        dl.create(
            as_EmbargoEvent(
                id_=embargo_id, context=case.id_, end_time=end_time
            )
        )
    activate(case, embargo_id)
    dl.create(case)
    return dl, case


def _tick(node, dl) -> Status:
    setup_blackboard(dl, actor_id=ACTOR)
    tree = py_trees.trees.BehaviourTree(root=node)
    tree.setup()
    tree.tick()
    return cast(Status, node.status)


@pytest.mark.spec("EMB-13-003")
def test_timely_guard_fails_closed_on_an_unreadable_embargo() -> None:
    dl, case = _store()
    node = TerminationIsTimelyNode(
        case_id=case.id_,
        termination=EmbargoTermination.end_time_reached(),
        terminated_at=now_utc(),
    )

    assert _tick(node, dl) == Status.FAILURE
    assert "Refused termination" in node.feedback_message


def test_timely_guard_has_nothing_to_check_for_an_early_termination() -> None:
    dl, case = _store()
    node = TerminationIsTimelyNode(
        case_id=case.id_,
        termination=EmbargoTermination.early(),
        terminated_at=None,
    )

    assert _tick(node, dl) == Status.SUCCESS


@pytest.mark.spec("EMB-13-003")
def test_end_time_passed_node_counts_the_end_time_itself() -> None:
    end = now_utc() - timedelta(minutes=1)
    dl, case = _store(end_time=end)

    assert _tick(EmbargoEndTimePassedNode(case.id_, now=end), dl) == (
        Status.SUCCESS
    )
    assert (
        _tick(
            EmbargoEndTimePassedNode(case.id_, now=end - timedelta(seconds=1)),
            dl,
        )
        == Status.FAILURE
    )


@pytest.mark.spec("EMB-18-003")
def test_end_time_passed_node_never_ends_an_embargo_it_cannot_read(
    caplog,
) -> None:
    dl, case = _store()
    node = EmbargoEndTimePassedNode(case.id_, now=now_utc())

    with caplog.at_level(logging.WARNING):
        assert _tick(node, dl) == Status.FAILURE

    assert any(
        r.levelno == logging.WARNING and case.id_ in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.spec("CLP-10-006")
@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize("trial_refuses", [False, True])
def test_timely_guard_trial_applies_the_step_the_remove_names(
    trial_refuses: bool,
) -> None:
    """With the named embargo in force, the guard runs the ``TERMINATE``
    step through the one apply function before intake commits (ADR-0124):
    a refused step refuses the act."""
    from unittest.mock import patch

    from vultron.core.behaviors.embargo.nodes import teardown
    from vultron.errors import VultronEntryRefusedError

    dl, case = _store(end_time=now_utc() + timedelta(days=1))
    node = TerminationIsTimelyNode(
        case_id=case.id_,
        termination=EmbargoTermination.early(),
        terminated_at=None,
        embargo_id=f"{case.id_}/embargo_events/e1",
    )

    with patch.object(
        teardown,
        "trial_apply",
        wraps=teardown.trial_apply,
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
