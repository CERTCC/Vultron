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
"""The CASE_MANAGER verdicts a handler applies to the runner's result (#3752).

The runner's own reading is tested in
``test/core/behaviors/case/test_received_run.py`` (ADR-0195).  What is left
here reads the DataLayer around the run, so it stays in the use cases until
#6394 moves it into the tree.
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases.received._bt_verdict import (
    case_manager_verdict,
    not_case_manager_refusal,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class _Fixed(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, status: Status) -> None:
        super().__init__(name=name)
        self._status = status

    def update(self) -> Status:
        return self._status


def _ran(
    *children: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    root = py_trees.composites.Sequence(name="Root", memory=False)
    root.add_children(list(children))
    root.tick_once()
    return root


# ---------------------------------------------------------------------------
# not_case_manager_refusal (HP-01-005, #3752)
# ---------------------------------------------------------------------------


_CASE_ID = "https://example.org/cases/gate-verdict"
_STORE_OWNER = "https://example.org/actors/store-owner"
_OTHER_MANAGER = "https://example.org/actors/other-manager"


def _store(
    holds_case: bool = True, manager_id: str | None = _OTHER_MANAGER
) -> SqliteDataLayer:
    """The store-owner's own store, holding (or not) the case.

    *manager_id* names who holds ``CVDRole.CASE_MANAGER`` on the case; ``None``
    seeds a case with no role holder at all.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_OWNER)
    if holds_case:
        case = make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_=_CASE_ID,
            name="Gate verdict",
        )
        if manager_id is not None:
            seed_case_manager_participant(dl, case, manager_id)
        dl.create(case)
    return dl


def _gated_run(gate_status: Status) -> py_trees.behaviour.Behaviour:
    """A tree whose CASE_MANAGER check reports *gate_status*.

    The check is the real node, so the helper's type lookup finds it; its
    status is set directly rather than ticked, since ticking needs the BT
    bridge's ports and store.
    """
    from vultron.core.behaviors.case.nodes.conditions import (
        CheckIsCaseManagerNode,
    )

    check = CheckIsCaseManagerNode()
    check.status = gate_status
    root = py_trees.composites.Selector(name="Root", memory=False)
    root.add_children(
        [
            py_trees.decorators.Inverter(name="Inv", child=check),
            _Fixed("Work", Status.SUCCESS),
        ]
    )
    return root


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_is_none_when_the_gate_passed():
    tree = _gated_run(Status.SUCCESS)
    assert not_case_manager_refusal(tree, _store(), _CASE_ID) is None


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("SYNC-18-007")
def test_the_ledger_position_gate_does_not_turn_the_act_away():
    """The answer to a stamped position skips at a replica ahead of every
    guard; that skip says nothing about whom the act was addressed to, so a
    run whose own gate never ran keeps its verdict."""
    from vultron.core.behaviors.sync.ledger_position_stage import (
        create_ledger_position_stage,
    )

    # Statuses are set directly, as in _gated_run: ticking needs the bridge.
    tree = create_ledger_position_stage(_CASE_ID, _OTHER_MANAGER)
    checks = [
        n
        for n in tree.iterate()
        if type(n).__name__ == "CheckIsCaseManagerNode"
    ]
    assert checks
    for check in checks:
        check.status = Status.FAILURE
    dl = _store()

    assert not_case_manager_refusal(tree, dl, _CASE_ID) is None
    skipped = HandlerResult.skipped("already recorded")
    assert case_manager_verdict(tree, skipped, dl, _CASE_ID) is skipped


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("SYNC-18-007")
def test_the_acts_own_gate_still_refuses_beside_the_ledger_position_gate():
    """Only the answer's gate is ignored: when the act's own CASE_MANAGER
    check fails in the same tree, the actor is still turned away."""
    from vultron.core.behaviors.sync.ledger_position_stage import (
        create_ledger_position_stage,
    )

    stage = create_ledger_position_stage(_CASE_ID, _OTHER_MANAGER)
    for node in stage.iterate():
        if type(node).__name__ == "CheckIsCaseManagerNode":
            node.status = Status.FAILURE
    root = py_trees.composites.Sequence(name="Root", memory=False)
    root.add_children([stage, _gated_run(Status.FAILURE)])

    verdict = not_case_manager_refusal(root, _store(), _CASE_ID)
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_is_none_without_a_gate():
    tree = _ran(_Fixed("Ok", Status.SUCCESS))
    assert not_case_manager_refusal(tree, _store(), _CASE_ID) is None


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_names_the_missing_role():
    """Somebody else holds CASE_MANAGER: this actor is not it."""
    tree = _gated_run(Status.FAILURE)
    verdict = not_case_manager_refusal(tree, _store(), _CASE_ID)
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == f"not the CASE_MANAGER of case '{_CASE_ID}'"


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_names_the_unknown_case():
    tree = _gated_run(Status.FAILURE)
    verdict = not_case_manager_refusal(
        tree, _store(holds_case=False), _CASE_ID
    )
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == f"unknown case '{_CASE_ID}'"


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_names_a_case_with_no_manager():
    """The gate also fails when no participant holds the role at all.

    That is a distinct state from "somebody else is the manager", and the
    reason says which, because at such a case nobody can pass the gate
    (CM-02-014, CM-02-015).
    """
    tree = _gated_run(Status.FAILURE)
    verdict = not_case_manager_refusal(tree, _store(manager_id=None), _CASE_ID)
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == f"case '{_CASE_ID}' has no CASE_MANAGER"


@pytest.mark.spec("HP-01-005")
@pytest.mark.parametrize(
    "verdict",
    [HandlerResult.applied(), HandlerResult.skipped("already recorded")],
    ids=["applied", "skipped"],
)
def test_case_manager_verdict_refuses_whatever_the_gate_turned_away(verdict):
    """A run the gate turned away is a misaddressed message, not an applied
    one and not a repeat: a repeat stops at intake, before the gate."""
    refused = case_manager_verdict(
        _gated_run(Status.FAILURE), verdict, _store(), _CASE_ID
    )
    assert refused.disposition is HandlerDisposition.REFUSED
    assert refused.reason == f"not the CASE_MANAGER of case '{_CASE_ID}'"


@pytest.mark.spec("HP-01-005")
def test_case_manager_verdict_keeps_a_refusal_the_run_reached():
    """The run's own refusal names its own reason; the gate does not replace it."""
    verdict = HandlerResult.refused("sender has no standing")
    assert (
        case_manager_verdict(
            _gated_run(Status.FAILURE), verdict, _store(), _CASE_ID
        )
        is verdict
    )


@pytest.mark.spec("HP-01-005")
def test_case_manager_verdict_keeps_the_case_managers_verdict():
    verdict = HandlerResult.applied()
    assert (
        case_manager_verdict(
            _gated_run(Status.SUCCESS), verdict, _store(), _CASE_ID
        )
        is verdict
    )
