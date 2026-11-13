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

"""The held-case door of a received tree (AKM-03-006, ADR-0165).

An act that names its case and carries none of it is refused, naming the
activity and the case, when the receiver does not hold the case; the factory
places the door after the seen-before door and before the path stage, and
the runner reads the door's own reason.
"""

from types import SimpleNamespace

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.objects import make
from vultron.core.behaviors.case.nodes.addressee import (
    ENCLOSING_TREE_ADDRESSEE_CHECK,
)
from vultron.core.behaviors.case.nodes.held_case import (
    CaseNamedByReference,
    ReceiverHoldsNamedCaseNode,
)
from vultron.core.behaviors.case.nodes.post_close import PostCloseExemption
from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
from vultron.core.behaviors.case.ownership_transfer_tree.proposal import (
    create_propose_ownership_transfer_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.receive_close_case_tree.factory import (
    create_close_case_received_tree,
)
from vultron.core.behaviors.case.receive_stages.tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.case.received_run import (
    door_refusal,
    held_case_refusal,
)
from vultron.core.behaviors.case_id_scope import unscoped
from vultron.core.behaviors.report.prioritize_tree import (
    create_defer_case_tree,
    create_engage_case_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
    any_of,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.core.models.case import VulnerabilityCase
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/held-case-door"
ACTOR_ID = "https://example.org/actors/manager"
SENDER_ID = "https://example.org/actors/vendor"
ACTIVITY_ID = "https://example.org/activities/join-1"

_RULE = SenderRule.to_case_manager(SenderEntitlementKind.PARTICIPANT)
_CONTEXT = SenderCheckContext(sender_id=SENDER_ID, case_id=CASE_ID)


def _run_door(*, held: bool) -> ReceiverHoldsNamedCaseNode:
    scenario = BTTestScenario(actor_id=ACTOR_ID)
    if held:
        scenario.seed(
            make(VulnerabilityCase, id_=CASE_ID, attributed_to=ACTOR_ID)
        )
    door = ReceiverHoldsNamedCaseNode(
        act=CaseNamedByReference.JOIN, case_id=CASE_ID
    )
    scenario.run(door, activity=SimpleNamespace(activity_id=ACTIVITY_ID))
    return door


@pytest.mark.spec("AKM-03-006")
def test_the_door_admits_a_held_case() -> None:
    assert _run_door(held=True).status == Status.SUCCESS


@pytest.mark.spec("AKM-03-006")
def test_the_door_refuses_an_unheld_case_naming_the_activity_and_case() -> (
    None
):
    door = _run_door(held=False)

    assert door.status == Status.FAILURE
    assert door.feedback_message == (
        f"Join '{ACTIVITY_ID}' names unknown case '{CASE_ID}'"
    )


@pytest.mark.spec("AKM-03-006")
def test_the_runner_reads_the_doors_own_reason() -> None:
    """``door_refusal`` returns the door's refusal, so the handler does."""
    door = _run_door(held=False)
    tree = py_trees.composites.Sequence(
        name="ProofBT", memory=False, children=[door]
    )

    refusal = held_case_refusal(tree)
    assert refusal is not None
    assert refusal.reason == door.feedback_message
    assert door_refusal(tree) == refusal


def _tree(
    held_case: CaseNamedByReference | None = None,
) -> ReceivedActivityTree:
    return create_receive_activity_tree(
        name="HeldCaseBT",
        case_id=CASE_ID,
        precondition_guards=[],
        paths={ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA},
        sender_rule=_RULE,
        sender_context=_CONTEXT,
        held_case=held_case,
    )


def _door_names(tree: ReceivedActivityTree) -> list[str]:
    return [type(unscoped(guard)).__name__ for guard in tree.door_guards]


@pytest.mark.spec("AKM-03-006")
@pytest.mark.spec("CLP-10-010")
def test_the_factory_places_the_door_before_the_path_stage() -> None:
    """After the seen-before door, ahead of the path stage's no-case refusal."""
    names = _door_names(_tree(CaseNamedByReference.JOIN))

    assert names[:4] == [
        "ActivityAddressedToReceiverNode",
        "ActivityNotSeenBeforeNode",
        "ReceiverHoldsNamedCaseNode",
        "ReceivedPathNode",
    ]


@pytest.mark.spec("AKM-03-006")
def test_a_tree_without_held_case_has_no_door() -> None:
    assert "ReceiverHoldsNamedCaseNode" not in _door_names(_tree())


@pytest.mark.spec("AKM-03-006")
def test_held_case_on_a_tree_naming_no_case_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="held_case"):
        create_receive_activity_tree(
            name="NoCaseBT",
            case_id=None,
            precondition_guards=[],
            held_case=CaseNamedByReference.LEAVE,
        )


@pytest.mark.spec("AKM-03-006")
def test_held_case_on_a_nested_tree_is_a_wiring_error() -> None:
    """A nested tree runs on its enclosing tree's doors (ADR-0154)."""
    with pytest.raises(VultronWiringError, match="enclosing tree"):
        create_receive_activity_tree(
            name="NestedBT",
            case_id=CASE_ID,
            precondition_guards=[],
            nested=True,
            addressee_exemption=ENCLOSING_TREE_ADDRESSEE_CHECK,
            post_close_exemption=PostCloseExemption.ENCLOSING_TREE_GUARDS,
            held_case=CaseNamedByReference.LEAVE,
        )


def _held_case_door_act(
    tree: py_trees.behaviour.Behaviour,
) -> CaseNamedByReference | None:
    doors = [
        node
        for node in tree.iterate()
        if isinstance(node, ReceiverHoldsNamedCaseNode)
    ]
    assert len(doors) <= 1
    if not doors:
        return None
    assert doors[0].case_id == CASE_ID
    return doors[0].act


@pytest.mark.spec("AKM-03-004")
@pytest.mark.spec("AKM-03-006")
@pytest.mark.parametrize(
    "build, act",
    [
        (
            lambda: create_engage_case_tree(
                case_id=CASE_ID, actor_id=SENDER_ID, sender_rule=_RULE
            ),
            CaseNamedByReference.JOIN,
        ),
        (
            lambda: create_defer_case_tree(
                case_id=CASE_ID, actor_id=SENDER_ID, sender_rule=_RULE
            ),
            CaseNamedByReference.IGNORE,
        ),
        (
            lambda: create_close_case_received_tree(
                case_id=CASE_ID,
                activity_id=ACTIVITY_ID,
                sender_actor_id=SENDER_ID,
                receiving_actor_id=ACTOR_ID,
                sender_rule=SenderRule.to_case_manager(
                    SenderEntitlementKind.CASE_OWNER,
                    SenderEntitlementKind.PARTICIPANT,
                ),
            ),
            CaseNamedByReference.LEAVE,
        ),
        (
            lambda: create_propose_ownership_transfer_tree(
                case_id=CASE_ID,
                proposed_case_id=CASE_ID,
                transferee_id=SENDER_ID,
                proposal_id=ACTIVITY_ID,
                answer_deadline=None,
                sender_rule=SenderRule(
                    at_case_manager=any_of(SenderEntitlementKind.CASE_OWNER)
                ),
                sender_id=SENDER_ID,
            ),
            CaseNamedByReference.OWNERSHIP_TRANSFER_PROPOSAL,
        ),
    ],
    ids=["Join", "Ignore", "Leave", "Offer(Offer)"],
)
def test_every_act_naming_its_case_carries_the_door(build, act) -> None:
    """Each AKM-03-004 act's tree has exactly one held-case door, on its case."""
    assert _held_case_door_act(build()) is act
