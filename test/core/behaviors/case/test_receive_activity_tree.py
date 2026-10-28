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

"""The factory owns the CASE_MANAGER gate of a received tree (BT-17-008).

``create_receive_activity_tree`` wraps ``manager_effects`` in the gate after
the commit and ``replica_effects``, and refuses at construction an
emit-capable node in ``replica_effects`` that no registered exemption covers.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.act_transaction import (
    ActTransaction,
    OneActExemption,
)
from vultron.core.behaviors.case.nodes.delegation import (
    EmitRejectCaseParticipantRoleNode,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    EmitRefusalNoticeNode,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    RefusalEffectsBestEffort,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
    received_stages,
    ungated_emitters,
    ungated_nodes,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.replica_emit_exemptions import (
    OFFER_ROLE,
    ReplicaEmitExemption,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderIsParticipantNode,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    ClosedSenderCheck,
    SenderCheckContext,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.ledger_position_stage import (
    LEDGER_POSITION_GATE_NAME,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/case-factory-gate-001"
COMMIT = "GuardedCommitCaseLedgerEntryBT"
POST_CLOSE = "CaseOpenToExternalWrites"
ADDRESSEE = "ActivityAddressedToReceiverNode"
CLOCK_GATE = "ClockDecisionsIfCaseManager"
POSITION_GATE = LEDGER_POSITION_GATE_NAME
#: The case-wide clock decision every case tree with a sender guard takes.
END_TIME = "EmbargoEndTimeDecision"
#: The stage a commit tree's guards sit in, with the refusal notice (CLP-02-005).
STAGE = "PreconditionGuardStage"


class _Emitter(EmitCapable, py_trees.behaviour.Behaviour):
    """A stand-in emit node: carries the marker, emits nothing."""

    def __init__(self, name: str = "Emitter") -> None:
        super().__init__(name=name)

    def update(self) -> Status:
        return Status.SUCCESS


class _Writer(StateWriteCapable, py_trees.behaviour.Behaviour):
    """A stand-in state-write node: carries the marker, writes nothing."""

    def __init__(self, name: str = "Writer") -> None:
        super().__init__(name=name)

    def update(self) -> Status:
        return Status.SUCCESS


class _EmittingWriter(StateWriteCapable, _Emitter):
    """A stand-in emit node that also writes case state."""


class _EmittingSequence(EmitCapable, py_trees.composites.Sequence):
    """A stand-in emit-capable composite, to hide a writer inside."""


def _effect(name: str = "Effect") -> py_trees.behaviour.Behaviour:
    return py_trees.behaviours.Success(name=name)


def _role_reject_emit() -> EmitRejectCaseParticipantRoleNode:
    return EmitRejectCaseParticipantRoleNode(
        offer_id="urn:uuid:offer",
        case_id=CASE_ID,
        role=CVDRole.VENDOR,
        target_actor_id="urn:uuid:target",
        vendor_id="urn:uuid:vendor",
    )


def _names(tree: py_trees.behaviour.Behaviour) -> list[str]:
    """The tree's stage names, its act block opened in place."""
    return [stage.name for stage in received_stages(tree)]


class TestStageOrder:
    def test_manager_effects_are_gated_after_the_commit_and_replica_effects(
        self,
    ) -> None:
        replica = _effect("Replica")
        manager = _Emitter("ManagerEmit")
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
            replica_effects=[replica],
            manager_effects=[manager],
            manager_case_id=CASE_ID,
        )

        assert isinstance(tree.children[0], IntakeReceivedActivityNode)
        assert _names(tree)[1:] == [
            POST_CLOSE,
            ADDRESSEE,
            STAGE,
            COMMIT,
            "Replica",
            "SampleBTIfCaseManager",
        ]
        gate = received_stages(tree)[-1]
        assert isinstance(gate, CaseManagerGate)
        assert gate.gated_branch is manager

    def test_several_manager_effects_share_one_gate(self) -> None:
        first, second = _Emitter("First"), _Emitter("Second")
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[],
            manager_effects=[first, second],
            manager_case_id=CASE_ID,
            manager_gate_name="EmitIfCaseManager",
        )

        gate = received_stages(tree)[-1]
        assert isinstance(gate, CaseManagerGate)
        assert gate.name == "EmitIfCaseManager"
        assert list(gate.gated_branch.children) == [first, second]
        assert gate.gated_branch.name == "EmitIfCaseManagerBody"

    def test_the_manager_body_takes_its_own_name(self) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[],
            manager_effects=[_Emitter("First"), _Emitter("Second")],
            manager_case_id=CASE_ID,
            manager_gate_name="EmitIfCaseManager",
            manager_body_name="EmitEffects",
        )

        gate = received_stages(tree)[-1]
        assert isinstance(gate, CaseManagerGate)
        assert gate.gated_branch.name == "EmitEffects"

    @pytest.mark.spec("CLP-07-015")
    def test_the_commit_and_every_effect_run_as_one_act(self) -> None:
        """By default the act's own commit, the replica effects and the
        gated manager effects sit in one ``ActTransaction`` (ADR-0151)."""
        replica = _effect("ReplicaEffect")
        first, second = _Emitter("First"), _Emitter("Second")
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[],
            replica_effects=[replica],
            manager_effects=[first, second],
            manager_case_id=CASE_ID,
            manager_gate_name="EmitIfCaseManager",
        )

        act = tree.children[-1]
        assert isinstance(act, ActTransaction)
        assert act.name == "SampleBTAct"
        commit, effect, gate = act.children
        assert commit.name == COMMIT
        assert effect is replica
        assert isinstance(gate, CaseManagerGate)
        assert gate.gated_branch.name == "EmitIfCaseManagerBody"
        assert list(gate.gated_branch.children) == [first, second]
        assert not any(
            isinstance(n, ActTransaction) for n in gate.iterate()
        ), "the act block is the one transaction"
        # The stage order opens the block in place.
        assert received_stages(tree)[-3:] == [commit, effect, gate]

    def test_a_tree_without_a_commit_has_no_act_block(self) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=None,
            precondition_guards=[],
            manager_effects=[_Emitter()],
            manager_case_id=CASE_ID,
        )

        assert not any(isinstance(n, ActTransaction) for n in tree.iterate())

    @pytest.mark.spec("CLP-07-015")
    def test_a_registered_one_act_exemption_runs_the_commit_outside_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vultron.core.behaviors import act_transaction

        exemption = OneActExemption(name="test-exemption", reason="a test")
        monkeypatch.setattr(
            act_transaction,
            "ONE_ACT_EXEMPTIONS",
            {exemption.name: exemption},
        )
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[],
            replica_effects=[_effect("ReplicaEffect")],
            one_act_exemption=exemption,
        )

        assert not any(isinstance(n, ActTransaction) for n in tree.iterate())
        assert _names(tree)[-2:] == [COMMIT, "ReplicaEffect"]

    @pytest.mark.spec("CLP-07-015")
    def test_an_unregistered_one_act_exemption_is_refused(self) -> None:
        with pytest.raises(VultronWiringError, match="ONE_ACT_EXEMPTIONS"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                one_act_exemption=OneActExemption(
                    name="unregistered", reason="no decision records it"
                ),
            )

    @pytest.mark.spec("CLP-07-015")
    def test_a_one_act_exemption_without_a_commit_is_a_wiring_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vultron.core.behaviors import act_transaction

        exemption = OneActExemption(name="test-exemption", reason="a test")
        monkeypatch.setattr(
            act_transaction,
            "ONE_ACT_EXEMPTIONS",
            {exemption.name: exemption},
        )
        with pytest.raises(VultronWiringError, match="commits to no case"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=None,
                precondition_guards=[],
                manager_effects=[_Emitter()],
                manager_case_id=CASE_ID,
                one_act_exemption=exemption,
            )

    def test_the_gate_takes_its_own_case_id_when_the_commit_is_omitted(
        self,
    ) -> None:
        from vultron.core.behaviors.case.nodes.conditions import (
            CheckIsCaseManagerNode,
        )

        tree = create_receive_activity_tree(
            name="NoCommitBT",
            case_id=None,
            precondition_guards=[],
            manager_effects=[_Emitter()],
            manager_case_id=CASE_ID,
        )

        assert COMMIT not in _names(tree)
        gate = received_stages(tree)[-1]
        assert isinstance(gate, CaseManagerGate)
        checks = [
            n for n in gate.iterate() if isinstance(n, CheckIsCaseManagerNode)
        ]
        assert [c._case_id for c in checks] == [CASE_ID]

    def test_manager_effects_without_a_case_to_gate_on_are_refused(
        self,
    ) -> None:
        with pytest.raises(VultronWiringError, match="manager_case_id"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                manager_effects=[_Emitter()],
            )

    @pytest.mark.parametrize(
        "gate_argument",
        [
            {"manager_case_id": CASE_ID},
            {"manager_gate_name": "EmitIfCaseManager"},
            {"manager_body_name": "EmitEffects"},
            {"manager_case_may_be_absent": True},
        ],
    )
    def test_gate_arguments_without_manager_effects_are_refused(
        self, gate_argument: dict[str, object]
    ) -> None:
        with pytest.raises(VultronWiringError, match="only with"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                replica_effects=[_effect()],
                **gate_argument,  # type: ignore[arg-type]
            )

    def test_effect_nodes_is_no_longer_a_parameter(self) -> None:
        """``effect_nodes`` was retired in #4307 (BT-17-008)."""
        with pytest.raises(TypeError):
            create_receive_activity_tree(
                name="LegacyBT",
                case_id=CASE_ID,
                precondition_guards=[],
                effect_nodes=[_Emitter("LegacyEmit")],  # type: ignore[call-arg]
            )


class TestReplicaEmitRefusal:
    def test_an_ungated_emitter_in_replica_effects_is_refused(self) -> None:
        with pytest.raises(VultronWiringError, match="_Emitter"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                replica_effects=[_effect(), _Emitter()],
            )

    def test_an_emitter_nested_in_a_composite_is_refused(self) -> None:
        nested = py_trees.composites.Selector(
            name="MaybeEmit",
            memory=False,
            children=[
                py_trees.decorators.Inverter(name="Skip", child=_Emitter())
            ],
        )
        with pytest.raises(VultronWiringError, match="_Emitter"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                replica_effects=[nested],
            )

    def test_an_emitter_inside_a_case_manager_gate_is_accepted(
        self,
    ) -> None:
        gated = create_case_manager_gated_tree(
            name="SharedGate", case_id=CASE_ID, children=[_Emitter()]
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[],
            replica_effects=[gated],
        )

        assert received_stages(tree)[-1] is gated

    def test_a_non_emitting_replica_effect_needs_no_exemption(self) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[],
            replica_effects=[_effect("Write")],
        )

        assert _names(tree)[-1] == "Write"


class TestNamedExemption:
    def test_a_registered_exemption_admits_the_emitters_it_covers(
        self,
    ) -> None:
        emit = _role_reject_emit()

        tree = create_receive_activity_tree(
            name="RoleOfferBT",
            case_id=CASE_ID,
            precondition_guards=[],
            replica_effects=[emit],
            replica_emit_exemption=OFFER_ROLE,
        )

        assert received_stages(tree)[-1] is emit

    def test_an_exemption_does_not_admit_an_emitter_it_does_not_cover(
        self,
    ) -> None:
        with pytest.raises(VultronWiringError, match="_Emitter"):
            create_receive_activity_tree(
                name="RoleOfferBT",
                case_id=CASE_ID,
                precondition_guards=[],
                replica_effects=[_role_reject_emit(), _Emitter()],
                replica_emit_exemption=OFFER_ROLE,
            )

    def test_an_unregistered_exemption_is_refused(self) -> None:
        homemade = ReplicaEmitExemption(
            name="homemade",
            reason="not a recorded decision",
            covers=frozenset({"_Emitter"}),
        )
        with pytest.raises(VultronWiringError, match="not registered"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                replica_effects=[_Emitter()],
                replica_emit_exemption=homemade,
            )

    def test_a_stale_exemption_that_covers_nothing_is_refused(self) -> None:
        with pytest.raises(VultronWiringError, match="covers none"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                replica_effects=[_effect()],
                replica_emit_exemption=OFFER_ROLE,
            )

    def test_an_exemption_needs_a_reason(self) -> None:
        with pytest.raises(ValueError):
            ReplicaEmitExemption(name="x", reason="", covers=frozenset())


def test_ungated_emitters_skips_only_the_case_manager_gate() -> None:
    inside = _Emitter("Inside")
    outside = _Emitter("Outside")
    roots: list[py_trees.behaviour.Behaviour] = [
        create_case_manager_gated_tree(
            name="Gate", case_id=CASE_ID, children=[inside]
        ),
        py_trees.composites.Sequence(
            name="Plain", memory=False, children=[outside]
        ),
    ]

    assert ungated_emitters(roots) == [outside]


def test_ungated_nodes_walks_the_replica_gate_but_not_the_manager_gate() -> (
    None
):
    """The RSH-08-003 walk: only the CASE_MANAGER gate hides a write."""
    gated = _Writer("Gated")
    replica = _Writer("ReplicaOnly")
    bare = _Writer("Bare")
    roots: list[py_trees.behaviour.Behaviour] = [
        create_case_manager_gated_tree(
            name="Gate", case_id=CASE_ID, children=[gated]
        ),
        create_participant_replica_gated_tree(
            name="ReplicaGate", case_id=CASE_ID, children=[replica]
        ),
        py_trees.composites.Sequence(
            name="Plain", memory=False, children=[bare, _Emitter()]
        ),
    ]

    assert ungated_nodes(roots, StateWriteCapable) == [replica, bare]


class TestRefusalEffects:
    """The factory owns the refusal-effects stage (CLP-10-022)."""

    @pytest.mark.spec("CLP-10-022")
    def test_refusal_effects_wrap_the_guards_ahead_of_the_commit(
        self,
    ) -> None:
        from vultron.core.behaviors.case.nodes.refusal_stage import (
            PreconditionGuardStage,
        )

        guard = _effect("Guard")
        note = _Emitter("RefusalNote")
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            sender_rule=SenderRule.in_case(SenderEntitlementKind.CASE_MANAGER),
            sender_context=SenderCheckContext(
                sender_id="https://example.org/actors/sender", case_id=CASE_ID
            ),
            precondition_guards=[guard],
            replica_effects=[_effect("Replica")],
            refusal_effects=[note],
        )

        assert _names(tree)[1:] == [
            POST_CLOSE,
            ADDRESSEE,
            "SenderIsCaseManagerNode",
            POSITION_GATE,
            CLOCK_GATE,
            "PreconditionGuardStage",
            COMMIT,
            "Replica",
        ]
        stage = tree.children[6]
        assert isinstance(stage, PreconditionGuardStage)
        assert list(stage.guards.children) == [guard]
        gates = [
            n
            for n in stage.refusal.iterate()
            if isinstance(n, CaseManagerGate)
        ]
        assert len(gates) == 1
        assert gates[0].name == "SampleBTRefusalIfCaseManager"
        # The refusal notice first, then the tree's own effect, each
        # best-effort on its own (CLP-02-005, CLP-10-022).
        wrapped = list(gates[0].gated_branch.children)
        assert [type(w) for w in wrapped] == [RefusalEffectsBestEffort] * 2
        assert isinstance(wrapped[0].children[0], EmitRefusalNoticeNode)
        assert wrapped[1].children[0] is note

    @pytest.mark.spec("BT-17-008")
    @pytest.mark.spec("CLP-10-022")
    def test_refusal_effects_are_gated_on_the_case_manager(self) -> None:
        from vultron.core.behaviors.case.nodes.conditions import (
            CheckIsCaseManagerNode,
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
            refusal_effects=[_Emitter()],
        )

        assert ungated_emitters([tree]) == []
        stage = tree.children[3]
        checks = [
            n for n in stage.iterate() if isinstance(n, CheckIsCaseManagerNode)
        ]
        assert [(c._case_id, c._case_may_be_absent) for c in checks] == [
            (CASE_ID, True)
        ]

    @pytest.mark.spec("CLP-10-022")
    def test_a_refusal_effect_that_does_not_emit_is_refused(self) -> None:
        with pytest.raises(VultronWiringError, match="not emit-capable"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[_effect("Guard")],
                refusal_effects=[_effect("Plain")],
            )

    @pytest.mark.spec("CLP-10-022")
    def test_a_refusal_effect_that_writes_state_is_refused(self) -> None:
        with pytest.raises(VultronWiringError, match="_EmittingWriter"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[_effect("Guard")],
                refusal_effects=[_EmittingWriter()],
            )

    @pytest.mark.spec("CLP-10-022")
    def test_a_state_writer_nested_in_a_refusal_effect_is_refused(
        self,
    ) -> None:
        nested = _EmittingSequence(
            name="EmitThenWrite",
            memory=False,
            children=[_Emitter(), _Writer("NestedWriter")],
        )
        with pytest.raises(
            VultronWiringError, match=r"state writers: \['_Writer'\]"
        ):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[_effect("Guard")],
                refusal_effects=[nested],
            )

    @pytest.mark.spec("CLP-10-022")
    def test_a_plain_composite_holding_an_emitter_is_refused(self) -> None:
        wrapper = py_trees.composites.Sequence(
            name="Wrapper", memory=False, children=[_Emitter()]
        )
        with pytest.raises(
            VultronWiringError, match=r"not emit-capable: \['Sequence'\]"
        ):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[_effect("Guard")],
                refusal_effects=[wrapper],
            )

    def test_refusal_effects_combine_with_replica_effects(self) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
            replica_effects=[_effect("ReplicaEffect")],
            refusal_effects=[_Emitter()],
        )

        assert _names(tree)[1:] == [
            POST_CLOSE,
            ADDRESSEE,
            "PreconditionGuardStage",
            COMMIT,
            "ReplicaEffect",
        ]

    def test_without_a_commit_or_refusal_effects_the_guards_stay_top_level(
        self,
    ) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=None,
            precondition_guards=[_effect("Guard")],
        )

        assert _names(tree)[1:] == [POST_CLOSE, ADDRESSEE, "Guard"]


class TestRefusalNotice:
    """The factory adds the refusal notice itself (CLP-02-005, CLP-05-001)."""

    @staticmethod
    def _notices(tree: py_trees.behaviour.Behaviour) -> list:
        return [
            n for n in tree.iterate() if isinstance(n, EmitRefusalNoticeNode)
        ]

    @pytest.mark.spec("CLP-02-005")
    @pytest.mark.spec("CLP-05-001")
    def test_a_guarded_commit_tree_answers_a_refusal_with_the_notice(
        self,
    ) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
        )

        assert _names(tree)[1:] == [POST_CLOSE, ADDRESSEE, STAGE, COMMIT]
        (notice,) = self._notices(tree)
        assert notice._case_id == CASE_ID
        assert tree.refusal_notice_exemption is None

    @pytest.mark.spec("CLP-02-005")
    @pytest.mark.parametrize(
        ("case_id", "guards"),
        [(None, [_effect("Guard")]), (CASE_ID, [])],
        ids=["no-commit", "no-guards"],
    )
    def test_a_tree_that_refuses_nothing_before_a_commit_sends_none(
        self, case_id: str | None, guards: list
    ) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT", case_id=case_id, precondition_guards=guards
        )

        assert self._notices(tree) == []

    @pytest.mark.spec("CLP-02-005")
    def test_a_registered_exemption_drops_the_notice_and_is_recorded(
        self,
    ) -> None:
        from vultron.core.behaviors.case.nodes.refusal_notice import (
            OWNER_CLOSE_DECLINE,
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
            refusal_notice_exemption=OWNER_CLOSE_DECLINE,
        )

        assert self._notices(tree) == []
        assert _names(tree)[1:] == [POST_CLOSE, ADDRESSEE, "Guard", COMMIT]
        assert tree.refusal_notice_exemption is OWNER_CLOSE_DECLINE

    @pytest.mark.spec("CLP-02-005")
    def test_an_unregistered_exemption_is_refused(self) -> None:
        from vultron.core.behaviors.case.nodes.refusal_notice import (
            RefusalNoticeExemption,
        )

        homemade = RefusalNoticeExemption(name="homemade", reason="no record")
        with pytest.raises(VultronWiringError, match="not registered"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[_effect("Guard")],
                refusal_notice_exemption=homemade,
            )

    @pytest.mark.spec("CLP-02-005")
    @pytest.mark.parametrize(
        ("case_id", "guards"),
        [(None, [_effect("Guard")]), (CASE_ID, [])],
        ids=["no-commit", "no-guards"],
    )
    def test_an_exemption_that_exempts_nothing_is_refused(
        self, case_id: str | None, guards: list
    ) -> None:
        from vultron.core.behaviors.case.nodes.refusal_notice import (
            OWNER_CLOSE_DECLINE,
        )

        with pytest.raises(VultronWiringError, match="exempts nothing"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=case_id,
                precondition_guards=guards,
                refusal_notice_exemption=OWNER_CLOSE_DECLINE,
            )

    @pytest.mark.spec("CLP-02-005")
    @pytest.mark.spec("CLP-10-026")
    def test_a_diverting_tree_takes_the_notice(self) -> None:
        """Its guards' refusals are answered; the refusal stage skips the
        notice for a diverted delivery, which its diversion answered."""
        from vultron.core.behaviors.case.nodes.diversion_stage import (
            Diversion,
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[
                Diversion(name="D", condition=_effect("Condition"))
            ],
        )

        assert len(self._notices(tree)) == 1

    def test_an_exemption_needs_a_reason(self) -> None:
        from vultron.core.behaviors.case.nodes.refusal_notice import (
            RefusalNoticeExemption,
        )

        with pytest.raises(ValueError):
            RefusalNoticeExemption(name="x", reason="")


class TestPostCloseStage:
    """The factory places the post-close write boundary (CM-23-013)."""

    @pytest.mark.spec("CM-23-013")
    def test_every_tree_gets_the_guard_right_after_intake(self) -> None:
        from vultron.core.behaviors.case.nodes.post_close import (
            CaseOpenToExternalWritesNode,
        )

        tree = create_receive_activity_tree(
            name="SampleBT", case_id=None, precondition_guards=[]
        )

        assert isinstance(tree.children[1], CaseOpenToExternalWritesNode)

    @pytest.mark.spec("CM-23-013")
    def test_the_guard_judges_the_commit_case_else_the_manager_case(
        self,
    ) -> None:
        from vultron.core.behaviors.case.nodes.post_close import (
            CaseOpenToExternalWritesNode,
        )

        committed = create_receive_activity_tree(
            name="SampleBT", case_id=CASE_ID, precondition_guards=[]
        )
        gated = create_receive_activity_tree(
            name="SampleBT",
            case_id=None,
            precondition_guards=[],
            manager_effects=[_Emitter()],
            manager_case_id=CASE_ID,
        )

        for tree in (committed, gated):
            guard = tree.children[1]
            assert isinstance(guard, CaseOpenToExternalWritesNode)
            assert guard._case_id == CASE_ID

    @pytest.mark.spec("CM-23-013")
    def test_an_exempt_tree_carries_no_guard(self) -> None:
        from vultron.core.behaviors.case.nodes.post_close import (
            PostCloseExemption,
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
            post_close_exemption=PostCloseExemption.LEDGER_RESYNC,
        )

        assert _names(tree)[1:] == [ADDRESSEE, STAGE, COMMIT]

    @pytest.mark.spec("CM-23-013")
    def test_a_reply_wraps_the_guard_in_a_gated_refusal_stage(self) -> None:
        from vultron.core.behaviors.case.nodes.post_close import (
            CaseOpenToExternalWritesNode,
        )
        from vultron.core.behaviors.case.nodes.refusal_stage import (
            PreconditionGuardStage,
        )

        reply = _Emitter("LateReply")
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
            post_close_reply=[reply],
        )

        assert _names(tree)[1:] == [
            "PostCloseStage",
            ADDRESSEE,
            STAGE,
            COMMIT,
        ]
        stage = tree.children[1]
        assert isinstance(stage, PreconditionGuardStage)
        assert [type(g) for g in stage.guards.children] == [
            CaseOpenToExternalWritesNode
        ]
        assert ungated_emitters([tree]) == []
        gates = [
            n
            for n in stage.refusal.iterate()
            if isinstance(n, CaseManagerGate)
        ]
        assert [g.gated_branch.children for g in gates] == [[reply]]

    @pytest.mark.spec("CM-23-013")
    def test_a_reply_on_an_exempt_tree_is_refused(self) -> None:
        from vultron.core.behaviors.case.nodes.post_close import (
            PostCloseExemption,
        )

        with pytest.raises(VultronWiringError, match="exempt"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                post_close_exemption=PostCloseExemption.LEDGER_RESYNC,
                post_close_reply=[_Emitter()],
            )

    @pytest.mark.spec("CM-23-013")
    def test_a_reply_that_writes_state_is_refused(self) -> None:
        with pytest.raises(VultronWiringError, match="post_close_reply"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                post_close_reply=[_EmittingWriter()],
            )


class _Counting(py_trees.behaviour.Behaviour):
    """Records that it ran; succeeds."""

    def __init__(self, name: str = "Counting") -> None:
        super().__init__(name=name)
        self.ran = 0

    def update(self) -> Status:
        self.ran += 1
        return Status.SUCCESS


class _Refused(py_trees.behaviour.Behaviour):
    """A clock decision whose commit the ledger refused."""

    def update(self) -> Status:
        self.feedback_message = "ledger refused the expiry entry"
        return Status.FAILURE


class _Crashing(py_trees.behaviour.Behaviour):
    """A clock decision with an internal error."""

    def update(self) -> Status:
        raise KeyError("bug")


def _sender_args(case_id: str | None = CASE_ID) -> dict:
    return {
        "sender_rule": SenderRule.in_case(SenderEntitlementKind.CASE_MANAGER),
        "sender_context": SenderCheckContext(
            sender_id="https://example.org/actors/sender", case_id=case_id
        ),
    }


class TestClockDecisionStage:
    """The factory owns the clock-decision stage (CLP-10-025, ADR-0135)."""

    @pytest.mark.spec("CLP-10-025")
    @pytest.mark.spec("CLP-10-010")
    def test_decisions_run_after_the_door_guards_and_before_the_guards(
        self,
    ) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
            clock_decisions=[_effect("Expiry")],
            replica_effects=[_effect("Replica")],
            **_sender_args(),
        )

        assert _names(tree)[1:] == [
            POST_CLOSE,
            ADDRESSEE,
            "SenderIsCaseManagerNode",
            POSITION_GATE,
            "ClockDecisionsIfCaseManager",
            STAGE,
            COMMIT,
            "Replica",
        ]

    @pytest.mark.spec("CLP-10-025")
    def test_decisions_precede_the_refusal_stage(self) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
            clock_decisions=[_effect("Expiry")],
            refusal_effects=[_Emitter()],
            **_sender_args(),
        )

        assert _names(tree)[1:] == [
            POST_CLOSE,
            ADDRESSEE,
            "SenderIsCaseManagerNode",
            POSITION_GATE,
            "ClockDecisionsIfCaseManager",
            "PreconditionGuardStage",
            COMMIT,
        ]

    @pytest.mark.spec("CLP-10-025")
    @pytest.mark.spec("BT-17-001")
    def test_decisions_are_gated_on_the_case_manager(self) -> None:
        from vultron.core.behaviors.case.nodes.clock_decision_stage import (
            ClockDecision,
            ClockDecisionStage,
        )
        from vultron.core.behaviors.case.nodes.conditions import (
            CheckIsCaseManagerNode,
        )

        first, second = _effect("First"), _effect("Second")
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[],
            clock_decisions=[first, second],
            **_sender_args(),
        )

        gate = tree.children[5]
        assert isinstance(gate, CaseManagerGate)
        stage = gate.gated_branch
        assert isinstance(stage, ClockDecisionStage)
        assert all(isinstance(c, ClockDecision) for c in stage.children)
        # The case-wide end-time decision first, then the tree's own.
        assert [d.name for d in stage.decisions[:1]] == [END_TIME]
        assert stage.decisions[1:] == [first, second]
        checks = [
            n
            for n in gate.children[0].iterate()
            if isinstance(n, CheckIsCaseManagerNode)
        ]
        assert [(c._case_id, c._case_may_be_absent) for c in checks] == [
            (CASE_ID, True)
        ]

    @pytest.mark.spec("CLP-10-025")
    def test_the_gate_takes_the_manager_case_when_the_commit_is_omitted(
        self,
    ) -> None:
        from vultron.core.behaviors.case.nodes.conditions import (
            CheckIsCaseManagerNode,
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=None,
            precondition_guards=[],
            clock_decisions=[_effect("Expiry")],
            manager_effects=[_Emitter()],
            manager_case_id=CASE_ID,
            # The sender is checked on the case the CASE_MANAGER writes for.
            **_sender_args(case_id=CASE_ID),
        )

        gate = next(c for c in tree.children if c.name == CLOCK_GATE)
        checks = [
            n
            for n in gate.children[0].iterate()
            if isinstance(n, CheckIsCaseManagerNode)
        ]
        assert [c._case_id for c in checks] == [CASE_ID]

    @pytest.mark.spec("HP-01-008")
    def test_a_tree_with_no_commit_checks_its_sender_on_the_manager_case(
        self,
    ) -> None:
        """A tree that commits nothing at its own level (the close-case tree)
        still checks its sender on the case whose CASE_MANAGER it writes
        for; a context naming no case is a wiring fault there."""
        with pytest.raises(VultronWiringError, match="HP-01-008"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=None,
                precondition_guards=[],
                manager_effects=[_Emitter()],
                manager_case_id=CASE_ID,
                **_sender_args(case_id=None),
            )

    @pytest.mark.spec("CLP-10-025")
    @pytest.mark.spec("EMB-13-003")
    def test_a_case_tree_with_a_sender_guard_takes_the_end_time_decision(
        self,
    ) -> None:
        """With no clock decisions of its own, a case tree with both door
        guards still takes the case-wide end-time check (EMB-13-003)."""
        from vultron.core.behaviors.case.nodes.clock_decision_stage import (
            ClockDecisionStage,
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
            **_sender_args(),
        )

        assert _names(tree)[1:] == [
            POST_CLOSE,
            ADDRESSEE,
            "SenderIsCaseManagerNode",
            POSITION_GATE,
            CLOCK_GATE,
            STAGE,
            COMMIT,
        ]
        (stage,) = [
            n for n in tree.iterate() if isinstance(n, ClockDecisionStage)
        ]
        assert [d.name for d in stage.decisions] == [END_TIME]

    @pytest.mark.spec("CLP-10-025")
    @pytest.mark.spec("HP-01-006")
    def test_a_tree_without_a_sender_guard_takes_no_case_decision(
        self,
    ) -> None:
        """A sender with no standing never makes the CASE_MANAGER write, so
        a tree with no sender guard takes no case-wide decision."""
        tree = create_receive_activity_tree(
            name="SampleBT", case_id=CASE_ID, precondition_guards=[]
        )

        assert CLOCK_GATE not in _names(tree)

    @pytest.mark.spec("CLP-10-025")
    @pytest.mark.spec("CM-23-013")
    def test_a_post_close_exempt_tree_takes_no_case_decision(self) -> None:
        from vultron.core.behaviors.case.nodes.post_close import (
            PostCloseExemption,
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[],
            post_close_exemption=PostCloseExemption.LEDGER_RESYNC,
            **_sender_args(),
        )

        assert CLOCK_GATE not in _names(tree)

    @pytest.mark.spec("CLP-10-025")
    def test_a_tree_naming_no_case_takes_no_case_decision(self) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=None,
            precondition_guards=[],
            **_sender_args(case_id=None),
        )

        assert CLOCK_GATE not in _names(tree)

    @pytest.mark.spec("CLP-10-025")
    def test_decisions_without_a_case_are_refused(self) -> None:
        with pytest.raises(VultronWiringError, match="clock_decisions need"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=None,
                precondition_guards=[],
                clock_decisions=[_effect("Expiry")],
            )

    @pytest.mark.spec("CLP-10-025")
    def test_a_decision_holding_the_activitys_commit_is_refused(self) -> None:
        from vultron.core.behaviors.case.receive_activity_tree import (
            create_guarded_commit_case_ledger_entry_tree,
        )

        with pytest.raises(VultronWiringError, match="never the received"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                clock_decisions=[
                    create_guarded_commit_case_ledger_entry_tree(CASE_ID)
                ],
                **_sender_args(),
            )

    @pytest.mark.spec("CLP-10-025")
    @pytest.mark.spec("HP-01-006")
    def test_decisions_without_a_sender_guard_are_refused(self) -> None:
        with pytest.raises(VultronWiringError, match="need a sender_rule"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                clock_decisions=[_effect("Expiry")],
            )

    @pytest.mark.spec("CLP-10-025")
    @pytest.mark.spec("CM-23-013")
    def test_decisions_on_a_post_close_exempt_tree_are_refused(self) -> None:
        from vultron.core.behaviors.case.nodes.post_close import (
            PostCloseExemption,
        )

        with pytest.raises(VultronWiringError, match="post-close boundary"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                clock_decisions=[_effect("Expiry")],
                post_close_exemption=PostCloseExemption.LEDGER_RESYNC,
                **_sender_args(),
            )

    def test_without_decisions_there_is_no_stage(self) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT", case_id=CASE_ID, precondition_guards=[]
        )

        assert "ClockDecisionsIfCaseManager" not in _names(tree)


class TestClockDecisionOutcomes:
    """What each clock-decision outcome does to the tree (CLP-10-025)."""

    @staticmethod
    def _run(datalayer, actor_id, decisions):
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.nodes.clock_decision_stage import (
            ClockDecisionStage,
        )

        after = _Counting("NextStage")
        root = py_trees.composites.Sequence(
            name="Root",
            memory=False,
            children=[
                ClockDecisionStage(name="ClockDecisions", decisions=decisions),
                after,
            ],
        )
        result = BTBridge(datalayer=datalayer).execute_with_setup(
            tree=root, actor_id=actor_id
        )
        return result, after

    @pytest.mark.spec("CLP-10-025")
    def test_a_decision_that_records_nothing_succeeds(
        self, datalayer, actor_id
    ) -> None:
        result, after = self._run(datalayer, actor_id, [_effect("NotDue")])

        assert result.status is Status.SUCCESS
        assert after.ran == 1

    @pytest.mark.spec("CLP-10-025")
    def test_a_refused_commit_warns_and_the_tree_continues(
        self, datalayer, actor_id, caplog
    ) -> None:
        second = _Counting("SecondDecision")

        with caplog.at_level("WARNING"):
            result, after = self._run(
                datalayer, actor_id, [_Refused(name="Expiry"), second]
            )

        assert result.status is Status.SUCCESS
        assert second.ran == 1 and after.ran == 1
        warnings = [
            r.getMessage() for r in caplog.records if r.levelname == "WARNING"
        ]
        assert any(
            "Expiry" in m and "ledger refused the expiry entry" in m
            for m in warnings
        )

    @pytest.mark.spec("CLP-10-025")
    def test_an_internal_error_ends_the_tree_as_an_internal_error(
        self, datalayer, actor_id
    ) -> None:
        result, after = self._run(
            datalayer, actor_id, [_Crashing(name="Expiry")]
        )

        assert result.status is Status.FAILURE
        assert result.internal_error is True
        assert after.ran == 0


class TestClosedSenderStage:
    """The closed-sender door guard (CM-23-018) is placed by the factory."""

    @pytest.mark.spec("CM-23-018")
    def test_it_follows_the_post_close_guard_and_precedes_the_sender_guard(
        self,
    ) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[],
            closed_sender=ClosedSenderCheck(sender_id="https://example.org/a"),
            sender_rule=SenderRule.in_case(SenderEntitlementKind.PARTICIPANT),
            sender_context=SenderCheckContext(
                sender_id="https://example.org/a", case_id=CASE_ID
            ),
        )
        names = [child.name for child in tree.children]
        door = names.index("SenderClosureNotRecordedNode")
        assert names.index(POST_CLOSE) < door
        assert tree.children[door] in tree.door_guards
        assert isinstance(tree.children[door + 1], SenderIsParticipantNode)

    @pytest.mark.spec("CM-23-018")
    def test_a_tree_with_no_case_is_refused(self) -> None:
        with pytest.raises(VultronWiringError, match="closed_sender"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=None,
                precondition_guards=[],
                closed_sender=ClosedSenderCheck(
                    sender_id="https://example.org/a"
                ),
            )


class TestLedgerPositionStage:
    """The factory answers the sender's stamped position (SYNC-18-007)."""

    @pytest.mark.spec("SYNC-18-007")
    @pytest.mark.spec("CLP-10-005")
    def test_a_tree_naming_its_sender_and_case_answers_the_position(
        self,
    ) -> None:
        from vultron.core.behaviors.sync.nodes.ledger_position import (
            ClassifyLedgerPositionNode,
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=None,
            precondition_guards=[],
            **_sender_args(),
        )

        gate = next(c for c in tree.children if c.name == POSITION_GATE)
        assert isinstance(gate, CaseManagerGate)
        assert gate not in tree.door_guards
        standings = [
            n
            for n in gate.iterate()
            if isinstance(n, ClassifyLedgerPositionNode)
        ]
        assert {(n.case_id, n.sender_id) for n in standings} == {
            (CASE_ID, "https://example.org/actors/sender")
        }

    @pytest.mark.spec("SYNC-18-007")
    def test_a_tree_with_no_sender_guard_answers_nothing(self) -> None:
        """A subtree whose enclosing tree runs the guard (the close arm)
        would answer the position a second time."""
        tree = create_receive_activity_tree(
            name="SampleBT", case_id=CASE_ID, precondition_guards=[]
        )

        assert POSITION_GATE not in _names(tree)

    @pytest.mark.spec("SYNC-18-007")
    def test_a_tree_whose_sender_context_names_no_case_answers_nothing(
        self,
    ) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=None,
            precondition_guards=[],
            **_sender_args(case_id=None),
        )

        assert POSITION_GATE not in _names(tree)

    @pytest.mark.spec("SYNC-18-007")
    @pytest.mark.spec("SYNC-17-005")
    def test_a_registered_exemption_leaves_the_answer_out(self) -> None:
        from vultron.core.behaviors.sync.nodes.ledger_position import (
            STATED_POSITION_ANSWERED_BY_TREE,
        )

        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=None,
            precondition_guards=[],
            ledger_position_exemption=STATED_POSITION_ANSWERED_BY_TREE,
            **_sender_args(),
        )

        assert POSITION_GATE not in _names(tree)

    @pytest.mark.spec("SYNC-18-007")
    def test_an_unregistered_exemption_is_a_wiring_fault(self) -> None:
        from vultron.core.behaviors.sync.nodes.ledger_position import (
            LedgerPositionExemption,
        )

        with pytest.raises(VultronWiringError, match="LEDGER_POSITION"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=None,
                precondition_guards=[],
                ledger_position_exemption=LedgerPositionExemption(
                    name="ad-hoc", reason="not a recorded decision"
                ),
                **_sender_args(),
            )

    @pytest.mark.spec("SYNC-18-007")
    @pytest.mark.spec("SYNC-18-001")
    def test_a_ledger_activity_tree_answers_no_position(self) -> None:
        """A tree whose sender and case come from the received ledger
        activity (``Reject(CaseLedgerEntry)``) states no position to answer:
        its own tree answers the one it reports (SYNC-03-002)."""
        from vultron.core.behaviors.sync.reject_tree import (
            create_reject_log_entry_tree,
        )
        from vultron.core.use_cases.received.sync import (
            RejectLedgerEntryReceivedUseCase,
        )

        tree = create_reject_log_entry_tree(
            CASE_ID,
            sender_rule=RejectLedgerEntryReceivedUseCase.sender_entitlement,
        )

        assert POSITION_GATE not in _names(tree)
