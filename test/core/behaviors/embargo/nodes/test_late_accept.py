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

"""The routing of a late embargo Accept (EMB-17, nodes/late_accept.py).

:func:`late_accept_route` names the arm; :class:`LateAcceptRouteIsNode` is
each arm's condition, read from the case when the node runs; and
:class:`ReinviteLateAccepterNode` sends nothing when there is nothing to
re-invite to, or no port to build the Invite with.
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    OTHER_PARTICIPANT_ACTOR,
    make_case_with_manager,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes.late_accept import (
    LateAcceptRoute,
    LateAcceptRouteIsNode,
    late_accept_route,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteLateAccepterNode,
)
from vultron.core.states.em import EM

_ACCEPTED = "https://example.org/embargo/accepted"
_OTHER = "https://example.org/embargo/other"


@pytest.mark.spec("EMB-17-001")
@pytest.mark.parametrize(
    ("em_state", "active", "route"),
    [
        (EM.ACTIVE, _ACCEPTED, LateAcceptRoute.HONOUR),
        (EM.REVISE, _ACCEPTED, LateAcceptRoute.HONOUR),
        (EM.ACTIVE, _OTHER, LateAcceptRoute.REINVITE),
        (EM.REVISE, _OTHER, LateAcceptRoute.REINVITE),
        (EM.PROPOSED, None, LateAcceptRoute.REINVITE),
        (EM.EXITED, None, LateAcceptRoute.ACKNOWLEDGE),
        (EM.NONE, None, LateAcceptRoute.ACKNOWLEDGE),
    ],
)
def test_each_case_state_has_one_route(em_state, active, route) -> None:
    assert late_accept_route(em_state, active, _ACCEPTED) is route


def _run(
    dl: SqliteDataLayer,
    node: py_trees.behaviour.Behaviour,
    actor_id: str = CASE_MANAGER_ACTOR,
    *,
    with_factory: bool = False,
) -> Status:
    tree = py_trees.composites.Sequence(
        name="Probe", memory=False, children=[node]
    )
    BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl) if with_factory else None,
    ).execute_with_setup(tree=tree, actor_id=actor_id)
    return node.status


@pytest.mark.spec("EMB-17-002")
@pytest.mark.spec("EMB-17-003")
@pytest.mark.parametrize("route", list(LateAcceptRoute))
def test_the_condition_holds_only_for_the_cases_route(route) -> None:
    case, _, dl = make_case_with_manager(f"late-route-{route.value}")
    embargo_id = case.active_embargo_id
    assert embargo_id is not None
    node = LateAcceptRouteIsNode(
        case_id=case.id_,
        embargo_id=embargo_id,
        accepting_actor_id=OTHER_PARTICIPANT_ACTOR,
        route=route,
    )

    status = _run(dl, node)

    expected = (
        Status.SUCCESS if route is LateAcceptRoute.HONOUR else Status.FAILURE
    )
    assert status is expected


class TestReinviteLateAccepterNode:
    @pytest.mark.spec("EMB-17-003")
    @pytest.mark.spec("EMB-17-007")
    def test_no_embargo_in_force_sends_nothing(self, caplog) -> None:
        case, _, dl = make_case_with_manager("late-reinvite-none", EM.PROPOSED)
        node = ReinviteLateAccepterNode(
            case_id=case.id_, invitee_id=OTHER_PARTICIPANT_ACTOR
        )

        with caplog.at_level("WARNING"):
            status = _run(dl, node, with_factory=True)

        assert status is Status.SUCCESS
        assert "no embargo in force" in caplog.text
        assert dl.outbox_list() == []

    @pytest.mark.spec("EMB-17-003")
    def test_no_port_sends_nothing(self, caplog) -> None:
        case, _, dl = make_case_with_manager("late-reinvite-noport")
        node = ReinviteLateAccepterNode(
            case_id=case.id_, invitee_id=OTHER_PARTICIPANT_ACTOR
        )

        with caplog.at_level("WARNING"):
            status = _run(dl, node)

        assert status is Status.SUCCESS
        assert "trigger_activity unavailable" in caplog.text
        assert dl.outbox_list() == []
