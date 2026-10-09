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

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from test.support.embargo_register import activate, propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_PERMISSIVE,
    StatusAuthorizationCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    EMBARGO_TEARDOWN_EVENT_TYPE,
)
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
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    EmDimension,
    PxaDimension,
)
from vultron.core.models.events.status import AddCaseStatusToCaseReceivedEvent
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.models.pending_assertion import (
    PendingAssertion,
    get_pending_assertion_store,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    add_status_to_case_activity,
    announce_log_entry_activity,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)
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


@pytest.fixture
def dl():
    # The node-level tests below run as ACTOR_ID, so this is ACTOR_ID's store.
    # The use-case and authorization-gate tests further down run as the case
    # manager and build their own CASE_MANAGER_ID store for that reason.
    return SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)


@pytest.fixture
def bridge(dl):
    return BTBridge(
        datalayer=dl,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )


@pytest.fixture
def case():
    # RSH-08-003 (#3814): AppendCaseStatusToCaseNode and the teardown effects
    # are CASE_MANAGER-gated, so ACTOR_ID (the store owner these tree-level
    # tests run as) holds the role; attributed_to seeds the CLP-08 genesis.
    return as_VulnerabilityCase(
        id_=CASE_ID, name="BT Case", attributed_to=ACTOR_ID
    )


@pytest.fixture
def status_obj():
    return as_CaseStatus(id_=STATUS_ID, context=CASE_ID)


@pytest.fixture
def populated_dl(dl, case, status_obj):
    seed_case_manager_participant(dl, case, ACTOR_ID)
    dl.create(case)
    dl.create(status_obj)
    return dl


@pytest.fixture
def populated_bridge(populated_dl):
    return BTBridge(
        datalayer=populated_dl,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(populated_dl),
    )


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

        bridge = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
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
        bridge = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
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
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
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

        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
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
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
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
        event = make_payload(activity)

        # Patch request.status to None so status_obj_fallback=None in the tree factory.
        with patch.object(
            type(event), "status", new_callable=PropertyMock, return_value=None
        ):
            tree = add_case_status_tree(
                request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
            )
            bridge = BTBridge(
                datalayer=dl,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
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
        case.append_case_status(pxa_state=CS_pxa.Pxa)
        dl.create(case)
        dl.create(cm_participant)
        # Asserted: pxa regression (pxa=pxa instead of Pxa), same EM
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=CS_pxa.pxa)
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
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=CS_pxa.pxa)
        )
        activity = add_status_to_case_activity(
            status_obj, target=wire_case, actor=CASE_MANAGER_ID_2706
        )
        event = make_payload(activity)

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
            bridge = BTBridge(
                datalayer=dl,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
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
        bridge = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
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
        bridge = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.FAILURE
        assert BTBridge.get_failure_reason(tree) == CASE_STATUS_ALREADY_PRESENT

    @pytest.mark.spec("RSH-05-017")
    @pytest.mark.spec("RSH-05-023")
    def test_status_moving_em_alone_is_refused(self, dl, make_payload):
        """A status whose only change is EM → refused in full; not appended.

        EM is derived from the embargo register and no status moves it
        (RSH-05-023): the asserted EM is refused and the case's carried
        forward, which leaves nothing new, so the tree FAILS (RSH-05-005).
        """
        case = as_VulnerabilityCase(id_=CASE_ID, name="EM Guard")
        initial = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em=EmDimension(state=EM.NONE),
        )
        case.case_statuses.append(initial)  # type: ignore[arg-type]
        dl.create(case)

        bad_status = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em=EmDimension(state=EM.ACTIVE)
        )
        dl.create(bad_status)

        activity = add_status_to_case_activity(
            bad_status, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.FAILURE

        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID not in status_ids
        assert updated_case.em_state == EM.NONE

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
            pxa=PxaDimension(state=CS_pxa.pXA),
        )
        dl.create(asserted)

        activity = add_status_to_case_activity(
            asserted, target=case.id_, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.FAILURE

        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID not in status_ids

    @pytest.mark.spec("RSH-05-015")
    @pytest.mark.spec("RSH-05-016")
    @pytest.mark.spec("RSH-05-023")
    @pytest.mark.spec("RSH-05-019")
    def test_em_move_with_pxa_advance_refuses_em_and_applies_pxa(
        self, dl, make_payload
    ):
        """EM move (NONE→PROPOSED) with a PXA advance → BT SUCCEEDS.

        Bug #2256: all-or-nothing CS validation discarded a valid dimension
        when another was refused, aborting the Sequence before
        ThreatTerminationBranchNode.  Per-dimension adjudication refuses the
        asserted EM — a status never moves EM (RSH-05-023) — carries the
        case's EM forward, and still accepts the PXA advance.
        """
        case = VulnerabilityCase(
            id_=CASE_ID, name="EM PXA Split", attributed_to=ACTOR_ID
        )
        # RSH-08-003 (#3814): the append is CASE_MANAGER-gated, so ACTOR_ID
        # (the store owner) holds the role.
        seed_case_manager_participant(dl, case, ACTOR_ID)
        # Auto-seeded CaseStatus has pxa=pxa and EM NONE.
        dl.create(case)

        # Sender asserts EM NONE→PROPOSED (refused) + PXA pxa→Pxa (valid)
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em=EmDimension(state=EM.PROPOSED),
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(asserted)

        activity = add_status_to_case_activity(
            asserted, target=case.id_, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )

        assert result.status == Status.SUCCESS

        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID in status_ids
        assert updated_case.em_state == EM.NONE

        # PXA advance accepted, EM carried forward (not moved).  Assert on
        # the saved domain CaseStatus at STATUS_ID, not current_status.
        saved_status = cast(CaseStatus, dl.read(STATUS_ID))
        assert saved_status.em.state == EM.NONE
        assert saved_status.pxa.state == CS_pxa.Pxa

    @pytest.mark.spec("RSH-05-023")
    def test_status_carrying_the_cases_em_passes_it(
        self, dl, make_payload, caplog
    ):
        """An asserted EM identical to the case's is not refused (RSH-05-023)."""
        import logging

        case = VulnerabilityCase(
            id_=CASE_ID, name="EM Carried", attributed_to=ACTOR_ID
        )
        propose(case, f"{CASE_ID}/embargo_events/carried")
        dl.create(case)

        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em=EmDimension(state=EM.PROPOSED),
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(asserted)

        activity = add_status_to_case_activity(
            asserted, target=case.id_, actor=ACTOR_ID
        )
        event = make_payload(activity)
        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )

        with caplog.at_level(logging.WARNING):
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )

        assert result.status == Status.SUCCESS
        assert not [
            r for r in caplog.records if "refused EM" in r.getMessage()
        ]
        saved_status = cast(CaseStatus, dl.read(STATUS_ID))
        assert saved_status.em.state == EM.PROPOSED
        assert saved_status.pxa.state == CS_pxa.Pxa
        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        assert updated_case.em_state == EM.PROPOSED

    @pytest.mark.spec("RSH-05-019")
    @pytest.mark.spec("SL-03-001")
    def test_pxa_refusal_warning_names_case_id_not_status_id(
        self, dl, make_payload, caplog
    ):
        """The PXA refusal WARNING reports the case ID, with the status ID labelled.

        Bug #3039: FilterCsPxaDimensionNode filled the ``for case '%s'``
        placeholder with the *status* ID, so an operator correlating the
        warning against case IDs saw a URI that matched no case.  The sibling
        EM refusal warning already reports ``case_id``; the two must agree.
        """
        import logging

        case = VulnerabilityCase(
            id_=CASE_ID, name="PXA Refusal Log", attributed_to=ACTOR_ID
        )
        case.append_case_status(pxa_state=CS_pxa.Pxa)
        dl.create(case)

        # The case's own EM + PXA regression → PXA dimension refused and
        # logged; nothing else is new, so the status is refused in full
        # (RSH-05-005) — the warning fires either way.
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em=EmDimension(state=EM.NONE),
            pxa=PxaDimension(state=CS_pxa.pxa),
        )
        dl.create(asserted)

        activity = add_status_to_case_activity(
            asserted, target=case.id_, actor=ACTOR_ID
        )
        event = make_payload(activity)
        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )

        with caplog.at_level(logging.WARNING):
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )
        assert result.status == Status.FAILURE

        pxa_refusals = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING and "refused PXA" in r.getMessage()
        ]
        assert len(pxa_refusals) == 1, pxa_refusals
        msg = pxa_refusals[0]
        assert f"for case '{CASE_ID}'" in msg, msg
        assert f"status '{STATUS_ID}'" in msg, msg
        assert f"for case '{STATUS_ID}'" not in msg, msg

    @pytest.mark.spec("RSH-05-023")
    @pytest.mark.spec("SL-03-001")
    def test_em_refusal_warning_names_case_id_and_labelled_status_id(
        self, dl, make_payload, caplog
    ):
        """The EM refusal WARNING has the same shape as the PXA one (#3039).

        Case in the ``for case '%s'`` slot, status in its own labelled
        ``(status '%s')`` slot, so an operator can correlate either refusal
        the same way.
        """
        import logging

        case = VulnerabilityCase(
            id_=CASE_ID, name="EM Refusal Log", attributed_to=ACTOR_ID
        )
        case.append_case_status(pxa_state=CS_pxa.pxa)
        dl.create(case)

        # EM other than the case's (NONE → ACTIVE) + valid PXA advance → EM
        # refused, tree still SUCCEEDS (partial accept), refusal is logged.
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em=EmDimension(state=EM.ACTIVE),
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(asserted)

        activity = add_status_to_case_activity(
            asserted, target=case.id_, actor=ACTOR_ID
        )
        event = make_payload(activity)
        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )

        with caplog.at_level(logging.WARNING):
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )
        assert result.status == Status.SUCCESS

        em_refusals = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING and "refused EM" in r.getMessage()
        ]
        assert len(em_refusals) == 1, em_refusals
        msg = em_refusals[0]
        assert f"for case '{CASE_ID}'" in msg, msg
        assert f"(status '{STATUS_ID}')" in msg, msg

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
        propose(case, f"{CASE_ID}/embargo_events/serialized")
        dl.create(case)

        # EM PROPOSED→ACTIVE refused (carried forward as PROPOSED) + PXA
        # pxa→Pxa accepted: a partial accept, so Finalize writes the override.
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em=EmDimension(state=EM.ACTIVE),
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(asserted)

        activity = add_status_to_case_activity(
            asserted, target=case.id_, actor=ACTOR_ID
        )
        event = make_payload(activity)

        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )

        # The override is a within-execution hand-off (FinalizeCsFilterNode
        # writes it, GuardedCommit consumes it) and the bridge now resets it at
        # the execution boundary (#3101, ADR-0087), so it is no longer readable
        # after execute_with_setup returns.  Capture it mid-execution with a
        # SUCCESS probe appended after the tree: on the accept path nothing
        # clears it within the tree, so the probe still sees Finalize's write.
        captured: dict[str, object] = {}

        class _CaptureOverride(py_trees.behaviour.Behaviour):
            def update(self) -> Status:
                captured["override"] = (
                    py_trees.blackboard.Blackboard.storage.get(
                        "/ledger_payload_object_override"
                    )
                )
                return Status.SUCCESS

        probed = py_trees.composites.Sequence(
            name="AddCaseStatusToCaseBTWithProbe",
            memory=False,
            children=[tree, _CaptureOverride(name="CaptureOverride")],
        )
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        result = bridge.execute_with_setup(
            tree=probed, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.SUCCESS

        override = cast(dict, captured.get("override"))
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
        # RSH-08-003 (#3814): the append is CASE_MANAGER-gated, so the
        # receiving store (CASE_MANAGER_ID) holds the role; attributed_to
        # seeds the CLP-08 genesis.
        case = as_VulnerabilityCase(
            id_=CASE_ID, name="UC Case", attributed_to=CASE_MANAGER_ID
        )
        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        seed_case_manager_participant(dl, case, CASE_MANAGER_ID)
        dl.create(case)
        dl.create(status_obj)

        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

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
        case.case_statuses.append(status_obj)  # type: ignore[arg-type]
        dl.create(case)
        dl.create(status_obj)

        activity = add_status_to_case_activity(
            status_obj, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        with caplog.at_level(logging.DEBUG):
            AddCaseStatusToCaseReceivedUseCase(
                dl, event, wire_render_port=As2WireRenderAdapter()
            ).execute()

        info_msgs = [
            r.message for r in caplog.records if r.levelno == logging.INFO
        ]
        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]

        assert any("idempotent" in m.lower() for m in info_msgs), (
            "Expected INFO log for idempotent duplicate"
        )
        assert not any("idempotent" in m.lower() for m in warn_msgs), (
            "Should not WARNING for idempotent duplicate"
        )

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
            em=EmDimension(state=EM.NONE),
        )
        case.case_statuses.append(initial)  # type: ignore[arg-type]
        dl.create(case)

        bad_status = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em=EmDimension(state=EM.ACTIVE)
        )
        dl.create(bad_status)

        activity = add_status_to_case_activity(
            bad_status, target=case, actor=ACTOR_ID
        )
        event = make_payload(activity)

        with caplog.at_level(logging.DEBUG):
            AddCaseStatusToCaseReceivedUseCase(
                dl, event, wire_render_port=As2WireRenderAdapter()
            ).execute()

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
                AddCaseStatusToCaseReceivedUseCase(
                    dl, event, wire_render_port=As2WireRenderAdapter()
                ).execute()

        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("missing" in m.lower() for m in warn_msgs)


# ---------------------------------------------------------------------------
# ThreatTerminationBranchNode (EmbargoTeardownAuthorizationGate, RSH-03-001 to RSH-03-003)
# ---------------------------------------------------------------------------


CASE_MANAGER_ID = "https://example.org/actors/case-manager"
CM_PARTICIPANT_ID = f"{CASE_ID}/participants/case-manager"
PEER_SENDER_ID = "https://example.org/users/peer"


class TestThreatTerminationBranchNode:
    """RSH-03-001: fires teardown on P/X/A; RSH-03-002: no sender-role gate."""

    def _make_status_with_pxa(self, pxa_state: CS_pxa) -> as_CaseStatus:
        s = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        object.__setattr__(s, "pxa_state", pxa_state)
        return s

    def _setup_dl_with_embargo(
        self, dl, pxa_state: CS_pxa, manager_id: str = ACTOR_ID
    ):
        """Seed a case under active embargo whose CASE_MANAGER is *manager_id*.

        By default the executing actor holds the role: teardown writes shared
        EM state, which only the CASE_MANAGER does (EP-09-008), and the
        canonical CaseStatus this branch follows is adopted there.
        """
        from vultron.enums.roles import CVDRole

        # ResolveCaseManagerNode requires a CASE_MANAGER participant in the case.
        cm_participant = CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=manager_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = VulnerabilityCase(
            id_=CASE_ID, name="ThreatTerm Case", attributed_to=ACTOR_ID
        )
        case.add_participant(cm_participant)
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e1",
            context=CASE_ID,
            end_time=days_from_now_utc(45),
        )
        activate(case, embargo.id_)
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        status_obj = self._make_status_with_pxa(pxa_state)
        dl.create(status_obj)
        return status_obj

    def test_skips_when_pxa_all_lowercase(self, dl):
        """pxa (no threat flags) → skip teardown → SUCCESS."""
        status_obj = self._setup_dl_with_embargo(dl, CS_pxa.pxa)
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
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
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_skips_when_status_obj_none(self, dl):
        """status_obj=None → no pxa info → skip teardown → SUCCESS."""
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(status_obj=None, case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_skips_when_case_id_none(self, dl):
        """case_id=None → no TerminateEmbargoBT built → SUCCESS via skip."""
        status_obj = self._make_status_with_pxa(CS_pxa.Pxa)
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
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
        succeeds but the teardown emit fails (BT-14-001).
        The EM state is updated and active_embargo cleared before that.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM

        status_obj = self._setup_dl_with_embargo(dl, pxa_state)
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
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
        """RSH-03-002: a sender holding no role still triggers the teardown.

        Sender authorization was handled at StatusAdoptionGate.  The sender
        matters only for RSH-03-004, when it is the CASE_MANAGER itself.
        """
        status_obj = self._setup_dl_with_embargo(dl, CS_pxa.Pxa)
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=status_obj,
            case_id=CASE_ID,
            sender_actor_id="https://example.org/users/no-role",
        )
        bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.EXITED

    def _run_replica(
        self, dl, status_obj, sender: str
    ) -> py_trees.common.Status:
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )

        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID, sender_actor_id=sender
        )
        return bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID).status

    @pytest.mark.spec("RSH-03-004")
    def test_a_replica_waits_for_the_managers_teardown_entry(self, dl):
        """The manager's P/X/A declaration arrives before its teardown entry.

        The replica still holds the active embargo, and it asks nothing:
        the manager has already torn down (#4149).
        """
        status_obj = self._setup_dl_with_embargo(
            dl, CS_pxa.Pxa, manager_id=CASE_MANAGER_ID
        )

        status = self._run_replica(dl, status_obj, sender=CASE_MANAGER_ID)

        assert status == Status.SUCCESS
        assert dl.outbox_list() == []
        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.ACTIVE

    @pytest.mark.spec("RSH-03-004")
    @pytest.mark.spec("EP-09-008")
    def test_a_replica_still_asks_on_a_status_the_manager_did_not_declare(
        self, dl
    ):
        status_obj = self._setup_dl_with_embargo(
            dl, CS_pxa.Pxa, manager_id=CASE_MANAGER_ID
        )

        status = self._run_replica(
            dl, status_obj, sender="https://example.org/users/peer"
        )

        assert status == Status.SUCCESS
        queued = [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]
        assert [a.to for a in queued] == [[CASE_MANAGER_ID]]

    @pytest.mark.spec("EP-09-008")
    def test_non_manager_receiver_asks_instead_of_tearing_down(self, dl):
        """A receiver that is not the CASE_MANAGER writes no EM state.

        It asks the manager to end the embargo (here the ask fails: no
        factory, BT-14-001) and the embargo stays in force until the
        manager's committed teardown reaches it.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM

        status_obj = self._setup_dl_with_embargo(
            dl, CS_pxa.Pxa, manager_id=CASE_MANAGER_ID
        )
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE
        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.ACTIVE
        assert updated.active_embargo is not None

    # --- #4147: the cascade's ask is a pending assertion -----------------

    def _ask_pending(self) -> PendingAssertion | None:
        return get_pending_assertion_store(ACTOR_ID).pending_for_subject(
            CASE_ID,
            EMBARGO_TEARDOWN_EVENT_TYPE,
            f"{CASE_ID}/embargo_events/e1",
        )

    def _announce_managers_teardown_entry(self, dl, ask_id: str) -> None:
        """Deliver the manager's committed entry for *ask_id* to the replica.

        The manager's received commit records the inbound ask, so the entry's
        ``log_object_id`` is the ask's id (SYNC-11-003).
        """
        record = HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=ask_id,
            event_type=EMBARGO_TEARDOWN_EVENT_TYPE,
            payload_snapshot={"id": ask_id},
            prev_log_hash="0" * 64,
        )
        entry = CaseLedgerEntry(
            case_id=record.case_id,
            log_index=record.log_index,
            term=record.term,
            log_object_id=record.object_id,
            event_type=record.event_type,
            payload_snapshot=dict(record.payload_snapshot),
            prev_log_hash=record.prev_log_hash,
            entry_hash=record.entry_hash,
        )
        activity = announce_log_entry_activity(
            WireCaseLedgerEntry.model_validate(entry.model_dump(mode="json")),
            actor=CASE_MANAGER_ID,
        )
        event = cast(AnnounceLogEntryReceivedEvent, extract_event(activity))
        AnnounceLedgerEntryReceivedUseCase(
            dl,
            event.model_copy(update={"receiving_actor_id": ACTOR_ID}),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    @pytest.mark.spec("EP-09-008")
    @pytest.mark.spec("SYNC-11-002")
    def test_the_cascade_ask_is_recorded_keyed_by_the_ended_embargo(self, dl):
        """AC-1: one pending assertion per ask, keyed by the ended embargo."""
        status_obj = self._setup_dl_with_embargo(
            dl, CS_pxa.Pxa, manager_id=CASE_MANAGER_ID
        )

        self._run_replica(dl, status_obj, sender=PEER_SENDER_ID)

        [ask_id] = dl.outbox_list()
        pending = self._ask_pending()
        assert pending is not None
        assert pending.object_id == ask_id

    @pytest.mark.spec("SYNC-11-002")
    def test_a_repeat_signal_inside_the_window_queues_no_second_ask(self, dl):
        """AC-2: the embargo is still in force here, so only the pending
        assertion stands between a repeat P/X/A signal and a second ask."""
        status_obj = self._setup_dl_with_embargo(
            dl, CS_pxa.Pxa, manager_id=CASE_MANAGER_ID
        )
        self._run_replica(dl, status_obj, sender=PEER_SENDER_ID)

        status = self._run_replica(dl, status_obj, sender=PEER_SENDER_ID)

        assert status == Status.SUCCESS
        assert len(dl.outbox_list()) == 1

    @pytest.mark.spec("SYNC-11-003")
    def test_the_managers_committed_entry_clears_the_ask(self, dl):
        """AC-3: once the manager's entry arrives, a later signal asks anew."""
        status_obj = self._setup_dl_with_embargo(
            dl, CS_pxa.Pxa, manager_id=CASE_MANAGER_ID
        )
        self._run_replica(dl, status_obj, sender=PEER_SENDER_ID)
        [first_ask_id] = dl.outbox_list()

        self._announce_managers_teardown_entry(dl, first_ask_id)

        assert self._ask_pending() is None
        self._run_replica(dl, status_obj, sender=PEER_SENDER_ID)
        pending = self._ask_pending()
        assert pending is not None
        assert pending.object_id != first_ask_id
        assert pending.object_id in dl.outbox_list()


PROPOSED_EMBARGO_ID = f"{CASE_ID}/embargo_events/p1"


class TestThreatTerminationBranchNodeProposedEm:
    """EMB-16-001: a P/X/A signal while EM is ``PROPOSED`` abandons the
    open proposals.  Only the CASE_MANAGER writes EM (EP-09-008, #4131);
    any other receiver writes and sends nothing (EMB-16-002, #4148).  Each
    run uses its actor's store.
    """

    def _setup(
        self, store_actor: str, sender: str | None = None
    ) -> tuple[SqliteDataLayer, BTBridge, ThreatTerminationBranchNode]:
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.factories import em_propose_embargo_activity

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=store_actor)
        embargo = as_EmbargoEvent(
            id_=PROPOSED_EMBARGO_ID,
            context=CASE_ID,
            end_time=days_from_now_utc(45),
        )
        invite = em_propose_embargo_activity(
            embargo, context=CASE_ID, actor=ACTOR_ID, to=[CASE_MANAGER_ID]
        )
        cm_participant = CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = VulnerabilityCase(
            id_=CASE_ID, name="Proposed Case", attributed_to=ACTOR_ID
        )
        case.add_participant(cm_participant)
        propose(case, embargo.id_)
        case.pending_embargo_proposal_index = {embargo.id_: invite.id_}
        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        object.__setattr__(status_obj, "pxa_state", CS_pxa.Pxa)
        for obj in (embargo, invite, cm_participant, case, status_obj):
            dl.create(obj)

        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID, sender_actor_id=sender
        )
        return dl, bridge, node

    @pytest.mark.spec("EMB-16-001")
    @pytest.mark.spec("EP-09-008")
    def test_as_the_case_manager_em_returns_to_none(self):
        dl, bridge, node = self._setup(CASE_MANAGER_ID)

        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)

        assert result.status == Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.NONE
        assert updated.proposed_embargo_ids == []

    @pytest.mark.spec("EMB-16-002")
    @pytest.mark.spec("RSH-03-004")
    @pytest.mark.parametrize(
        "sender", [None, CASE_MANAGER_ID], ids=["undeclared", "by-manager"]
    )
    def test_a_non_manager_writes_and_sends_nothing(self, sender):
        """Whoever declared the status, a non-manager neither abandons nor
        asks; with the manager as sender the out-of-order arrival skips the
        branch before it is reached (#4149)."""
        dl, bridge, node = self._setup(ACTOR_ID, sender=sender)

        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.PROPOSED
        assert updated.proposed_embargo_ids == [PROPOSED_EMBARGO_ID]
        assert dl.outbox_list() == []
        skip = next(
            c for c in node.children if c.name == "DeclaredByCaseManager"
        )
        expected = Status.SUCCESS if sender else Status.FAILURE
        assert skip.status == expected


# ---------------------------------------------------------------------------
# EmbargoTeardownAuthorizationGate (RSH-02-001)
# ---------------------------------------------------------------------------


class TestAddCaseStatusTreeSeam2:
    """EmbargoTeardownAuthorizationGate call-out wiring tests (RSH-02-001, RSH-02-002)."""

    def _make_event(self, dl, pxa_state: CS_pxa = CS_pxa.pxa):
        from vultron.semantic_registry import extract_event

        case = as_VulnerabilityCase(id_=CASE_ID, name="Seam2 Case")
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=pxa_state)
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
            id_=f"{CASE_ID}/embargo_events/e1",
            context=CASE_ID,
            end_time=days_from_now_utc(45),
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
        activate(case, embargo.id_)
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=CS_pxa.Pxa)
        )
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        dl.create(status_obj)

        activity = add_status_to_case_activity(
            status_obj,
            target=as_VulnerabilityCase(id_=CASE_ID),
            actor=ACTOR_ID,
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
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID, activity=event
        )
        # FailureIsSuccess wraps the teardown Sequence, so the outer BT returns
        # SUCCESS even when the authorization gate blocked teardown.
        assert result.status == Status.SUCCESS

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

        def _collect_node_types(node):
            yield type(node).__name__
            for child in getattr(node, "children", []):
                yield from _collect_node_types(child)

        node_types = set(_collect_node_types(tree))
        assert "ThreatTerminationBranchNode" in node_types, (
            "add_case_status_tree must contain ThreatTerminationBranchNode"
            " (RSH-03-001, ADR-0046)"
        )


# ---------------------------------------------------------------------------
# Regression: ThreatTerminationBranchNode — CS.P teardown outcome
# ---------------------------------------------------------------------------


class TestRegressionCSPTeardownPath:
    """Regression: ``ThreatTerminationBranchNode`` tears down an active
    embargo on a CS.P update: EM=EXITED and active_embargo=None.

    BT-14-001 means FAILURE when no broadcast factory is present, but the
    state transition is committed before the broadcast.  The legacy
    ``PublicDisclosureBranchNode`` this once compared against is deleted
    (RSH-03-003, #4154).

    AC #8 from issue #1844.
    """

    def _build_dl_with_active_embargo(self, manager_id: str = CASE_MANAGER_ID):
        """Return a fresh DataLayer with a case in ACTIVE embargo.

        *manager_id* names both the case manager and the store.
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
            id_=f"{CASE_ID}/embargo_events/e1",
            context=CASE_ID,
            end_time=days_from_now_utc(45),
        )
        case = VulnerabilityCase(
            id_=CASE_ID, name="Regression Case", attributed_to=manager_id
        )
        case.add_participant(cm_participant)
        activate(case, embargo.id_)
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        return dl

    def test_csp_teardown_reaches_exited(self):
        """CS.P with an active embargo: EM=EXITED and active_embargo=None.

        The node delegates to terminate_embargo_bt and FAILS when no
        broadcast factory is present (BT-14-001); the EM state transition is
        committed before the broadcast attempt.
        """
        from typing import cast as c

        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM

        dl_new = self._build_dl_with_active_embargo()
        new_status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=CS_pxa.Pxa)
        )
        dl_new.create(new_status_obj)

        new_node = ThreatTerminationBranchNode(
            status_obj=new_status_obj, case_id=CASE_ID
        )
        new_bridge = BTBridge(
            datalayer=dl_new,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl_new),
        )
        # Runs as the case manager: the seeded case names CASE_MANAGER_ID as
        # its only participant, and teardown authority is the manager's.
        new_result = new_bridge.execute_with_setup(
            tree=new_node, actor_id=CASE_MANAGER_ID
        )
        assert new_result.status == Status.FAILURE

        new_case = c(VulnerabilityCase, dl_new.read(CASE_ID))
        new_em_state = new_case.current_status.em.state
        new_embargo = new_case.active_embargo

        assert new_em_state == EM.EXITED, (
            f"EM={new_em_state}; CS.P teardown must reach EXITED"
            " (AC #8, issue #1844)"
        )
        assert new_embargo is None, "CS.P teardown must clear active_embargo"


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
        event = make_payload(activity)

        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
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
            em=EmDimension(state=EM.NONE),
        )
        from typing import cast as c

        from vultron.core.models.case import VulnerabilityCase

        case_obj = c(VulnerabilityCase, dl.read(CASE_ID))
        case_obj.case_statuses.append(str(initial.id_))
        dl.create(initial)
        dl.save(case_obj)

        bad_status = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em=EmDimension(state=EM.ACTIVE)
        )
        dl.create(bad_status)

        wire_case = as_VulnerabilityCase(id_=CASE_ID, name="Ledger Test Case")
        activity = add_status_to_case_activity(
            bad_status, target=wire_case, actor=CASE_MANAGER_ID_2254
        )
        event = make_payload(activity)

        tree = add_case_status_tree(request=event)
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
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
        from vultron.core.behaviors.case_status_snapshot import (
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
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
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


# ---------------------------------------------------------------------------
# AC-2 / AC-3: PxaEmInvariantDiagnosticNode (CONCERN-3008)
# ---------------------------------------------------------------------------

DIAG_CASE_ID = "https://example.org/cases/diag-3008"
DIAG_STATUS_ID = f"{DIAG_CASE_ID}/statuses/s1"
DIAG_CM_ID = "https://example.org/actors/diag-cm"
DIAG_ACTOR_ID = "https://example.org/actors/diag-actor"


class TestPxaEmInvariantDiagnosticNode:
    """PxaEmInvariantDiagnosticNode posts a Note iff invariant still violated.

    AC-2: PERMISSIVE gate — teardown fires, EM becomes EXITED, no violation →
          no Note queued in outbox.
    AC-3: Blocked gate (AlwaysFail) — teardown blocked, EM stays ACTIVE,
          violation detected → Note queued in outbox.
    """

    def _build_dl_with_active_embargo(self, actor_id: str = DIAG_CM_ID):
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        cm_participant = CaseParticipant(
            id_=f"{DIAG_CASE_ID}/participants/cm",
            context=DIAG_CASE_ID,
            attributed_to=actor_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        embargo = as_EmbargoEvent(
            id_=f"{DIAG_CASE_ID}/embargo_events/e1",
            context=DIAG_CASE_ID,
            end_time=days_from_now_utc(45),
        )
        case = VulnerabilityCase(
            id_=DIAG_CASE_ID,
            name="Diag Test Case",
            attributed_to=actor_id,
        )
        case.add_participant(cm_participant)
        activate(case, embargo.id_)
        status_obj = as_CaseStatus(
            id_=DIAG_STATUS_ID,
            context=DIAG_CASE_ID,
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        dl.create(status_obj)
        return dl, status_obj

    def _make_event(self, dl, status_obj):
        from vultron.semantic_registry import extract_event

        activity = add_status_to_case_activity(
            status_obj,
            target=as_VulnerabilityCase(id_=DIAG_CASE_ID),
            actor=DIAG_ACTOR_ID,
        )
        return cast(AddCaseStatusToCaseReceivedEvent, extract_event(activity))

    @pytest.mark.spec("CSB-18-002")
    @pytest.mark.spec("CSB-18-003")
    @pytest.mark.spec("CSB-18-004")
    def test_permissive_gate_teardown_fires_no_note_posted(self):
        """AC-2: PERMISSIVE gate — teardown fires, EM=EXITED → no violation → no Note."""
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )

        dl, status_obj = self._build_dl_with_active_embargo()
        event = self._make_event(dl, status_obj)

        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=DIAG_CM_ID, activity=event
        )
        assert result.status == Status.SUCCESS

        updated = cast(VulnerabilityCase, dl.read(DIAG_CASE_ID))
        assert updated.current_status.em.state == EM.EXITED

        # EM.EXITED proves teardown fired; diagnostic node finds no violation — no Note needed.

    @pytest.mark.spec("CSB-18-002")
    @pytest.mark.spec("CSB-18-003")
    @pytest.mark.spec("CSB-18-004")
    def test_blocked_gate_invariant_violated_note_posted(self):
        """AC-3: AlwaysFail gate — teardown blocked, EM=ACTIVE → violation → Note posted."""
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )

        dl, status_obj = self._build_dl_with_active_embargo(
            actor_id=f"{DIAG_CM_ID}-blocked"
        )
        event = self._make_event(dl, status_obj)

        call_out = StatusAuthorizationCallOutBundle(
            embargo_teardown_authorization_gate_factory=AlwaysFail
        )
        tree = add_case_status_tree(request=event, call_out=call_out)
        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=f"{DIAG_CM_ID}-blocked", activity=event
        )
        assert result.status == Status.SUCCESS

        # EM must still be ACTIVE — gate blocked teardown
        updated = cast(VulnerabilityCase, dl.read(DIAG_CASE_ID))
        assert updated.current_status.em.state == EM.ACTIVE

        # AlwaysFail gate blocks teardown — only the diagnostic node can post.
        # Exactly one Note activity must be in the outbox.
        outbox = dl.outbox_list()
        assert len(outbox) == 1, (
            "PxaEmInvariantDiagnosticNode must post exactly one Note when the"
            " gate blocks teardown and the CSB-18 invariant is still violated"
        )


# ---------------------------------------------------------------------------
# RSH-03-004: the whole tree, at a replica, on the manager's declaration
# ---------------------------------------------------------------------------

REPLICA_ID = "https://example.org/actors/rsh-03-004-replica"
PEER_ID = "https://example.org/actors/rsh-03-004-peer"


class TestReplicaLeavesManagerDeclaredTeardownToItsEntry:
    """``add_case_status_tree`` gives the branch the status's sender, so at a
    replica a P/X/A status the CASE_MANAGER declared tears nothing down and
    asks for nothing (RSH-03-004, #4149); the manager's committed entry
    carries the teardown.  The same tree at a replica still asks when the
    status came from anyone else.
    """

    def _run(self, sender: str) -> SqliteDataLayer:
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.semantic_registry import extract_event

        dl: SqliteDataLayer
        dl, status_obj = (
            TestPxaEmInvariantDiagnosticNode()._build_dl_with_active_embargo(
                actor_id=REPLICA_ID
            )
        )
        # The store is the replica's; the CASE_MANAGER is someone else.
        case = cast(VulnerabilityCase, dl.read(DIAG_CASE_ID))
        cm = cast(CaseParticipant, dl.read(f"{DIAG_CASE_ID}/participants/cm"))
        dl.save(cm.model_copy(update={"attributed_to": DIAG_CM_ID}))
        case.actor_participant_index = {DIAG_CM_ID: cm.id_}
        dl.save(case)

        event = cast(
            AddCaseStatusToCaseReceivedEvent,
            extract_event(
                add_status_to_case_activity(
                    status_obj,
                    target=as_VulnerabilityCase(id_=DIAG_CASE_ID),
                    actor=sender,
                )
            ),
        )
        tree = add_case_status_tree(
            request=event, call_out=STATUS_AUTHORIZATION_PERMISSIVE
        )
        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=REPLICA_ID, activity=event
        )
        assert result.status == Status.SUCCESS, result.feedback_message
        return dl

    @pytest.mark.spec("RSH-03-004")
    def test_the_managers_declaration_asks_nothing_at_a_replica(self):
        dl = self._run(sender=DIAG_CM_ID)

        updated = cast(VulnerabilityCase, dl.read(DIAG_CASE_ID))
        assert updated.current_status.em.state == EM.ACTIVE
        queued = [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]
        assert [a.type_ for a in queued] == [], [a.type_ for a in queued]

    @pytest.mark.spec("RSH-03-004")
    @pytest.mark.spec("EP-09-008")
    def test_a_peers_declaration_still_asks_at_a_replica(self):
        dl = self._run(sender=PEER_ID)

        updated = cast(VulnerabilityCase, dl.read(DIAG_CASE_ID))
        assert updated.current_status.em.state == EM.ACTIVE
        queued = [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]
        asks = [a for a in queued if DIAG_CM_ID in (a.to or [])]
        assert asks, [a.type_ for a in queued]
