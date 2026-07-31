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
from vultron.core.behaviors.call_out.bundles.status_authorization import (
    StatusAuthorizationCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail
from vultron.core.behaviors.status.add_case_status_tree import (
    add_case_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    CASE_STATUS_ALREADY_PRESENT,
    AppendCaseStatusToCaseNode,
    CheckCaseStatusIdempotencyNode,
    ValidateCaseStatusTransitionNode,
)
from vultron.core.behaviors.status.nodes.lifecycle import (
    ThreatTerminationBranchNode,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.models.events.status import AddCaseStatusToCaseReceivedEvent
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
)
from vultron.wire.as2.factories import add_status_to_case_activity
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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
    return as_VulnerabilityCase(id_=CASE_ID, name="BT Case")


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
        case = cast(as_VulnerabilityCase, populated_dl.read(CASE_ID))
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
        case = as_VulnerabilityCase(id_=CASE_ID, name="EM Valid")
        initial = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial)
        dl.create(case)

        good_status = as_CaseStatus(
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
        case = as_VulnerabilityCase(id_=CASE_ID, name="EM Invalid")
        initial = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial)
        dl.create(case)

        bad_status = as_CaseStatus(
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
        # The default seed as_CaseStatus already has pxa_state=CS_pxa.pxa.
        # A direct jump from pxa to PXA (all bits set at once) is invalid.
        case = as_VulnerabilityCase(id_=CASE_ID, name="PXA Invalid")
        dl.create(case)

        bad_status = as_CaseStatus(
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

        case = cast(as_VulnerabilityCase, populated_dl.read(CASE_ID))
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
        case = as_VulnerabilityCase(id_=CASE_ID, name="Fallback Case")
        dl.create(case)

        inline_status = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        bridge = BTBridge(datalayer=dl)
        node = AppendCaseStatusToCaseNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=inline_status,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in case.case_statuses]
        assert STATUS_ID in status_ids


# ---------------------------------------------------------------------------
# Full tree: add_case_status_tree
# ---------------------------------------------------------------------------


class TestAddCaseStatusTree:
    def test_happy_path_appends_status(
        self, populated_dl, make_payload, case, status_obj
    ):
        """Full Sequence: new status is appended to case."""
        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(datalayer=populated_dl)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        updated_case = populated_dl.read(CASE_ID)
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID in status_ids

    def test_idempotent_duplicate_fails_with_sentinel(
        self, populated_dl, make_payload, case, status_obj
    ):
        """Duplicate status → BT FAILURE with CASE_STATUS_ALREADY_PRESENT."""
        # Pre-load the status onto the case (use wire types for DL save)
        case.case_statuses.append(status_obj.id_)
        populated_dl.save(case)

        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(datalayer=populated_dl)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        assert BTBridge.get_failure_reason(tree) == CASE_STATUS_ALREADY_PRESENT

    def test_invalid_em_transition_fails(self, dl, make_payload):
        """Invalid EM transition → BT FAILURE; status not appended."""
        case = as_VulnerabilityCase(id_=CASE_ID, name="EM Guard")
        initial = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial)
        dl.create(case)

        bad_status = as_CaseStatus(
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

        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID not in status_ids


# ---------------------------------------------------------------------------
# Use-case level (integration with BT)
# ---------------------------------------------------------------------------


class TestAddCaseStatusToCaseReceivedUseCase:
    def test_use_case_appends_status(self, make_payload):
        """Use case succeeds: status is appended to case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(id_=CASE_ID, name="UC Case")
        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        dl.create(case)
        dl.create(status_obj)

        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID in status_ids

    def test_use_case_idempotent_logs_info(self, make_payload, caplog):
        """Duplicate status → no append; use case ledgers at INFO not WARNING."""
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(id_=CASE_ID, name="Idempotent Case")
        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
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
        case = as_VulnerabilityCase(id_=CASE_ID, name="EM Guard Case")
        initial = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial)
        dl.create(case)

        bad_status = as_CaseStatus(
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

        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID not in status_ids

    def test_use_case_missing_status_id_logs_warning(
        self, make_payload, caplog
    ):
        """Missing status_id in event → WARNING; no BT executed."""
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(id_=CASE_ID, name="Missing ID Case")
        dl.create(case)

        # Construct a status with no ID to force status_id=None via factory
        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
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


# ---------------------------------------------------------------------------
# ThreatTerminationBranchNode (Seam 2, RSH-03-001 to RSH-03-003)
# ---------------------------------------------------------------------------


CASE_MANAGER_ID = "https://example.org/actors/case-manager"
CM_PARTICIPANT_ID = f"{CASE_ID}/participants/case-manager"


class TestThreatTerminationBranchNode:
    """RSH-03-001: fires teardown on P/X/A; RSH-03-002: no sender-role gate."""

    def _make_status_with_pxa(self, pxa_state: CS_pxa) -> as_CaseStatus:
        s = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        s.pxa_state = pxa_state
        return s

    def _setup_dl_with_embargo(self, dl, pxa_state: CS_pxa):
        from vultron.core.states.em import EM
        from vultron.enums.roles import CVDRole

        # ResolveCaseManagerNode requires a CASE_MANAGER participant in the case.
        cm_participant = as_CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = as_VulnerabilityCase(id_=CASE_ID, name="ThreatTerm Case")
        case.add_participant(cm_participant)
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e1", context=CASE_ID
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        status_obj = self._make_status_with_pxa(pxa_state)
        dl.create(status_obj)
        return status_obj

    def test_skips_when_pxa_all_lowercase(self, dl):
        """pxa (no threat flags) → skip teardown → SUCCESS."""
        status_obj = self._setup_dl_with_embargo(dl, CS_pxa.pxa)
        bridge = BTBridge(datalayer=dl)
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_skips_when_no_active_embargo(self, dl):
        """CS.P set but no active embargo → skip teardown → SUCCESS."""
        case = as_VulnerabilityCase(id_=CASE_ID, name="No Embargo")
        status_obj = self._make_status_with_pxa(CS_pxa.Pxa)
        dl.create(case)
        dl.create(status_obj)
        bridge = BTBridge(datalayer=dl)
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_skips_when_status_obj_none(self, dl):
        """status_obj=None → no pxa info → skip teardown → SUCCESS."""
        bridge = BTBridge(datalayer=dl)
        node = ThreatTerminationBranchNode(status_obj=None, case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_skips_when_case_id_none(self, dl):
        """case_id=None → no TerminateEmbargoBT built → SUCCESS via skip."""
        status_obj = self._make_status_with_pxa(CS_pxa.Pxa)
        bridge = BTBridge(datalayer=dl)
        node = ThreatTerminationBranchNode(status_obj=status_obj, case_id=None)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    @pytest.mark.parametrize(
        "pxa_state",
        [
            CS_pxa.Pxa,
            CS_pxa.pXa,
            CS_pxa.pxA,
            CS_pxa.PXa,
            CS_pxa.PxA,
            CS_pxa.pXA,
            CS_pxa.PXA,
        ],
    )
    def test_triggers_teardown_on_threat_pxa_states(self, dl, pxa_state):
        """All CS_pxa states except pxa trigger embargo teardown attempt.

        Without a broadcast factory, TerminateEmbargoLifecycleNode still
        succeeds but SendTerminateEmbargoActivityNode fails (BT-14-001).
        The EM state is updated and active_embargo cleared before that.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM

        status_obj = self._setup_dl_with_embargo(dl, pxa_state)
        bridge = BTBridge(datalayer=dl)
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
        )
        # No trigger_activity in bridge → broadcast fails → FAILURE (BT-14-001)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

        # EM state was still applied
        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.EXITED
        assert updated.active_embargo is None

    def test_no_sender_role_gate(self, dl):
        """RSH-03-002: teardown fires regardless of sender role (no CASE_OWNER check).

        Unlike PublicDisclosureBranchNode, any actor_id triggers teardown when
        pxa conditions are met — sender authorization was handled at Seam 1.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM

        # Use a non-CASE_OWNER actor — teardown must still fire
        non_owner_actor = "https://example.org/actors/non-owner"
        status_obj = self._setup_dl_with_embargo(dl, CS_pxa.Pxa)
        bridge = BTBridge(datalayer=dl)
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=non_owner_actor)
        # FAILURE because no broadcast factory, but state was applied
        assert result.status == Status.FAILURE
        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.EXITED


# ---------------------------------------------------------------------------
# SideEffectsGuard (Seam 2, RSH-02-001)
# ---------------------------------------------------------------------------


class TestAddCaseStatusTreeSeam2:
    """Seam 2 call-out wiring tests (RSH-02-001, RSH-02-002)."""

    def _make_event(self, dl, pxa_state: CS_pxa = CS_pxa.pxa):
        from vultron.semantic_registry import extract_event

        case = as_VulnerabilityCase(id_=CASE_ID, name="Seam2 Case")
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=pxa_state
        )
        dl.create(case)
        dl.create(status_obj)

        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        return cast(AddCaseStatusToCaseReceivedEvent, extract_event(activity))

    def test_side_effects_guard_always_fail_blocks_threat_termination(self):
        """SideEffectsGuard=AlwaysFail → ThreatTerminationBranch never runs.

        Even with CS.P set and an active embargo, the Sequence fails at the
        guard node and the BT returns FAILURE without touching the EM state.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM
        from vultron.enums.roles import CVDRole
        from vultron.semantic_registry import extract_event

        dl = SqliteDataLayer("sqlite:///:memory:")
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e1", context=CASE_ID
        )
        cm_participant = as_CaseParticipant(
            id_=f"{CASE_ID}/participants/cm",
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        # Build case with ACTIVE em_state before storing in DataLayer
        case = as_VulnerabilityCase(id_=CASE_ID, name="Seam2 Guard Case")
        case.add_participant(cm_participant)
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.Pxa
        )
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        dl.create(status_obj)

        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        event = cast(AddCaseStatusToCaseReceivedEvent, extract_event(activity))

        def _always_fail(name: str):
            return AlwaysFail(name)

        call_out = StatusAuthorizationCallOutBundle(
            side_effects_guard_factory=_always_fail
        )

        from vultron.core.behaviors.status.add_case_status_tree import (
            add_case_status_tree,
        )

        tree = add_case_status_tree(request=event, call_out=call_out)
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.FAILURE

        # EM state must NOT have changed — guard blocked teardown
        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.ACTIVE

    def test_tree_contains_threat_termination_branch_node(self, dl):
        """add_case_status_tree must contain ThreatTerminationBranchNode (RSH-03-001)."""
        event = self._make_event(dl)
        from vultron.core.behaviors.status.add_case_status_tree import (
            add_case_status_tree,
        )

        tree = add_case_status_tree(request=event)
        node_types = {type(n).__name__ for n in tree.children}
        assert "ThreatTerminationBranchNode" in node_types, (
            "add_case_status_tree must contain ThreatTerminationBranchNode"
            " (RSH-03-001, ADR-0046)"
        )


# ---------------------------------------------------------------------------
# Regression: new pipeline (ThreatTerminationBranchNode) vs old
#             (PublicDisclosureBranchNode) — CS.P teardown outcome
# ---------------------------------------------------------------------------


class TestRegressionCSPTeardownPath:
    """Regression: Seam 2 ThreatTerminationBranchNode produces the same
    end-state as the legacy PublicDisclosureBranchNode for a CS.P update
    sent by a CASE_OWNER.

    Both paths must result in EM=EXITED and active_embargo=None (BT-14-001
    means FAILURE when no broadcast factory, but the state transition is
    committed before broadcast in both paths).

    The new pipeline uses ThreatTerminationBranchNode directly (Seam 2).
    ValidateCaseStatusTransitionNode is tested separately; this regression
    focuses on teardown outcome parity.

    AC #8 from issue #1844.
    """

    def _build_dl_with_active_embargo(self):
        """Return a fresh DataLayer with a case in ACTIVE embargo."""
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:")
        cm_participant = as_CaseParticipant(
            id_=f"{CASE_ID}/participants/cm",
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e1", context=CASE_ID
        )
        case = as_VulnerabilityCase(id_=CASE_ID, name="Regression Case")
        case.add_participant(cm_participant)
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        return dl

    def test_new_pipeline_csp_teardown_matches_old_path_end_state(self):
        """Seam 2 (ThreatTerminationBranchNode, new pipeline) produces the
        same end-state as legacy PublicDisclosureBranchNode for CS.P with a
        CASE_OWNER sender: EM=EXITED and active_embargo=None.

        Both nodes delegate to terminate_embargo_bt and FAIL when no broadcast
        factory is present (BT-14-001); the EM state transition is committed
        before the broadcast attempt in both cases.
        """
        from typing import cast as c

        from vultron.core.behaviors.status.nodes.lifecycle import (
            PublicDisclosureBranchNode,
        )
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus,
        )

        # — New pipeline: ThreatTerminationBranchNode (Seam 2) —
        dl_new = self._build_dl_with_active_embargo()
        new_status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.Pxa
        )
        dl_new.create(new_status_obj)

        new_node = ThreatTerminationBranchNode(
            status_obj=new_status_obj, case_id=CASE_ID
        )
        new_bridge = BTBridge(datalayer=dl_new)
        # No broadcast factory → FAILURE (BT-14-001), but EM state committed
        new_result = new_bridge.execute_with_setup(
            tree=new_node, actor_id=ACTOR_ID
        )
        assert new_result.status == Status.FAILURE

        new_case = c(VulnerabilityCase, dl_new.read(CASE_ID))
        new_em_state = new_case.current_status.em.state
        new_embargo = new_case.active_embargo

        # — Legacy path: PublicDisclosureBranchNode (CASE_OWNER + CS.P) —
        dl_old = self._build_dl_with_active_embargo()
        owner_participant = as_CaseParticipant(
            id_=f"{CASE_ID}/participants/vendor",
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        dl_old.create(owner_participant)
        case_old = c(VulnerabilityCase, dl_old.read(CASE_ID))
        case_old.actor_participant_index[ACTOR_ID] = owner_participant.id_
        dl_old.save(case_old)

        cs_old = as_CaseStatus()
        cs_old.pxa_state = CS_pxa.Pxa
        ps_with_cs = as_ParticipantStatus(
            id_=f"{CASE_ID}/participants/vendor/statuses/s1",
            context=CASE_ID,
        )
        ps_with_cs.case_status = cs_old

        old_node = PublicDisclosureBranchNode(
            status_obj=ps_with_cs,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        old_bridge = BTBridge(datalayer=dl_old)
        # No factory → FAILURE from broadcast (BT-14-001)
        old_result = old_bridge.execute_with_setup(
            tree=old_node, actor_id=CASE_MANAGER_ID
        )
        assert old_result.status == Status.FAILURE

        old_case = c(VulnerabilityCase, dl_old.read(CASE_ID))
        old_em_state = old_case.current_status.em.state
        old_embargo = old_case.active_embargo

        # Both paths must produce identical end-state
        assert new_em_state == old_em_state == EM.EXITED, (
            f"New pipeline EM={new_em_state}, old path EM={old_em_state};"
            " both must be EXITED for CS.P teardown (AC #8, issue #1844)"
        )
        assert (
            new_embargo is None and old_embargo is None
        ), "Both paths must clear active_embargo after CS.P teardown"
