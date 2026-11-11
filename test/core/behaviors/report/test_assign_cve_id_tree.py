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
"""Tests for the CVE ID assignment behavior tree (issues #1817, #2518).

Verifies BT-18-004/BT-23-003: bundle parameter accepted and used;
DETERMINISTIC default produces AlwaysSucceed/AlwaysFail nodes and an
output-writing ``EvaluateCveEligibility`` default (BT-23-013); STOCHASTIC
bundle produces the correct fuzzer classes; CVE eligibility is one
``EvaluateCveEligibility`` call-out point (BTND-05-007, BTND-05-008);
factory injection for all 7 call-out points.
(13 nodes = 4 composites + 7 factory call-out leaves + 2 ProtocolInternal leaves.)
"""

import dataclasses

import py_trees
import pytest
from py_trees.common import Status

from test.support.call_out import answer_for, tick_call_out
from vultron.core.behaviors.call_out import unwrap_call_out
from vultron.core.behaviors.call_out.answer import CallOutAnswer
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.bundles.assign_cve_id import (
    ASSIGN_CVE_ID_DETERMINISTIC,
    CNA_RULES_REFERENCE_EDITION,
    CVE_ELIGIBILITY_RATIONALE_KEY,
    CVE_ELIGIBILITY_VERDICT_KEY,
    AssignCveIdCallOutBundle,
    DeterministicEvaluateCveEligibility,
)
from vultron.core.behaviors.call_out.capabilities.report_management.assign_vul_id.eligibility import (
    EvaluateCveEligibilityCapability,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.report.assign_cve_id_tree import (
    _IsIDAssignmentAuthorityNode,
    _IsOrWillBePubliclyDisclosedNode,
    create_assign_cve_id_tree,
)
from vultron.enums import CVDRole

CASE_ID = "https://example.org/cases/test-cve-001"

_ASSIGN_IF_POSSIBLE_CHILDREN = [
    "IsIDAssignmentAuthority",
    "ProductInCNAScope",
    "IsMostAppropriateCNA",
    "IsOrWillBePubliclyDisclosed",
    "EvaluateCveEligibility",
    "AssignId",
]

#: The per-criterion nodes BTND-05-007 folds into ``EvaluateCveEligibility``.
_RETIRED_CRITERION_NODES = [
    "IdAssignable",
    "IsNotMaliciousCode",
    "IsNotDependencyUpdate",
    "IsNotEOLStatusAlone",
    "IsNotDeliberatelyEducational",
    "IsPubliclyAvailableProduct",
    "NoDuplicateCVE",
    "MeetsEvidenceBar",
    "IsRealVulnerability",
]


def _marker_factory(label, status=Status.SUCCESS):
    def factory(name):
        class _Marker(CallOutBackend):
            def answer(self) -> CallOutAnswer:
                return answer_for(status)

        return _Marker(name=label)

    return factory


def _collect_all_names(tree) -> set:
    """Collect all node names recursively from a tree."""
    names = {tree.name}
    if hasattr(tree, "children"):
        for child in tree.children:
            names |= _collect_all_names(child)
    return names


def _assign_if_possible(tree):
    """Return the ``_AssignIdIfPossible`` Sequence of *tree*."""
    return tree.children[1].children[1].children[0]


def _seed_blackboard(*, cna: bool, publication_intent: bool) -> None:
    """Write the two ProtocolInternal inputs to the blackboard."""
    writer = py_trees.blackboard.Client(name="test_seed")
    writer.register_key("/actor_roles", py_trees.common.Access.WRITE)
    writer.register_key(
        "/publication_intent_set", py_trees.common.Access.WRITE
    )
    writer.set(
        "/actor_roles",
        [CVDRole.CVE_NUMBERING_AUTHORITY] if cna else [CVDRole.VENDOR],
    )
    writer.set("/publication_intent_set", publication_intent)


def _tick(tree) -> None:
    tree.setup_with_descendants()
    tree.tick_once()


# ---------------------------------------------------------------------------
# Basic structure tests
# ---------------------------------------------------------------------------


def test_create_assign_cve_id_tree_returns_behaviour():
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_assign_cve_id_tree_root_name():
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assert tree.name == "AssignVulID"


def test_root_is_fallback_selector():
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.composites.Selector)


def test_root_has_two_children():
    """Root Fallback has IdAssigned and _AssignIdIfInScope."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assert len(tree.children) == 2


def test_root_first_child_is_id_assigned():
    """Root first child is IdAssigned (early-exit guard)."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assert tree.children[0].name == "IdAssigned"


def test_root_second_child_is_assign_id_if_in_scope():
    """Root second child is _AssignIdIfInScope Sequence."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    seq = tree.children[1]
    assert seq.name == "_AssignIdIfInScope"
    assert isinstance(seq, py_trees.composites.Sequence)


# ---------------------------------------------------------------------------
# Tree depth / full structure
# ---------------------------------------------------------------------------


def test_tree_contains_exactly_the_named_nodes():
    """The tree holds exactly its 13 named nodes."""
    expected_names = {
        "AssignVulID",
        "IdAssigned",
        "_AssignIdIfInScope",
        "InScope",
        "_AssignOrRequestId",
        "_AssignIdIfPossible",
        *_ASSIGN_IF_POSSIBLE_CHILDREN,
        "RequestId",
    }
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assert _collect_all_names(tree) == expected_names


def test_assign_if_possible_children_order():
    """_AssignIdIfPossible runs the gates cheapest-first, then AssignId."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    names = [child.name for child in _assign_if_possible(tree).children]
    assert names == _ASSIGN_IF_POSSIBLE_CHILDREN


@pytest.mark.spec("BTND-05-007")
@pytest.mark.parametrize("retired_name", _RETIRED_CRITERION_NODES)
def test_no_per_criterion_eligibility_nodes(retired_name):
    """No eligibility criterion is its own node (BTND-05-007)."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assert retired_name not in _collect_all_names(tree)


@pytest.mark.spec("BTND-05-007")
def test_eligibility_is_one_call_out_leaf():
    """EvaluateCveEligibility is a single leaf, not a composite subtree."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    node = _assign_if_possible(tree).children[4]
    assert node.name == "EvaluateCveEligibility"
    assert not isinstance(unwrap_call_out(node), py_trees.composites.Composite)


@pytest.mark.spec("BTND-05-007")
def test_bundle_has_one_eligibility_factory():
    """The bundle exposes one eligibility factory and no per-criterion ones."""
    names = {f.name for f in dataclasses.fields(AssignCveIdCallOutBundle)}
    assert names == {
        "id_assigned_factory",
        "in_scope_factory",
        "product_in_cna_scope_factory",
        "is_most_appropriate_cna_factory",
        "evaluate_cve_eligibility_factory",
        "assign_id_factory",
        "request_id_factory",
    }


def test_protocol_internal_nodes_are_inline():
    """ProtocolInternal nodes are the correct inline classes (no factory seam)."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assign_if_possible = _assign_if_possible(tree)
    assert isinstance(
        assign_if_possible.children[0], _IsIDAssignmentAuthorityNode
    )
    assert isinstance(
        assign_if_possible.children[3], _IsOrWillBePubliclyDisclosedNode
    )


# ---------------------------------------------------------------------------
# DETERMINISTIC default tests
# ---------------------------------------------------------------------------


def test_default_id_assigned_is_always_fail():
    """DETERMINISTIC default: IdAssigned is AlwaysFail (p=0.25, BT-23-002)."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assert isinstance(unwrap_call_out(tree.children[0]), AlwaysFail)


def test_default_in_scope_is_always_succeed():
    """DETERMINISTIC default: InScope is AlwaysSucceed."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    in_scope = tree.children[1].children[0]
    assert isinstance(unwrap_call_out(in_scope), AlwaysSucceed)


def test_default_evaluate_cve_eligibility_writes_outputs():
    """DETERMINISTIC default: EvaluateCveEligibility is the output-writing backend."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    node = _assign_if_possible(tree).children[4]
    assert isinstance(
        unwrap_call_out(node), DeterministicEvaluateCveEligibility
    )


def test_default_assign_id_is_always_succeed():
    """DETERMINISTIC default: AssignId is AlwaysSucceed."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assign_id = _assign_if_possible(tree).children[5]
    assert isinstance(unwrap_call_out(assign_id), AlwaysSucceed)


def test_default_request_id_is_always_succeed():
    """DETERMINISTIC default: RequestId is AlwaysSucceed."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assign_or_request = tree.children[1].children[1]
    request_id = assign_or_request.children[1]
    assert isinstance(unwrap_call_out(request_id), AlwaysSucceed)


def test_deterministic_singleton_accepted():
    tree = create_assign_cve_id_tree(
        case_id=CASE_ID, call_out=ASSIGN_CVE_ID_DETERMINISTIC
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_none_call_out_uses_deterministic():
    """Passing call_out=None uses the DETERMINISTIC default."""
    tree_default = create_assign_cve_id_tree(case_id=CASE_ID)
    tree_none = create_assign_cve_id_tree(case_id=CASE_ID, call_out=None)
    assert type(tree_default) is type(tree_none)
    assert tree_default.name == tree_none.name


# ---------------------------------------------------------------------------
# EvaluateCveEligibility contract (BTND-05-008, BT-18-002, BT-23-013)
# ---------------------------------------------------------------------------


@pytest.mark.spec("BTND-05-008")
def test_reference_rules_edition_is_4_1_0():
    """The reference implementation follows CNA Operational Rules v4.1.0."""
    assert CNA_RULES_REFERENCE_EDITION == "4.1.0"


#: The outputs BTND-05-008 names for the eligibility capability.
_ELIGIBILITY_OUTPUTS = {
    CVE_ELIGIBILITY_VERDICT_KEY: bool,
    CVE_ELIGIBILITY_RATIONALE_KEY: str,
}


@pytest.mark.spec("BTND-05-008")
@pytest.mark.spec("BT-18-012")
def test_eligibility_contract_declares_verdict_and_rationale():
    """The eligibility ports declare a bool verdict and a str rationale."""
    ports = EvaluateCveEligibilityCapability.OUTPUT_PORTS
    assert {k: p.data_type for k, p in ports.items()} == _ELIGIBILITY_OUTPUTS
    assert all(p.required for p in ports.values())


@pytest.mark.spec("BTND-05-008")
@pytest.mark.parametrize(
    "contract_owner",
    ["core_default", "fuzzer"],
)
def test_eligibility_docstring_documents_edition_and_outputs(contract_owner):
    """Both backends name the edition and bind to the one declaration."""
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        EvaluateCveEligibility,
    )

    cls = {
        "core_default": DeterministicEvaluateCveEligibility,
        "fuzzer": EvaluateCveEligibility,
    }[contract_owner]
    assert f"v{CNA_RULES_REFERENCE_EDITION}" in (cls.__doc__ or "")
    assert cls.declaration() is EvaluateCveEligibilityCapability
    declared = EvaluateCveEligibilityCapability.__doc__ or ""
    assert "Blackboard contract (BT-18-001)" in declared
    for key, typ in _ELIGIBILITY_OUTPUTS.items():
        assert f"{key}: {typ.__name__}" in declared
    assert cls.contract.outputs == _ELIGIBILITY_OUTPUTS


@pytest.mark.spec("BT-23-013")
def test_deterministic_default_writes_declared_outputs_on_success():
    """The DETERMINISTIC default gives both declared outputs on yes (BT-23-013)."""
    node = DeterministicEvaluateCveEligibility("EvaluateCveEligibility")
    # no setup(): the seam must still write the outputs
    assert tick_call_out(node) == Status.SUCCESS
    storage = py_trees.blackboard.Blackboard.storage
    assert storage[f"/{CVE_ELIGIBILITY_VERDICT_KEY}"] is True
    rationale = storage[f"/{CVE_ELIGIBILITY_RATIONALE_KEY}"]
    assert isinstance(rationale, str)
    assert CNA_RULES_REFERENCE_EDITION in rationale


@pytest.mark.parametrize(
    "roll,expected", [(0.0, Status.SUCCESS), (0.99, Status.FAILURE)]
)
@pytest.mark.spec("BT-18-003")
def test_stochastic_eligibility_writes_outputs_only_on_success(
    monkeypatch, roll, expected
):
    """The fuzzer gives type-conformant outputs on yes only (BT-18-003)."""
    from vultron.demo.fuzzer import base
    from vultron.demo.fuzzer.call_out_point import EvaluatorCallOutPoint
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        EvaluateCveEligibility,
    )

    assert issubclass(EvaluateCveEligibility, EvaluatorCallOutPoint)
    monkeypatch.setattr(base.random, "random", lambda: roll)
    node = EvaluateCveEligibility()
    node.setup()
    assert tick_call_out(node) == expected
    storage = py_trees.blackboard.Blackboard.storage
    for key, typ in _ELIGIBILITY_OUTPUTS.items():
        if expected == Status.SUCCESS:
            assert isinstance(storage[f"/{key}"], typ)
        else:
            assert f"/{key}" not in storage


# ---------------------------------------------------------------------------
# Tick behaviour: the CNA direct path and its fallbacks
# ---------------------------------------------------------------------------


def _path_bundle(eligibility_status=Status.SUCCESS):
    """DETERMINISTIC bundle whose eligibility backend returns *eligibility_status*."""
    return dataclasses.replace(
        ASSIGN_CVE_ID_DETERMINISTIC,
        evaluate_cve_eligibility_factory=_marker_factory(  # type: ignore[arg-type]
            "EvaluateCveEligibility", eligibility_status
        ),
    )


def test_cna_with_publication_intent_and_eligible_assigns_directly():
    """A CNA with publication intent and an eligible vul takes AssignId."""
    _seed_blackboard(cna=True, publication_intent=True)
    tree = create_assign_cve_id_tree(case_id=CASE_ID, call_out=_path_bundle())
    _tick(tree)
    assert tree.status == Status.SUCCESS
    assign_if_possible = _assign_if_possible(tree)
    assert assign_if_possible.status == Status.SUCCESS
    assert assign_if_possible.children[5].status == Status.SUCCESS
    request_id = tree.children[1].children[1].children[1]
    assert request_id.status == Status.INVALID


def test_ineligible_vul_falls_back_to_request_id():
    """EvaluateCveEligibility FAILURE skips AssignId and requests an ID."""
    _seed_blackboard(cna=True, publication_intent=True)
    tree = create_assign_cve_id_tree(
        case_id=CASE_ID, call_out=_path_bundle(Status.FAILURE)
    )
    _tick(tree)
    assert tree.status == Status.SUCCESS
    assign_if_possible = _assign_if_possible(tree)
    assert assign_if_possible.status == Status.FAILURE
    assert assign_if_possible.children[5].status == Status.INVALID
    request_id = tree.children[1].children[1].children[1]
    assert request_id.status == Status.SUCCESS


def test_no_publication_intent_skips_eligibility_and_requests_id():
    """Without publication intent the eligibility call-out is never consulted."""
    _seed_blackboard(cna=True, publication_intent=False)
    tree = create_assign_cve_id_tree(case_id=CASE_ID, call_out=_path_bundle())
    _tick(tree)
    assert tree.status == Status.SUCCESS
    assign_if_possible = _assign_if_possible(tree)
    assert assign_if_possible.status == Status.FAILURE
    assert assign_if_possible.children[4].status == Status.INVALID
    request_id = tree.children[1].children[1].children[1]
    assert request_id.status == Status.SUCCESS


def test_non_cna_requests_id_without_eligibility_check():
    """A non-CNA actor never reaches EvaluateCveEligibility."""
    _seed_blackboard(cna=False, publication_intent=True)
    tree = create_assign_cve_id_tree(case_id=CASE_ID, call_out=_path_bundle())
    _tick(tree)
    assert tree.status == Status.SUCCESS
    assert _assign_if_possible(tree).children[4].status == Status.INVALID
    request_id = tree.children[1].children[1].children[1]
    assert request_id.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# STOCHASTIC bundle tests
# ---------------------------------------------------------------------------


def test_stochastic_bundle_produces_fuzzer_nodes():
    """STOCHASTIC bundle produces fuzzer classes for all call-out points."""
    from vultron.demo.fuzzer.bundles.assign_cve_id import (
        ASSIGN_CVE_ID_STOCHASTIC,
    )
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        AssignId,
        EvaluateCveEligibility,
        IdAssigned,
        InScope,
        IsMostAppropriateCNA,
        ProductInCNAScope,
        RequestId,
    )

    tree = create_assign_cve_id_tree(
        case_id=CASE_ID, call_out=ASSIGN_CVE_ID_STOCHASTIC
    )

    assert isinstance(unwrap_call_out(tree.children[0]), IdAssigned)

    assign_if_in_scope = tree.children[1]
    assert isinstance(unwrap_call_out(assign_if_in_scope.children[0]), InScope)

    assign_or_request = assign_if_in_scope.children[1]
    assign_if_possible = assign_or_request.children[0]

    assert isinstance(
        unwrap_call_out(assign_if_possible.children[1]), ProductInCNAScope
    )
    assert isinstance(
        unwrap_call_out(assign_if_possible.children[2]), IsMostAppropriateCNA
    )
    # child[3] is ProtocolInternal (inline) — not a fuzzer node
    assert isinstance(
        unwrap_call_out(assign_if_possible.children[4]),
        EvaluateCveEligibility,
    )
    assert isinstance(
        unwrap_call_out(assign_if_possible.children[5]), AssignId
    )
    assert isinstance(
        unwrap_call_out(assign_or_request.children[1]), RequestId
    )


# ---------------------------------------------------------------------------
# Factory injection tests (per-field)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_name,expected_label",
    [
        ("id_assigned_factory", "CustomIdAssigned"),
        ("in_scope_factory", "CustomInScope"),
        ("product_in_cna_scope_factory", "CustomProductInCNAScope"),
        ("is_most_appropriate_cna_factory", "CustomIsMostAppropriateCNA"),
        (
            "evaluate_cve_eligibility_factory",
            "CustomEvaluateCveEligibility",
        ),
        ("assign_id_factory", "CustomAssignId"),
        ("request_id_factory", "CustomRequestId"),
    ],
)
def test_each_factory_is_injectable(field_name, expected_label):
    """Each call-out factory field of the bundle is replaceable."""
    called = {"called": False}

    def custom_factory(name):
        called["called"] = True
        return _marker_factory(expected_label)(name)

    bundle = AssignCveIdCallOutBundle(**{field_name: custom_factory})  # type: ignore[arg-type]
    tree = create_assign_cve_id_tree(case_id=CASE_ID, call_out=bundle)
    assert called["called"], f"factory {field_name!r} was not called"
    assert expected_label in _collect_all_names(tree), (
        f"Expected node '{expected_label}' not in tree for field {field_name!r}"
    )
