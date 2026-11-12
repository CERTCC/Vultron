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

"""Tests for create_embargo_response_decision_tree (EMB-15).

Verify tree structure, the absence of any approval gate ahead of
``EvaluateEmbargoProposal``, and both flows' accept/reject/counter delegation.

Covers:
  - EMB-15-001: default-accept (EvaluateEmbargoProposal → SUCCESS)
  - EMB-15-013: no approval gate; EvaluateEmbargoProposal alone decides
  - EMB-15-003: counter arm present/absent (Flow A vs Flow B)
  - EMB-15-004: reject arm always present as fallback
  - BT-18-004: factory parameter wired + deterministic default
  - BT-23-002: DETERMINISTIC bundle uses AlwaysSucceed/AlwaysFail
"""

import dataclasses

import py_trees
import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.call_out import no as call_out_no
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import make
from vultron.core.behaviors.call_out import unwrap_call_out
from vultron.core.behaviors.call_out.answer import CallOutAnswer
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EmbargoCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.embargo.response_decision_tree import (
    create_embargo_response_decision_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.demo.fuzzer.bundles.embargo import EMBARGO_STOCHASTIC
from vultron.demo.fuzzer.embargo import (
    EvaluateEmbargoProposal,
    WillingToCounterEmbargoProposal,
)
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/emb15-test"
DECIDING_ACTOR_ID = "https://example.org/actors/local-deciding-actor"


def _stub(name: str = "stub") -> py_trees.behaviour.Behaviour:
    """Return a no-op stub behaviour."""

    class _Stub(CallOutBackend):
        def answer(self) -> CallOutAnswer:
            return CallOutAnswer.yes()

    return _Stub(name=name)


def _make_tree(
    *,
    counter: bool = False,
    call_out: EmbargoCallOutBundle = EMBARGO_DETERMINISTIC,
) -> py_trees.behaviour.Behaviour:
    return create_embargo_response_decision_tree(
        case_id=CASE_ID,
        deciding_actor_id=DECIDING_ACTOR_ID,
        accept_bt=_stub("AcceptDelegate"),
        reject_bt=_stub("RejectDelegate"),
        counter_bt=_stub("CounterDelegate") if counter else None,
        call_out=call_out,
    )


# ---------------------------------------------------------------------------
# Root structure
# ---------------------------------------------------------------------------


class TestRootStructure:
    def test_returns_behaviour(self):
        tree = _make_tree()
        assert isinstance(tree, py_trees.behaviour.Behaviour)

    def test_root_name(self):
        tree = _make_tree()
        assert tree.name == "ResponseDecisionSelector"

    def test_root_is_selector(self):
        tree = _make_tree()
        assert isinstance(tree, py_trees.composites.Selector)

    def test_root_memory_false(self):
        tree = _make_tree()
        assert tree.memory is False  # type: ignore[attr-defined]

    @pytest.mark.spec("EMB-15-003")
    def test_two_arms_without_counter(self):
        """Flow B (no counter): accept + reject = 2 arms."""
        tree = _make_tree(counter=False)
        assert len(tree.children) == 2

    @pytest.mark.spec("EMB-15-003")
    def test_three_arms_with_counter(self):
        """Flow A (with counter): accept + counter + reject = 3 arms."""
        tree = _make_tree(counter=True)
        assert len(tree.children) == 3


# ---------------------------------------------------------------------------
# Accept arm (child 0)
# ---------------------------------------------------------------------------


class TestAcceptArm:
    def test_accept_arm_is_sequence(self):
        tree = _make_tree()
        accept_arm = tree.children[0]
        assert isinstance(accept_arm, py_trees.composites.Sequence)

    def test_accept_arm_memory_false(self):
        tree = _make_tree()
        assert tree.children[0].memory is False  # type: ignore[attr-defined]

    def test_accept_arm_name(self):
        tree = _make_tree()
        assert tree.children[0].name == "AcceptArm"

    @pytest.mark.spec("EMB-15-013")
    def test_accept_arm_has_two_children(self):
        """AcceptArm: EvaluateEmbargoProposal + delegate, no approval gate."""
        tree = _make_tree()
        accept_arm = tree.children[0]
        assert len(accept_arm.children) == 2

    @pytest.mark.spec("EMB-15-005")
    def test_accept_arm_first_child_is_evaluate_embargo_proposal_deterministic(
        self,
    ):
        """EMB-15-001: EvaluateEmbargoProposal defaults to AlwaysSucceed."""
        tree = _make_tree()
        evaluate_node = tree.children[0].children[0]
        assert isinstance(unwrap_call_out(evaluate_node), AlwaysSucceed)

    @pytest.mark.spec("EMB-15-013")
    def test_accept_arm_first_child_name(self):
        tree = _make_tree()
        evaluate_node = tree.children[0].children[0]
        assert evaluate_node.name == "EvaluateEmbargoProposal"

    def test_accept_arm_second_child_is_delegate(self):
        tree = _make_tree()
        delegate = tree.children[0].children[1]
        assert delegate.name == "AcceptDelegate"


# ---------------------------------------------------------------------------
# No approval gate (EMB-15-013)
# ---------------------------------------------------------------------------

_REMOVED_GATE_NAMES = {
    "AuthorizeSelector",
    "CheckIsCaseOwner",
    "CaseOwnerApprovesEmbargoResponse",
}


class TestNoApprovalGate:
    """EMB-15-013: no arm asks another actor to approve the answer."""

    @pytest.mark.spec("EMB-15-013")
    @pytest.mark.parametrize("counter", [False, True])
    def test_tree_has_no_approval_gate(self, counter: bool):
        tree = _make_tree(counter=counter)
        names = {node.name for node in tree.iterate()}
        assert names.isdisjoint(_REMOVED_GATE_NAMES)

    @pytest.mark.spec("EMB-15-013")
    def test_bundle_has_no_owner_approval_factory(self):
        field_names = {
            f.name for f in dataclasses.fields(EmbargoCallOutBundle)
        }
        assert (
            "case_owner_approves_embargo_response_factory" not in field_names
        )


# ---------------------------------------------------------------------------
# EvaluateEmbargoProposal call-out (EMB-15-001)
# ---------------------------------------------------------------------------


class TestEvaluateEmbargoProposalCallOut:
    @pytest.mark.spec("EMB-15-005")
    def test_stochastic_evaluate_is_correct_fuzzer_class(self):
        """STOCHASTIC bundle: EvaluateEmbargoProposal → fuzzer class."""
        tree = _make_tree(call_out=EMBARGO_STOCHASTIC)
        evaluate_node = tree.children[0].children[0]
        assert isinstance(
            unwrap_call_out(evaluate_node), EvaluateEmbargoProposal
        )

    @pytest.mark.spec("EMB-15-005")
    def test_custom_evaluate_factory_wired(self):
        """Custom evaluate_embargo_proposal_factory is injected."""
        called = {"flag": False}

        def custom_factory(name: str) -> py_trees.behaviour.Behaviour:
            called["flag"] = True

            class _Custom(CallOutBackend):
                def answer(self) -> CallOutAnswer:
                    return CallOutAnswer.yes()

            return _Custom(name="CustomEvaluate")

        bundle = EmbargoCallOutBundle(
            evaluate_embargo_proposal_factory=custom_factory  # type: ignore[arg-type]
        )
        tree = _make_tree(call_out=bundle)
        assert called["flag"]
        assert tree.children[0].children[0].name == "CustomEvaluate"


# ---------------------------------------------------------------------------
# Counter arm (EMB-15-003, Flow A only)
# ---------------------------------------------------------------------------


class TestCounterArm:
    @pytest.mark.spec("EMB-15-003")
    def test_counter_arm_absent_when_no_counter_bt(self):
        """Flow B: no counter_bt → only 2 arms (no CounterArm)."""
        tree = _make_tree(counter=False)
        names = [c.name for c in tree.children]
        assert "CounterArm" not in names

    @pytest.mark.spec("EMB-15-003")
    def test_counter_arm_present_when_counter_bt_supplied(self):
        """Flow A: counter_bt supplied → CounterArm is child[1]."""
        tree = _make_tree(counter=True)
        assert tree.children[1].name == "CounterArm"

    def test_counter_arm_is_sequence(self):
        tree = _make_tree(counter=True)
        assert isinstance(tree.children[1], py_trees.composites.Sequence)

    def test_counter_arm_memory_false(self):
        tree = _make_tree(counter=True)
        assert tree.children[1].memory is False  # type: ignore[attr-defined]

    def test_counter_arm_has_two_children(self):
        tree = _make_tree(counter=True)
        counter_arm = tree.children[1]
        assert len(counter_arm.children) == 2

    @pytest.mark.spec("EMB-15-003")
    @pytest.mark.spec("EMB-15-012")
    def test_counter_arm_first_child_is_willing_to_counter_deterministic(self):
        """EMB-15-003: WillingToCounterEmbargoProposal defaults to AlwaysFail."""
        tree = _make_tree(counter=True)
        willing = tree.children[1].children[0]
        assert isinstance(unwrap_call_out(willing), AlwaysFail)

    def test_counter_arm_first_child_name(self):
        tree = _make_tree(counter=True)
        willing = tree.children[1].children[0]
        assert willing.name == "WillingToCounterEmbargoProposal"

    @pytest.mark.spec("EMB-15-011")
    def test_counter_arm_second_child_is_delegate(self):
        tree = _make_tree(counter=True)
        delegate = tree.children[1].children[1]
        assert delegate.name == "CounterDelegate"

    @pytest.mark.spec("EMB-15-003")
    def test_counter_arm_first_child_stochastic(self):
        """STOCHASTIC bundle: WillingToCounterEmbargoProposal → fuzzer class."""
        tree = _make_tree(counter=True, call_out=EMBARGO_STOCHASTIC)
        willing = tree.children[1].children[0]
        assert isinstance(
            unwrap_call_out(willing), WillingToCounterEmbargoProposal
        )

    def test_custom_willing_to_counter_factory_wired(self):
        """Custom willing_to_counter_factory is injected into the counter arm."""
        called = {"flag": False}

        def custom_factory(name: str) -> py_trees.behaviour.Behaviour:
            called["flag"] = True

            class _Custom(CallOutBackend):
                def answer(self) -> CallOutAnswer:
                    return CallOutAnswer.no("test backend declines")

            return _Custom(name="CustomCounter")

        bundle = EmbargoCallOutBundle(
            willing_to_counter_factory=custom_factory  # type: ignore[arg-type]
        )
        tree = _make_tree(counter=True, call_out=bundle)
        assert called["flag"]
        assert tree.children[1].children[0].name == "CustomCounter"


# ---------------------------------------------------------------------------
# Reject arm (EMB-15-004)
# ---------------------------------------------------------------------------


class TestRejectArm:
    @pytest.mark.spec("EMB-15-004")
    @pytest.mark.spec("EMB-15-008")
    def test_reject_arm_is_last_child_without_counter(self):
        """Flow B: reject arm is child[1] (last, index 1)."""
        tree = _make_tree(counter=False)
        assert tree.children[1].name == "RejectDelegate"

    @pytest.mark.spec("EMB-15-004")
    def test_reject_arm_is_last_child_with_counter(self):
        """Flow A: reject arm is child[2] (last, index 2)."""
        tree = _make_tree(counter=True)
        assert tree.children[2].name == "RejectDelegate"


# ---------------------------------------------------------------------------
# BTBridge integration tests (EMB-15 end-to-end via real DataLayer)
# ---------------------------------------------------------------------------

_OWNER_ACTOR = "https://example.org/actors/case-owner"
_NON_OWNER_ACTOR = "https://example.org/actors/non-owner"
_UNKNOWN_ACTOR = "https://example.org/actors/unknown"
_INT_CASE_ID = "https://example.org/cases/emb15-integration"


def _make_participant(
    actor_id: str,
    role: CVDRole,
    case_id: str = _INT_CASE_ID,
) -> CaseParticipant:
    slug = actor_id.rsplit("/", 1)[-1]
    return make(
        CaseParticipant,
        id_=f"{case_id}/participants/{slug}",
        attributed_to=actor_id,
        context=case_id,
        case_roles=[role],
    )


def _make_case_with_participants(
    scenario: BTTestScenario,
    *participants: CaseParticipant,
) -> VulnerabilityCase:
    case = make(
        VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
        id_=_INT_CASE_ID,
        name="EMB-15 Integration Test Case",
        case_participants=[p.id_ for p in participants],
        actor_participant_index={
            str(p.attributed_to): p.id_ for p in participants
        },
    )
    scenario.seed(*participants, case)
    return case


def _tracking_stub(name: str) -> tuple[py_trees.behaviour.Behaviour, dict]:
    """Return a stub that records whether it was ticked, plus the call log."""
    log: dict = {"ticked": False}

    class _Tracking(py_trees.behaviour.Behaviour):
        def update(self) -> py_trees.common.Status:
            log["ticked"] = True
            return py_trees.common.Status.SUCCESS

    return _Tracking(name=name), log


def _failing_stub(name: str) -> py_trees.behaviour.Behaviour:
    """A delegate subtree (not a call-out backend) that fails."""
    return py_trees.behaviours.Failure(name=name)


class TestBTBridgeIntegration:
    """End-to-end integration tests for create_embargo_response_decision_tree.

    Ticks the tree through BTBridge with a real in-memory SQLite DataLayer and
    verifies routing decisions (EMB-15-001 through EMB-15-004).
    """

    # ------------------------------------------------------------------
    # EvaluateEmbargoProposal alone decides the answer (EMB-15-013)
    # ------------------------------------------------------------------

    @pytest.mark.spec("EMB-15-006")
    @pytest.mark.spec("EMB-15-013")
    @pytest.mark.parametrize("accepts", [True, False])
    def test_case_owner_answer_follows_evaluate_alone(self, accepts: bool):
        """CASE_OWNER: EvaluateEmbargoProposal's answer is the owner's answer."""
        self._assert_answer_follows_evaluate(
            _OWNER_ACTOR, CVDRole.CASE_OWNER, accepts=accepts
        )

    @pytest.mark.spec("EMB-15-013")
    @pytest.mark.parametrize("accepts", [True, False])
    def test_non_owner_answer_follows_evaluate_alone(self, accepts: bool):
        """Non-owner invitee: EvaluateEmbargoProposal alone decides its answer.

        No approval is sought from the Case Owner: a yes ticks the accept
        delegate, a no falls through to the reject delegate.
        """
        self._assert_answer_follows_evaluate(
            _NON_OWNER_ACTOR, CVDRole.VENDOR, accepts=accepts
        )

    @staticmethod
    def _assert_answer_follows_evaluate(
        actor_id: str, role: CVDRole, *, accepts: bool
    ) -> None:
        evaluated: dict = {"count": 0}

        def evaluate_factory(name: str) -> py_trees.behaviour.Behaviour:
            class _Evaluate(CallOutBackend):
                def answer(self) -> CallOutAnswer:
                    evaluated["count"] += 1
                    if accepts:
                        return CallOutAnswer.yes()
                    return CallOutAnswer.no("test policy declines")

            return _Evaluate(name=name)

        bundle = EmbargoCallOutBundle(
            evaluate_embargo_proposal_factory=evaluate_factory  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=actor_id)
        _make_case_with_participants(
            scenario, _make_participant(actor_id, role)
        )

        accept_bt, accept_log = _tracking_stub("AcceptDelegate")
        reject_bt, reject_log = _tracking_stub("RejectDelegate")
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=actor_id,
            accept_bt=accept_bt,
            reject_bt=reject_bt,
            call_out=bundle,
        )
        result = scenario.run(tree, actor_id=actor_id)
        scenario.assert_success(result)
        assert evaluated["count"] == 1
        assert accept_log["ticked"] is accepts
        assert reject_log["ticked"] is not accepts

    @pytest.mark.spec("EMB-15-004")
    @pytest.mark.spec("EMB-15-013")
    @pytest.mark.parametrize("accepts", [True, False])
    def test_unknown_actor_answer_follows_evaluate_alone(self, accepts: bool):
        """Actor not in the case: no role read gates the accept arm.

        EvaluateEmbargoProposal's yes ticks the accept delegate even for an
        actor with no participant record; its no falls through to reject.
        """
        bundle = EmbargoCallOutBundle(
            evaluate_embargo_proposal_factory=(  # type: ignore[arg-type]
                _stub if accepts else call_out_no
            ),
        )
        scenario = BTTestScenario(actor_id=_UNKNOWN_ACTOR)
        # Seed case with no entry for _UNKNOWN_ACTOR
        known_p = _make_participant(_NON_OWNER_ACTOR, CVDRole.COORDINATOR)
        _make_case_with_participants(scenario, known_p)

        accept_bt, accept_log = _tracking_stub("AcceptDelegate")
        reject_bt, reject_log = _tracking_stub("RejectDelegate")
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_UNKNOWN_ACTOR,
            accept_bt=accept_bt,
            reject_bt=reject_bt,
            call_out=bundle,
        )
        result = scenario.run(tree, actor_id=_UNKNOWN_ACTOR)
        scenario.assert_success(result)
        assert accept_log["ticked"] is accepts
        assert reject_log["ticked"] is not accepts

    # ------------------------------------------------------------------
    # Flow A — accept/counter/reject delegation (EMB-15-001 / EMB-15-003 / EMB-15-004)
    # ------------------------------------------------------------------

    @pytest.mark.spec("EMB-15-001")
    def test_flow_a_accept_delegation(self):
        """Flow A: deterministic default → accept_bt is ticked, result is SUCCESS."""
        scenario = BTTestScenario(actor_id=_OWNER_ACTOR)
        owner_p = _make_participant(_OWNER_ACTOR, CVDRole.CASE_OWNER)
        _make_case_with_participants(scenario, owner_p)

        accept_bt, accept_log = _tracking_stub("FlowAAccept")
        reject_bt, reject_log = _tracking_stub("FlowAReject")
        counter_bt, counter_log = _tracking_stub("FlowACounter")

        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_OWNER_ACTOR,
            accept_bt=accept_bt,
            reject_bt=reject_bt,
            counter_bt=counter_bt,
        )
        result = scenario.run(tree, actor_id=_OWNER_ACTOR)
        scenario.assert_success(result)
        assert accept_log["ticked"], (
            "accept_bt must be ticked in Flow A default-accept"
        )
        assert not counter_log["ticked"], (
            "counter_bt must NOT be ticked on default-accept"
        )
        assert not reject_log["ticked"], (
            "reject_bt must NOT be ticked on default-accept"
        )

    @pytest.mark.spec("EMB-15-003")
    @pytest.mark.spec("EMB-15-011")
    def test_flow_a_counter_delegation_when_willing(self):
        """Flow A: WillingToCounter → SUCCESS → counter_bt is ticked."""
        # Accept arm fails because EvaluateEmbargoProposal returns FAILURE,
        # so the AcceptArm Sequence short-circuits at child[0] (never
        # reaches accept_bt).
        # WillingToCounter returns SUCCESS so counter arm is then taken.
        accept_fail_bundle = EmbargoCallOutBundle(
            evaluate_embargo_proposal_factory=call_out_no,  # type: ignore[arg-type]
            willing_to_counter_factory=_stub,  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=_UNKNOWN_ACTOR)
        known_p = _make_participant(_NON_OWNER_ACTOR, CVDRole.COORDINATOR)
        case = make(
            VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_=_INT_CASE_ID,
            name="Flow A Counter Test",
            case_participants=[known_p.id_],
            actor_participant_index={_NON_OWNER_ACTOR: known_p.id_},
        )
        scenario.seed(known_p, case)

        counter_bt, counter_log = _tracking_stub("FlowACounter")
        reject_bt, reject_log = _tracking_stub("FlowAReject")
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_UNKNOWN_ACTOR,
            accept_bt=_failing_stub("FlowAAccept"),
            reject_bt=reject_bt,
            counter_bt=counter_bt,
            call_out=accept_fail_bundle,
        )
        result = scenario.run(tree, actor_id=_UNKNOWN_ACTOR)
        scenario.assert_success(result)
        assert counter_log["ticked"], (
            "counter_bt must be ticked when WillingToCounter succeeds"
        )
        assert not reject_log["ticked"], (
            "reject_bt must NOT be ticked when counter arm taken"
        )

    @pytest.mark.spec("EMB-15-004")
    @pytest.mark.spec("EMB-15-008")
    def test_flow_a_reject_delegation_when_all_arms_fail(self):
        """Flow A: accept + counter arms fail → reject_bt is ticked (EMB-15-004).

        Accept arm fails because EvaluateEmbargoProposal → FAILURE.
        Counter arm fails because WillingToCounter → FAILURE.
        """
        deny_all = EmbargoCallOutBundle(
            evaluate_embargo_proposal_factory=call_out_no,  # type: ignore[arg-type]
            willing_to_counter_factory=call_out_no,  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=_UNKNOWN_ACTOR)
        known_p = _make_participant(_NON_OWNER_ACTOR, CVDRole.COORDINATOR)
        case = make(
            VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_=_INT_CASE_ID,
            name="Flow A Reject Test",
            case_participants=[known_p.id_],
            actor_participant_index={_NON_OWNER_ACTOR: known_p.id_},
        )
        scenario.seed(known_p, case)

        reject_bt, reject_log = _tracking_stub("FlowAReject")
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_UNKNOWN_ACTOR,
            accept_bt=_failing_stub("FlowAAccept"),
            reject_bt=reject_bt,
            counter_bt=_failing_stub("FlowACounter"),
            call_out=deny_all,
        )
        result = scenario.run(tree, actor_id=_UNKNOWN_ACTOR)
        scenario.assert_success(result)
        assert reject_log["ticked"], (
            "reject_bt must be ticked when all other arms fail"
        )

    # ------------------------------------------------------------------
    # Flow B — accept/reject delegation (no counter arm)
    # ------------------------------------------------------------------

    @pytest.mark.spec("EMB-15-001")
    def test_flow_b_accept_delegation(self):
        """Flow B: CASE_OWNER + default-accept → accept_bt ticked, no counter arm."""
        scenario = BTTestScenario(actor_id=_OWNER_ACTOR)
        owner_p = _make_participant(_OWNER_ACTOR, CVDRole.CASE_OWNER)
        _make_case_with_participants(scenario, owner_p)

        accept_bt, accept_log = _tracking_stub("FlowBAccept")
        reject_bt, reject_log = _tracking_stub("FlowBReject")

        # Flow B: counter_bt=None (default)
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_OWNER_ACTOR,
            accept_bt=accept_bt,
            reject_bt=reject_bt,
        )
        result = scenario.run(tree, actor_id=_OWNER_ACTOR)
        scenario.assert_success(result)
        assert accept_log["ticked"], (
            "accept_bt must be ticked in Flow B default-accept"
        )
        assert not reject_log["ticked"], (
            "reject_bt must NOT be ticked on Flow B accept"
        )

    @pytest.mark.spec("EMB-15-004")
    def test_flow_b_reject_delegation(self):
        """Flow B: accept arm fails → reject_bt is ticked (EMB-15-004).

        The accept arm fails because EvaluateEmbargoProposal → FAILURE.
        """
        deny_accept = EmbargoCallOutBundle(
            evaluate_embargo_proposal_factory=call_out_no,  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=_UNKNOWN_ACTOR)
        known_p = _make_participant(_NON_OWNER_ACTOR, CVDRole.COORDINATOR)
        case = make(
            VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_=_INT_CASE_ID,
            name="Flow B Reject Test",
            case_participants=[known_p.id_],
            actor_participant_index={_NON_OWNER_ACTOR: known_p.id_},
        )
        scenario.seed(known_p, case)

        reject_bt, reject_log = _tracking_stub("FlowBReject")
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_UNKNOWN_ACTOR,
            accept_bt=_failing_stub("FlowBAccept"),
            reject_bt=reject_bt,
            call_out=deny_accept,
        )
        result = scenario.run(tree, actor_id=_UNKNOWN_ACTOR)
        scenario.assert_success(result)
        assert reject_log["ticked"], (
            "reject_bt must be ticked in Flow B when accept fails"
        )
