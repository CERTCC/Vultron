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

"""Tests for AddCaseStatus BT nodes and tree factory.

Covers all three steps of the AddCaseStatusToCaseBT sequence:
  1. CheckCaseStatusIdempotencyNode  — duplicate skipped, new status passes
  2. ValidateCaseStatusTransitionNode — invalid EM/PXA rejected, valid passes
  3. AppendCaseStatusToCaseNode      — status appended and persisted

Also covers the full tree factory and use-case-level integration.

Per issue #758 AC-1, AC-2, AC-3.
"""

from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.add_case_status_tree import (
    add_case_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    CASE_STATUS_ALREADY_PRESENT,
    AppendCaseStatusToCaseNode,
    CheckCaseStatusIdempotencyNode,
    ValidateCaseStatusTransitionNode,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
)
from vultron.wire.as2.factories import add_status_to_case_activity
from vultron.wire.as2.vocab.objects.case_status import CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-bt-01"
STATUS_ID = "https://example.org/cases/case-bt-01/statuses/s1"
STATUS2_ID = "https://example.org/cases/case-bt-01/statuses/s2"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_blackboard():
    """Clear py_trees global blackboard storage between tests."""
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def case():
    return VulnerabilityCase(id_=CASE_ID, name="BT Case")


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
# CheckCaseStatusIdempotencyNode
# ---------------------------------------------------------------------------


class TestCheckCaseStatusIdempotencyNode:
    def test_new_status_succeeds(self, populated_bridge):
        """Status not yet in case → SUCCESS, Sequence should continue."""
        node = CheckCaseStatusIdempotencyNode(
            case_id=CASE_ID, status_id=STATUS_ID
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_duplicate_status_fails_with_sentinel(self, populated_dl):
        """Status already present → FAILURE with CASE_STATUS_ALREADY_PRESENT."""
        # Pre-load the status onto the case
        case = cast(VulnerabilityCase, populated_dl.read(CASE_ID))
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

    def test_case_not_found_fails(self, bridge):
        """Case not in DataLayer → FAILURE (not idempotent sentinel)."""
        node = CheckCaseStatusIdempotencyNode(
            case_id="https://example.org/cases/nonexistent",
            status_id=STATUS_ID,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert node.feedback_message != CASE_STATUS_ALREADY_PRESENT


# ---------------------------------------------------------------------------
# ValidateCaseStatusTransitionNode
# ---------------------------------------------------------------------------


class TestValidateCaseStatusTransitionNode:
    def test_first_status_always_valid(self, populated_bridge):
        """No current_status → transition always allowed (first status)."""
        node = ValidateCaseStatusTransitionNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=None,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_valid_em_transition_succeeds(self, dl):
        """NONE → PROPOSED is a valid EM transition → SUCCESS."""
        case = VulnerabilityCase(id_=CASE_ID, name="EM Valid")
        initial = CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial)
        dl.create(case)

        good_status = CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em_state=EM.PROPOSED
        )
        dl.create(good_status)

        bridge = BTBridge(datalayer=dl)
        node = ValidateCaseStatusTransitionNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=good_status,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_invalid_em_transition_fails(self, dl):
        """NONE → ACTIVE skips PROPOSED — invalid EM transition → FAILURE."""
        case = VulnerabilityCase(id_=CASE_ID, name="EM Invalid")
        initial = CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial)
        dl.create(case)

        bad_status = CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em_state=EM.ACTIVE
        )
        dl.create(bad_status)

        bridge = BTBridge(datalayer=dl)
        node = ValidateCaseStatusTransitionNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=bad_status,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_invalid_pxa_transition_fails(self, dl):
        """pxa → PXA skips intermediate steps — invalid PXA transition → FAILURE."""
        # The default seed CaseStatus already has pxa_state=CS_pxa.pxa.
        # A direct jump from pxa to PXA (all bits set at once) is invalid.
        case = VulnerabilityCase(id_=CASE_ID, name="PXA Invalid")
        dl.create(case)

        bad_status = CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.PXA
        )
        dl.create(bad_status)

        bridge = BTBridge(datalayer=dl)
        node = ValidateCaseStatusTransitionNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=bad_status,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_case_not_found_fails(self, bridge):
        """Case not in DataLayer → FAILURE."""
        node = ValidateCaseStatusTransitionNode(
            case_id="https://example.org/cases/nonexistent",
            status_id=STATUS_ID,
            status_obj_fallback=None,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# AppendCaseStatusToCaseNode
# ---------------------------------------------------------------------------


class TestAppendCaseStatusToCaseNode:
    def test_appends_status_to_case(self, populated_dl):
        """Status is appended to case.case_statuses and case is saved."""
        bridge = BTBridge(datalayer=populated_dl)
        node = AppendCaseStatusToCaseNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=None,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        case = cast(VulnerabilityCase, populated_dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in case.case_statuses]
        assert STATUS_ID in status_ids

    def test_case_not_found_fails(self, bridge):
        """Case not in DataLayer → FAILURE."""
        node = AppendCaseStatusToCaseNode(
            case_id="https://example.org/cases/nonexistent",
            status_id=STATUS_ID,
            status_obj_fallback=None,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_status_not_in_dl_uses_fallback(self, dl):
        """Status not in DL; fallback inline object is saved and used."""
        case = VulnerabilityCase(id_=CASE_ID, name="Fallback Case")
        dl.create(case)

        inline_status = CaseStatus(id_=STATUS_ID, context=CASE_ID)
        bridge = BTBridge(datalayer=dl)
        node = AppendCaseStatusToCaseNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=inline_status,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        case = cast(VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in case.case_statuses]
        assert STATUS_ID in status_ids


# ---------------------------------------------------------------------------
# Full tree: add_case_status_tree
# ---------------------------------------------------------------------------


class TestAddCaseStatusTree:
    def test_happy_path_appends_status(self, populated_dl, make_payload):
        """Full Sequence: new status is appended to case."""
        status_obj = cast(CaseStatus, populated_dl.read(STATUS_ID))
        case_obj = cast(VulnerabilityCase, populated_dl.read(CASE_ID))

        activity = add_status_to_case_activity(
            status_obj, target=case_obj, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(datalayer=populated_dl)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        case = cast(VulnerabilityCase, populated_dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in case.case_statuses]
        assert STATUS_ID in status_ids

    def test_idempotent_duplicate_fails_with_sentinel(
        self, populated_dl, make_payload
    ):
        """Duplicate status → BT FAILURE with CASE_STATUS_ALREADY_PRESENT."""
        # Pre-load the status onto the case
        case = cast(VulnerabilityCase, populated_dl.read(CASE_ID))
        status = populated_dl.read(STATUS_ID)
        case.case_statuses.append(status)
        populated_dl.save(case)

        status_obj = cast(CaseStatus, populated_dl.read(STATUS_ID))
        case_obj = cast(VulnerabilityCase, populated_dl.read(CASE_ID))

        activity = add_status_to_case_activity(
            status_obj, target=case_obj, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(datalayer=populated_dl)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert BTBridge.get_failure_reason(tree) == CASE_STATUS_ALREADY_PRESENT

    def test_invalid_em_transition_fails(self, dl, make_payload):
        """Invalid EM transition → BT FAILURE; status not appended."""
        case = VulnerabilityCase(id_=CASE_ID, name="EM Guard")
        initial = CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial)
        dl.create(case)

        bad_status = CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em_state=EM.ACTIVE
        )
        dl.create(bad_status)

        activity = add_status_to_case_activity(
            bad_status, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

        updated_case = cast(VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID not in status_ids


# ---------------------------------------------------------------------------
# Use-case level (integration with BT)
# ---------------------------------------------------------------------------


class TestAddCaseStatusToCaseReceivedUseCase:
    def test_use_case_appends_status(self, make_payload):
        """Use case succeeds: status is appended to case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(id_=CASE_ID, name="UC Case")
        status_obj = CaseStatus(id_=STATUS_ID, context=CASE_ID)
        dl.create(case)
        dl.create(status_obj)

        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        updated_case = cast(VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID in status_ids

    def test_use_case_idempotent_logs_info(self, make_payload, caplog):
        """Duplicate status → no append; use case ledgers at INFO not WARNING."""
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(id_=CASE_ID, name="Idempotent Case")
        status_obj = CaseStatus(id_=STATUS_ID, context=CASE_ID)
        case.case_statuses.append(status_obj)
        dl.create(case)
        dl.create(status_obj)

        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        with caplog.at_level(logging.DEBUG):
            AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        info_msgs = [
            r.message for r in caplog.records if r.levelno == logging.INFO
        ]
        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]

        assert any(
            "idempotent" in m.lower() for m in info_msgs
        ), "Expected INFO log for idempotent duplicate"
        assert not any(
            "idempotent" in m.lower() for m in warn_msgs
        ), "Should not WARNING for idempotent duplicate"

    def test_use_case_invalid_em_logs_warning(self, make_payload, caplog):
        """Invalid EM transition → no append; use case ledgers at WARNING."""
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(id_=CASE_ID, name="EM Guard Case")
        initial = CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial)
        dl.create(case)

        bad_status = CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em_state=EM.ACTIVE
        )
        dl.create(bad_status)

        activity = add_status_to_case_activity(
            bad_status, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        with caplog.at_level(logging.DEBUG):
            AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any(
            "AddCaseStatusToCaseBT" in m or "invalid" in m.lower()
            for m in warn_msgs
        ), "Expected WARNING for invalid transition"

        updated_case = cast(VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID not in status_ids

    def test_use_case_missing_status_id_logs_warning(
        self, make_payload, caplog
    ):
        """Missing status_id in event → WARNING; no BT executed."""
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(id_=CASE_ID, name="Missing ID Case")
        dl.create(case)

        # Construct a status with no ID to force status_id=None via factory
        status_obj = CaseStatus(id_=STATUS_ID, context=CASE_ID)
        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        # Patch status_id to None to simulate the missing-ID edge case
        from unittest.mock import PropertyMock, patch

        with patch.object(
            type(event),
            "status_id",
            new_callable=PropertyMock,
            return_value=None,
        ):
            with caplog.at_level(logging.DEBUG):
                AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("missing" in m.lower() for m in warn_msgs)
