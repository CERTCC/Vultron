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
from vultron.demo.fuzzer.bundles.embargo import EMBARGO_STOCHASTIC
from vultron.demo.fuzzer.embargo import (
    CaseOwnerApprovesEmbargoResponse,
    EvaluateEmbargoProposal,
    WillingToCounterEmbargoProposal,
)

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

    def test_two_arms_without_counter(self):
        """Flow B (no counter): accept + reject = 2 arms."""
        tree = _make_tree(counter=False)
        assert len(tree.children) == 2

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

    def test_authorize_first_child_is_check_is_case_owner(self):
        """EMB-15-002: gospel-bypass guard is CheckIsCaseOwnerNode."""
        tree = _make_tree()
        auth = tree.children[0].children[0]
        assert isinstance(auth.children[0], CheckIsCaseOwnerNode)

    def test_authorize_first_child_name(self):
        tree = _make_tree()
        auth = tree.children[0].children[0]
        assert auth.children[0].name == "CheckIsCaseOwner"

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
    def test_non_owner_seam_deterministic_is_always_succeed(self):
        """DETERMINISTIC bundle: CaseOwnerApprovesEmbargoResponse → AlwaysSucceed."""
        tree = _make_tree()
        auth = tree.children[0].children[0]
        non_owner_node = auth.children[1]
        assert isinstance(non_owner_node, AlwaysSucceed)

    def test_non_owner_seam_name(self):
        tree = _make_tree()
        auth = tree.children[0].children[0]
        non_owner_node = auth.children[1]
        assert non_owner_node.name == "CaseOwnerApprovesEmbargoResponse"

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
    def test_stochastic_evaluate_is_correct_fuzzer_class(self):
        """STOCHASTIC bundle: EvaluateEmbargoProposal → fuzzer class."""
        tree = _make_tree(call_out=EMBARGO_STOCHASTIC)
        evaluate_node = tree.children[0].children[1]
        assert isinstance(evaluate_node, EvaluateEmbargoProposal)

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
    def test_counter_arm_absent_when_no_counter_bt(self):
        """Flow B: no counter_bt → only 2 arms (no CounterArm)."""
        tree = _make_tree(counter=False)
        names = [c.name for c in tree.children]
        assert "CounterArm" not in names

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
    def test_reject_arm_is_last_child_without_counter(self):
        """Flow B: reject arm is child[1] (last, index 1)."""
        tree = _make_tree(counter=False)
        assert tree.children[1].name == "RejectDelegate"

    def test_reject_arm_is_last_child_with_counter(self):
        """Flow A: reject arm is child[2] (last, index 2)."""
        tree = _make_tree(counter=True)
        assert tree.children[2].name == "RejectDelegate"
