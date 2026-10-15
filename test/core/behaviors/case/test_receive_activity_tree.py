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

from vultron.core.behaviors.case.nodes.delegation import (
    EmitRejectCaseParticipantRoleNode,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
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
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/case-factory-gate-001"
COMMIT = "GuardedCommitCaseLedgerEntryBT"
POST_CLOSE = "CaseOpenToExternalWrites"


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
    return [child.name for child in tree.children]


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
            "Guard",
            COMMIT,
            "Replica",
            "SampleBTIfCaseManager",
        ]
        gate = tree.children[-1]
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

        gate = tree.children[-1]
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

        gate = tree.children[-1]
        assert isinstance(gate, CaseManagerGate)
        assert gate.gated_branch.name == "EmitEffects"

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
        gate = tree.children[-1]
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

        assert tree.children[-1] is gated

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

        assert tree.children[-1] is emit

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
            "SenderIsCaseManagerNode",
            "PreconditionGuardStage",
            COMMIT,
            "Replica",
        ]
        stage = tree.children[3]
        assert isinstance(stage, PreconditionGuardStage)
        assert list(stage.guards.children) == [guard]
        gates = [
            n
            for n in stage.refusal.iterate()
            if isinstance(n, CaseManagerGate)
        ]
        assert len(gates) == 1
        assert gates[0].name == "SampleBTRefusalIfCaseManager"
        assert gates[0].gated_branch is note

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
        stage = tree.children[2]
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
            "PreconditionGuardStage",
            COMMIT,
            "ReplicaEffect",
        ]

    def test_without_refusal_effects_the_guards_stay_top_level(self) -> None:
        tree = create_receive_activity_tree(
            name="SampleBT",
            case_id=CASE_ID,
            precondition_guards=[_effect("Guard")],
        )

        assert _names(tree)[1:] == [POST_CLOSE, "Guard", COMMIT]


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

        assert _names(tree)[1:] == ["Guard", COMMIT]

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

        assert _names(tree)[1:] == ["PostCloseStage", "Guard", COMMIT]
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
        assert [g.gated_branch for g in gates] == [reply]

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
            "SenderIsCaseManagerNode",
            "ClockDecisionsIfCaseManager",
            "Guard",
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
            "SenderIsCaseManagerNode",
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

        gate = tree.children[3]
        assert isinstance(gate, CaseManagerGate)
        stage = gate.gated_branch
        assert isinstance(stage, ClockDecisionStage)
        assert all(isinstance(c, ClockDecision) for c in stage.children)
        assert stage.decisions == [first, second]
        checks = [
            n for n in gate.iterate() if isinstance(n, CheckIsCaseManagerNode)
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
            **_sender_args(case_id=None),
        )

        gate = next(
            c for c in tree.children if c.name == "ClockDecisionsIfCaseManager"
        )
        checks = [
            n for n in gate.iterate() if isinstance(n, CheckIsCaseManagerNode)
        ]
        assert [c._case_id for c in checks] == [CASE_ID]

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
