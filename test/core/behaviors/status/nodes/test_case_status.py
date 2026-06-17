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

"""Unit tests for case status workflow nodes (submodule path).

Verifies CASE_STATUS_ALREADY_PRESENT, CheckCaseStatusIdempotencyNode,
ValidateCaseStatusTransitionNode, and AppendCaseStatusToCaseNode imported
directly from the submodule.

Per issue #758 AC-1, AC-2, AC-3.
"""

import pytest
import py_trees
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.nodes.case_status import (
    CASE_STATUS_ALREADY_PRESENT,
    AppendCaseStatusToCaseNode,
    CheckCaseStatusIdempotencyNode,
    ValidateCaseStatusTransitionNode,
)
from vultron.core.states.em import EM
from vultron.wire.as2.vocab.objects.case_status import CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-01"
STATUS_ID = "https://example.org/cases/case-01/statuses/s1"
STATUS2_ID = "https://example.org/cases/case-01/statuses/s2"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def case():
    return VulnerabilityCase(id_=CASE_ID, name="Test Case")


@pytest.fixture
def status_obj():
    return CaseStatus(id_=STATUS_ID, context=CASE_ID)


@pytest.fixture
def populated_dl(dl, case, status_obj):
    dl.create(case)
    dl.create(status_obj)
    return dl


@pytest.fixture
def populated_bridge(populated_dl):
    return BTBridge(datalayer=populated_dl)


# ---------------------------------------------------------------------------
# CASE_STATUS_ALREADY_PRESENT constant
# ---------------------------------------------------------------------------


def test_case_status_already_present_constant():
    assert CASE_STATUS_ALREADY_PRESENT == "case_status_already_present"


# ---------------------------------------------------------------------------
# CheckCaseStatusIdempotencyNode
# ---------------------------------------------------------------------------


class TestCheckCaseStatusIdempotencyNode:
    def test_new_status_succeeds(self, populated_bridge):
        node = CheckCaseStatusIdempotencyNode(
            case_id=CASE_ID, status_id=STATUS_ID
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_duplicate_status_fails_with_sentinel(self, populated_dl):
        case = populated_dl.read(CASE_ID)
        status = populated_dl.read(STATUS_ID)
        case.case_statuses.append(status)
        populated_dl.save(case)

        bridge = BTBridge(datalayer=populated_dl)
        node = CheckCaseStatusIdempotencyNode(
            case_id=CASE_ID, status_id=STATUS_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert node.feedback_message == CASE_STATUS_ALREADY_PRESENT

    def test_missing_case_fails(self, bridge):
        node = CheckCaseStatusIdempotencyNode(
            case_id="https://example.org/cases/missing", status_id=STATUS_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# ValidateCaseStatusTransitionNode
# ---------------------------------------------------------------------------


class TestValidateCaseStatusTransitionNode:
    def test_first_status_always_passes(self, populated_bridge, status_obj):
        node = ValidateCaseStatusTransitionNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=status_obj,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_valid_em_transition_passes(self, populated_bridge, status_obj):
        # Default case has a CaseStatus with em_state=EM.NONE;
        # NONE → PROPOSED is a valid forward transition.
        new_status = CaseStatus(
            id_=STATUS2_ID, context=CASE_ID, em_state=EM.PROPOSED
        )
        populated_bridge.datalayer.save(new_status)

        node = ValidateCaseStatusTransitionNode(
            case_id=CASE_ID,
            status_id=STATUS2_ID,
            status_obj_fallback=new_status,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_invalid_em_transition_fails(self, populated_bridge):
        # Default case has a CaseStatus with em_state=EM.NONE;
        # NONE → ACTIVE is invalid (skips PROPOSED).
        new_status = CaseStatus(
            id_=STATUS2_ID, context=CASE_ID, em_state=EM.ACTIVE
        )
        populated_bridge.datalayer.save(new_status)

        node = ValidateCaseStatusTransitionNode(
            case_id=CASE_ID,
            status_id=STATUS2_ID,
            status_obj_fallback=new_status,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# AppendCaseStatusToCaseNode
# ---------------------------------------------------------------------------


class TestAppendCaseStatusToCaseNode:
    def test_appends_status(self, populated_bridge, populated_dl, status_obj):
        case_before = populated_dl.read(CASE_ID)
        initial_count = len(case_before.case_statuses)

        node = AppendCaseStatusToCaseNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=status_obj,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

        case_after = populated_dl.read(CASE_ID)
        assert len(case_after.case_statuses) == initial_count + 1

    def test_missing_case_fails(self, bridge, status_obj):
        node = AppendCaseStatusToCaseNode(
            case_id="https://example.org/cases/missing",
            status_id=STATUS_ID,
            status_obj_fallback=status_obj,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
