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

"""The path door stage of a received tree (ADR-0153).

One role question picks the manager, participant-replica or no-case path;
a path the message type declares no branch for is refused there, with one
reason shared by every message type; and the sender guard's addressee arms
read that answer instead of asking again.
"""

from collections.abc import Collection

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.invite_actor_to_case_received_tree import (
    create_invite_actor_to_case_received_tree,
)
from vultron.core.behaviors.case.nodes.addressee import (
    ActivityAddressedToReceiverNode,
)
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    CheckReceivedPathNode,
    ReceivedPath,
    ReceivedPathNode,
    undeclared_path_reason,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    SenderCheckContext,
    compose_sender_guard,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.events.case_context import (
    CASE_PRECEDING_SEMANTICS,
    is_deferral_exempt,
)
from vultron.core.use_cases.received._bt_verdict import (
    door_refusal,
    path_refusal,
    received_path,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/path-stage"
MANAGER_ID = "https://example.org/actors/coordinator"
VENDOR_ID = "https://example.org/actors/vendor"
OWNER_ID = "https://example.org/actors/owner"
STRANGER_ID = "https://example.org/actors/stranger"

#: Every path, so a test that sweeps them cannot miss one the enum gains.
PATHS_IN_ORDER: list[ReceivedPath] = list(ReceivedPath)
ALL_PATHS: frozenset[ReceivedPath] = frozenset(PATHS_IN_ORDER)

_RULE = SenderRule.to_case_manager(SenderEntitlementKind.CASE_OWNER)
_CONTEXT = SenderCheckContext(sender_id=OWNER_ID, case_id=CASE_ID)


def _participant(suffix: str, actor_id: str, *roles: CVDRole):
    return CaseParticipant(
        id_=f"{CASE_ID}/participants/{suffix}",
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=list(roles),
    )


def _seed_case(scenario: BTTestScenario) -> None:
    manager = _participant("manager", MANAGER_ID, CVDRole.CASE_MANAGER)
    vendor = _participant("vendor", VENDOR_ID, CVDRole.VENDOR)
    scenario.seed(
        manager,
        vendor,
        VulnerabilityCase(
            id_=CASE_ID,
            name="PATH-STAGE",
            attributed_to=OWNER_ID,
            case_participants=[manager.id_, vendor.id_],
            actor_participant_index={
                MANAGER_ID: manager.id_,
                VENDOR_ID: vendor.id_,
            },
        ),
    )


#: The actor whose store takes each path, and who is seeded into it.
_ACTOR_ON_PATH: dict[ReceivedPath, str] = {
    ReceivedPath.CASE_MANAGER: MANAGER_ID,
    ReceivedPath.PARTICIPANT_REPLICA: VENDOR_ID,
    ReceivedPath.NO_CASE: STRANGER_ID,
}


def _run_stage(
    path: ReceivedPath, declared: Collection[ReceivedPath]
) -> ReceivedPathNode:
    """The stage, run in the store of an actor on *path*, declaring *declared*."""
    actor_id = _ACTOR_ON_PATH[path]
    scenario = BTTestScenario(actor_id=actor_id)
    if path is not ReceivedPath.NO_CASE:
        _seed_case(scenario)
    stage = ReceivedPathNode(
        declared=frozenset(declared), case_id=CASE_ID, label="ProofBT"
    )
    scenario.run(stage, actor_id=actor_id)
    return stage


@pytest.mark.spec("CM-02-011")
@pytest.mark.parametrize("path", PATHS_IN_ORDER)
def test_the_stage_resolves_each_path(path: ReceivedPath) -> None:
    """The role question picks the receiver's path, and only the role does.

    The manager holds ``CVDRole.CASE_MANAGER`` in the roster, the vendor
    holds a replica without it, and a store that holds no replica is on the
    no-case path (ADR-0153 detail 2).
    """
    stage = _run_stage(path, ALL_PATHS)

    assert stage.status is Status.SUCCESS
    assert stage.resolved_path is path


@pytest.mark.spec("HP-01-005")
@pytest.mark.parametrize("path", PATHS_IN_ORDER)
def test_an_undeclared_path_is_refused_with_the_shared_reason(
    path: ReceivedPath,
) -> None:
    """A test per path: a type with no branch for it is REFUSED there.

    The reason is the factory's, the same for every message type, so one
    cause gets one verdict (ADR-0153 detail 5, HP-01-005).
    """
    stage = _run_stage(path, ALL_PATHS - {path})

    assert stage.status is Status.FAILURE
    assert stage.resolved_path is path
    assert stage.feedback_message == undeclared_path_reason(CASE_ID)
    assert stage.feedback_message == (
        f"not the CASE_MANAGER of case '{CASE_ID}'"
    )


@pytest.mark.spec("HP-01-005")
def test_every_path_is_refused_with_one_and_the_same_reason() -> None:
    """The reason does not vary by path or by message type (ADR-0153)."""
    reasons = {
        _run_stage(path, ALL_PATHS - {path}).feedback_message
        for path in ALL_PATHS
    }

    assert reasons == {f"not the CASE_MANAGER of case '{CASE_ID}'"}


@pytest.mark.spec("HP-01-005")
def test_a_refused_path_is_the_handlers_door_refusal() -> None:
    """``door_refusal`` returns the stage's refusal, so every handler agrees.

    No handler maps a gate failure to a verdict of its own: the one the
    factory composed is what the handler reports (ADR-0153 detail 5).
    """
    stage = _run_stage(
        ReceivedPath.PARTICIPANT_REPLICA, {ReceivedPath.CASE_MANAGER}
    )
    tree = py_trees.composites.Sequence(
        name="ProofBT", memory=False, children=[stage]
    )

    refusal = path_refusal(tree)
    assert refusal is not None
    assert refusal.reason == f"not the CASE_MANAGER of case '{CASE_ID}'"
    assert door_refusal(tree) == refusal


@pytest.mark.spec("HP-01-005")
def test_an_admitted_path_owes_no_refusal() -> None:
    stage = _run_stage(ReceivedPath.CASE_MANAGER, {ReceivedPath.CASE_MANAGER})
    tree = py_trees.composites.Sequence(
        name="ProofBT", memory=False, children=[stage]
    )

    assert path_refusal(tree) is None
    assert received_path(tree) is ReceivedPath.CASE_MANAGER


@pytest.mark.spec("HP-01-012")
def test_a_tree_without_a_declaration_reports_no_path() -> None:
    """``received_path`` is ``None`` for a tree that declared no paths."""
    tree = create_receive_activity_tree(
        name="UndeclaredBT",
        case_id=CASE_ID,
        precondition_guards=[],
        sender_rule=_RULE,
        sender_context=_CONTEXT,
    )

    assert received_path(tree) is None
    assert path_refusal(tree) is None


# ---------------------------------------------------------------------------
# CLP-10-010 / HP-01-012: where the stage sits
# ---------------------------------------------------------------------------


def _declared_tree() -> ReceivedActivityTree:
    return create_receive_activity_tree(
        name="DeclaredBT",
        case_id=CASE_ID,
        precondition_guards=[],
        paths={ReceivedPath.CASE_MANAGER},
        sender_rule=_RULE,
        sender_context=_CONTEXT,
    )


@pytest.mark.spec("CLP-10-010")
@pytest.mark.spec("HP-01-012")
def test_the_stage_runs_after_the_addressee_check_and_before_the_guard() -> (
    None
):
    """The path stage is a door stage, in the CLP-10-010 order."""
    tree = _declared_tree()
    stages = [type(child).__name__ for child in tree.children]
    names = [child.name for child in tree.children]

    addressee = stages.index(ActivityAddressedToReceiverNode.__name__)
    path = stages.index(ReceivedPathNode.__name__)
    guard = names.index("SenderRuleGuard")

    assert addressee < path < guard


@pytest.mark.spec("CLP-10-010")
def test_the_stage_is_one_of_the_trees_door_guards() -> None:
    """A delivery the stage refused did not get past the door."""
    tree = _declared_tree()

    assert any(
        isinstance(guard, ReceivedPathNode) for guard in tree.door_guards
    )


@pytest.mark.spec("HP-01-007")
def test_a_declaration_naming_no_path_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="at least one ReceivedPath"):
        create_receive_activity_tree(
            name="EmptyDeclarationBT",
            case_id=CASE_ID,
            precondition_guards=[],
            paths=frozenset(),
            sender_rule=_RULE,
            sender_context=_CONTEXT,
        )


# ---------------------------------------------------------------------------
# HP-01-008: the sender guard reads the path instead of asking again
# ---------------------------------------------------------------------------


def _leaf_types(node: py_trees.behaviour.Behaviour) -> set[str]:
    return {type(each).__name__ for each in node.iterate()}


@pytest.mark.spec("HP-01-008")
def test_the_sender_guards_arms_read_the_path_stages_answer() -> None:
    """With a path stage the arms are path checks, not a second role read."""
    stage = ReceivedPathNode(
        declared=frozenset({ReceivedPath.CASE_MANAGER}), case_id=CASE_ID
    )
    guard = compose_sender_guard(_RULE, _CONTEXT, stage)
    assert guard is not None

    types = _leaf_types(guard)
    assert CheckReceivedPathNode.__name__ in types
    assert CheckIsCaseManagerNode.__name__ not in types
    assert all(
        arm.stage is stage
        for arm in guard.iterate()
        if isinstance(arm, CheckReceivedPathNode)
    )


@pytest.mark.spec("HP-01-008")
def test_without_a_path_stage_the_arms_read_the_role_themselves() -> None:
    """The unmigrated shape is unchanged, so a tree may declare paths later."""
    guard = compose_sender_guard(_RULE, _CONTEXT)
    assert guard is not None

    types = _leaf_types(guard)
    assert CheckIsCaseManagerNode.__name__ in types
    assert CheckReceivedPathNode.__name__ not in types


@pytest.mark.spec("HP-01-008")
def test_the_declared_tree_asks_the_role_question_once() -> None:
    """One role read answers the path and both sender-guard arms.

    The stage is the only node ahead of the commit that reads the roster for
    the receiver's role; the arms read its answer (ADR-0153 detail 3).
    """
    tree = _declared_tree()

    asked = [
        node
        for guard in tree.door_guards
        for node in guard.iterate()
        if isinstance(node, (ReceivedPathNode, CheckIsCaseManagerNode))
    ]
    assert [type(node).__name__ for node in asked] == [
        ReceivedPathNode.__name__
    ]


@pytest.mark.spec("HP-01-008")
@pytest.mark.parametrize("path", PATHS_IN_ORDER)
def test_the_manager_arm_matches_only_the_manager_path(
    path: ReceivedPath,
) -> None:
    """``CheckReceivedPathNode`` answers for exactly the path it names."""
    stage = _run_stage(path, ALL_PATHS)
    arm = CheckReceivedPathNode.on_manager_path(stage)

    expected = (
        Status.SUCCESS if path is ReceivedPath.CASE_MANAGER else Status.FAILURE
    )
    assert arm.update() is expected


@pytest.mark.spec("HP-01-008")
def test_an_arm_whose_stage_has_not_run_does_not_match() -> None:
    """No arm is entered before the door stage answered."""
    stage = ReceivedPathNode(declared=ALL_PATHS, case_id=CASE_ID)

    assert stage.resolved_path is None
    assert (
        CheckReceivedPathNode.on_manager_path(stage).update() is Status.FAILURE
    )


# ---------------------------------------------------------------------------
# ADR-0153 detail 6: no case yet either waits or proceeds
# ---------------------------------------------------------------------------


def _event(semantics: MessageSemantics) -> VultronEvent:
    return VultronEvent(
        semantic_type=semantics,
        activity_id=f"{CASE_ID}/activities/1",
        actor_id=OWNER_ID,
    )


@pytest.mark.spec("HP-01-005")
def test_a_case_scoped_type_waits_for_its_case_rather_than_being_refused() -> (
    None
):
    """The inbox's defer check holds a case-scoped type, so no path refuses it.

    ``Accept(Offer(CaseParticipant))`` is case-scoped and not deferral
    exempt, so it never reaches its received tree — and its path stage —
    until the receiver holds the case (ADR-0153 detail 6, IO-02-001).  Only
    the activities that precede or establish their case are exempt, and the
    stub Invite is the one that precedes it.
    """
    case_scoped = MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT

    assert case_scoped not in CASE_PRECEDING_SEMANTICS
    assert not is_deferral_exempt(_event(case_scoped))
    assert is_deferral_exempt(_event(MessageSemantics.INVITE_ACTOR_TO_CASE))


@pytest.mark.spec("HP-01-005")
def test_the_type_that_precedes_its_case_declares_the_no_case_branch() -> None:
    """The stub Invite declares the no-case path and takes it.

    It is deferral exempt because its case only arrives after the invitee
    answers (MV-10-005), so its tree must handle a receiver that holds no
    replica rather than wait for one (ADR-0153 detail 6).
    """
    assert MessageSemantics.INVITE_ACTOR_TO_CASE in CASE_PRECEDING_SEMANTICS

    tree = create_invite_actor_to_case_received_tree(
        case_id=CASE_ID,
        invitee_id=STRANGER_ID,
        inviter_id=MANAGER_ID,
        invite_id=f"{CASE_ID}/invitations/1",
        sender_rule=SenderRule.in_case(SenderEntitlementKind.CASE_MANAGER),
    )
    stage = next(
        node for node in tree.iterate() if isinstance(node, ReceivedPathNode)
    )

    assert ReceivedPath.NO_CASE in stage.declared

    scenario = BTTestScenario(actor_id=STRANGER_ID)
    scenario.run(stage, actor_id=STRANGER_ID)

    assert stage.resolved_path is ReceivedPath.NO_CASE
    assert stage.status is Status.SUCCESS
