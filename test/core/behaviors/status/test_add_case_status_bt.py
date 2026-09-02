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

Covers steps of the AddCaseStatusToCaseBT sequence:
  1. CheckCaseStatusIdempotencyNode  — duplicate skipped, new status passes
  2. AppendCaseStatusToCaseNode      — status appended and persisted

Also covers the full tree factory and use-case-level integration.

Regression coverage:
  - Bug #2704: FilterCsEmDimensionNode must return FAILURE (not SUCCESS) when
    _resolve_asserted() returns None (CLP-10-009).
  - Bug #2706: FilterCsPxaDimensionNode must write the updated accumulator back
    via _set_output so PXA refusals survive a copy-returning blackboard.

Per issue #758 AC-1, AC-3.
"""

from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_PERMISSIVE,
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
)
from vultron.core.behaviors.status.nodes.cs_dimension_filter import (
    FilterCsEmDimensionNode,
    FilterCsPxaDimensionNode,
)
from vultron.core.behaviors.status.nodes.lifecycle import (
    ThreatTerminationBranchNode,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.models.events.status import AddCaseStatusToCaseReceivedEvent
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
)
from vultron.wire.as2.factories import add_status_to_case_activity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
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
    # The node-level tests below run as ACTOR_ID, so this is ACTOR_ID's store.
    # The use-case and authorization-gate tests further down run as the case
    # manager and build their own CASE_MANAGER_ID store for that reason.
    return SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)


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

    def test_ephemeral_pXa_promoted_before_append(self, dl):
        """AC-1 / SM-09-001: pXa PXA is promoted to PXa before appending."""
        from vultron.core.models.dimensions import PxaDimension

        case = as_VulnerabilityCase(id_=CASE_ID, name="Promotion Case")
        dl.create(case)

        # em defaults to EmDimension() via default_factory
        ephemeral_status = CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            pxa=PxaDimension(state=CS_pxa.pXa),
        )
        dl.save(ephemeral_status)

        bridge = BTBridge(datalayer=dl)
        node = AppendCaseStatusToCaseNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=None,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        reloaded_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        promoted = [
            s
            for s in reloaded_case.case_statuses
            if isinstance(s, CaseStatus)
            and getattr(s, "id_", None) == STATUS_ID
        ]
        assert promoted, "Promoted CaseStatus must be appended to case"
        assert promoted[0].pxa.state is CS_pxa.PXa


# ---------------------------------------------------------------------------
# FilterCsEmDimensionNode — Bug #2704 (CLP-10-009)
# ---------------------------------------------------------------------------

CASE_MANAGER_ID_2704 = "https://example.org/actors/case-mgr-2704"


class TestFilterCsEmDimensionNodeBug2704:
    """Guard must return FAILURE when status object is unresolvable (#2704).

    Before the fix FilterCsEmDimensionNode returned SUCCESS when
    _resolve_asserted() returned None, allowing GuardedCommit to fire and write
    a ledger entry for a status that could never be applied (CLP-10-009).
    """

    def _build_dl(self):
        """Return a DataLayer with a case that has one CaseStatus already present."""
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=CASE_MANAGER_ID_2704
        )
        cm_participant = CaseParticipant(
            id_=f"{CASE_ID}/participants/cm-2704",
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID_2704,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="2704 Test Case",
            attributed_to=CASE_MANAGER_ID_2704,
        )
        case.add_participant(cm_participant)
        # VulnerabilityCase auto-seeds a core CaseStatus via _init_case_statuses
        # when attributed_to is set and case_statuses is empty, so current_status
        # resolves after the DL round-trip without any manual seeding.
        dl.create(case)
        dl.create(cm_participant)
        return dl

    @pytest.mark.spec("CLP-10-009")
    def test_guard_fails_when_status_unresolvable(self):
        """Guard returns FAILURE when status not in DL and fallback is None (#2704).

        This test FAILS on pre-fix code where the guard returned SUCCESS.
        """
        dl = self._build_dl()
        bridge = BTBridge(datalayer=dl)
        node = FilterCsEmDimensionNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=None,
        )
        result = bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID_2704
        )
        assert result.status == Status.FAILURE, (
            "FilterCsEmDimensionNode must return FAILURE when the status object"
            " cannot be resolved (CLP-10-009, #2704)"
        )

    @pytest.mark.spec("CLP-10-009")
    def test_unresolvable_status_produces_no_ledger_entry(self, make_payload):
        """Full tree: unresolvable status aborts before GuardedCommit → zero CaseLedgerEntries (#2704).

        This test FAILS on pre-fix code where the guard returned SUCCESS,
        allowing GuardedCommit to fire and leave an orphaned ledger entry.
        """
        from unittest.mock import PropertyMock, patch

        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        dl = self._build_dl()
        # STATUS_ID intentionally NOT written to DL — _resolve_asserted() returns None.
        wire_case = as_VulnerabilityCase(id_=CASE_ID, name="2704 Case")
        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        activity = add_status_to_case_activity(
            status_obj, target=wire_case, actor=CASE_MANAGER_ID_2704
        )
        event = make_payload(activity).model_copy(
            update={"activity": activity}
        )

        # Patch request.status to None so status_obj_fallback=None in the tree factory.
        with patch.object(
            type(event), "status", new_callable=PropertyMock, return_value=None
        ):
            tree = add_case_status_tree(
                request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
            )
            bridge = BTBridge(datalayer=dl)
            result = bridge.execute_with_setup(
                tree=tree, actor_id=CASE_MANAGER_ID_2704, activity=event
            )

        assert result.status == Status.FAILURE

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ]
        assert len(entries) == 0, (
            "An unresolvable status must be rejected by FilterCsEmDimensionNode"
            " before GuardedCommit fires — zero CaseLedgerEntries (CLP-10-009, #2704)"
        )


# ---------------------------------------------------------------------------
# FilterCsEmDimensionNode — absent case_id (ARCH-15-001)
# ---------------------------------------------------------------------------


class TestFilterCsEmDimensionNodeAbsentCaseId:
    """Guard returns SUCCESS immediately when case_id is absent (ARCH-15-001)."""

    @pytest.mark.spec("ARCH-15-001")
    def test_none_case_id_returns_success(self, bridge):
        """None case_id → SUCCESS (no case to look up; nothing to filter)."""
        node = FilterCsEmDimensionNode(case_id=None, status_id=STATUS_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    @pytest.mark.spec("ARCH-15-001")
    def test_empty_string_case_id_returns_success(self, bridge):
        """Empty-string case_id → SUCCESS (no case to look up; nothing to filter)."""
        node = FilterCsEmDimensionNode(case_id="", status_id=STATUS_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# FilterCsPxaDimensionNode — Bug #2706 (explicit _set_output write-back)
# ---------------------------------------------------------------------------

CASE_MANAGER_ID_2706 = "https://example.org/actors/case-mgr-2706"


class TestFilterCsPxaDimensionNodeBug2706:
    """PXA accumulator write-back must be explicit via _set_output (#2706).

    Before the fix FilterCsPxaDimensionNode relied on in-place mutation of the
    blackboard reference to propagate PXA refusals to FinalizeCsFilterNode.
    If the blackboard ever returns a copy from get_input the mutation is
    silently discarded — PXA refusals are lost and the tree incorrectly accepts
    a refused assertion.
    """

    def _build_dl(self):
        """Return a DataLayer with pxa=Pxa current state and a pxa=pxa regression asserted."""
        from vultron.enums.roles import CVDRole
        from vultron.core.states.em import EM

        dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=CASE_MANAGER_ID_2706
        )
        cm_participant = CaseParticipant(
            id_=f"{CASE_ID}/participants/cm-2706",
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID_2706,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="2706 Test Case",
            attributed_to=CASE_MANAGER_ID_2706,
        )
        case.add_participant(cm_participant)
        case.append_case_status(pxa_state=CS_pxa.Pxa, em_state=EM.NONE)
        dl.create(case)
        dl.create(cm_participant)
        # Asserted: pxa regression (pxa=pxa instead of Pxa), same EM
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.pxa
        )
        dl.create(asserted)
        return dl

    def test_output_ports_include_acc_write_back(self):
        """FilterCsPxaDimensionNode must declare an output port for accumulator write-back (#2706).

        Before the fix the node had no output ports and relied on in-place mutation.
        This test FAILS on pre-fix code.
        """
        output_ports = FilterCsPxaDimensionNode.output_ports()
        assert output_ports, (
            "FilterCsPxaDimensionNode must declare at least one output port for"
            " the accumulator write-back (#2706)"
        )

    @pytest.mark.spec("CLP-10-009")
    def test_pxa_refusal_survives_copy_returning_blackboard(
        self, make_payload
    ):
        """PXA refusal propagates correctly even when get_input returns a copy (#2706).

        Simulates a copy-returning blackboard: in-place dict mutation is lost,
        so the only way to propagate the updated acc is via _set_output.
        Without the fix the mutation is discarded, FinalizeCsFilterNode sees an
        empty refused list and the tree incorrectly returns SUCCESS.

        This test FAILS on pre-fix code and PASSES after the fix.
        """
        from unittest.mock import patch

        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        dl = self._build_dl()
        wire_case = as_VulnerabilityCase(id_=CASE_ID, name="2706 Case")
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.pxa
        )
        activity = add_status_to_case_activity(
            status_obj, target=wire_case, actor=CASE_MANAGER_ID_2706
        )
        event = make_payload(activity).model_copy(
            update={"activity": activity}
        )

        # Patch get_input on FilterCsPxaDimensionNode to return a DEEP COPY of any dict,
        # simulating a blackboard that never returns mutable references.
        # A shallow dict() copy shares nested lists, so deep copy is required to
        # isolate the mutation from the stored object.
        import copy as _copy

        _real_get_input = FilterCsPxaDimensionNode.get_input

        def _copy_returning(self_node, port_name, default=None):
            val = _real_get_input(self_node, port_name, default)
            return _copy.deepcopy(val) if isinstance(val, dict) else val

        with patch.object(
            FilterCsPxaDimensionNode, "get_input", new=_copy_returning
        ):
            tree = add_case_status_tree(
                request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
            )
            bridge = BTBridge(datalayer=dl)
            result = bridge.execute_with_setup(
                tree=tree, actor_id=CASE_MANAGER_ID_2706, activity=event
            )

        # pxa regression with no EM change → whole refusal → FAILURE, zero ledger entries.
        # Without fix: copy mutation discarded → Finalize sees refused=[] → SUCCESS → ledger written.
        # With fix:    _set_output writes updated acc → Finalize sees refused=['pxa'] → FAILURE.
        assert result.status == Status.FAILURE

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ]
        assert len(entries) == 0, (
            "A whole-refused PXA regression must produce zero CaseLedgerEntries."
            " FilterCsPxaDimensionNode must write the updated acc back via _set_output (#2706)"
        )


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

        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
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

    @pytest.mark.spec("RSH-05-017")
    @pytest.mark.spec("RSH-05-018")
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

    @pytest.mark.spec("CSB-17-012")
    def test_px_ephemeral_a_event_rejected_no_ledger_write(
        self, dl, make_payload
    ):
        """Full tree rejects A-event from pX state; no ledger write (CSB-17-012, ISSUE-2524).

        When the current PXA state is pXa (exploit public, public unaware),
        the CheckCsEphemeralStateNode guard must return FAILURE for any asserted
        CaseStatus that does not advance P.  The full tree must return FAILURE
        and no CaseStatus entry should be appended to the case.
        """
        case = VulnerabilityCase(
            id_=CASE_ID, name="Ephemeral pX Guard", attributed_to=ACTOR_ID
        )
        # Auto-seeded baseline is pxa; advance to pXa (X exploit published,
        # P still false — the ephemeral state that requires P next).
        case.append_case_status(pxa_state=CS_pxa.pXa)
        dl.create(case)

        # Asserted status fires A-event only (pXa → pXA); P is NOT advanced.
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            pxa_state=CS_pxa.pXA,
        )
        dl.create(asserted)

        activity = add_status_to_case_activity(
            asserted, target=case.id_, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID not in status_ids

    @pytest.mark.spec("RSH-05-015")
    @pytest.mark.spec("RSH-05-016")
    @pytest.mark.spec("RSH-05-018")
    @pytest.mark.spec("RSH-05-019")
    def test_valid_em_advance_with_pxa_regression_applies_em_and_refuses_pxa(
        self, dl, make_payload
    ):
        """EM advances (NONE→PROPOSED) with stale PXA regression → BT SUCCEEDS.

        Bug #2256: all-or-nothing CS validation discarded the valid EM advance
        when PXA regressed and aborted the Sequence before
        ThreatTerminationBranchNode.  Per-dimension adjudication must accept
        the EM advance and carry the current PXA forward.
        """
        case = VulnerabilityCase(
            id_=CASE_ID, name="EM PXA Split", attributed_to=ACTOR_ID
        )
        # Auto-seeded CaseStatus has pxa=pxa; advance pxa to Pxa so that
        # the asserted pxa=pxa from the sender is a real regression.
        case.append_case_status(pxa_state=CS_pxa.Pxa)
        dl.create(case)

        # Sender asserts EM NONE→PROPOSED (valid) + PXA Pxa→pxa (stale regression)
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em_state=EM.PROPOSED,
            pxa_state=CS_pxa.pxa,  # regression: P was True, sender claims False
        )
        dl.create(asserted)

        activity = add_status_to_case_activity(
            asserted, target=case.id_, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS

        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID in status_ids

        # EM advance accepted, PXA carried forward (not regressed).
        # Assert on the saved domain CaseStatus at STATUS_ID, not
        # current_status: current_status uses max-by-ID and the auto-seeded
        # UUID-ID status sorts lexically higher than STATUS_ID.
        saved_status = cast(CaseStatus, dl.read(STATUS_ID))
        assert saved_status.em.state == EM.PROPOSED
        assert saved_status.pxa.state == CS_pxa.Pxa

    @pytest.mark.spec("RSH-05-012")
    def test_finalize_cs_filter_node_emstate_uses_name_serialization(
        self, dl, make_payload
    ):
        """emState in BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE equals EM member .name.

        Regression guard for the FinalizeCsFilterNode serialization invariant:
        ``emState`` must equal ``filtered.em.state.name`` so that
        ``_coerce_em(emState)`` via ``EM[v]`` (name-based lookup) round-trips
        correctly.  Using ``str()`` is fragile because it returns .value, which
        equals .name only while no EM member has value ≠ name (RSH-05-012).
        """
        case = VulnerabilityCase(
            id_=CASE_ID, name="EM PXA Split", attributed_to=ACTOR_ID
        )
        case.append_case_status(pxa_state=CS_pxa.Pxa)
        dl.create(case)

        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em_state=EM.PROPOSED,
            pxa_state=CS_pxa.pxa,
        )
        dl.create(asserted)

        activity = add_status_to_case_activity(
            asserted, target=case.id_, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        override = py_trees.blackboard.Blackboard.storage.get(
            "/ledger_payload_object_override"
        )
        assert override is not None, (
            "FinalizeCsFilterNode must set BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE"
            " during a partial-accept"
        )
        em_state_field = override["fields"]["emState"]
        assert em_state_field == EM.PROPOSED.name, (
            f"emState must be EM member .name ('{EM.PROPOSED.name}'),"
            f" got {em_state_field!r}"
        )
        assert EM[em_state_field] == EM.PROPOSED


# ---------------------------------------------------------------------------
# Use-case level (integration with BT)
# ---------------------------------------------------------------------------


class TestAddCaseStatusToCaseReceivedUseCase:
    def test_use_case_appends_status(self, make_payload):
        """Use case succeeds: status is appended to case."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=CASE_MANAGER_ID,
        )
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=CASE_MANAGER_ID,
        )
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=CASE_MANAGER_ID,
        )
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=CASE_MANAGER_ID,
        )
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
# ThreatTerminationBranchNode (EmbargoTeardownAuthorizationGate, RSH-03-001 to RSH-03-003)
# ---------------------------------------------------------------------------


CASE_MANAGER_ID = "https://example.org/actors/case-manager"
CM_PARTICIPANT_ID = f"{CASE_ID}/participants/case-manager"


class TestThreatTerminationBranchNode:
    """RSH-03-001: fires teardown on P/X/A; RSH-03-002: no sender-role gate."""

    def _make_status_with_pxa(self, pxa_state: CS_pxa) -> as_CaseStatus:
        s = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        object.__setattr__(s, "pxa_state", pxa_state)
        return s

    def _setup_dl_with_embargo(self, dl, pxa_state: CS_pxa):
        from vultron.core.states.em import EM
        from vultron.enums.roles import CVDRole

        # ResolveCaseManagerNode requires a CASE_MANAGER participant in the case.
        cm_participant = CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = VulnerabilityCase(
            id_=CASE_ID, name="ThreatTerm Case", attributed_to=ACTOR_ID
        )
        case.add_participant(cm_participant)
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e1", context=CASE_ID
        )
        case.active_embargo = embargo.id_
        case.append_case_status(em_state=EM.ACTIVE)
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

    @pytest.mark.spec("RSH-03-001")
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

    @pytest.mark.spec("RSH-03-002")
    def test_no_sender_role_gate(self, dl):
        """RSH-03-002: teardown fires regardless of sender role (no CASE_OWNER check).

        Unlike PublicDisclosureBranchNode, any actor_id triggers teardown when
        pxa conditions are met — sender authorization was handled at StatusAdoptionGate.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM

        # ACTOR_ID holds no role at all in the seeded case — the only
        # participant is CASE_MANAGER_ID — so executing as ACTOR_ID *is* the
        # non-CASE_OWNER condition this test asserts.  A separate stand-in id
        # would only name an actor whose store is empty, which tests nothing.
        status_obj = self._setup_dl_with_embargo(dl, CS_pxa.Pxa)
        bridge = BTBridge(datalayer=dl)
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        # FAILURE because no broadcast factory, but state was applied
        assert result.status == Status.FAILURE
        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.EXITED


# ---------------------------------------------------------------------------
# EmbargoTeardownAuthorizationGate (RSH-02-001)
# ---------------------------------------------------------------------------


class TestAddCaseStatusTreeSeam2:
    """EmbargoTeardownAuthorizationGate call-out wiring tests (RSH-02-001, RSH-02-002)."""

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

    @pytest.mark.spec("RSH-02-001")
    def test_side_effects_guard_always_fail_blocks_threat_termination(self):
        """EmbargoTeardownAuthorizationGate=AlwaysFail → ThreatTerminationBranch never runs.

        Even with CS.P set and an active embargo, the Sequence fails at the
        guard node and the BT returns FAILURE without touching the EM state.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM
        from vultron.enums.roles import CVDRole
        from vultron.semantic_registry import extract_event

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=CASE_MANAGER_ID,
        )
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e1", context=CASE_ID
        )
        cm_participant = CaseParticipant(
            id_=f"{CASE_ID}/participants/cm",
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        # Build case with ACTIVE em_state before storing in DataLayer
        case = VulnerabilityCase(
            id_=CASE_ID, name="Seam2 Guard Case", attributed_to=CASE_MANAGER_ID
        )
        case.add_participant(cm_participant)
        case.active_embargo = embargo.id_
        case.append_case_status(em_state=EM.ACTIVE)
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.Pxa
        )
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        dl.create(status_obj)

        activity = add_status_to_case_activity(
            status_obj, target=case.id_, actor=ACTOR_ID
        )
        event = cast(AddCaseStatusToCaseReceivedEvent, extract_event(activity))

        def _always_fail(name: str):
            return AlwaysFail(name)

        call_out = StatusAuthorizationCallOutBundle(
            embargo_teardown_authorization_gate_factory=_always_fail
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

    @pytest.mark.spec("RSH-03-001")
    @pytest.mark.spec("RSH-03-003")
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
    """Regression: EmbargoTeardownAuthorizationGate ThreatTerminationBranchNode produces the same
    end-state as the legacy PublicDisclosureBranchNode for a CS.P update
    sent by a CASE_OWNER.

    Both paths must result in EM=EXITED and active_embargo=None (BT-14-001
    means FAILURE when no broadcast factory, but the state transition is
    committed before broadcast in both paths).

    The new pipeline uses ThreatTerminationBranchNode directly (EmbargoTeardownAuthorizationGate).
    This regression focuses on teardown outcome parity.

    AC #8 from issue #1844.
    """

    def _build_dl_with_active_embargo(self, manager_id: str = CASE_MANAGER_ID):
        """Return a fresh DataLayer with a case in ACTIVE embargo.

        *manager_id* names both the case manager and the store, so the two
        halves of the regression comparison below must pass **different** ids:
        in-memory stores are keyed by ``(db_url, actor_id)``, so two calls with
        the same id would hand back the *same* database and the second seed
        would collide on ``CASE_ID``.
        """
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=manager_id)
        cm_participant = CaseParticipant(
            id_=f"{CASE_ID}/participants/cm",
            context=CASE_ID,
            attributed_to=manager_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e1", context=CASE_ID
        )
        case = VulnerabilityCase(
            id_=CASE_ID, name="Regression Case", attributed_to=manager_id
        )
        case.add_participant(cm_participant)
        case.active_embargo = embargo.id_
        case.append_case_status(em_state=EM.ACTIVE)
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        return dl

    def test_new_pipeline_csp_teardown_matches_old_path_end_state(self):
        """EmbargoTeardownAuthorizationGate (ThreatTerminationBranchNode, new pipeline) produces the
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

        # — New pipeline: ThreatTerminationBranchNode (EmbargoTeardownAuthorizationGate) —
        dl_new = self._build_dl_with_active_embargo()
        new_status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.Pxa
        )
        dl_new.create(new_status_obj)

        new_node = ThreatTerminationBranchNode(
            status_obj=new_status_obj, case_id=CASE_ID
        )
        new_bridge = BTBridge(datalayer=dl_new)
        # Runs as the case manager, matching the legacy half below: the seeded
        # case names CASE_MANAGER_ID as its only participant, and teardown
        # authority is the manager's.  ACTOR_ID here would execute against an
        # empty store and hold no authority either.
        new_result = new_bridge.execute_with_setup(
            tree=new_node, actor_id=CASE_MANAGER_ID
        )
        assert new_result.status == Status.FAILURE

        new_case = c(VulnerabilityCase, dl_new.read(CASE_ID))
        new_em_state = new_case.current_status.em.state
        new_embargo = new_case.active_embargo

        # — Legacy path: PublicDisclosureBranchNode (CASE_OWNER + CS.P) —
        # A distinct manager id, so this half gets its own store rather than
        # the one the new-pipeline half above already seeded.
        legacy_manager_id = f"{CASE_MANAGER_ID}-legacy"
        dl_old = self._build_dl_with_active_embargo(legacy_manager_id)
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
        object.__setattr__(cs_old, "pxa_state", CS_pxa.Pxa)
        ps_with_cs = as_ParticipantStatus(
            id_=f"{CASE_ID}/participants/vendor/statuses/s1",
            context=CASE_ID,
        )
        object.__setattr__(ps_with_cs, "case_status", cs_old)

        old_node = PublicDisclosureBranchNode(
            status_obj=ps_with_cs,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        old_bridge = BTBridge(datalayer=dl_old)
        # No factory → FAILURE from broadcast (BT-14-001)
        old_result = old_bridge.execute_with_setup(
            tree=old_node, actor_id=legacy_manager_id
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


# ---------------------------------------------------------------------------
# Regression: CLP-10-009 — validators in preconditions, ledger entry on accept
# ---------------------------------------------------------------------------

CASE_MANAGER_ID_2254 = "https://example.org/actors/case-mgr-2254"
CM_PARTICIPANT_ID_2254 = f"{CASE_ID}/participants/case-mgr-2254"


class TestCaseLedgerEntryCreation:
    """CLP-10-009 / ISSUE-2254 regression: add_case_status_tree must commit a
    canonical ledger entry for valid updates (Fix 2: plain Sequence → create_receive_activity_tree).

    Before the fix add_case_status_tree used a plain Sequence with no
    GuardedCommit, so NO ledger entries were ever produced.  After the fix the
    tree uses create_receive_activity_tree and a CaseLedgerEntry is created
    for every valid accepted update when the receiving actor is the CASE_MANAGER.
    """

    def _build_dl_with_case_manager(self):
        from vultron.enums.roles import CVDRole

        # The tree runs as the case manager, so this is the case manager's own
        # store (BT-05-005, ADR-0073).
        dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=CASE_MANAGER_ID_2254
        )
        cm_participant = CaseParticipant(
            id_=CM_PARTICIPANT_ID_2254,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID_2254,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        # attributed_to seeds the per-case genesis hash (CLP-08-003); without
        # it the guarded commit cannot anchor a hash chain.
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Ledger Test Case",
            attributed_to=CASE_MANAGER_ID_2254,
        )
        case.add_participant(cm_participant)
        dl.create(case)
        dl.create(cm_participant)
        return dl

    @pytest.mark.spec("CLP-10-009")
    def test_valid_update_produces_ledger_entry(self, make_payload):
        """A valid Add(CaseStatus) produces exactly one CaseLedgerEntry when
        the receiving actor is the CASE_MANAGER (CLP-10-009, Fix 2).

        This test FAILS on pre-fix code where add_case_status_tree used a
        plain Sequence with no GuardedCommit.
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        dl = self._build_dl_with_case_manager()
        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        dl.create(status_obj)

        wire_case = as_VulnerabilityCase(id_=CASE_ID, name="Ledger Test Case")
        activity = add_status_to_case_activity(
            status_obj, target=wire_case, actor=CASE_MANAGER_ID_2254
        )
        event = make_payload(activity).model_copy(
            update={"activity": activity}
        )

        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID_2254, activity=event
        )
        assert result.status == Status.SUCCESS

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ]
        assert len(entries) == 1, (
            "A valid Add(CaseStatus) accepted by the CASE_MANAGER must produce"
            " exactly one CaseLedgerEntry (CLP-10-009)"
        )

    @pytest.mark.spec("CLP-10-009")
    def test_invalid_em_transition_produces_no_ledger_entry(
        self, make_payload
    ):
        """An invalid EM transition is rejected in precondition_guards → zero
        CaseLedgerEntries (CLP-10-009: validators run before GuardedCommit).
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        dl = self._build_dl_with_case_manager()
        initial = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em_state=EM.NONE,
        )
        from typing import cast as c
        from vultron.core.models.case import VulnerabilityCase

        case_obj = c(VulnerabilityCase, dl.read(CASE_ID))
        case_obj.case_statuses.append(str(initial.id_))
        dl.create(initial)
        dl.save(case_obj)

        bad_status = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em_state=EM.ACTIVE
        )
        dl.create(bad_status)

        wire_case = as_VulnerabilityCase(id_=CASE_ID, name="Ledger Test Case")
        activity = add_status_to_case_activity(
            bad_status, target=wire_case, actor=CASE_MANAGER_ID_2254
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID_2254, activity=event
        )
        assert result.status == Status.FAILURE

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ]
        assert len(entries) == 0, (
            "An invalid Add(CaseStatus) rejected by a precondition guard must"
            " produce zero CaseLedgerEntries (CLP-10-009)"
        )


# ---------------------------------------------------------------------------
# EmitCaseStatusUpdateNode — AC-1 pX promotion (SM-09-001)
# ---------------------------------------------------------------------------

EMIT_ACTOR_ID = "https://example.org/actors/emit-node-actor"
EMIT_PARTICIPANT_ID = f"{CASE_ID}/participants/emit-node-actor"


class TestEmitCaseStatusUpdateNodePromotion:
    """AC-1 / SM-09-001: EmitCaseStatusUpdateNode promotes pX states before write."""

    def _build_dl(self):
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=EMIT_ACTOR_ID)
        participant = CaseParticipant(
            id_=EMIT_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=EMIT_ACTOR_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Emit Promotion Test",
            attributed_to=EMIT_ACTOR_ID,
        )
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)
        return dl

    def test_pXa_promoted_to_PXa_by_emit_node(self):
        """AC-1 / SM-09-001: pXa in case.current_status is promoted to PXa."""
        from vultron.core.behaviors.status.nodes.case_status import (
            EmitCaseStatusUpdateNode,
        )
        from vultron.core.models.dimensions import EmDimension, PxaDimension

        dl = self._build_dl()

        # Seed a pXa CaseStatus — simulating a pre-AC-1 state or in-flight
        # transition where the exploit just became public (X fired).
        case_obj = dl.read(CASE_ID)
        assert isinstance(case_obj, VulnerabilityCase)
        pxa_seed = CaseStatus(
            context=CASE_ID,
            attributed_to=EMIT_ACTOR_ID,
            em=EmDimension(state=EM.NONE),
            pxa=PxaDimension(state=CS_pxa.pXa),
        )
        dl.create(pxa_seed)
        # Clear auto-seeded statuses so current_status resolves to the pXa seed
        case_obj.case_statuses.clear()
        case_obj.case_statuses.append(pxa_seed)
        dl.save(case_obj)

        node = EmitCaseStatusUpdateNode(case_id=CASE_ID)
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(tree=node, actor_id=EMIT_ACTOR_ID)
        assert result.status == Status.SUCCESS

        updated_case = dl.read(CASE_ID)
        assert isinstance(updated_case, VulnerabilityCase)
        last = updated_case.case_statuses[-1]
        if isinstance(last, str):
            last = dl.read(last)
        assert isinstance(last, CaseStatus)
        assert last.pxa.state is CS_pxa.PXa


# ---------------------------------------------------------------------------
# AC-4: FilterCsEmDimensionNode returns FAILURE on missing case (#2957)
# ---------------------------------------------------------------------------


class TestFilterCsEmDimensionNodeMissingCase:
    """AC-4 regression: FAILURE (not SUCCESS) when case absent from DataLayer.

    CLP-10-009: the guard must abort before GuardedCommit when the case
    cannot be resolved.  Prior to #2957 the node returned SUCCESS, allowing
    a ledger write for an unresolvable case.
    """

    def test_missing_case_returns_failure(self, bridge):
        """case_id set but case not in DataLayer → FAILURE."""
        node = FilterCsEmDimensionNode(case_id=CASE_ID, status_id=STATUS_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_missing_case_feedback_message_names_case(self, bridge):
        """FAILURE feedback_message includes the missing case_id."""
        node = FilterCsEmDimensionNode(case_id=CASE_ID, status_id=STATUS_ID)
        bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert node.feedback_message
        assert CASE_ID in node.feedback_message


# ---------------------------------------------------------------------------
# AC-5: FilterCsEmDimensionNode._clear() does not own BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE (#2957)
# ---------------------------------------------------------------------------


class TestFilterCsEmDimensionNodeClearBehavior:
    """AC-5 regression: _clear() must not zero BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE.

    That key is solely owned by FinalizeCsFilterNode (CONCERN-2711, BT-17-003).
    Prior to #2957 FilterCsEmDimensionNode zeroed it in _clear(), potentially
    wiping a value set by FinalizeCsFilterNode in the same tick.
    """

    def test_clear_preserves_ledger_override_sentinel(self, bridge):
        """Pre-seeded BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE survives _clear()."""
        sentinel = {"test": "sentinel_2957"}
        py_trees.blackboard.Blackboard.storage[
            "/ledger_payload_object_override"
        ] = sentinel

        # Empty DL → FAILURE after _clear(); _clear() must not touch the key.
        node = FilterCsEmDimensionNode(case_id=CASE_ID, status_id=STATUS_ID)
        bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        stored = py_trees.blackboard.Blackboard.storage.get(
            "/ledger_payload_object_override"
        )
        assert stored is sentinel, (
            "FilterCsEmDimensionNode._clear() must not zero"
            " BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE (CONCERN-2711, #2957)"
        )
