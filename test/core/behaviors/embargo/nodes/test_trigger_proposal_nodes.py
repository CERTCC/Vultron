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

"""The propose trigger's admission guard and the manager's own-proposal index."""

import py_trees
import pytest

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes import (
    COMMITTED_ACTIVITY_KEY,
    IndexOwnEmbargoProposalNode,
    ValidateEmbargoProposalStateNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.errors import VultronInvalidStateTransitionError

ACTOR = "https://test.example/api/v2/actors/test-actor"


def _store_with_case(suffix: str, em_state: EM) -> tuple[SqliteDataLayer, str]:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR)
    case, _embargo = make_case_and_embargo(suffix, em_state=em_state)
    dl.create(case)
    setup_blackboard(dl)
    return dl, case.id_


def _tick(node: py_trees.behaviour.Behaviour) -> py_trees.common.Status:
    bt = py_trees.trees.BehaviourTree(root=node)
    bt.setup()
    bt.tick()
    return node.status


@pytest.mark.spec("EP-09-001")
@pytest.mark.parametrize(
    "em_state", [EM.NONE, EM.PROPOSED, EM.ACTIVE, EM.REVISE]
)
def test_proposal_state_guard_admits_every_state_but_exited(em_state: EM):
    _dl, case_id = _store_with_case(f"admit-{em_state.name}", em_state)
    result_out: dict[str, object] = {}

    status = _tick(
        ValidateEmbargoProposalStateNode(
            case_id=case_id, result_out=result_out
        )
    )

    assert status == py_trees.common.Status.SUCCESS
    assert "error" not in result_out


@pytest.mark.spec("EP-09-001")
def test_proposal_state_guard_refuses_exited_with_an_error():
    _dl, case_id = _store_with_case("refuse-exited", EM.EXITED)
    result_out: dict[str, object] = {}

    status = _tick(
        ValidateEmbargoProposalStateNode(
            case_id=case_id, result_out=result_out
        )
    )

    assert status == py_trees.common.Status.FAILURE
    assert isinstance(result_out["error"], VultronInvalidStateTransitionError)


@pytest.mark.spec("ID-04-005")
def test_index_own_proposal_records_the_committed_proposal():
    dl, case_id = _store_with_case("index-own", EM.PROPOSED)
    embargo_id = f"{case_id}/embargo_events/e2"
    proposal_id = f"{case_id}/proposals/p2"
    result_out: dict[str, object] = {COMMITTED_ACTIVITY_KEY: proposal_id}

    status = _tick(
        IndexOwnEmbargoProposalNode(
            case_id=case_id, embargo_id=embargo_id, result_out=result_out
        )
    )

    assert status == py_trees.common.Status.SUCCESS
    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase)
    assert case.pending_embargo_proposal_index[embargo_id] == proposal_id


def test_index_own_proposal_raises_without_a_committed_proposal():
    """A missing id is a fault in the tree, not a refusal (BT-14-001)."""
    _dl, case_id = _store_with_case("index-missing", EM.PROPOSED)
    node = IndexOwnEmbargoProposalNode(
        case_id=case_id,
        embargo_id=f"{case_id}/embargo_events/e2",
        result_out={},
    )
    bt = py_trees.trees.BehaviourTree(root=node)
    bt.setup()

    with pytest.raises(RuntimeError, match="no committed proposal id"):
        bt.tick()
