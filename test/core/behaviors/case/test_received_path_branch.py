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
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext
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
    tree = _tree(_BOTH, OnPaths.at_case_manager("Adjudicate", _Marker("work")))
    stage = next(
        node for node in tree.iterate() if isinstance(node, ReceivedPathNode)
    )
    branch = _branch_of(tree)

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
