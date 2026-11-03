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

"""Diversions: an arm a delivery takes instead of its commit (CLP-10-026).

A diversion whose condition fails lets the tree go on; one whose condition
holds runs its effects and ends the tree before anything after it.  Where a
diversion may run is the tree's path declaration (HP-01-038): a tree that
declares the CASE_MANAGER path alone reaches its diversion only there,
because the path stage refused every other receiver, and the factory refuses
a diversion that could commit the received activity, write state where it
may not, or emit uncovered.
"""

from collections.abc import Collection

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    OTHER_PARTICIPANT_ACTOR,
    make_case_with_manager,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.diversion_stage import (
    Diversion,
    DiversionStage,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    EmitRefusalNoticeNode,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.replica_emit_exemptions import (
    EMBARGO_INVITE_REFUSAL,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes.chain import CreateLogEntryNode
from vultron.errors import VultronWiringError

_CASE = "https://example.org/cases/diversion"


class _Counted(py_trees.behaviour.Behaviour):
    """A leaf that records each tick and returns a fixed status."""

    def __init__(self, name: str, status: Status = Status.SUCCESS) -> None:
        super().__init__(name=name)
        self._status = status
        self.ticks = 0

    def update(self) -> Status:
        self.ticks += 1
        return self._status


class _Emitter(_Counted, EmitCapable):
    pass


class _SendEmbargoProposalRefusalNode(_Counted, EmitCapable):
    """Named like the emit the refusal exemption covers."""


_SendEmbargoProposalRefusalNode.__name__ = "SendEmbargoProposalRefusalNode"


class _Writer(_Counted, StateWriteCapable):
    pass


def _tick(root: py_trees.behaviour.Behaviour) -> None:
    py_trees.trees.BehaviourTree(root=root).tick()


def _stage(condition_status: Status, effects_status: Status = Status.SUCCESS):
    condition = _Counted("Condition", condition_status)
    effects = _Counted("Effects", effects_status)
    after = _Counted("After")
    stage = DiversionStage("Probe", condition, effects)
    root = py_trees.composites.Sequence(
        name="Root", memory=False, children=[stage, after]
    )
    _tick(root)
    return root, stage, effects, after


class TestDiversionStage:
    @pytest.mark.spec("CLP-10-026")
    @pytest.mark.spec("CLP-10-061")
    def test_a_condition_that_fails_lets_the_tree_go_on(self) -> None:
        root, stage, effects, after = _stage(Status.FAILURE)

        assert stage.status is Status.SUCCESS
        assert not stage.taken
        assert effects.ticks == 0
        assert after.ticks == 1
        assert root.status is Status.SUCCESS

    @pytest.mark.spec("CLP-10-026")
    @pytest.mark.spec("CLP-10-062")
    @pytest.mark.spec("CLP-10-063")
    def test_a_condition_that_holds_answers_and_ends_the_tree(self) -> None:
        root, stage, effects, after = _stage(Status.SUCCESS)

        assert stage.taken and stage.effects_succeeded
        assert effects.ticks == 1
        assert stage.status is Status.FAILURE
        assert after.ticks == 0
        assert root.status is Status.FAILURE
        assert "diverted to Probe" in BTBridge.get_failure_reason(root)

    @pytest.mark.spec("CLP-10-026")
    @pytest.mark.spec("CLP-10-063")
    def test_an_answer_that_fails_still_ends_the_tree(self) -> None:
        root, stage, _, after = _stage(Status.SUCCESS, Status.FAILURE)

        assert stage.taken and not stage.effects_succeeded
        assert after.ticks == 0
        assert root.status is Status.FAILURE


#: The declaration a tree that reaches a diversion at any receiver makes.
_BOTH_PATHS = frozenset(
    {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA}
)


def _tree(
    *guards,
    paths: Collection[ReceivedPath] | None = _BOTH_PATHS,
    **kwargs,
) -> py_trees.composites.Sequence:
    return create_receive_activity_tree(
        name="Probe",
        case_id=_CASE,
        paths=paths,
        precondition_guards=list(guards),
        **kwargs,
    )


class TestFactoryChecks:
    @pytest.mark.spec("CLP-10-026")
    @pytest.mark.spec("CLP-10-061")
    def test_a_condition_must_be_read_only(self) -> None:
        with pytest.raises(VultronWiringError, match="read-only"):
            _tree(Diversion(name="D", condition=_Emitter("Emit")))

    @pytest.mark.spec("CLP-10-026")
    @pytest.mark.spec("CLP-10-064")
    def test_no_diversion_commits_the_received_activity(self) -> None:
        with pytest.raises(VultronWiringError, match="never committed"):
            _tree(
                Diversion(
                    name="D",
                    condition=_Counted("C"),
                    effects=(CommitCaseLedgerEntryNode(case_id=_CASE),),
                )
            )

    @pytest.mark.spec("RSH-08-003")
    @pytest.mark.spec("CLP-10-067")
    def test_a_receiver_diversion_writes_no_case_state(self) -> None:
        with pytest.raises(VultronWiringError, match="no case state"):
            _tree(
                Diversion(
                    name="D",
                    condition=_Counted("C"),
                    effects=(_Writer("W"),),
                )
            )

    @pytest.mark.spec("CLP-10-026")
    @pytest.mark.spec("CLP-10-067")
    def test_a_receiver_diversion_commits_no_entry(self) -> None:
        """A commit of the CASE_MANAGER's own entry runs only at the
        CASE_MANAGER, so a receiver's own answer may not hold one."""
        with pytest.raises(VultronWiringError, match="only at the"):
            _tree(
                Diversion(
                    name="D",
                    condition=_Counted("C"),
                    effects=(
                        CreateLogEntryNode(
                            case_id=_CASE,
                            object_id=_CASE,
                            semantic_type="probe",
                        ),
                    ),
                )
            )

    @pytest.mark.spec("BT-17-008")
    @pytest.mark.spec("CLP-10-069")
    def test_a_receiver_diversion_needs_an_exemption_to_emit(self) -> None:
        with pytest.raises(VultronWiringError, match="ReplicaEmitExemption"):
            _tree(
                Diversion(
                    name="D",
                    condition=_Counted("C"),
                    effects=(_Emitter("E"),),
                )
            )

    @pytest.mark.spec("BT-17-008")
    @pytest.mark.spec("CLP-10-068")
    @pytest.mark.spec("CLP-10-069")
    def test_a_receiver_diversion_with_a_covering_exemption_builds(
        self,
    ) -> None:
        tree = _tree(
            Diversion(
                name="D",
                condition=_Counted("C"),
                effects=(_SendEmbargoProposalRefusalNode("E"),),
                emit_exemption=EMBARGO_INVITE_REFUSAL,
            )
        )
        assert [
            n.name for n in tree.iterate() if isinstance(n, DiversionStage)
        ] == ["D"]

    @pytest.mark.spec("BT-17-008")
    @pytest.mark.spec("HP-01-038")
    def test_a_manager_only_declaration_takes_no_exemption(self) -> None:
        with pytest.raises(VultronWiringError, match="drop its emit"):
            _tree(
                Diversion(
                    name="D",
                    condition=_Counted("C"),
                    emit_exemption=EMBARGO_INVITE_REFUSAL,
                ),
                paths={ReceivedPath.CASE_MANAGER},
            )

    @pytest.mark.spec("HP-01-038")
    @pytest.mark.spec("CLP-10-026")
    def test_a_diversion_needs_the_trees_path_declaration(self) -> None:
        """Nothing else says where a diversion may run (ADR-0153)."""
        with pytest.raises(VultronWiringError, match="paths the tree"):
            _tree(
                Diversion(name="D", condition=_Counted("C")),
                paths=None,
            )

    @pytest.mark.spec("CLP-10-022")
    @pytest.mark.spec("CLP-10-026")
    def test_a_tree_with_diversions_takes_the_refusal_notice(self) -> None:
        """The notice answers the guards' refusals; the stage skips it for a
        diverted delivery, which its diversion answered."""
        tree = _tree(
            Diversion(name="D", condition=_Counted("C")),
            refusal_effects=[_Emitter("Answer")],
        )

        (stage,) = [
            n for n in tree.iterate() if isinstance(n, PreconditionGuardStage)
        ]
        assert [
            type(n)
            for n in stage.refusal.iterate()
            if isinstance(n, (EmitRefusalNoticeNode, _Emitter))
        ] == [EmitRefusalNoticeNode, _Emitter]
        assert [
            n.name
            for n in stage.guards.iterate()
            if isinstance(n, DiversionStage)
        ] == ["D"]


class TestManagerOnlyDeclarationReachesItsDiversion:
    """A manager-only declaration is what keeps a diversion at the manager.

    The diversion carries no gate of its own any more (HP-01-038): the path
    stage the factory placed refuses every other receiver before the guards
    run, so the condition is never evaluated there.  These run the whole
    tree, because the stage is the protection and a stage lifted out of its
    tree protects nothing.
    """

    @staticmethod
    def _run(store_actor: str) -> tuple[DiversionStage, _Counted, _Counted]:
        case, _, dl = make_case_with_manager(
            f"diversion-{store_actor.rsplit('/', 1)[-1]}",
            store_actor_id=store_actor,
        )
        condition, effect = _Counted("Condition"), _Counted("Effect")
        tree = create_receive_activity_tree(
            name="Probe",
            case_id=case.id_,
            paths={ReceivedPath.CASE_MANAGER},
            precondition_guards=[
                Diversion(name="D", condition=condition, effects=(effect,))
            ],
        )
        (stage,) = [n for n in tree.iterate() if isinstance(n, DiversionStage)]
        (path_stage,) = [
            n for n in tree.iterate() if isinstance(n, ReceivedPathNode)
        ]
        BTBridge(datalayer=dl).execute_with_setup(
            tree=path_stage, actor_id=store_actor
        )
        if path_stage.status is Status.SUCCESS:
            BTBridge(datalayer=dl).execute_with_setup(
                tree=stage, actor_id=store_actor
            )
        return stage, condition, effect

    @pytest.mark.spec("BT-17-001")
    @pytest.mark.spec("CLP-10-026")
    @pytest.mark.spec("CLP-10-065")
    def test_the_case_manager_diverts(self) -> None:
        stage, condition, effect = self._run(CASE_MANAGER_ACTOR)

        assert stage.taken and stage.effects_succeeded
        assert condition.ticks == 1 and effect.ticks == 1

    @pytest.mark.spec("HP-01-039")
    @pytest.mark.spec("CLP-10-026")
    @pytest.mark.spec("CLP-10-065")
    def test_another_store_is_refused_before_the_diversion(self) -> None:
        stage, condition, effect = self._run(OTHER_PARTICIPANT_ACTOR)

        assert not stage.taken
        assert condition.ticks == 0 and effect.ticks == 0
