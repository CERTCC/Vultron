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
"""Tests for the notification-loop behavior tree (Production Collapse 3).

Verifies ADR-0029 / BT-20-003 and BT-23-003:
- AC-1: InjectParticipant/InjectVendor/InjectCoordinator/InjectOther eliminated
  as separate leaves; replaced by suggest_*_factory call-out points.
- AC-2: Each sub-loop writes the appropriate suggested_roles_{case_id_segment}
  blackboard key before invoking its trigger factory.
- AC-3: Outer loop structure (typed sub-loops, AllPartiesKnown, TotalEffortLimitMet)
  preserved.
- AC-4: ADR-0025 factory pattern applied to every call-out point (via bundle).
- BT-23-003: DETERMINISTIC default uses AlwaysSucceed/AlwaysFail per ceiling/floor rule.
"""

import pytest
import py_trees
from py_trees.common import Status

from vultron.core.behaviors.report.report_to_others_tree import (
    _WriteRolesNode,
    create_report_to_others_tree,
)
from vultron.demo.fuzzer.base import AlwaysFail, AlwaysSucceed
from vultron.demo.fuzzer.bundles.report_to_others import (
    REPORT_TO_OTHERS_DETERMINISTIC,
    REPORT_TO_OTHERS_STOCHASTIC,
    ReportToOthersCallOutBundle,
)
from vultron.demo.fuzzer.report_management.report_to_others import (
    AllPartiesKnown,
    InjectCoordinator,
    InjectOther,
    InjectVendor,
    MoreCoordinators,
    MoreOthers,
    MoreVendors,
    TotalEffortLimitMet,
)
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/test-001"
CASE_ID_SEGMENT = CASE_ID.split("/")[-1]


@pytest.fixture(autouse=True)
def clear_blackboard():
    """Clear py_trees global blackboard state between tests."""
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def _marker_factory(label):
    def factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return Status.SUCCESS

        return _Marker(name=label)

    return factory


# ---------------------------------------------------------------------------
# _WriteRolesNode unit tests
# ---------------------------------------------------------------------------


def test_write_roles_node_defaults():
    node = _WriteRolesNode(roles=[CVDRole.VENDOR], case_id=CASE_ID)
    assert node.roles == [CVDRole.VENDOR]
    assert node.case_id == CASE_ID


def test_write_vendor_roles_writes_blackboard():
    """WriteRolesNode writes suggested_roles_{id_segment} on tick."""
    node = _WriteRolesNode(
        roles=[CVDRole.VENDOR],
        case_id=CASE_ID,
        name="WriteVendorRoles",
    )
    node.setup()
    status = node.update()
    assert status == Status.SUCCESS
    key = f"/suggested_roles_{CASE_ID_SEGMENT}"
    assert key in py_trees.blackboard.Blackboard.storage
    assert py_trees.blackboard.Blackboard.storage[key] == [CVDRole.VENDOR]


def test_write_coordinator_roles_writes_blackboard():
    node = _WriteRolesNode(
        roles=[CVDRole.COORDINATOR],
        case_id=CASE_ID,
        name="WriteCoordinatorRoles",
    )
    node.setup()
    node.update()
    key = f"/suggested_roles_{CASE_ID_SEGMENT}"
    assert py_trees.blackboard.Blackboard.storage[key] == [CVDRole.COORDINATOR]


def test_write_other_roles_writes_blackboard():
    node = _WriteRolesNode(
        roles=[CVDRole.OTHER],
        case_id=CASE_ID,
        name="WriteOtherRoles",
    )
    node.setup()
    node.update()
    key = f"/suggested_roles_{CASE_ID_SEGMENT}"
    assert py_trees.blackboard.Blackboard.storage[key] == [CVDRole.OTHER]


# ---------------------------------------------------------------------------
# Tree structure — AC-3
# ---------------------------------------------------------------------------


def test_create_report_to_others_tree_returns_behaviour():
    tree = create_report_to_others_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_report_to_others_tree_root_name():
    tree = create_report_to_others_tree(case_id=CASE_ID)
    assert tree.name == "ReportToOthersBT"


def test_root_is_sequence():
    tree = create_report_to_others_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.composites.Sequence)


def test_root_has_five_direct_children():
    """AC-3: AllPartiesKnown, TotalEffortLimitMet, and three sub-loops."""
    tree = create_report_to_others_tree(case_id=CASE_ID)
    assert len(tree.children) == 5


def test_root_children_names():
    tree = create_report_to_others_tree(case_id=CASE_ID)
    names = [c.name for c in tree.children]
    assert names[0] == "AllPartiesKnown"
    assert names[1] == "TotalEffortLimitMet"
    assert names[2] == "VendorSubLoop"
    assert names[3] == "CoordinatorSubLoop"
    assert names[4] == "OtherSubLoop"


def test_sub_loops_are_selectors():
    tree = create_report_to_others_tree(case_id=CASE_ID)
    for sub_loop in tree.children[2:]:
        assert isinstance(
            sub_loop, py_trees.composites.Selector
        ), f"{sub_loop.name} should be a Selector"


# ---------------------------------------------------------------------------
# AC-1: eliminated nodes absent as separate leaves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "eliminated_class_name",
    [
        "InjectParticipant",
        "InjectVendor",
        "InjectCoordinator",
        "InjectOther",
        "RemoveRecipient",
        "SetRcptQrmR",
    ],
)
def test_eliminated_actuator_nodes_not_top_level_leaves(eliminated_class_name):
    """AC-1: eliminated nodes are not direct children of the root."""
    tree = create_report_to_others_tree(case_id=CASE_ID)
    direct_class_names = [c.__class__.__name__ for c in tree.children]
    assert eliminated_class_name not in direct_class_names


def test_default_outer_guards_are_deterministic():
    """DETERMINISTIC default: AllPartiesKnown(p=0.5)→Succeed, TotalEffortLimitMet(p=0.1)→Fail."""
    tree = create_report_to_others_tree(case_id=CASE_ID)
    assert isinstance(tree.children[0], AlwaysSucceed)
    assert isinstance(tree.children[1], AlwaysFail)


def test_stochastic_bundle_outer_guards_are_fuzzer_nodes():
    """STOCHASTIC bundle: outer guard nodes are the correct fuzzer classes."""
    tree = create_report_to_others_tree(
        case_id=CASE_ID, call_out=REPORT_TO_OTHERS_STOCHASTIC
    )
    assert isinstance(tree.children[0], AllPartiesKnown)
    assert isinstance(tree.children[1], TotalEffortLimitMet)


# ---------------------------------------------------------------------------
# AC-4: Factory pattern — Evaluator factories via bundle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,label,child_index",
    [
        ("all_parties_known_factory", "APK", 0),
        ("total_effort_limit_factory", "TEL", 1),
    ],
)
def test_evaluator_factory_wired(field, label, child_index):
    """AC-4: each Evaluator factory field is wired into the root Sequence via bundle."""
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return Status.SUCCESS

        return _Marker(name=label)

    bundle = ReportToOthersCallOutBundle(**{field: custom_factory})  # type: ignore[arg-type]
    tree = create_report_to_others_tree(case_id=CASE_ID, call_out=bundle)
    assert sentinel["called"]
    assert tree.children[child_index].name == label


# ---------------------------------------------------------------------------
# AC-3/AC-4: Sub-loop factory wiring
# ---------------------------------------------------------------------------


def _find_node_by_name_recursive(root, name):
    """DFS search for a node by name."""
    if root.name == name:
        return root
    children = getattr(root, "children", [])
    for child in children:
        found = _find_node_by_name_recursive(child, name)
        if found is not None:
            return found
    if hasattr(root, "child"):
        return _find_node_by_name_recursive(root.child, name)
    return None


@pytest.mark.parametrize(
    "more_field,more_label,suggest_field,suggest_label,loop_name",
    [
        (
            "more_vendors_factory",
            "MV",
            "suggest_vendor_factory",
            "SV",
            "VendorSubLoop",
        ),
        (
            "more_coordinators_factory",
            "MC",
            "suggest_coordinator_factory",
            "SC",
            "CoordinatorSubLoop",
        ),
        (
            "more_others_factory",
            "MO",
            "suggest_other_factory",
            "SO",
            "OtherSubLoop",
        ),
    ],
)
def test_sub_loop_factories_wired(
    more_field, more_label, suggest_field, suggest_label, loop_name
):
    """AC-3/AC-4: each sub-loop factory pair is wired into the correct sub-loop via bundle."""
    bundle = ReportToOthersCallOutBundle(
        **{
            more_field: _marker_factory(more_label),  # type: ignore[arg-type]
            suggest_field: _marker_factory(suggest_label),  # type: ignore[arg-type]
        }
    )
    tree = create_report_to_others_tree(case_id=CASE_ID, call_out=bundle)
    sub_loop = _find_node_by_name_recursive(tree, loop_name)
    assert sub_loop is not None
    tree_str = py_trees.display.ascii_tree(sub_loop)
    assert more_label in tree_str
    assert suggest_label in tree_str


# ---------------------------------------------------------------------------
# AC-2: WriteRolesNode is present and correctly placed before trigger factory
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "loop_name,write_node_name,expected_role",
    [
        ("VendorSubLoop", "WriteVendorRoles", CVDRole.VENDOR),
        ("CoordinatorSubLoop", "WriteCoordinatorRoles", CVDRole.COORDINATOR),
        ("OtherSubLoop", "WriteOtherRoles", CVDRole.OTHER),
    ],
)
def test_write_roles_node_present_in_sub_loop(
    loop_name, write_node_name, expected_role
):
    """AC-2: each sub-loop contains a WriteRolesNode before the trigger."""
    tree = create_report_to_others_tree(case_id=CASE_ID)
    write_node = _find_node_by_name_recursive(tree, write_node_name)
    assert (
        write_node is not None
    ), f"WriteRolesNode '{write_node_name}' not found in {loop_name}"
    assert isinstance(write_node, _WriteRolesNode)
    assert write_node.roles == [expected_role]


def test_vendor_write_roles_node_precedes_trigger():
    """AC-2: WriteVendorRoles is an earlier sibling of SuggestVendor in DoVendorSubLoop."""
    tree = create_report_to_others_tree(case_id=CASE_ID)
    execute_seq = _find_node_by_name_recursive(tree, "DoVendorSubLoop")
    assert execute_seq is not None
    child_names = [c.name for c in execute_seq.children]
    write_idx = child_names.index("WriteVendorRoles")
    suggest_idx = child_names.index("SuggestVendor")
    assert write_idx < suggest_idx


def test_coordinator_write_roles_node_precedes_trigger():
    """AC-2: WriteCoordinatorRoles is an earlier sibling of SuggestCoordinator."""
    tree = create_report_to_others_tree(case_id=CASE_ID)
    execute_seq = _find_node_by_name_recursive(tree, "DoCoordinatorSubLoop")
    assert execute_seq is not None
    child_names = [c.name for c in execute_seq.children]
    write_idx = child_names.index("WriteCoordinatorRoles")
    suggest_idx = child_names.index("SuggestCoordinator")
    assert write_idx < suggest_idx


def test_other_write_roles_node_precedes_trigger():
    """AC-2: WriteOtherRoles is an earlier sibling of SuggestOther."""
    tree = create_report_to_others_tree(case_id=CASE_ID)
    execute_seq = _find_node_by_name_recursive(tree, "DoOtherSubLoop")
    assert execute_seq is not None
    child_names = [c.name for c in execute_seq.children]
    write_idx = child_names.index("WriteOtherRoles")
    suggest_idx = child_names.index("SuggestOther")
    assert write_idx < suggest_idx


# ---------------------------------------------------------------------------
# AC-2 behavioral: WriteRolesNode writes correct role on sub-loop execution
# ---------------------------------------------------------------------------


def _make_always_succeed_factory(name):
    class _AS(py_trees.behaviour.Behaviour):
        def update(self):
            return Status.SUCCESS

    return _AS(name=name)


def _make_always_fail_factory(name):
    class _AF(py_trees.behaviour.Behaviour):
        def update(self):
            return Status.FAILURE

    return _AF(name=name)


@pytest.mark.parametrize(
    "more_field,suggest_field,expected_role",
    [
        ("more_vendors_factory", "suggest_vendor_factory", CVDRole.VENDOR),
        (
            "more_coordinators_factory",
            "suggest_coordinator_factory",
            CVDRole.COORDINATOR,
        ),
        ("more_others_factory", "suggest_other_factory", CVDRole.OTHER),
    ],
)
def test_write_roles_key_written_when_sub_loop_executes(
    more_field, suggest_field, expected_role
):
    """AC-2 behavioral: ticking a sub-loop with MoreX=SUCCESS writes the correct roles key.

    All other sub-loops' more-factories are forced to always-fail so their
    Inverter arms succeed as graceful no-ops — the test target sub-loop is the
    only one that executes, keeping the blackboard key unambiguous.
    """
    _all_more_fields = [
        "more_vendors_factory",
        "more_coordinators_factory",
        "more_others_factory",
    ]
    more_kwargs = {
        k: (
            _make_always_succeed_factory
            if k == more_field
            else _make_always_fail_factory
        )
        for k in _all_more_fields
    }
    bundle = ReportToOthersCallOutBundle(
        all_parties_known_factory=_make_always_succeed_factory,  # type: ignore[arg-type]
        total_effort_limit_factory=_make_always_succeed_factory,  # type: ignore[arg-type]
        **{suggest_field: _make_always_succeed_factory},  # type: ignore[arg-type]
        **more_kwargs,  # type: ignore[arg-type]
    )
    tree = create_report_to_others_tree(case_id=CASE_ID, call_out=bundle)
    tree.setup_with_descendants()
    tree.tick_once()

    key = f"/suggested_roles_{CASE_ID_SEGMENT}"
    assert key in py_trees.blackboard.Blackboard.storage
    assert py_trees.blackboard.Blackboard.storage[key] == [expected_role]


# ---------------------------------------------------------------------------
# AC-3: STOCHASTIC bundle uses correct fuzzer node types
# ---------------------------------------------------------------------------


def test_stochastic_more_vendors_factory():
    """STOCHASTIC bundle more_vendors_factory produces a MoreVendors node."""
    node = REPORT_TO_OTHERS_STOCHASTIC.more_vendors_factory("MoreVendors")
    assert isinstance(node, MoreVendors)


def test_stochastic_more_coordinators_factory():
    """STOCHASTIC bundle more_coordinators_factory produces a MoreCoordinators node."""
    node = REPORT_TO_OTHERS_STOCHASTIC.more_coordinators_factory(
        "MoreCoordinators"
    )
    assert isinstance(node, MoreCoordinators)


def test_stochastic_more_others_factory():
    """STOCHASTIC bundle more_others_factory produces a MoreOthers node."""
    node = REPORT_TO_OTHERS_STOCHASTIC.more_others_factory("MoreOthers")
    assert isinstance(node, MoreOthers)


# ---------------------------------------------------------------------------
# AC-1/AC-4: STOCHASTIC bundle suggest_* factories use InjectX fuzzer stubs
# ---------------------------------------------------------------------------


def test_stochastic_suggest_vendor_factory():
    """STOCHASTIC bundle suggest_vendor_factory produces an InjectVendor node."""
    node = REPORT_TO_OTHERS_STOCHASTIC.suggest_vendor_factory("SuggestVendor")
    assert isinstance(node, InjectVendor)


def test_stochastic_suggest_coordinator_factory():
    """STOCHASTIC bundle suggest_coordinator_factory produces an InjectCoordinator node."""
    node = REPORT_TO_OTHERS_STOCHASTIC.suggest_coordinator_factory(
        "SuggestCoordinator"
    )
    assert isinstance(node, InjectCoordinator)


def test_stochastic_suggest_other_factory():
    """STOCHASTIC bundle suggest_other_factory produces an InjectOther node."""
    node = REPORT_TO_OTHERS_STOCHASTIC.suggest_other_factory("SuggestOther")
    assert isinstance(node, InjectOther)


# ---------------------------------------------------------------------------
# AC-4: All factories replaceable simultaneously via bundle
# ---------------------------------------------------------------------------


def test_all_factories_replaceable():
    """AC-4: every factory field can be replaced simultaneously via a bundle."""
    bundle = ReportToOthersCallOutBundle(
        all_parties_known_factory=_marker_factory("APK"),  # type: ignore[arg-type]
        total_effort_limit_factory=_marker_factory("TEL"),  # type: ignore[arg-type]
        more_vendors_factory=_marker_factory("MV"),  # type: ignore[arg-type]
        more_coordinators_factory=_marker_factory("MC"),  # type: ignore[arg-type]
        more_others_factory=_marker_factory("MO"),  # type: ignore[arg-type]
        suggest_vendor_factory=_marker_factory("SV"),  # type: ignore[arg-type]
        suggest_coordinator_factory=_marker_factory("SC"),  # type: ignore[arg-type]
        suggest_other_factory=_marker_factory("SO"),  # type: ignore[arg-type]
    )
    tree = create_report_to_others_tree(case_id=CASE_ID, call_out=bundle)
    tree_str = py_trees.display.ascii_tree(tree)
    for label in ("APK", "TEL", "MV", "MC", "MO", "SV", "SC", "SO"):
        assert label in tree_str


def test_deterministic_singleton_accepted():
    tree = create_report_to_others_tree(
        case_id=CASE_ID, call_out=REPORT_TO_OTHERS_DETERMINISTIC
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)
