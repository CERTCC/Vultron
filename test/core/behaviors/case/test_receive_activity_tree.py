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

from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
    ungated_emitters,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.replica_emit_exemptions import (
    ACK_ECHO,
    ReplicaEmitExemption,
)
from vultron.core.behaviors.report.nodes.emit import EmitAckReportActivity
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/case-factory-gate-001"
COMMIT = "GuardedCommitCaseLedgerEntryBT"


class _Emitter(EmitCapable, py_trees.behaviour.Behaviour):
    """A stand-in emit node: carries the marker, emits nothing."""

    def __init__(self, name: str = "Emitter") -> None:
        super().__init__(name=name)

    def update(self) -> Status:
        return Status.SUCCESS


def _effect(name: str = "Effect") -> py_trees.behaviour.Behaviour:
    return py_trees.behaviours.Success(name=name)


def _ack_emit() -> EmitAckReportActivity:
    return EmitAckReportActivity(offer_id="urn:uuid:offer", report_id="r")


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

    def test_legacy_effect_nodes_cannot_be_mixed_with_the_new_kinds(
        self,
    ) -> None:
        with pytest.raises(VultronWiringError, match="effect_nodes"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                effect_nodes=[_effect()],
                replica_effects=[_effect()],
            )

    def test_an_exemption_cannot_be_mixed_with_legacy_effect_nodes(
        self,
    ) -> None:
        with pytest.raises(VultronWiringError, match="effect_nodes"):
            create_receive_activity_tree(
                name="SampleBT",
                case_id=CASE_ID,
                precondition_guards=[],
                effect_nodes=[_ack_emit()],
                replica_emit_exemption=ACK_ECHO,
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

    def test_legacy_effect_nodes_still_build_ungated(self) -> None:
        tree = create_receive_activity_tree(
            name="LegacyBT",
            case_id=CASE_ID,
            precondition_guards=[],
            effect_nodes=[_Emitter("LegacyEmit")],
        )

        assert _names(tree)[1:] == [COMMIT, "LegacyEmit"]


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
        emit = _ack_emit()

        tree = create_receive_activity_tree(
            name="AckBT",
            case_id=CASE_ID,
            precondition_guards=[],
            replica_effects=[emit],
            replica_emit_exemption=ACK_ECHO,
        )

        assert tree.children[-1] is emit

    def test_an_exemption_does_not_admit_an_emitter_it_does_not_cover(
        self,
    ) -> None:
        with pytest.raises(VultronWiringError, match="_Emitter"):
            create_receive_activity_tree(
                name="AckBT",
                case_id=CASE_ID,
                precondition_guards=[],
                replica_effects=[_ack_emit(), _Emitter()],
                replica_emit_exemption=ACK_ECHO,
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
                replica_emit_exemption=ACK_ECHO,
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
