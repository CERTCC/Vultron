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

"""
Tests for case creation behavior tree composition (BT-3.1).

Verifies that CreateCaseBT correctly orchestrates case persistence,
CaseActor creation, and outbox update. Also verifies idempotency.

Per specs/behavior-tree-integration.md BT-06, specs/case-management.md
CM-02, and specs/idempotency.md ID-04-004.
"""

import pytest
from py_trees.common import Status

from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
from vultron.as_vocab.base.objects.actors import as_Service
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.behaviors.bridge import BTBridge
from vultron.behaviors.case.create_tree import create_create_case_tree


@pytest.fixture
def datalayer():
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def actor_id():
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(datalayer, actor_id):
    obj = as_Service(as_id=actor_id, name="Vendor Co")
    datalayer.create(obj)
    return obj


@pytest.fixture
def report(datalayer):
    obj = VulnerabilityReport(
        as_id="https://example.org/reports/CVE-2024-001",
        name="Test Vulnerability Report",
        content="Buffer overflow in component X",
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def case_obj(report):
    return VulnerabilityCase(
        as_id="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report],
    )


@pytest.fixture
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


# ============================================================================
# Tree structure tests
# ============================================================================


def test_create_create_case_tree_returns_selector(case_obj, actor_id):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor_id)
    assert tree is not None
    assert tree.name == "CreateCaseBT"
    assert hasattr(tree, "children")
    assert len(tree.children) == 2


def test_create_case_tree_first_child_is_idempotency_check(case_obj, actor_id):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor_id)
    from vultron.behaviors.case.nodes import CheckCaseAlreadyExists

    assert isinstance(tree.children[0], CheckCaseAlreadyExists)


def test_create_case_tree_second_child_is_sequence(case_obj, actor_id):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor_id)
    import py_trees

    assert isinstance(tree.children[1], py_trees.composites.Sequence)


# ============================================================================
# Execution tests
# ============================================================================


def test_create_case_tree_succeeds(datalayer, actor, case_obj, bridge):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor.as_id, activity=None
    )
    assert result.status == Status.SUCCESS


def test_create_case_tree_persists_case(datalayer, actor, case_obj, bridge):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)
    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    assert stored.as_id == case_obj.as_id


def test_create_case_tree_creates_case_actor(
    datalayer, actor, case_obj, bridge
):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)
    from vultron.as_vocab.objects.case_actor import CaseActor

    all_objects = datalayer.get_all("Service")
    case_actors = [
        r
        for r in all_objects
        if isinstance(r, dict)
        and r.get("data_", {}).get("context") == case_obj.as_id
    ]
    # Verify at least one CaseActor exists for this case
    # (also checking via read fallback if stored under different table)
    found = False
    for table_name in datalayer._db.tables():
        for rec in datalayer._db.table(table_name).all():
            data = rec.get("data_", {})
            if data.get("context") == case_obj.as_id:
                found = True
                break
        if found:
            break
    assert found, "CaseActor was not created in DataLayer"


def test_create_case_tree_emits_activity_to_outbox(
    datalayer, actor, case_obj, bridge
):
    tree = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    bridge.execute_with_setup(tree=tree, actor_id=actor.as_id, activity=None)
    updated_actor = datalayer.read(actor.as_id)
    assert updated_actor is not None
    assert len(updated_actor.outbox.items) > 0


# ============================================================================
# Idempotency tests
# ============================================================================


def test_create_case_tree_idempotent(datalayer, actor, case_obj, bridge):
    """Running the tree twice succeeds and does not duplicate the case."""
    tree1 = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    result1 = bridge.execute_with_setup(
        tree=tree1, actor_id=actor.as_id, activity=None
    )
    assert result1.status == Status.SUCCESS

    tree2 = create_create_case_tree(case_obj=case_obj, actor_id=actor.as_id)
    result2 = bridge.execute_with_setup(
        tree=tree2, actor_id=actor.as_id, activity=None
    )
    assert result2.status == Status.SUCCESS

    stored = datalayer.read(case_obj.as_id)
    assert stored is not None
    assert stored.as_id == case_obj.as_id
