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
"""Tests for the manage-embargo behavior tree (Phase 1 stub).

Verifies BT-18-004: all ten factory params are accepted and wired; defaults
are the correct fuzzer classes.
"""

import pytest
import py_trees

from vultron.core.behaviors.embargo.manage_embargo_tree import (
    create_manage_embargo_tree,
)
from vultron.demo.fuzzer.embargo import (
    CurrentEmbargoAcceptable,
    EvaluateEmbargoProposal,
    ExitEmbargoForOtherReason,
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    ReasonToProposeEmbargoWhenDeployed,
    SelectEmbargoOfferTerms,
    StopProposingEmbargo,
    WantToProposeEmbargo,
    WillingToCounterEmbargoProposal,
)

CASE_ID = "https://example.org/cases/test-001"

_EXPECTED_DEFAULTS = [
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

_FACTORY_PARAMS = [
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


@pytest.mark.parametrize("index,cls", list(enumerate(_EXPECTED_DEFAULTS)))
def test_default_child_is_correct_fuzzer_node(index, cls):
    """Each child defaults to the expected fuzzer class (BT-18-004)."""
    tree = create_manage_embargo_tree(case_id=CASE_ID)
    assert isinstance(tree.children[index], cls)


@pytest.mark.parametrize("param,index", list(zip(_FACTORY_PARAMS, range(10))))
def test_each_factory_is_wired(param, index):
    """Each factory parameter is individually wired into the corresponding child."""
    label = f"Custom_{index}"
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    tree = create_manage_embargo_tree(
        case_id=CASE_ID, **{param: custom_factory}
    )
    assert sentinel["called"]
    assert tree.children[index].name == label


def test_all_factories_replaceable():
    """All factory params can be replaced simultaneously."""
    kwargs = {
        param: _marker_factory(f"M{i}")
        for i, param in enumerate(_FACTORY_PARAMS)
    }
    tree = create_manage_embargo_tree(case_id=CASE_ID, **kwargs)
    tree_str = py_trees.display.ascii_tree(tree)
    for i in range(10):
        assert f"M{i}" in tree_str


# ---------------------------------------------------------------------------
# Actuator factory params — Phase 2 reserved (BT-18-004)
# ---------------------------------------------------------------------------


def test_actuator_factories_accepted():
    """All three Actuator factory params are accepted (Phase 2 reserved)."""
    tree = create_manage_embargo_tree(case_id=CASE_ID)
    assert tree is not None


def test_on_embargo_exit_default_factory_produces_correct_node():
    from vultron.core.behaviors.embargo.manage_embargo_tree import (
        _default_on_embargo_exit_factory,
    )
    from vultron.demo.fuzzer.embargo import OnEmbargoExit

    node = _default_on_embargo_exit_factory("OnEmbargoExit")
    assert isinstance(node, OnEmbargoExit)


def test_on_embargo_accept_default_factory_produces_correct_node():
    from vultron.core.behaviors.embargo.manage_embargo_tree import (
        _default_on_embargo_accept_factory,
    )
    from vultron.demo.fuzzer.embargo import OnEmbargoAccept

    node = _default_on_embargo_accept_factory("OnEmbargoAccept")
    assert isinstance(node, OnEmbargoAccept)


def test_on_embargo_reject_default_factory_produces_correct_node():
    from vultron.core.behaviors.embargo.manage_embargo_tree import (
        _default_on_embargo_reject_factory,
    )
    from vultron.demo.fuzzer.embargo import OnEmbargoReject

    node = _default_on_embargo_reject_factory("OnEmbargoReject")
    assert isinstance(node, OnEmbargoReject)


def test_actuator_custom_factories_accepted():
    """Custom Actuator factories are accepted without error."""
    tree = create_manage_embargo_tree(
        case_id=CASE_ID,
        on_embargo_exit_factory=_marker_factory("OEE"),
        on_embargo_accept_factory=_marker_factory("OEA"),
        on_embargo_reject_factory=_marker_factory("OER"),
    )
    assert tree is not None
