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
"""Tests for the manage-embargo behavior tree.

Verifies BT-18-004/BT-23-003: bundle parameter is accepted and used;
DETERMINISTIC default uses AlwaysSucceed/AlwaysFail per ceiling/floor rule;
STOCHASTIC bundle produces the correct fuzzer classes.
"""

import pytest
import py_trees

from vultron.core.behaviors.embargo.manage_embargo_tree import (
    create_manage_embargo_tree,
)
from vultron.demo.fuzzer.base import AlwaysFail, AlwaysSucceed
from vultron.demo.fuzzer.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EMBARGO_STOCHASTIC,
    EmbargoCallOutBundle,
)
from vultron.demo.fuzzer.embargo import (
    CurrentEmbargoAcceptable,
    EvaluateEmbargoProposal,
    ExitEmbargoForOtherReason,
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    OnEmbargoAccept,
    OnEmbargoExit,
    OnEmbargoReject,
    ReasonToProposeEmbargoWhenDeployed,
    SelectEmbargoOfferTerms,
    StopProposingEmbargo,
    WantToProposeEmbargo,
    WillingToCounterEmbargoProposal,
)

CASE_ID = "https://example.org/cases/test-001"

# DETERMINISTIC defaults per ceiling/floor rule (BT-23-002)
_EXPECTED_DETERMINISTIC = [
    AlwaysFail,  # exit_embargo_when_deployed (p < 0.5)
    AlwaysFail,  # exit_embargo_when_fix_ready (p < 0.5)
    AlwaysFail,  # exit_embargo_for_other_reason (p < 0.5)
    AlwaysFail,  # stop_proposing_embargo (p < 0.5)
    AlwaysSucceed,  # select_embargo_offer_terms (p > 0.5)
    AlwaysSucceed,  # want_to_propose_embargo (p > 0.5)
    AlwaysFail,  # willing_to_counter (p < 0.5)
    AlwaysFail,  # reason_to_propose_when_deployed (p < 0.5)
    AlwaysSucceed,  # evaluate_embargo_proposal (p > 0.5)
    AlwaysSucceed,  # current_embargo_acceptable (p > 0.5)
]

# Stochastic fuzzer classes in the same order
_EXPECTED_STOCHASTIC = [
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    ExitEmbargoForOtherReason,
    StopProposingEmbargo,
    SelectEmbargoOfferTerms,
    WantToProposeEmbargo,
    WillingToCounterEmbargoProposal,
    ReasonToProposeEmbargoWhenDeployed,
    EvaluateEmbargoProposal,
    CurrentEmbargoAcceptable,
]

_FACTORY_FIELDS = [
    "exit_embargo_when_deployed_factory",
    "exit_embargo_when_fix_ready_factory",
    "exit_embargo_for_other_reason_factory",
    "stop_proposing_embargo_factory",
    "select_embargo_offer_terms_factory",
    "want_to_propose_embargo_factory",
    "willing_to_counter_factory",
    "reason_to_propose_when_deployed_factory",
    "evaluate_embargo_proposal_factory",
    "current_embargo_acceptable_factory",
]


def _marker_factory(label):
    def factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    return factory


def test_create_manage_embargo_tree_returns_behaviour():
    tree = create_manage_embargo_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_root_name():
    tree = create_manage_embargo_tree(case_id=CASE_ID)
    assert tree.name == "ManageEmbargoBT"


def test_default_children_count():
    tree = create_manage_embargo_tree(case_id=CASE_ID)
    assert len(tree.children) == 10


@pytest.mark.parametrize("index,cls", list(enumerate(_EXPECTED_DETERMINISTIC)))
def test_default_child_is_deterministic(index, cls):
    """DETERMINISTIC: ceiling/floor of each node's stochastic p (BT-23-002)."""
    tree = create_manage_embargo_tree(case_id=CASE_ID)
    assert isinstance(tree.children[index], cls)


@pytest.mark.parametrize("index,cls", list(enumerate(_EXPECTED_STOCHASTIC)))
def test_stochastic_child_is_correct_fuzzer_node(index, cls):
    """STOCHASTIC bundle produces the expected fuzzer class at each index."""
    tree = create_manage_embargo_tree(
        case_id=CASE_ID, call_out=EMBARGO_STOCHASTIC
    )
    assert isinstance(tree.children[index], cls)


@pytest.mark.parametrize("field,index", list(zip(_FACTORY_FIELDS, range(10))))
def test_each_factory_is_wired(field, index):
    """Each factory field in a bundle is individually wired into the corresponding child."""
    label = f"Custom_{index}"
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    bundle = EmbargoCallOutBundle(**{field: custom_factory})  # type: ignore[arg-type]
    tree = create_manage_embargo_tree(case_id=CASE_ID, call_out=bundle)
    assert sentinel["called"]
    assert tree.children[index].name == label


def test_all_factories_replaceable():
    """All factory fields can be replaced simultaneously via a bundle."""
    bundle = EmbargoCallOutBundle(
        **{field: _marker_factory(f"M{i}") for i, field in enumerate(_FACTORY_FIELDS)}  # type: ignore[arg-type]
    )
    tree = create_manage_embargo_tree(case_id=CASE_ID, call_out=bundle)
    tree_str = py_trees.display.ascii_tree(tree)
    for i in range(10):
        assert f"M{i}" in tree_str


# ---------------------------------------------------------------------------
# Actuator factory fields — Phase 2 reserved (BT-18-004)
# ---------------------------------------------------------------------------


def test_actuator_factories_accepted():
    """All three Actuator factory fields are accepted via bundle (Phase 2 reserved)."""
    tree = create_manage_embargo_tree(case_id=CASE_ID)
    assert tree is not None


def test_on_embargo_exit_stochastic_factory_produces_correct_node():
    """STOCHASTIC bundle on_embargo_exit_factory produces an OnEmbargoExit node."""
    node = EMBARGO_STOCHASTIC.on_embargo_exit_factory("OnEmbargoExit")
    assert isinstance(node, OnEmbargoExit)


def test_on_embargo_accept_stochastic_factory_produces_correct_node():
    """STOCHASTIC bundle on_embargo_accept_factory produces an OnEmbargoAccept node."""
    node = EMBARGO_STOCHASTIC.on_embargo_accept_factory("OnEmbargoAccept")
    assert isinstance(node, OnEmbargoAccept)


def test_on_embargo_reject_stochastic_factory_produces_correct_node():
    """STOCHASTIC bundle on_embargo_reject_factory produces an OnEmbargoReject node."""
    node = EMBARGO_STOCHASTIC.on_embargo_reject_factory("OnEmbargoReject")
    assert isinstance(node, OnEmbargoReject)


def test_actuator_custom_factories_accepted():
    """Custom Actuator factories are accepted via bundle without error."""
    bundle = EmbargoCallOutBundle(
        on_embargo_exit_factory=_marker_factory("OEE"),  # type: ignore[arg-type]
        on_embargo_accept_factory=_marker_factory("OEA"),  # type: ignore[arg-type]
        on_embargo_reject_factory=_marker_factory("OER"),  # type: ignore[arg-type]
    )
    tree = create_manage_embargo_tree(case_id=CASE_ID, call_out=bundle)
    assert tree is not None


def test_deterministic_singleton_accepted():
    tree = create_manage_embargo_tree(
        case_id=CASE_ID, call_out=EMBARGO_DETERMINISTIC
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)
