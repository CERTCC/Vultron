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

"""``sender_guard_refused`` reads where a received tree's run ended (#4522).

Only the composed sender guard, a child of the root, counts: a sender node
deeper in the tree picks an effect after admission (HP-01-006, HP-01-008).
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    SenderCheckContext,
    case_owner_guard,
    compose_sender_guard,
    sender_guard_refused,
)
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
)

CASE_ID = "https://example.org/cases/refused"
SENDER_ID = "https://example.org/actors/sender"


def _root(
    *children: py_trees.behaviour.Behaviour,
) -> py_trees.composites.Sequence:
    return py_trees.composites.Sequence(
        name="ReceivedBT", memory=False, children=list(children)
    )


def _ran(node: py_trees.behaviour.Behaviour, status: Status) -> None:
    for each in node.iterate():
        each.status = status


def _guard(rule: SenderRule) -> py_trees.behaviour.Behaviour:
    guard = compose_sender_guard(
        rule, SenderCheckContext(sender_id=SENDER_ID, case_id=CASE_ID)
    )
    assert guard is not None
    return guard


@pytest.mark.spec("HP-01-006")
@pytest.mark.parametrize(
    "rule",
    [
        pytest.param(
            AddCaseStatusToCaseReceivedUseCase.sender_entitlement,
            id="per-side-dispatch",
        ),
        pytest.param(
            CloseCaseReceivedUseCase.sender_entitlement, id="any-of-selector"
        ),
        pytest.param(
            SenderRule.in_case(SenderEntitlementKind.PARTICIPANT),
            id="single-kind-node",
        ),
    ],
)
def test_a_run_that_ended_at_the_composed_guard_is_refused_there(
    rule: SenderRule,
) -> None:
    intake = py_trees.behaviours.Success(name="Intake")
    guard = _guard(rule)
    _ran(intake, Status.SUCCESS)
    _ran(guard, Status.FAILURE)

    assert sender_guard_refused(_root(intake, guard))


@pytest.mark.spec("HP-01-006")
def test_a_sender_node_deeper_in_the_tree_is_not_the_guard() -> None:
    """A standing read inside an effect gate failing is not a refusal of the
    sender (the close-case tree's owner arm, say)."""
    guard = _guard(SenderRule.in_case(SenderEntitlementKind.PARTICIPANT))
    effects = py_trees.composites.Sequence(
        name="CloseOrDeclineIfCaseManager",
        memory=False,
        children=[case_owner_guard(CASE_ID, SENDER_ID)],
    )
    _ran(guard, Status.SUCCESS)
    _ran(effects, Status.FAILURE)

    assert not sender_guard_refused(_root(guard, effects))


def test_a_run_that_succeeded_was_not_refused() -> None:
    guard = _guard(SenderRule.in_case(SenderEntitlementKind.PARTICIPANT))
    _ran(guard, Status.SUCCESS)

    assert not sender_guard_refused(_root(guard))


@pytest.mark.spec("HP-01-006")
def test_a_failing_sender_node_at_the_root_that_was_not_composed_is_not_the_guard() -> (
    None
):
    """The guard is known by its origin, not its type: a sender node a tree
    lists itself at the root is not the composed guard."""
    guard = _guard(SenderRule.in_case(SenderEntitlementKind.PARTICIPANT))
    own_check = case_owner_guard(CASE_ID, SENDER_ID)
    _ran(guard, Status.SUCCESS)
    _ran(own_check, Status.FAILURE)

    assert not sender_guard_refused(_root(guard, own_check))
