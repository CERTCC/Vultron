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

import logging
from collections.abc import Collection
from dataclasses import dataclass

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    OTHER_PARTICIPANT_ACTOR,
    make_case_with_manager,
)
from test.support.act_runner import run_tree
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
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
from vultron.core.behaviors.case.receive_stages.tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.case.received_run.reading import (
    ReceivedOutcome,
    read_outcome,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.idempotency import (
    ReportsRefusal,
    SilentIdempotencyGuardMixin,
    refusal_ending_run,
)
from vultron.core.behaviors.replica_emit_exemptions import (
    EMBARGO_INVITE_FAULT,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes.chain import CreateLogEntryNode
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.ports.case_persistence import CasePersistence
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


@dataclass(frozen=True)
class _Probe:
    """One factory-built probe tree and the parts a test reads off it."""

    tree: ReceivedActivityTree
    stage: DiversionStage
    path_stage: ReceivedPathNode
    condition: _Counted
    effect: _Counted
    datalayer: CasePersistence


class _EmitEmbargoInviteFaultNode(_Counted, EmitCapable):
    """Named like the emit the surviving exemption covers."""


_EmitEmbargoInviteFaultNode.__name__ = "EmitEmbargoInviteFaultNode"


class _Writer(_Counted, StateWriteCapable):
    pass


def _tick(root: py_trees.behaviour.Behaviour) -> None:
    py_trees.trees.BehaviourTree(root=root).tick()


class _Reasoned(_Counted):
    """A condition that gives its reason when it holds."""

    def __init__(self, name: str, status: Status, reason: str) -> None:
        super().__init__(name, status)
        self._reason = reason

    def update(self) -> Status:
        self.feedback_message = self._reason
        return super().update()


class _Repeat(SilentIdempotencyGuardMixin, py_trees.behaviour.Behaviour):
    """An answer that stops as an idempotent repeat (HP-01-014)."""

    def update(self) -> Status:
        return self._idempotent_failure(
            logging.getLogger(__name__), "%s: sent", self.name
        )


def _stage_with(
    condition_status: Status,
    effects: py_trees.behaviour.Behaviour,
    *,
    refuses: bool = False,
    refuses_unanswered: bool = False,
    reason: str = "",
) -> tuple[py_trees.composites.Sequence, DiversionStage, _Counted]:
    """Tick a stage over *effects*; the root, the stage and its successor."""
    condition = _Reasoned("Condition", condition_status, reason)
    after = _Counted("After")
    stage = DiversionStage(
        "Probe",
        condition,
        effects,
        refuses=refuses,
        refuses_unanswered=refuses_unanswered,
    )
    root = py_trees.composites.Sequence(
        name="Root", memory=False, children=[stage, after]
    )
    _tick(root)
    return root, stage, after


def _stage(
    condition_status: Status,
    effects_status: Status = Status.SUCCESS,
    *,
    refuses: bool = False,
    refuses_unanswered: bool = False,
    reason: str = "",
):
    effects = _Counted("Effects", effects_status)
    root, stage, after = _stage_with(
        condition_status,
        effects,
        refuses=refuses,
        refuses_unanswered=refuses_unanswered,
        reason=reason,
    )
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


class TestDiversionStageDeclaredRefusal:
    """A refusing diversion declares the refusal the runner reads (HP-01-003)."""

    @pytest.mark.spec("HP-01-003")
    def test_a_refusing_diversion_it_answered_declares_its_conditions_reason(
        self,
    ) -> None:
        root, stage, _, _ = _stage(
            Status.SUCCESS, refuses=True, reason="embargo 'e' ended (X-1)"
        )

        assert isinstance(stage, ReportsRefusal)
        assert stage.declared_refusal == "embargo 'e' ended (X-1)"
        assert refusal_ending_run(root) == "embargo 'e' ended (X-1)"

    @pytest.mark.spec("HP-01-003")
    def test_a_condition_with_no_reason_is_named_by_the_stage(self) -> None:
        _, stage, _, _ = _stage(Status.SUCCESS, refuses=True)

        assert stage.declared_refusal == (
            "Probe: the delivery was answered, not recorded"
        )

    @pytest.mark.spec("HP-01-003")
    def test_an_answer_that_failed_declares_no_refusal(self) -> None:
        _, stage, _, _ = _stage(
            Status.SUCCESS, Status.FAILURE, refuses=True, reason="why"
        )

        assert stage.status is Status.FAILURE
        assert stage.declared_refusal is None

    @pytest.mark.spec("HP-01-003")
    def test_a_diversion_not_taken_declares_no_refusal(self) -> None:
        _, stage, _, _ = _stage(Status.FAILURE, refuses=True, reason="why")

        assert stage.declared_refusal is None

    @pytest.mark.spec("HP-01-003")
    def test_a_diversion_that_does_not_refuse_declares_nothing(self) -> None:
        _, stage, _, _ = _stage(Status.SUCCESS, reason="why")

        assert stage.declared_refusal is None

    @pytest.mark.spec("HP-01-003")
    def test_the_runner_reports_the_declared_refusal(self) -> None:
        """With no handler reader, the run is ``REFUSED`` for exactly the
        condition's reason (ADR-0195)."""
        root, _, _, _ = _stage(
            Status.SUCCESS, refuses=True, reason="embargo 'e' ended (X-1)"
        )
        result = BTExecutionResult(
            status=Status.FAILURE,
            feedback_message=BTBridge.get_failure_reason(root),
        )

        verdict = read_outcome(
            ReceivedOutcome.of(
                root, result, "ProbeBT", receiving_actor_id=CASE_MANAGER_ACTOR
            )
        )

        assert verdict.disposition is HandlerDisposition.REFUSED
        assert verdict.reason == "embargo 'e' ended (X-1)"

    @pytest.mark.spec("HP-01-003")
    def test_the_factory_carries_the_declaration_to_the_stage(self) -> None:
        refusing = _tree(
            Diversion(
                name="Probe",
                condition=_Counted("Condition"),
                effects=(_Counted("Answer"),),
                refuses=True,
            ),
            paths={ReceivedPath.CASE_MANAGER},
        )
        quiet = _tree(
            Diversion(
                name="Probe",
                condition=_Counted("Condition"),
                effects=(_Counted("Answer"),),
            ),
            paths={ReceivedPath.CASE_MANAGER},
        )

        def stage_of(tree: py_trees.behaviour.Behaviour) -> DiversionStage:
            return next(
                n for n in tree.iterate() if isinstance(n, DiversionStage)
            )

        assert stage_of(refusing).refuses
        assert not stage_of(quiet).refuses
        assert not stage_of(refusing).refuses_unanswered


class TestDiversionStageRefusalStandingUnanswered:
    """A refusal whose answer only notifies it stands without that answer.

    The P/X/A refusal of an embargo Invite or Accept is refused whether or
    not its ``Reject`` could be sent (EMB-01-002, EMB-02-004), so its stage
    declares the refusal on an answer that failed, but not on one that
    stopped as a repeat of a ``Reject`` already sent (HP-01-014).
    """

    @pytest.mark.spec("HP-01-003")
    def test_an_answer_that_failed_still_declares_the_refusal(self) -> None:
        root, stage, _, _ = _stage(
            Status.SUCCESS,
            Status.FAILURE,
            refuses=True,
            refuses_unanswered=True,
            reason="P/X/A set (EMB-01-002)",
        )

        assert not stage.effects_succeeded
        assert stage.declared_refusal == "P/X/A set (EMB-01-002)"
        assert refusal_ending_run(root) == "P/X/A set (EMB-01-002)"

    @pytest.mark.spec("HP-01-003")
    def test_an_answer_it_completed_declares_the_refusal(self) -> None:
        _, stage, _, _ = _stage(
            Status.SUCCESS,
            refuses=True,
            refuses_unanswered=True,
            reason="why",
        )

        assert stage.declared_refusal == "why"

    @pytest.mark.spec("HP-01-003")
    def test_a_condition_with_no_reason_is_named_by_the_stage(self) -> None:
        _, stage, _, _ = _stage(
            Status.SUCCESS,
            Status.FAILURE,
            refuses=True,
            refuses_unanswered=True,
        )

        assert stage.declared_refusal == (
            "Probe: the delivery was diverted, not recorded"
        )

    @pytest.mark.spec("HP-01-003", "HP-01-014")
    def test_an_answer_that_stopped_as_a_repeat_declares_no_refusal(
        self,
    ) -> None:
        _, stage, _ = _stage_with(
            Status.SUCCESS,
            _Repeat(name="AlreadySent"),
            refuses=True,
            refuses_unanswered=True,
            reason="why",
        )

        assert stage.taken and not stage.effects_succeeded
        assert stage.declared_refusal is None

    @pytest.mark.spec("HP-01-003")
    def test_a_diversion_not_taken_declares_no_refusal(self) -> None:
        _, stage, _, _ = _stage(
            Status.FAILURE,
            refuses=True,
            refuses_unanswered=True,
            reason="why",
        )

        assert stage.declared_refusal is None

    @pytest.mark.spec("CLP-10-026")
    def test_it_needs_a_refusing_diversion(self) -> None:
        with pytest.raises(ValueError, match="refuses_unanswered needs"):
            Diversion(
                name="Probe",
                condition=_Counted("Condition"),
                refuses_unanswered=True,
            )

    @pytest.mark.spec("HP-01-003")
    def test_the_factory_carries_it_to_the_stage(self) -> None:
        tree = _tree(
            Diversion(
                name="Probe",
                condition=_Counted("Condition"),
                effects=(_Counted("Answer"),),
                refuses=True,
                refuses_unanswered=True,
            ),
            paths={ReceivedPath.CASE_MANAGER},
        )

        stage = next(
            n for n in tree.iterate() if isinstance(n, DiversionStage)
        )
        assert stage.refuses and stage.refuses_unanswered


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
                    effects=(
                        with_case_id(CommitCaseLedgerEntryNode(), _CASE),
                    ),
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
                effects=(_EmitEmbargoInviteFaultNode("E"),),
                emit_exemption=EMBARGO_INVITE_FAULT,
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
                    emit_exemption=EMBARGO_INVITE_FAULT,
                ),
                paths={ReceivedPath.CASE_MANAGER},
            )

    @pytest.mark.spec("HP-01-038")
    @pytest.mark.spec("CLP-10-026")
    def test_a_diversion_needs_the_trees_path_declaration(self) -> None:
        """The declaration is the only statement of where a diversion runs.

        ADR-0153 retires the ``gate=`` choice beside it, so a tree with no
        declaration says nothing about whether its diversion may commit or
        must stay the receiver's own answer, and the factory refuses to
        guess.
        """
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
    run, so the condition is never evaluated there.

    The claim has two halves and they are checked separately, because a
    factory-built tree cannot be ticked whole without a received activity
    for its intake node:

    - that the path stage really runs *first* is asserted off the built tree
      in :meth:`test_the_path_stage_is_a_door_ahead_of_the_diversion`, rather
      than supplied by the order :meth:`_run` ticks things in (#5533);
    - that the stage's verdict is what reaches, or does not reach, the
      diversion is what :meth:`_run` exercises.
    """

    @staticmethod
    def _build(store_actor: str) -> _Probe:
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
        return _Probe(tree, stage, path_stage, condition, effect, dl)

    @pytest.mark.spec("HP-01-038")
    def test_the_path_stage_is_a_door_ahead_of_the_diversion(self) -> None:
        """The order comes from the tree, not from the test.

        Without this, :meth:`_run` would only show that *a* refusing stage
        stops the diversion, and would take on faith that the factory put it
        in front (#5533, #5534).
        """
        probe = self._build(CASE_MANAGER_ACTOR)
        order = [id(node) for node in probe.tree.iterate()]

        # The stage sits under the scope that seeds its /case_id port.
        assert probe.path_stage.parent in probe.tree.door_guards
        assert order.index(id(probe.path_stage)) < order.index(id(probe.stage))

    @staticmethod
    def _run(store_actor: str) -> tuple[DiversionStage, _Counted, _Counted]:
        probe = TestManagerOnlyDeclarationReachesItsDiversion._build(
            store_actor
        )
        door = probe.path_stage.parent
        assert door is not None
        run_tree(
            BTBridge(datalayer=probe.datalayer),
            tree=door,
            actor_id=store_actor,
        )
        if probe.path_stage.status is Status.SUCCESS:
            run_tree(
                BTBridge(datalayer=probe.datalayer),
                tree=probe.stage,
                actor_id=store_actor,
            )
        return probe.stage, probe.condition, probe.effect

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
