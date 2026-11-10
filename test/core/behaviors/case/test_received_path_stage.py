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
a path the message type declares no branch for is refused there, with a
reason composed in one place and true of the receiver it refuses; and the
sender guard's addressee arms read that answer instead of asking again.
"""

from collections.abc import Collection
from datetime import datetime

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BlackboardKeyProbe, BTTestScenario
from vultron.core.behaviors.case.invite_actor_to_case_received_tree import (
    create_invite_actor_to_case_received_tree,
)
from vultron.core.behaviors.case.nodes.addressee import (
    ActivityAddressedToReceiverNode,
)
from vultron.core.behaviors.case.nodes.case_lookup import (
    RequireCaseForReport,
)
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.nodes.diversion_stage import Diversion
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
from vultron.core.behaviors.case.receive_stages.doors import (
    path_stage_case_id,
)
from vultron.core.behaviors.case_id_scope import (
    CaseIdScope,
    unscoped,
    with_case_id,
)
from vultron.core.behaviors.inbox.nodes.pipeline import DeferCheckNode
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
REPORT_ID = "https://example.org/reports/path-stage"

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
    path: ReceivedPath,
    declared: Collection[ReceivedPath],
    then: py_trees.behaviour.Behaviour | None = None,
) -> ReceivedPathNode:
    """The stage, run in the store of an actor on *path*, declaring *declared*.

    *then*, when given, runs after the stage in the same execution.
    """
    actor_id = _ACTOR_ON_PATH[path]
    scenario = BTTestScenario(actor_id=actor_id)
    if path is not ReceivedPath.NO_CASE:
        _seed_case(scenario)
    stage = ReceivedPathNode(declared=frozenset(declared), label="ProofBT")
    seeded = with_case_id(stage, CASE_ID)
    tree: py_trees.behaviour.Behaviour = seeded
    if then is not None:
        tree = py_trees.composites.Sequence(
            name="StageThen", memory=False, children=[seeded, then]
        )
    scenario.run(tree, actor_id=actor_id)
    return stage


def _seeding_scope(stage: ReceivedPathNode) -> CaseIdScope:
    """The :class:`CaseIdScope` that seeds *stage*'s ``/case_id`` port."""
    scope = stage.parent
    assert isinstance(scope, CaseIdScope)
    return scope


#: The reason each path is refused with when every *other* path is declared,
#: so the declaration always includes the manager path.  Each string is a
#: true statement about the receiver the stage turned away (HP-01-039).
_MANAGER_INCLUSIVE_REASON: dict[ReceivedPath, str] = {
    ReceivedPath.CASE_MANAGER: (
        f"the CASE_MANAGER of case '{CASE_ID}',"
        " which this message type does not address"
    ),
    ReceivedPath.PARTICIPANT_REPLICA: (
        f"not the CASE_MANAGER of case '{CASE_ID}'"
    ),
    ReceivedPath.NO_CASE: f"holds no replica of case '{CASE_ID}'",
}


@pytest.mark.spec("CM-02-011")
@pytest.mark.spec("HP-01-037")
@pytest.mark.parametrize("path", PATHS_IN_ORDER)
def test_the_stage_resolves_each_path(path: ReceivedPath) -> None:
    """The role question picks the receiver's path, and only the role does.

    The manager holds ``CVDRole.CASE_MANAGER`` in the roster, the vendor
    holds a replica without it, and a store that holds no replica is on the
    no-case path (HP-01-037).
    """
    stage = _run_stage(path, ALL_PATHS)

    assert stage.status is Status.SUCCESS
    assert stage.resolved_path is path


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-039")
@pytest.mark.parametrize("path", PATHS_IN_ORDER)
def test_an_undeclared_path_is_refused_with_a_reason_true_of_the_receiver(
    path: ReceivedPath,
) -> None:
    """A test per path: a type with no branch for it is REFUSED there.

    The reason is composed in one place from the resolved path and the
    declaration, so it says something true of the receiver it refuses rather
    than one fixed string that is false of two of the three
    (HP-01-039, HP-01-005).
    """
    declared = ALL_PATHS - {path}
    stage = _run_stage(path, declared)

    assert stage.status is Status.FAILURE
    assert stage.resolved_path is path
    assert stage.feedback_message == undeclared_path_reason(
        path, declared, CASE_ID
    )
    assert stage.feedback_message == _MANAGER_INCLUSIVE_REASON[path]


@pytest.mark.spec("HP-01-039")
def test_a_manager_inclusive_declaration_states_only_the_path() -> None:
    """With the manager path declared, the clause already says what is missing.

    A receiver refused by such a declaration is not the case's CASE_MANAGER,
    so naming its path names the role it lacks and no further clause is owed.
    """
    manager_inclusive = {
        ReceivedPath.CASE_MANAGER,
        ReceivedPath.PARTICIPANT_REPLICA,
    }

    assert (
        undeclared_path_reason(
            ReceivedPath.NO_CASE, manager_inclusive, CASE_ID
        )
        == f"holds no replica of case '{CASE_ID}'"
    )
    assert (
        undeclared_path_reason(
            ReceivedPath.PARTICIPANT_REPLICA,
            {ReceivedPath.CASE_MANAGER},
            CASE_ID,
        )
        == f"not the CASE_MANAGER of case '{CASE_ID}'"
    )


@pytest.mark.spec("HP-01-039")
def test_a_declaration_without_the_manager_path_says_what_is_missing() -> None:
    """A replica-only type refuses the CASE_MANAGER, and must not deny its role.

    The one case the single fixed string got wrong: the receiver really is
    the case's CASE_MANAGER, and what the type has no branch for is that
    path, not the role (HP-01-005).
    """
    reason = undeclared_path_reason(
        ReceivedPath.CASE_MANAGER,
        {ReceivedPath.PARTICIPANT_REPLICA},
        CASE_ID,
    )

    assert reason == (
        f"the CASE_MANAGER of case '{CASE_ID}',"
        " which this message type does not address"
    )
    assert "not the CASE_MANAGER" not in reason


@pytest.mark.spec("HP-01-039")
def test_the_reason_has_one_shape_for_every_message_type() -> None:
    """One composer, so the reason varies by path and never by message type.

    Two message types whose declarations differ still get the same wording
    for the same resolved path, as long as they agree on whether they handle
    the manager path. That is what keeps a handler from mapping a gate
    failure to a verdict of its own: the wording is the composer's, not the
    message type's.
    """
    # The no-case path, refused by two different manager-inclusive
    # declarations: one that handles the manager path only, one that also
    # handles the replica path.
    assert undeclared_path_reason(
        ReceivedPath.NO_CASE, {ReceivedPath.CASE_MANAGER}, CASE_ID
    ) == undeclared_path_reason(
        ReceivedPath.NO_CASE,
        {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA},
        CASE_ID,
    )
    # And the replica path, likewise.
    assert undeclared_path_reason(
        ReceivedPath.PARTICIPANT_REPLICA, {ReceivedPath.CASE_MANAGER}, CASE_ID
    ) == undeclared_path_reason(
        ReceivedPath.PARTICIPANT_REPLICA,
        {ReceivedPath.CASE_MANAGER, ReceivedPath.NO_CASE},
        CASE_ID,
    )
    # The clause varies with the path, so the three are not one string.
    reasons = {
        _run_stage(path, ALL_PATHS - {path}).feedback_message
        for path in ALL_PATHS
    }
    assert reasons == set(_MANAGER_INCLUSIVE_REASON.values())
    assert len(reasons) == len(PATHS_IN_ORDER)


@pytest.mark.spec("HP-01-005")
def test_a_refused_path_is_the_handlers_door_refusal() -> None:
    """``door_refusal`` returns the stage's refusal, so every handler agrees.

    No handler maps a gate failure to a verdict of its own: the one the
    stage composed is what the handler reports (HP-01-039).
    """
    stage = _run_stage(
        ReceivedPath.PARTICIPANT_REPLICA, {ReceivedPath.CASE_MANAGER}
    )
    tree = py_trees.composites.Sequence(
        name="ProofBT", memory=False, children=[_seeding_scope(stage)]
    )

    refusal = path_refusal(tree)
    assert refusal is not None
    assert refusal.reason == f"not the CASE_MANAGER of case '{CASE_ID}'"
    assert door_refusal(tree) == refusal


@pytest.mark.spec("HP-01-005")
def test_an_admitted_path_owes_no_refusal() -> None:
    stage = _run_stage(ReceivedPath.CASE_MANAGER, {ReceivedPath.CASE_MANAGER})
    tree = py_trees.composites.Sequence(
        name="ProofBT", memory=False, children=[_seeding_scope(stage)]
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
@pytest.mark.spec("HP-01-035")
def test_the_stage_runs_after_the_addressee_check_and_before_the_guard() -> (
    None
):
    """The path stage is a door stage, in the CLP-10-010 order."""
    tree = _declared_tree()
    stages = [type(unscoped(child)).__name__ for child in tree.children]
    names = [child.name for child in tree.children]

    addressee = stages.index(ActivityAddressedToReceiverNode.__name__)
    seen = stages.index("ActivityNotSeenBeforeNode")
    path = stages.index(ReceivedPathNode.__name__)
    guard = names.index("SenderRuleGuard")

    assert addressee < seen < path < guard
    # Directly after the seen-before door (HP-01-035).
    assert path == seen + 1


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-039")
def test_the_reason_names_the_activitys_case_when_no_case_is_known() -> None:
    """With no case resolvable the reason names the activity, not ``None``.

    The branch a tree reaches when neither its commit case, its manager case
    nor its sender context names one: the reason still has to read as a
    sentence rather than interpolate a missing id.  Only the no-case path is
    reachable with no case id, since an unresolvable case *is* that path.
    """
    assert undeclared_path_reason(
        ReceivedPath.NO_CASE, {ReceivedPath.CASE_MANAGER}, None
    ) == ("holds no replica of the case this activity names")
    assert undeclared_path_reason(
        ReceivedPath.NO_CASE, {ReceivedPath.CASE_MANAGER}, CASE_ID
    ) == (f"holds no replica of case '{CASE_ID}'")


@pytest.mark.spec("HP-01-040")
def test_the_stage_reads_the_case_the_sender_context_names() -> None:
    """A tree that commits nothing still asks about the activity's case.

    The resolution order the stage shares with the sender guard: the commit
    case, else the manager case, else the case the sender context names
    (HP-01-040).  Without the last step a tree built with ``case_id=None``
    would read the no-case path for every delivery.
    """
    assert path_stage_case_id(CASE_ID, None, None) == CASE_ID
    assert path_stage_case_id(None, CASE_ID, None) == CASE_ID
    assert (
        path_stage_case_id(None, None, SenderCheckContext(sender_id=OWNER_ID))
        is None
    )
    assert path_stage_case_id(None, None, _CONTEXT) == CASE_ID

    tree = create_receive_activity_tree(
        name="NoCommitCaseBT",
        case_id=None,
        precondition_guards=[],
        paths={ReceivedPath.PARTICIPANT_REPLICA},
        sender_rule=_RULE,
        sender_context=_CONTEXT,
    )
    stage = next(
        node for node in tree.iterate() if isinstance(node, ReceivedPathNode)
    )
    scope = _seeding_scope(stage)
    assert scope.case_id == CASE_ID
    scenario = BTTestScenario(actor_id=VENDOR_ID)
    _seed_case(scenario)
    scenario.run(scope, actor_id=VENDOR_ID)

    assert stage.resolved_case_id == CASE_ID
    assert stage.resolved_path is ReceivedPath.PARTICIPANT_REPLICA


@pytest.mark.spec("BTND-03-009")
def test_the_manager_path_publishes_the_resolved_manager_id() -> None:
    """The stage publishes ``/case_actor_id``, as the gate it stands in for does.

    A later node that reads the resolved manager's id must find it whichever
    of the two answered the role question, or swapping a sender-guard arm
    onto the path check would silently drop the key.

    The key is scoped to its execution (#5803), so a probe reads it there.
    """
    probe = BlackboardKeyProbe("case_actor_id")
    stage = _run_stage(ReceivedPath.CASE_MANAGER, ALL_PATHS, then=probe)

    assert stage.resolved_path is ReceivedPath.CASE_MANAGER
    assert probe.ran
    assert probe.value == MANAGER_ID
    assert "/case_actor_id" not in py_trees.blackboard.Blackboard.storage


@pytest.mark.spec("CLP-10-010")
@pytest.mark.spec("HP-01-035")
def test_the_door_guards_run_in_the_clp_10_010_order() -> None:
    """The whole door-guard sequence, pinned by name and in order.

    The relative assertions above each pin one edge; this pins the sequence,
    so a stage inserted anywhere among the door guards is a deliberate edit
    to this list (CLP-10-010).
    """
    tree = _declared_tree()

    assert [type(unscoped(guard)).__name__ for guard in tree.door_guards] == [
        "ActivityAddressedToReceiverNode",
        "ActivityNotSeenBeforeNode",
        "ReceivedPathNode",
        "CaseOpenToExternalWritesNode",
        "Sequence",  # the composed SenderRuleGuard
    ]


@pytest.mark.spec("CLP-10-010")
@pytest.mark.spec("HP-01-035")
def test_the_stage_is_one_of_the_trees_door_guards() -> None:
    """A delivery the stage refused did not get past the door."""
    tree = _declared_tree()

    assert any(
        isinstance(unscoped(guard), ReceivedPathNode)
        for guard in tree.door_guards
    )


@pytest.mark.spec("HP-01-040")
@pytest.mark.spec("BT-17-001")
@pytest.mark.spec("CLP-10-026")
def test_a_manager_only_diversion_needs_the_trees_case() -> None:
    """A diversion that may commit must know the case it commits against.

    A manager-only declaration carries no gate of its own, and a tree that
    names no case leaves the stage to resolve one at run time from the
    activity — so the diversion would commit against whatever case arrived.
    """
    with pytest.raises(VultronWiringError, match="must name the case"):
        create_receive_activity_tree(
            name="CaselessDiversionBT",
            case_id=None,
            paths={ReceivedPath.CASE_MANAGER},
            precondition_guards=[
                Diversion(
                    name="D",
                    condition=py_trees.behaviours.Success(name="C"),
                )
            ],
            sender_rule=_RULE,
            sender_context=_CONTEXT,
        )


@pytest.mark.spec("HP-01-007")
@pytest.mark.spec("HP-01-038")
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


@pytest.mark.spec("HP-01-035")
def test_declaring_paths_on_a_run_time_resolved_case_is_a_wiring_error() -> (
    None
):
    """The stage runs before ``case_resolution``, so it must name its case.

    A tree whose case only ``case_resolution`` publishes would have the
    stage read the no-case path for every delivery and refuse any tree that
    did not declare it — a refusal with nothing wrong with the delivery.  The
    factory refuses the combination instead of shipping that trap.
    """
    with pytest.raises(
        VultronWiringError, match="runs before case_resolution"
    ):
        create_receive_activity_tree(
            name="RunTimeCaseBT",
            case_id=None,
            precondition_guards=[],
            paths={ReceivedPath.CASE_MANAGER},
            sender_rule=_RULE,
            sender_context=SenderCheckContext(
                sender_id=OWNER_ID, case_id=None
            ),
            case_resolution=[RequireCaseForReport(report_id=REPORT_ID)],
        )


# ---------------------------------------------------------------------------
# HP-01-008: the sender guard reads the path instead of asking again
# ---------------------------------------------------------------------------


def _leaf_types(node: py_trees.behaviour.Behaviour) -> set[str]:
    return {type(each).__name__ for each in node.iterate()}


@pytest.mark.spec("HP-01-036")
def test_the_sender_guards_arms_read_the_path_stages_answer() -> None:
    """With a path stage the arms are path checks, not a second role read."""
    stage = ReceivedPathNode(declared=frozenset({ReceivedPath.CASE_MANAGER}))
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


@pytest.mark.spec("HP-01-036")
def test_without_a_path_stage_the_arms_read_the_role_themselves() -> None:
    """The stageless shape still composes, which is what the tests rely on.

    No received tree reaches it: after #5044 every call site that passes a
    sender rule also declares its paths, so this is the shape the
    guard-composition tests get when they compose a guard in isolation and
    let the fallback read the receiver's role from their store fixture.  It
    goes with the fallback itself, in #5876.
    """
    guard = compose_sender_guard(_RULE, _CONTEXT)
    assert guard is not None

    types = _leaf_types(guard)
    assert CheckIsCaseManagerNode.__name__ in types
    assert CheckReceivedPathNode.__name__ not in types


@pytest.mark.spec("HP-01-036")
def test_the_declared_tree_asks_the_role_question_once() -> None:
    """One role read answers the path and both sender-guard arms.

    The stage is the only node ahead of the commit that reads the roster for
    the receiver's role; the arms read its answer (HP-01-036).
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


@pytest.mark.spec("HP-01-036")
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


@pytest.mark.spec("HP-01-036")
def test_an_arm_whose_stage_has_not_run_does_not_match() -> None:
    """No arm is entered before the door stage answered."""
    stage = ReceivedPathNode(declared=ALL_PATHS)

    assert stage.resolved_path is None
    assert (
        CheckReceivedPathNode.on_manager_path(stage).update() is Status.FAILURE
    )


# ---------------------------------------------------------------------------
# HP-01-041: no case yet either waits or proceeds
# ---------------------------------------------------------------------------


def _event(semantics: MessageSemantics) -> VultronEvent:
    return VultronEvent(
        semantic_type=semantics,
        activity_id=f"{CASE_ID}/activities/1",
        actor_id=OWNER_ID,
    )


class _UnknownCaseQueue:
    """An inbox queue that holds no case and records what it was asked to hold."""

    def __init__(self) -> None:
        self.queued: list[tuple[str, str, str | None]] = []

    def is_case_known(self, case_id: str) -> bool:
        return False

    def check_and_expire(self, case_id: str, *, at: datetime) -> bool:
        return False

    def queue(
        self,
        activity_id: str,
        case_id: str,
        case_actor_id: str | None = None,
        *,
        at: datetime,
    ) -> None:
        self.queued.append((activity_id, case_id, case_actor_id))


def _defer_check(semantics: MessageSemantics) -> _UnknownCaseQueue:
    """Tick the inbox's defer check for *semantics* at a store with no case."""
    queue = _UnknownCaseQueue()
    client = py_trees.blackboard.Client(name="_defer_check_setup")
    for key in ("inbox_event", "inbox_context_id", "inbox_queue"):
        client.register_key(key, access=py_trees.common.Access.WRITE)
    client.inbox_event = _event(semantics)
    client.inbox_context_id = CASE_ID
    client.inbox_queue = queue

    tree = py_trees.trees.BehaviourTree(root=DeferCheckNode(name="Defer"))
    tree.setup()
    tree.tick()
    return queue


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-041")
def test_a_case_scoped_type_waits_for_its_case_rather_than_being_refused() -> (
    None
):
    """The inbox's defer check holds a case-scoped type, so no path refuses it.

    ``Accept(Offer(CaseParticipant))`` is case-scoped and not deferral
    exempt, so the inbox queues it and it never reaches its received tree —
    or its path stage — until the receiver holds the case (HP-01-041).
    The stub Invite, whose tree declares the no-case branch
    (see the next test), is exempt and proceeds.  The pairing is the point:
    a type takes the no-case path only when the defer check lets it.
    """
    case_scoped = MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT
    assert case_scoped not in CASE_PRECEDING_SEMANTICS
    assert not is_deferral_exempt(_event(case_scoped))

    held = _defer_check(case_scoped)
    assert [case_id for _, case_id, _ in held.queued] == [CASE_ID], (
        "a case-scoped type at a store with no case is queued by the inbox,"
        " not delivered to a tree whose path stage would refuse it"
    )

    proceeds = _defer_check(MessageSemantics.INVITE_ACTOR_TO_CASE)
    assert proceeds.queued == [], (
        "the stub Invite precedes its case by design, so the inbox lets it"
        " reach the tree that declares the no-case branch"
    )


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-041")
def test_the_type_that_precedes_its_case_declares_the_no_case_branch() -> None:
    """The stub Invite declares the no-case path and takes it.

    It is deferral exempt because its case only arrives after the invitee
    answers (MV-10-005), so its tree must handle a receiver that holds no
    replica rather than wait for one (HP-01-041).
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
    scenario.run(_seeding_scope(stage), actor_id=STRANGER_ID)

    assert stage.resolved_path is ReceivedPath.NO_CASE
    assert stage.status is Status.SUCCESS
