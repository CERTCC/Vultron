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
and AppendCaseStatusToCaseNode imported directly from the submodule.

Per issue #758 AC-1, AC-3.
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
    EmitCaseStatusUpdateNode,
)
from vultron.core.models.case import VulnerabilityCase as CoreCase
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-01"
STATUS_ID = "https://example.org/cases/case-01/statuses/s1"
STATUS2_ID = "https://example.org/cases/case-01/statuses/s2"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=ACTOR_ID,
    )


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def case():
    # attributed_to triggers genesis_hash computation so ledger chain can bootstrap
    return as_VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=ACTOR_ID
    )


@pytest.fixture
def status_obj():
    return as_CaseStatus(id_=STATUS_ID, context=CASE_ID)


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

    @pytest.mark.spec("ARCH-15-001")
    def test_empty_string_case_id_returns_failure_with_diagnostic(
        self, bridge
    ):
        """Empty string case_id → FAILURE with a diagnostic mentioning absence."""
        node = CheckCaseStatusIdempotencyNode(case_id="", status_id=STATUS_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert (
            "absent" in node.feedback_message.lower()
            or "case_id" in node.feedback_message.lower()
        )

    @pytest.mark.spec("ARCH-15-001")
    def test_none_case_id_returns_failure_with_diagnostic(self, bridge):
        """None case_id → FAILURE with a diagnostic mentioning absence."""
        node = CheckCaseStatusIdempotencyNode(
            case_id=None, status_id=STATUS_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert (
            "absent" in node.feedback_message.lower()
            or "case_id" in node.feedback_message.lower()
        )


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

    @pytest.mark.spec("ARCH-15-001")
    def test_empty_string_case_id_returns_failure_with_diagnostic(
        self, bridge, status_obj
    ):
        """Empty string case_id → FAILURE with a diagnostic mentioning absence."""
        node = AppendCaseStatusToCaseNode(
            case_id="", status_id=STATUS_ID, status_obj_fallback=status_obj
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert (
            "absent" in node.feedback_message.lower()
            or "case_id" in node.feedback_message.lower()
        )

    @pytest.mark.spec("ARCH-15-001")
    def test_none_case_id_returns_failure_with_diagnostic(
        self, bridge, status_obj
    ):
        """None case_id → FAILURE with a diagnostic mentioning absence."""
        node = AppendCaseStatusToCaseNode(
            case_id=None, status_id=STATUS_ID, status_obj_fallback=status_obj
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert (
            "absent" in node.feedback_message.lower()
            or "case_id" in node.feedback_message.lower()
        )


# ---------------------------------------------------------------------------
# EmitCaseStatusUpdateNode
# ---------------------------------------------------------------------------


class TestEmitCaseStatusUpdateNode:
    @pytest.mark.spec("RSH-04-004")
    @pytest.mark.spec("RSH-04-002")
    def test_happy_path_appends_new_case_status(self, populated_dl):
        """SUCCESS: appends a new CaseStatus to case.case_statuses."""
        bridge = BTBridge(datalayer=populated_dl)
        case_before = populated_dl.read(CASE_ID)
        assert isinstance(case_before, CoreCase)
        initial_count = len(case_before.case_statuses)

        node = EmitCaseStatusUpdateNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        case_after = populated_dl.read(CASE_ID)
        assert isinstance(case_after, CoreCase)
        assert len(case_after.case_statuses) == initial_count + 1

    @pytest.mark.spec("RSH-04-004")
    def test_happy_path_commits_ledger_entry(self, populated_dl):
        """SUCCESS: a CaseLedgerEntry with event_type='add_case_status_to_case' is committed."""
        bridge = BTBridge(datalayer=populated_dl)
        node = EmitCaseStatusUpdateNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        entries = [
            obj
            for obj in populated_dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, VultronCaseLedgerEntry)
            and getattr(obj, "case_id", None) == CASE_ID
            and getattr(obj, "event_type", None) == "add_case_status_to_case"
        ]
        assert len(entries) >= 1, (
            "EmitCaseStatusUpdateNode must commit a CaseLedgerEntry"
            " with event_type='add_case_status_to_case'"
        )

    @pytest.mark.spec("RSH-04-004")
    def test_missing_case_fails(self, bridge):
        """FAILURE when the case is not found in the DataLayer."""
        node = EmitCaseStatusUpdateNode(
            case_id="https://example.org/cases/nonexistent"
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    @pytest.mark.spec("RSH-04-004")
    def test_attributed_to_set_on_new_status(self, populated_dl):
        """The new CaseStatus has attributed_to set to the executing actor."""
        from vultron.core.models.case_status import CaseStatus

        bridge = BTBridge(datalayer=populated_dl)
        node = EmitCaseStatusUpdateNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        case_after = populated_dl.read(CASE_ID)
        assert isinstance(case_after, CoreCase)
        latest = case_after.case_statuses[-1]
        if isinstance(latest, str):
            latest = populated_dl.read(latest)
        assert isinstance(latest, CaseStatus)
        assert latest.attributed_to == ACTOR_ID

    @pytest.mark.spec("ARCH-15-001")
    def test_empty_string_case_id_returns_failure_with_diagnostic(
        self, bridge
    ):
        """Empty string case_id → FAILURE with a diagnostic mentioning absence."""
        node = EmitCaseStatusUpdateNode(case_id="")
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert (
            "absent" in node.feedback_message.lower()
            or "case_id" in node.feedback_message.lower()
        )

    @pytest.mark.spec("ARCH-15-001")
    def test_none_case_id_returns_failure_with_diagnostic(self, bridge):
        """None case_id → FAILURE with a diagnostic mentioning absence."""
        node = EmitCaseStatusUpdateNode(case_id=None)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert (
            "absent" in node.feedback_message.lower()
            or "case_id" in node.feedback_message.lower()
        )
