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

AC-6: verify tree structure, CASE_OWNER bypass vs call-out routing, and
both flows' accept/reject/counter delegation.

Covers:
  - EMB-15-001: default-accept (EvaluateEmbargoProposal → SUCCESS)
  - EMB-15-002: CASE_OWNER gospel-bypass seam
  - EMB-15-003: counter arm present/absent (Flow A vs Flow B)
  - EMB-15-004: reject arm always present as fallback
  - BT-18-004: factory parameter wired + deterministic default
  - BT-23-002: DETERMINISTIC bundle uses AlwaysSucceed/AlwaysFail
"""

import py_trees
import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckIsCaseOwnerNode,
)
from vultron.core.behaviors.embargo.response_decision_tree import (
    create_embargo_response_decision_tree,
)
from vultron.core.behaviors.call_out.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EmbargoCallOutBundle,
)
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.demo.fuzzer.bundles.embargo import EMBARGO_STOCHASTIC
from vultron.demo.fuzzer.embargo import (
    CaseOwnerApprovesEmbargoResponse,
    EvaluateEmbargoProposal,
    WillingToCounterEmbargoProposal,
)
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/emb15-test"
DECIDING_ACTOR_ID = "https://example.org/actors/local-deciding-actor"


def _stub(name: str = "stub") -> py_trees.behaviour.Behaviour:
    """Return a no-op stub behaviour."""

    class _Stub(py_trees.behaviour.Behaviour):
        def update(self) -> py_trees.common.Status:
            return py_trees.common.Status.SUCCESS

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

    def test_accept_arm_has_three_children(self):
        """AcceptArm: AuthorizeSelector + EvaluateEmbargoProposal + delegate."""
        tree = _make_tree()
        accept_arm = tree.children[0]
        assert len(accept_arm.children) == 3

    def test_accept_arm_first_child_is_authorize_selector(self):
        tree = _make_tree()
        auth = tree.children[0].children[0]
        assert isinstance(auth, py_trees.composites.Selector)
        assert auth.name == "AuthorizeSelector"

    def test_authorize_selector_memory_false(self):
        tree = _make_tree()
        auth = tree.children[0].children[0]
        assert auth.memory is False  # type: ignore[attr-defined]

    def test_authorize_selector_has_two_children(self):
        tree = _make_tree()
        auth = tree.children[0].children[0]
        assert len(auth.children) == 2

    @pytest.mark.spec("EMB-15-002")
    def test_authorize_first_child_is_check_is_case_owner(self):
        """EMB-15-002: gospel-bypass guard is CheckIsCaseOwnerNode."""
        tree = _make_tree()
        auth = tree.children[0].children[0]
        assert isinstance(auth.children[0], CheckIsCaseOwnerNode)

    def test_authorize_first_child_name(self):
        tree = _make_tree()
        auth = tree.children[0].children[0]
        assert auth.children[0].name == "CheckIsCaseOwner"

    @pytest.mark.spec("EMB-15-005")
    def test_accept_arm_second_child_is_evaluate_embargo_proposal_deterministic(
        self,
    ):
        """EMB-15-001: EvaluateEmbargoProposal defaults to AlwaysSucceed."""
        tree = _make_tree()
        evaluate_node = tree.children[0].children[1]
        assert isinstance(evaluate_node, AlwaysSucceed)

    def test_accept_arm_second_child_name(self):
        tree = _make_tree()
        evaluate_node = tree.children[0].children[1]
        assert evaluate_node.name == "EvaluateEmbargoProposal"

    def test_accept_arm_third_child_is_delegate(self):
        tree = _make_tree()
        delegate = tree.children[0].children[2]
        assert delegate.name == "AcceptDelegate"


# ---------------------------------------------------------------------------
# CASE_OWNER authorization seam (EMB-15-002)
# ---------------------------------------------------------------------------


class TestAuthorizeSeam:
    @pytest.mark.spec("EMB-15-007")
    def test_non_owner_seam_deterministic_is_always_succeed(self):
        """DETERMINISTIC bundle: CaseOwnerApprovesEmbargoResponse → AlwaysSucceed."""
        tree = _make_tree()
        auth = tree.children[0].children[0]
        non_owner_node = auth.children[1]
        assert isinstance(non_owner_node, AlwaysSucceed)

    @pytest.mark.spec("EMB-15-007")
    def test_non_owner_seam_name(self):
        tree = _make_tree()
        auth = tree.children[0].children[0]
        non_owner_node = auth.children[1]
        assert non_owner_node.name == "CaseOwnerApprovesEmbargoResponse"

    @pytest.mark.spec("EMB-15-007")
    def test_non_owner_seam_stochastic_is_correct_fuzzer_class(self):
        """STOCHASTIC bundle: CaseOwnerApprovesEmbargoResponse → fuzzer class."""
        tree = _make_tree(call_out=EMBARGO_STOCHASTIC)
        auth = tree.children[0].children[0]
        non_owner_node = auth.children[1]
        assert isinstance(non_owner_node, CaseOwnerApprovesEmbargoResponse)

    def test_custom_case_owner_approves_factory_wired(self):
        """BT-18-004: custom factory is injected into the authorize seam."""
        called = {"flag": False}

        def custom_factory(name: str) -> py_trees.behaviour.Behaviour:
            called["flag"] = True

            class _Custom(py_trees.behaviour.Behaviour):
                def update(self):
                    return py_trees.common.Status.SUCCESS

            return _Custom(name="CustomApproval")

        bundle = EmbargoCallOutBundle(
            case_owner_approves_embargo_response_factory=custom_factory  # type: ignore[arg-type]
        )
        tree = _make_tree(call_out=bundle)
        assert called["flag"]
        auth = tree.children[0].children[0]
        assert auth.children[1].name == "CustomApproval"


# ---------------------------------------------------------------------------
# EvaluateEmbargoProposal call-out (EMB-15-001)
# ---------------------------------------------------------------------------


class TestEvaluateEmbargoProposalCallOut:
    @pytest.mark.spec("EMB-15-005")
    def test_stochastic_evaluate_is_correct_fuzzer_class(self):
        """STOCHASTIC bundle: EvaluateEmbargoProposal → fuzzer class."""
        tree = _make_tree(call_out=EMBARGO_STOCHASTIC)
        evaluate_node = tree.children[0].children[1]
        assert isinstance(evaluate_node, EvaluateEmbargoProposal)

    @pytest.mark.spec("EMB-15-005")
    def test_custom_evaluate_factory_wired(self):
        """Custom evaluate_embargo_proposal_factory is injected."""
        called = {"flag": False}

        def custom_factory(name: str) -> py_trees.behaviour.Behaviour:
            called["flag"] = True

            class _Custom(py_trees.behaviour.Behaviour):
                def update(self):
                    return py_trees.common.Status.SUCCESS

            return _Custom(name="CustomEvaluate")

        bundle = EmbargoCallOutBundle(
            evaluate_embargo_proposal_factory=custom_factory  # type: ignore[arg-type]
        )
        tree = _make_tree(call_out=bundle)
        assert called["flag"]
        assert tree.children[0].children[1].name == "CustomEvaluate"


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
    def test_counter_arm_first_child_is_willing_to_counter_deterministic(self):
        """EMB-15-003: WillingToCounterEmbargoProposal defaults to AlwaysFail."""
        tree = _make_tree(counter=True)
        willing = tree.children[1].children[0]
        assert isinstance(willing, AlwaysFail)

    def test_counter_arm_first_child_name(self):
        tree = _make_tree(counter=True)
        willing = tree.children[1].children[0]
        assert willing.name == "WillingToCounterEmbargoProposal"

    def test_counter_arm_second_child_is_delegate(self):
        tree = _make_tree(counter=True)
        delegate = tree.children[1].children[1]
        assert delegate.name == "CounterDelegate"

    @pytest.mark.spec("EMB-15-003")
    def test_counter_arm_first_child_stochastic(self):
        """STOCHASTIC bundle: WillingToCounterEmbargoProposal → fuzzer class."""
        tree = _make_tree(counter=True, call_out=EMBARGO_STOCHASTIC)
        willing = tree.children[1].children[0]
        assert isinstance(willing, WillingToCounterEmbargoProposal)

    def test_custom_willing_to_counter_factory_wired(self):
        """Custom willing_to_counter_factory is injected into the counter arm."""
        called = {"flag": False}

        def custom_factory(name: str) -> py_trees.behaviour.Behaviour:
            called["flag"] = True

            class _Custom(py_trees.behaviour.Behaviour):
                def update(self):
                    return py_trees.common.Status.FAILURE

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
) -> VultronParticipant:
    slug = actor_id.rsplit("/", 1)[-1]
    return VultronParticipant(
        id_=f"{case_id}/participants/{slug}",
        attributed_to=actor_id,
        context=case_id,
        case_roles=[role],
    )


def _make_case_with_participants(
    scenario: BTTestScenario,
    *participants: VultronParticipant,
) -> VultronCase:
    case = VultronCase(
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
    class _Fail(py_trees.behaviour.Behaviour):
        def update(self) -> py_trees.common.Status:
            return py_trees.common.Status.FAILURE

    return _Fail(name=name)


class TestBTBridgeIntegration:
    """End-to-end integration tests for create_embargo_response_decision_tree.

    Ticks the tree through BTBridge with a real in-memory SQLite DataLayer and
    verifies routing decisions (EMB-15-001 through EMB-15-004).
    """

    @pytest.fixture(autouse=True)
    def _clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    # ------------------------------------------------------------------
    # CASE_OWNER gospel bypass (EMB-15-002)
    # ------------------------------------------------------------------

    @pytest.mark.spec("EMB-15-006")
    def test_case_owner_reaches_accept_bt(self):
        """CASE_OWNER actor: accept arm fires; accept_bt is ticked."""
        scenario = BTTestScenario(actor_id=_OWNER_ACTOR)
        owner_p = _make_participant(_OWNER_ACTOR, CVDRole.CASE_OWNER)
        _make_case_with_participants(scenario, owner_p)

        accept_bt, accept_log = _tracking_stub("AcceptDelegate")
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_OWNER_ACTOR,
            accept_bt=accept_bt,
            reject_bt=_failing_stub("RejectDelegate"),
        )
        result = scenario.run(tree, actor_id=_OWNER_ACTOR)
        scenario.assert_success(result)
        assert accept_log["ticked"], "accept_bt must be ticked for CASE_OWNER"

    @pytest.mark.spec("EMB-15-006")
    def test_case_owner_skips_case_owner_approves_call_out(self):
        """CASE_OWNER gospel bypass: CaseOwnerApproves call-out is never reached."""
        called: dict = {"flag": False}

        def tracking_approves_factory(
            name: str,
        ) -> py_trees.behaviour.Behaviour:
            class _Track(py_trees.behaviour.Behaviour):
                def update(self) -> py_trees.common.Status:
                    called["flag"] = True
                    return py_trees.common.Status.SUCCESS

            return _Track(name=name)

        bundle = EmbargoCallOutBundle(
            case_owner_approves_embargo_response_factory=tracking_approves_factory  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=_OWNER_ACTOR)
        owner_p = _make_participant(_OWNER_ACTOR, CVDRole.CASE_OWNER)
        _make_case_with_participants(scenario, owner_p)

        accept_bt, _ = _tracking_stub("AcceptDelegate")
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_OWNER_ACTOR,
            accept_bt=accept_bt,
            reject_bt=_failing_stub("RejectDelegate"),
            call_out=bundle,
        )
        scenario.run(tree, actor_id=_OWNER_ACTOR)
        assert not called[
            "flag"
        ], "CaseOwnerApprovesEmbargoResponse must NOT be called for CASE_OWNER"

    # ------------------------------------------------------------------
    # Non-owner routes through call-out seam (EMB-15-002)
    # ------------------------------------------------------------------

    @pytest.mark.spec("EMB-15-007")
    def test_non_owner_routes_through_case_owner_approves_call_out(self):
        """Non-owner: CaseOwnerApprovesEmbargoResponse call-out IS invoked."""
        called: dict = {"flag": False}

        def tracking_approves_factory(
            name: str,
        ) -> py_trees.behaviour.Behaviour:
            class _Track(py_trees.behaviour.Behaviour):
                def update(self) -> py_trees.common.Status:
                    called["flag"] = True
                    return py_trees.common.Status.SUCCESS

            return _Track(name=name)

        bundle = EmbargoCallOutBundle(
            case_owner_approves_embargo_response_factory=tracking_approves_factory  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=_NON_OWNER_ACTOR)
        non_owner_p = _make_participant(_NON_OWNER_ACTOR, CVDRole.COORDINATOR)
        _make_case_with_participants(scenario, non_owner_p)

        accept_bt, _ = _tracking_stub("AcceptDelegate")
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_NON_OWNER_ACTOR,
            accept_bt=accept_bt,
            reject_bt=_failing_stub("RejectDelegate"),
            call_out=bundle,
        )
        scenario.run(tree, actor_id=_NON_OWNER_ACTOR)
        assert called[
            "flag"
        ], "CaseOwnerApprovesEmbargoResponse must be called for non-owner"

    @pytest.mark.spec("EMB-15-004")
    def test_unknown_actor_falls_through_to_reject(self):
        """Actor not in case: CheckIsCaseOwner → FAILURE; call-out denies → reject."""
        deny_factory_called: dict = {"flag": False}

        def deny_factory(name: str) -> py_trees.behaviour.Behaviour:
            class _Deny(py_trees.behaviour.Behaviour):
                def update(self) -> py_trees.common.Status:
                    deny_factory_called["flag"] = True
                    return py_trees.common.Status.FAILURE

            return _Deny(name=name)

        bundle = EmbargoCallOutBundle(
            case_owner_approves_embargo_response_factory=deny_factory  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=_UNKNOWN_ACTOR)
        # Seed case with no entry for _UNKNOWN_ACTOR
        known_p = _make_participant(_NON_OWNER_ACTOR, CVDRole.COORDINATOR)
        _make_case_with_participants(scenario, known_p)

        reject_bt, reject_log = _tracking_stub("RejectDelegate")
        tree = create_embargo_response_decision_tree(
            case_id=_INT_CASE_ID,
            deciding_actor_id=_UNKNOWN_ACTOR,
            accept_bt=_stub("AcceptDelegate"),
            reject_bt=reject_bt,
            call_out=bundle,
        )
        result = scenario.run(tree, actor_id=_UNKNOWN_ACTOR)
        scenario.assert_success(result)
        assert deny_factory_called[
            "flag"
        ], "CaseOwnerApproves call-out seam must be reached for unknown actor"
        assert reject_log[
            "ticked"
        ], "reject_bt must be ticked for unknown actor"

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
        assert accept_log[
            "ticked"
        ], "accept_bt must be ticked in Flow A default-accept"
        assert not counter_log[
            "ticked"
        ], "counter_bt must NOT be ticked on default-accept"
        assert not reject_log[
            "ticked"
        ], "reject_bt must NOT be ticked on default-accept"

    @pytest.mark.spec("EMB-15-003")
    def test_flow_a_counter_delegation_when_willing(self):
        """Flow A: WillingToCounter → SUCCESS → counter_bt is ticked."""
        # Accept arm fails because AuthorizeSelector fails:
        # _UNKNOWN_ACTOR is not in case → CheckIsCaseOwner FAILURE,
        # CaseOwnerApproves also returns FAILURE → AuthorizeSelector FAILURE
        # → AcceptArm Sequence short-circuits at child[0] (never reaches
        # EvaluateProposal or accept_bt).
        # WillingToCounter returns SUCCESS so counter arm is then taken.
        accept_fail_bundle = EmbargoCallOutBundle(
            case_owner_approves_embargo_response_factory=lambda name: _failing_stub(name),  # type: ignore[arg-type]
            willing_to_counter_factory=lambda name: _stub(name),  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=_UNKNOWN_ACTOR)
        known_p = _make_participant(_NON_OWNER_ACTOR, CVDRole.COORDINATOR)
        # Case has no entry for _UNKNOWN_ACTOR so CheckIsCaseOwner returns FAILURE
        case = VultronCase(
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
        assert counter_log[
            "ticked"
        ], "counter_bt must be ticked when WillingToCounter succeeds"
        assert not reject_log[
            "ticked"
        ], "reject_bt must NOT be ticked when counter arm taken"

    @pytest.mark.spec("EMB-15-004")
    def test_flow_a_reject_delegation_when_all_arms_fail(self):
        """Flow A: accept + counter arms fail → reject_bt is ticked (EMB-15-004).

        Accept arm fails via AuthorizeSelector: _UNKNOWN_ACTOR not in case →
        CheckIsCaseOwner FAILURE; CaseOwnerApproves → FAILURE → AcceptArm fails.
        Counter arm fails because WillingToCounter → FAILURE.
        """
        deny_all = EmbargoCallOutBundle(
            case_owner_approves_embargo_response_factory=lambda name: _failing_stub(name),  # type: ignore[arg-type]
            willing_to_counter_factory=lambda name: _failing_stub(name),  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=_UNKNOWN_ACTOR)
        known_p = _make_participant(_NON_OWNER_ACTOR, CVDRole.COORDINATOR)
        case = VultronCase(
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
        assert reject_log[
            "ticked"
        ], "reject_bt must be ticked when all other arms fail"

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
        assert accept_log[
            "ticked"
        ], "accept_bt must be ticked in Flow B default-accept"
        assert not reject_log[
            "ticked"
        ], "reject_bt must NOT be ticked on Flow B accept"

    @pytest.mark.spec("EMB-15-004")
    def test_flow_b_reject_delegation(self):
        """Flow B: accept arm fails → reject_bt is ticked (EMB-15-004).

        AuthorizeSelector fails because _UNKNOWN_ACTOR is not in the case:
        CheckIsCaseOwner → FAILURE; CaseOwnerApproves → FAILURE.
        EvaluateEmbargoProposal is never reached, so no factory override needed.
        """
        deny_accept = EmbargoCallOutBundle(
            case_owner_approves_embargo_response_factory=lambda name: _failing_stub(name),  # type: ignore[arg-type]
        )
        scenario = BTTestScenario(actor_id=_UNKNOWN_ACTOR)
        known_p = _make_participant(_NON_OWNER_ACTOR, CVDRole.COORDINATOR)
        case = VultronCase(
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
        assert reject_log[
            "ticked"
        ], "reject_bt must be ticked in Flow B when accept fails"
