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

"""The branch a received tree runs on some of its declared paths (ADR-0153).

``OnPaths`` is how a tree says that part of its work belongs to one of the
paths it declared, and the factory builds a ``PathBranch`` in its place
(HP-01-038).  Three things make it the replacement for the role-gate
composites rather than a second one: it reads the path stage's answer instead
of asking the roster again (HP-01-036), a failure of its work propagates
rather than reading as a skip, and a branch that could never run — or that
runs on every declared path — is a wiring error at composition time.
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.path_branch import (
    OnPaths,
    PathBranch,
    path_branch_stage,
    wrap_children,
)
from vultron.core.behaviors.case.nodes.received_path import (
    CheckReceivedPathNode,
    ReceivedPath,
    ReceivedPathNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
    ungated_emitters,
    ungated_nodes,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/path-branch"
MANAGER_ID = "https://example.org/actors/coordinator"
VENDOR_ID = "https://example.org/actors/vendor"
OWNER_ID = "https://example.org/actors/owner"

_RULE = SenderRule.to_case_manager(SenderEntitlementKind.CASE_OWNER)
_CONTEXT = SenderCheckContext(sender_id=OWNER_ID, case_id=CASE_ID)


class _Emitter(EmitCapable, py_trees.behaviour.Behaviour):
    """A leaf the factory reads as reaching the outbox (BT-17-008)."""

    def update(self) -> Status:
        return Status.SUCCESS


class _Writer(StateWriteCapable, py_trees.behaviour.Behaviour):
    """A leaf the walks read as writing case state (RSH-08-003)."""

    def update(self) -> Status:
        return Status.SUCCESS


class _Marker(py_trees.behaviour.Behaviour):
    """A leaf that records whether it ran, and returns what it was told to."""

    def __init__(self, name: str, status: Status = Status.SUCCESS) -> None:
        super().__init__(name=name)
        self.ran = False
        self._status = status

    def update(self) -> Status:
        self.ran = True
        return self._status


def _tree(
    declared: set[ReceivedPath],
    *guards: py_trees.behaviour.Behaviour | OnPaths,
):
    return create_receive_activity_tree(
        name="PathBranchProofBT",
        case_id=CASE_ID,
        paths=declared,
        sender_rule=_RULE,
        sender_context=_CONTEXT,
        precondition_guards=list(guards),
    )


def _branch_of(tree) -> PathBranch:
    branch = next(
        (node for node in tree.iterate() if isinstance(node, PathBranch)),
        None,
    )
    assert branch is not None, "the factory built no PathBranch"
    return branch


def _run_branch(
    declaration: OnPaths, declared: set[ReceivedPath], actor_id: str
) -> PathBranch:
    """Run the stage and the branch it feeds, in *actor_id*'s store.

    The pair, not the whole tree: the factory's placement of the branch is
    checked structurally above, and this is about what the branch does with
    the answer the stage put there.
    """
    stage = ReceivedPathNode(
        declared=frozenset(declared),
        case_id=CASE_ID,
        label="PathBranchProofBT",
    )
    branch = path_branch_stage("proof", declaration, stage)
    _run(
        py_trees.composites.Sequence(
            name="StageThenBranch", memory=False, children=[stage, branch]
        ),
        actor_id,
    )
    return branch


def _run(tree, actor_id: str) -> None:
    manager = CaseParticipant(
        id_=f"{CASE_ID}/participants/manager",
        attributed_to=MANAGER_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    vendor = CaseParticipant(
        id_=f"{CASE_ID}/participants/vendor",
        attributed_to=VENDOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )
    scenario = BTTestScenario(actor_id=actor_id)
    scenario.seed(
        manager,
        vendor,
        VulnerabilityCase(
            id_=CASE_ID,
            name="PATH-BRANCH",
            attributed_to=OWNER_ID,
            case_participants=[manager.id_, vendor.id_],
            actor_participant_index={
                MANAGER_ID: manager.id_,
                VENDOR_ID: vendor.id_,
            },
        ),
    )
    scenario.run(tree, actor_id=actor_id)


_BOTH = {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA}


@pytest.mark.spec("HP-01-036")
def test_the_branch_reads_the_stages_answer_and_asks_nothing_itself() -> None:
    """The skip arm is a condition over the resolved path, bound to the stage.

    What makes the branch one role question per message rather than two: its
    only condition nodes are
    :class:`~vultron.core.behaviors.case.nodes.received_path.CheckReceivedPathNode`
    instances holding the tree's own stage.
    """
    work = _Marker("work")
    tree = _tree(_BOTH, OnPaths.at_case_manager("Adjudicate", work))
    stage = next(
        node for node in tree.iterate() if isinstance(node, ReceivedPathNode)
    )
    branch = _branch_of(tree)
    assert branch.branch is work

    readers = [
        node
        for node in branch.children[0].iterate()
        if isinstance(node, CheckReceivedPathNode)
    ]
    assert readers, "the skip arm reads no resolved path"
    assert all(reader.stage is stage for reader in readers)


@pytest.mark.spec("HP-01-038")
def test_a_manager_branch_runs_at_the_manager_and_skips_at_a_replica() -> None:
    """One declaration, two dispositions, from the one role question."""
    work = _Marker("work")
    branch = _run_branch(
        OnPaths.at_case_manager("Adjudicate", work), _BOTH, MANAGER_ID
    )
    assert work.ran
    assert branch.status is Status.SUCCESS

    skipped = _Marker("work")
    branch = _run_branch(
        OnPaths.at_case_manager("Adjudicate", skipped), _BOTH, VENDOR_ID
    )
    assert not skipped.ran
    assert branch.status is Status.SUCCESS


@pytest.mark.spec("RSH-08-003")
def test_an_off_manager_branch_is_narrowed_to_the_declared_paths() -> None:
    """``off_case_manager`` means "every declared path but the manager's".

    The declaration decides the branch, so the same helper gives a
    replica-only branch in a two-path tree and a replica-or-no-case branch in
    a three-path one, with no tree repeating the set.
    """
    tree = _tree(_BOTH, OnPaths.off_case_manager("Records", _Marker("work")))
    assert _branch_of(tree).paths == frozenset(
        {ReceivedPath.PARTICIPANT_REPLICA}
    )

    tree = _tree(
        set(ReceivedPath), OnPaths.off_case_manager("Records", _Marker("work"))
    )
    assert _branch_of(tree).paths == frozenset(ReceivedPath) - {
        ReceivedPath.CASE_MANAGER
    }


@pytest.mark.spec("HP-01-038")
def test_a_failure_on_the_branchs_own_path_propagates() -> None:
    """A FAILURE of the work is the branch's FAILURE, never a skip.

    The hazard the ``Inverter`` in the skip arm exists for: a bare success
    fallback would report "this receiver is on another path" and "the work
    failed here" alike, which is how a genuine failure reads as a benign
    no-op (BTND-07-005).
    """
    work = _Marker("work", status=Status.FAILURE)
    branch = _run_branch(
        OnPaths.at_case_manager("Adjudicate", work), _BOTH, MANAGER_ID
    )

    assert work.ran
    assert branch.status is Status.FAILURE


@pytest.mark.spec("HP-01-038")
def test_a_branch_in_a_tree_that_declared_no_paths_is_a_wiring_error() -> None:
    """No stage, no answer to read."""
    with pytest.raises(VultronWiringError, match="declare its paths"):
        create_receive_activity_tree(
            name="PathBranchProofBT",
            case_id=CASE_ID,
            sender_rule=_RULE,
            sender_context=_CONTEXT,
            precondition_guards=[
                OnPaths.at_case_manager("Adjudicate", _Marker("work"))
            ],
        )


@pytest.mark.spec("HP-01-038")
def test_a_branch_naming_no_declared_path_is_a_wiring_error() -> None:
    """A branch that could never run is a mistake, not a dead arm."""
    with pytest.raises(VultronWiringError, match="none of which the tree"):
        _tree(
            {ReceivedPath.PARTICIPANT_REPLICA},
            OnPaths.at_case_manager("Adjudicate", _Marker("work")),
        )


@pytest.mark.spec("HP-01-038")
def test_a_branch_naming_every_declared_path_is_a_wiring_error() -> None:
    """A branch on every declared path is the tree's own work.

    Keeping it a branch would hide that: a reader would take the gate as a
    statement that some receiver skips the work, when none does.
    """
    with pytest.raises(VultronWiringError, match="every path the tree"):
        _tree(
            {ReceivedPath.CASE_MANAGER},
            OnPaths.at_case_manager("Adjudicate", _Marker("work")),
        )


@pytest.mark.spec("HP-01-038")
def test_an_empty_branch_declaration_is_a_wiring_error() -> None:
    """A branch has to name a path to run on."""
    with pytest.raises(VultronWiringError, match="names no path"):
        _tree(
            _BOTH,
            OnPaths(name="Adjudicate", paths=frozenset(), children=()),
        )


@pytest.mark.spec("HP-01-038")
def test_a_branch_holding_no_node_is_a_wiring_error() -> None:
    """A branch with no work would read as a path the tree acts on.

    An empty body is a Sequence that always succeeds, so the tree would say
    it does something on that path and do nothing there.
    """
    with pytest.raises(VultronWiringError, match="holds no node"):
        _tree(_BOTH, OnPaths.at_case_manager("Adjudicate"))


@pytest.mark.spec("BT-17-008")
def test_an_emit_on_the_manager_path_alone_needs_no_replica_exemption() -> (
    None
):
    """A manager-only branch gates its emits, as the CASE_MANAGER gate does.

    ``check_replica_effects`` refuses an ungated emit in ``replica_effects``
    because it would run at a replica.  A branch declared on the manager
    path alone is the same statement as the gate, so an emit inside it is
    not ungated and needs no ``ReplicaEmitExemption`` — without this, an
    author would invent one for a node that never runs at a replica.
    """
    emit = _Emitter("EmitSomething")
    tree = create_receive_activity_tree(
        name="PathBranchProofBT",
        case_id=CASE_ID,
        paths=_BOTH,
        sender_rule=_RULE,
        sender_context=_CONTEXT,
        precondition_guards=[],
        replica_effects=[OnPaths.at_case_manager("ManagerEmits", emit)],
    )

    assert ungated_emitters([_branch_of(tree)]) == []
    assert emit in list(_branch_of(tree).branch.iterate())


@pytest.mark.spec("BT-17-008")
def test_an_emit_off_the_manager_path_is_still_ungated() -> None:
    """The complement: a branch that runs at a replica holds ungated emits."""
    emit = _Emitter("EmitSomething")

    with pytest.raises(VultronWiringError, match="would run on every replica"):
        create_receive_activity_tree(
            name="PathBranchProofBT",
            case_id=CASE_ID,
            paths=_BOTH,
            sender_rule=_RULE,
            sender_context=_CONTEXT,
            precondition_guards=[],
            replica_effects=[OnPaths.off_case_manager("ReplicaEmits", emit)],
        )


@pytest.mark.spec("HP-01-042")
def test_a_state_write_is_bounded_only_by_a_manager_only_branch() -> None:
    """The state-write walk reads the branch the same way the emit walk does.

    :func:`ungated_nodes` takes the marker as an argument and skips on the
    branch alone, so the asymmetry HP-01-042 states holds for a state write
    too: a branch on the manager path alone is the gate, and a branch on any
    other path is not.  No tree in the corpus puts a write in either kind of
    branch, so without this the manager-only half of that rule would rest on
    the emit walk's test and a reading of the code.
    """
    bounded = _Writer("WriteOnManagerPath")
    unbounded = _Writer("WriteOffManagerPath")

    at_manager = _tree(_BOTH, OnPaths.at_case_manager("Adjudicate", bounded))
    off_manager = _tree(
        _BOTH, OnPaths.off_case_manager("AnswerOnReplica", unbounded)
    )

    assert bounded in list(_branch_of(at_manager).branch.iterate())
    assert unbounded in list(_branch_of(off_manager).branch.iterate())

    assert ungated_nodes([_branch_of(at_manager)], StateWriteCapable) == []
    assert ungated_nodes([_branch_of(off_manager)], StateWriteCapable) == [
        unbounded
    ]


@pytest.mark.spec("CS-22-001")
def test_the_gates_and_the_branches_share_one_body_shape() -> None:
    """One child runs bare; several become a Sequence.

    The role gates and the path branches call the same helper, so a reader of
    either sees the same body and a mid-body FAILURE propagates in both.
    """
    one = _Marker("only")
    assert wrap_children("Body", [one]) is one

    several: list[py_trees.behaviour.Behaviour] = [
        _Marker("first"),
        _Marker("second"),
    ]
    body = wrap_children("Body", several)
    assert isinstance(body, py_trees.composites.Sequence)
    assert body.name == "BodyBody"
    assert body.children == several

    named = wrap_children(
        "Body", [_Marker("first"), _Marker("second")], "Adjudicate"
    )
    assert named.name == "Adjudicate"
