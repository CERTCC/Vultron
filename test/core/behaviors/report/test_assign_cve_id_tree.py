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
"""Tests for the full 21-node CVE ID assignment behavior tree (issue #1817).

Verifies BT-18-004/BT-23-003: bundle parameter accepted and used;
DETERMINISTIC default produces AlwaysSucceed/AlwaysFail nodes;
STOCHASTIC bundle produces the correct fuzzer classes;
IdAssignable subtree structure; factory injection for all 14 call-out points.
(21 nodes = 5 composites + 14 factory call-out leaves + 2 ProtocolInternal leaves.)
"""

import py_trees
import pytest

from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.call_out.bundles.assign_cve_id import (
    ASSIGN_CVE_ID_DETERMINISTIC,
    AssignCveIdCallOutBundle,
)
from vultron.core.behaviors.report.assign_cve_id_tree import (
    _IsIDAssignmentAuthorityNode,
    _IsOrWillBePubliclyDisclosedNode,
    create_assign_cve_id_tree,
)

CASE_ID = "https://example.org/cases/test-cve-001"


def _marker_factory(label):
    def factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    return factory


def _collect_all_names(tree) -> set:
    """Collect all node names recursively from a tree."""
    names = {tree.name}
    if hasattr(tree, "children"):
        for child in tree.children:
            names |= _collect_all_names(child)
    return names


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


def test_tree_contains_all_named_nodes():
    """Full tree contains all 21 named nodes from the spec."""
    expected_names = {
        "AssignVulID",
        "IdAssigned",
        "_AssignIdIfInScope",
        "InScope",
        "_AssignOrRequestId",
        "_AssignIdIfPossible",
        "IsIDAssignmentAuthority",
        "ProductInCNAScope",
        "IsMostAppropriateCNA",
        "IdAssignable",
        "IsNotMaliciousCode",
        "IsNotDependencyUpdate",
        "IsNotEOLStatusAlone",
        "IsNotDeliberatelyEducational",
        "IsOrWillBePubliclyDisclosed",
        "IsPubliclyAvailableProduct",
        "NoDuplicateCVE",
        "MeetsEvidenceBar",
        "IsRealVulnerability",
        "AssignId",
        "RequestId",
    }
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    actual = _collect_all_names(tree)
    for name in expected_names:
        assert name in actual, f"Expected node '{name}' not found in tree"


def test_id_assignable_subtree_has_nine_children():
    """IdAssignable Sequence has exactly 9 children (cheapest-first order)."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    # Traverse: root → _AssignIdIfInScope → _AssignOrRequestId → _AssignIdIfPossible → IdAssignable
    assign_if_in_scope = tree.children[1]
    assign_or_request = assign_if_in_scope.children[1]
    assign_if_possible = assign_or_request.children[0]
    id_assignable = assign_if_possible.children[3]
    assert id_assignable.name == "IdAssignable"
    assert len(id_assignable.children) == 9


def test_id_assignable_children_order():
    """IdAssignable subtree children are in cheapest-first order."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assign_if_possible = tree.children[1].children[1].children[0]
    id_assignable = assign_if_possible.children[3]
    names = [child.name for child in id_assignable.children]
    assert names == [
        "IsNotMaliciousCode",
        "IsNotDependencyUpdate",
        "IsNotEOLStatusAlone",
        "IsNotDeliberatelyEducational",
        "IsOrWillBePubliclyDisclosed",
        "IsPubliclyAvailableProduct",
        "NoDuplicateCVE",
        "MeetsEvidenceBar",
        "IsRealVulnerability",
    ]


def test_protocol_internal_nodes_are_inline():
    """ProtocolInternal nodes are the correct inline classes (no factory seam)."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assign_if_possible = tree.children[1].children[1].children[0]
    # IsIDAssignmentAuthority is first child of _AssignIdIfPossible
    assert isinstance(
        assign_if_possible.children[0], _IsIDAssignmentAuthorityNode
    )
    # IsOrWillBePubliclyDisclosed is 5th child of IdAssignable
    id_assignable = assign_if_possible.children[3]
    assert isinstance(
        id_assignable.children[4], _IsOrWillBePubliclyDisclosedNode
    )


# ---------------------------------------------------------------------------
# DETERMINISTIC default tests
# ---------------------------------------------------------------------------


def test_default_id_assigned_is_always_fail():
    """DETERMINISTIC default: IdAssigned is AlwaysFail (p=0.25, BT-23-002)."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assert isinstance(tree.children[0], AlwaysFail)


def test_default_in_scope_is_always_succeed():
    """DETERMINISTIC default: InScope is AlwaysSucceed."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    in_scope = tree.children[1].children[0]
    assert isinstance(in_scope, AlwaysSucceed)


def test_default_assign_id_is_always_succeed():
    """DETERMINISTIC default: AssignId is AlwaysSucceed."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assign_if_possible = tree.children[1].children[1].children[0]
    assign_id = assign_if_possible.children[4]
    assert isinstance(assign_id, AlwaysSucceed)


def test_default_request_id_is_always_succeed():
    """DETERMINISTIC default: RequestId is AlwaysSucceed."""
    tree = create_assign_cve_id_tree(case_id=CASE_ID)
    assign_or_request = tree.children[1].children[1]
    request_id = assign_or_request.children[1]
    assert isinstance(request_id, AlwaysSucceed)


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
# STOCHASTIC bundle tests
# ---------------------------------------------------------------------------


def test_stochastic_bundle_produces_fuzzer_nodes():
    """STOCHASTIC bundle produces fuzzer classes for all call-out points."""
    from vultron.demo.fuzzer.bundles.assign_cve_id import (
        ASSIGN_CVE_ID_STOCHASTIC,
    )
    from vultron.demo.fuzzer.report_management.assign_vul_id import (
        IdAssigned,
        InScope,
        AssignId,
        RequestId,
        ProductInCNAScope,
        IsMostAppropriateCNA,
        IsNotMaliciousCode,
        IsNotDependencyUpdate,
        IsNotEOLStatusAlone,
        IsNotDeliberatelyEducational,
        IsPubliclyAvailableProduct,
        NoDuplicateCVE,
        MeetsEvidenceBar,
        IsRealVulnerability,
    )

    tree = create_assign_cve_id_tree(
        case_id=CASE_ID, call_out=ASSIGN_CVE_ID_STOCHASTIC
    )

    # IdAssigned (root child 0)
    assert isinstance(tree.children[0], IdAssigned)

    assign_if_in_scope = tree.children[1]
    # InScope (first child of _AssignIdIfInScope)
    assert isinstance(assign_if_in_scope.children[0], InScope)

    assign_or_request = assign_if_in_scope.children[1]
    assign_if_possible = assign_or_request.children[0]

    # ProductInCNAScope, IsMostAppropriateCNA
    assert isinstance(assign_if_possible.children[1], ProductInCNAScope)
    assert isinstance(assign_if_possible.children[2], IsMostAppropriateCNA)

    id_assignable = assign_if_possible.children[3]
    # 9 IdAssignable children
    assert isinstance(id_assignable.children[0], IsNotMaliciousCode)
    assert isinstance(id_assignable.children[1], IsNotDependencyUpdate)
    assert isinstance(id_assignable.children[2], IsNotEOLStatusAlone)
    assert isinstance(id_assignable.children[3], IsNotDeliberatelyEducational)
    # child[4] is ProtocolInternal (inline) — not a fuzzer node
    assert isinstance(id_assignable.children[5], IsPubliclyAvailableProduct)
    assert isinstance(id_assignable.children[6], NoDuplicateCVE)
    assert isinstance(id_assignable.children[7], MeetsEvidenceBar)
    assert isinstance(id_assignable.children[8], IsRealVulnerability)

    # AssignId (last child of _AssignIdIfPossible), RequestId
    assert isinstance(assign_if_possible.children[4], AssignId)
    assert isinstance(assign_or_request.children[1], RequestId)


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
        ("is_not_malicious_code_factory", "CustomIsNotMaliciousCode"),
        ("is_not_dependency_update_factory", "CustomIsNotDependencyUpdate"),
        ("is_not_eol_status_alone_factory", "CustomIsNotEOLStatusAlone"),
        (
            "is_not_deliberately_educational_factory",
            "CustomIsNotDeliberatelyEducational",
        ),
        (
            "is_publicly_available_product_factory",
            "CustomIsPubliclyAvailableProduct",
        ),
        ("no_duplicate_cve_factory", "CustomNoDuplicateCVE"),
        ("meets_evidence_bar_factory", "CustomMeetsEvidenceBar"),
        ("is_real_vulnerability_factory", "CustomIsRealVulnerability"),
        ("assign_id_factory", "CustomAssignId"),
        ("request_id_factory", "CustomRequestId"),
    ],
)
def test_each_factory_is_injectable(field_name, expected_label):
    """Each of the 14 call-out factory fields is replaceable."""
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=expected_label)

    bundle = AssignCveIdCallOutBundle(**{field_name: custom_factory})  # type: ignore[arg-type]
    tree = create_assign_cve_id_tree(case_id=CASE_ID, call_out=bundle)
    assert sentinel["called"], f"factory {field_name!r} was not called"
    assert expected_label in _collect_all_names(
        tree
    ), f"Expected node '{expected_label}' not in tree for field {field_name!r}"
