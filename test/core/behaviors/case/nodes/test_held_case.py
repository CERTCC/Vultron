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

"""The path stage's refusal of an act naming an unheld case (AKM-03-006).

An act that names its case and carries none of it (AKM-03-004) is refused,
naming the activity and the case, when the receiver holds no replica of the
case.  The refusal is the path stage's on the no-case path, composed in one
place (HP-01-039), so the door order is unchanged (HP-01-035).
"""

from types import SimpleNamespace

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.objects import make
from vultron.core.behaviors.case.nodes.held_case import CaseNamedByReference
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
    undeclared_path_reason,
)
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
from vultron.core.behaviors.case.received_run import door_refusal
from vultron.core.behaviors.case_id_scope import unscoped, with_case_id
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

CASE_ID = "https://example.org/cases/held-case"
ACTOR_ID = "https://example.org/actors/manager"
SENDER_ID = "https://example.org/actors/vendor"
ACTIVITY_ID = "https://example.org/activities/join-1"

_RULE = SenderRule.to_case_manager(SenderEntitlementKind.PARTICIPANT)
_CONTEXT = SenderCheckContext(sender_id=SENDER_ID, case_id=CASE_ID)
_DECLARED = frozenset(
    {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA}
)


def _run_stage(*, held: bool) -> ReceivedPathNode:
    scenario = BTTestScenario(actor_id=ACTOR_ID)
    if held:
        scenario.seed(
            make(VulnerabilityCase, id_=CASE_ID, attributed_to=SENDER_ID)
        )
    stage = ReceivedPathNode(
        declared=_DECLARED,
        label="ProofBT",
        held_case=CaseNamedByReference.JOIN,
    )
    scenario.run(
        with_case_id(stage, CASE_ID),
        activity=SimpleNamespace(activity_id=ACTIVITY_ID),
    )
    return stage


@pytest.mark.spec("AKM-03-006")
@pytest.mark.spec("HP-01-039")
def test_an_unheld_case_is_refused_naming_the_activity_and_the_case() -> None:
    stage = _run_stage(held=False)

    assert stage.status == Status.FAILURE
    assert stage.resolved_path is ReceivedPath.NO_CASE
    assert stage.feedback_message == (
        f"Join '{ACTIVITY_ID}' names unknown case '{CASE_ID}'"
    )


@pytest.mark.spec("AKM-03-006")
def test_the_handler_reads_the_stages_own_reason() -> None:
    stage = _run_stage(held=False)
    assert stage.parent is not None
    tree = py_trees.composites.Sequence(
        name="ProofBT", memory=False, children=[stage.parent]
    )

    refusal = door_refusal(tree)
    assert refusal is not None
    assert refusal.reason == stage.feedback_message


@pytest.mark.spec("AKM-03-006")
def test_a_held_case_takes_its_path_as_before() -> None:
    """A held replica is the participant-replica path, admitted."""
    stage = _run_stage(held=True)

    assert stage.status == Status.SUCCESS
    assert stage.resolved_path is ReceivedPath.PARTICIPANT_REPLICA


@pytest.mark.spec("HP-01-039")
def test_the_act_changes_only_the_no_case_reason() -> None:
    """Every other refused path keeps the composed reason (HP-01-039)."""
    for path in (ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA):
        declared = frozenset(ReceivedPath) - {path}
        assert undeclared_path_reason(
            path,
            declared,
            CASE_ID,
            held_case=CaseNamedByReference.LEAVE,
            activity_id=ACTIVITY_ID,
        ) == undeclared_path_reason(path, declared, CASE_ID)


def _tree(
    held_case: CaseNamedByReference | None = CaseNamedByReference.JOIN,
    paths: frozenset[ReceivedPath] | None = _DECLARED,
    case_id: str | None = CASE_ID,
) -> ReceivedActivityTree:
    return create_receive_activity_tree(
        name="HeldCaseBT",
        case_id=case_id,
        precondition_guards=[],
        paths=paths,
        sender_rule=_RULE if paths is not None else None,
        sender_context=_CONTEXT if paths is not None else None,
        held_case=held_case,
    )


@pytest.mark.spec("HP-01-035")
@pytest.mark.spec("CLP-10-010")
def test_the_door_order_is_unchanged() -> None:
    """The act rides on the path stage, directly after the seen-before door."""
    names = [type(unscoped(g)).__name__ for g in _tree().door_guards]

    assert names[:3] == [
        "ActivityAddressedToReceiverNode",
        "ActivityNotSeenBeforeNode",
        "ReceivedPathNode",
    ]


@pytest.mark.spec("AKM-03-006")
def test_held_case_without_paths_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="declare its paths"):
        _tree(paths=None)


@pytest.mark.spec("HP-01-041")
def test_held_case_with_the_no_case_path_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="no-case path"):
        _tree(paths=frozenset({ReceivedPath.NO_CASE}), case_id=None)


@pytest.mark.spec("AKM-03-006")
def test_held_case_naming_no_case_at_build_time_is_a_wiring_error() -> None:
    """A manager-and-replica declaration with no case anywhere at build time
    leaves the stage no case to name in the AKM-03-006 reason."""
    with pytest.raises(VultronWiringError, match="name its case at build"):
        create_receive_activity_tree(
            name="HeldCaseBT",
            case_id=None,
            precondition_guards=[],
            paths=_DECLARED,
            sender_rule=_RULE,
            sender_context=SenderCheckContext(sender_id=SENDER_ID),
            held_case=CaseNamedByReference.JOIN,
        )


@pytest.mark.spec("AKM-03-006")
def test_held_case_with_no_activity_id_keeps_the_paths_own_reason() -> None:
    """With no activity to name, the stage gives the no-case path's reason
    rather than a reason naming ``'None'``."""
    assert undeclared_path_reason(
        ReceivedPath.NO_CASE,
        _DECLARED,
        CASE_ID,
        held_case=CaseNamedByReference.JOIN,
        activity_id=None,
    ) == undeclared_path_reason(ReceivedPath.NO_CASE, _DECLARED, CASE_ID)


def _stage_act(
    tree: py_trees.behaviour.Behaviour,
) -> CaseNamedByReference | None:
    (stage,) = [n for n in tree.iterate() if isinstance(n, ReceivedPathNode)]
    return stage.held_case


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
def test_every_act_naming_its_case_declares_it(build, act) -> None:
    """Each AKM-03-004 act's path stage carries the act."""
    assert _stage_act(build()) is act
