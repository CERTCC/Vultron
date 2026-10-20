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

``Add(CaseStatus)`` is the CASE_MANAGER's record of the case status it
adopted, admitted only from the case's CASE_MANAGER at a participant replica
(RSH-04-001, RSH-04-005).  The tree-level and use-case tests here therefore
run at a replica — the store's owner is an ordinary participant and the case
names another actor as its CASE_MANAGER — with the CASE_MANAGER as sender, and
assert that the guards they target, not the sender guard, decided the verdict
(``door_guards_admitted``).  A replica writes no case state on receipt
(RSH-08-003); the CASE_MANAGER's adoption of a participant's P, X or A, its
teardown gate and its CSB-18 note are tested on ``Add(ParticipantStatus)`` in
``test_add_participant_status_bt.py``.

Covers:
  - CheckCaseStatusIdempotencyNode, the Cs dimension filters and the
    Cs invariant guards (node level and through the tree);
  - the sender rule: refused at the CASE_MANAGER and from a non-manager;
  - ThreatTerminationBranchNode and EmitCaseStatusUpdateNode (node level).

Regression coverage:
  - Bug #2704: FilterCsEmDimensionNode must return FAILURE (not SUCCESS) when
    _resolve_asserted() returns None (CLP-10-009).
  - Bug #2706: FilterCsPxaDimensionNode must write the updated accumulator back
    via _set_output so PXA refusals survive a copy-returning blackboard.

Per issue #758 AC-1, AC-3; issue #4851.
"""

from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_participant,
)
from test.support.embargo_register import activate, propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.carried_object_case import (
    CarriedObjectInTargetCaseNode,
)
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    EMBARGO_TEARDOWN_SEMANTIC_TYPE,
)
from vultron.core.behaviors.status.add_case_status_tree import (
    add_case_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    CASE_STATUS_ALREADY_PRESENT,
    CheckCaseStatusIdempotencyNode,
)
from vultron.core.behaviors.status.nodes.cs_dimension_filter import (
    FilterCsEmDimensionNode,
    FilterCsPxaDimensionNode,
    FinalizeCsFilterNode,
)
from vultron.core.behaviors.status.nodes.cs_invariant_guards import (
    CheckCsEphemeralStateNode,
)
from vultron.core.behaviors.status.nodes.lifecycle import (
    ThreatTerminationBranchNode,
)
from vultron.core.models._helpers import _as_id, days_from_now_utc
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
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.use_cases.received._bt_verdict import (
    door_guards_admitted,
    node_failed,
)
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

#: The store owner of the replica tests: an ordinary participant.
ACTOR_ID = "https://example.org/actors/vendor"
#: The case's CASE_MANAGER: the only sender of ``Add(CaseStatus)``.
CASE_MANAGER_ID = "https://example.org/actors/case-manager"
CM_PARTICIPANT_ID = (
    "https://example.org/cases/case-bt-01/participants/case-manager"
)
CASE_ID = "https://example.org/cases/case-bt-01"
#: The declared rule the factory composes the sender guard from (HP-01-008).
_CASE_STATUS_RULE = AddCaseStatusToCaseReceivedUseCase.sender_entitlement
STATUS_ID = "https://example.org/cases/case-bt-01/statuses/s1"
STATUS2_ID = "https://example.org/cases/case-bt-01/statuses/s2"


# ---------------------------------------------------------------------------
# Replica helpers
# ---------------------------------------------------------------------------


def _replica_store(
    case: VulnerabilityCase, replica_id: str = ACTOR_ID
) -> SqliteDataLayer:
    """*replica_id*'s store holding *case*, seated beside its CASE_MANAGER.

    The CASE_MANAGER is :data:`CASE_MANAGER_ID`, so the store's owner
    receives ``Add(CaseStatus)`` as a participant replica (RSH-04-005).
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=replica_id)
    seed_case_manager_participant(dl, case, CASE_MANAGER_ID)
    seed_case_participant(dl, case, replica_id)
    dl.create(case)
    return dl


def _from_manager(
    status: as_CaseStatus,
    target: str | as_VulnerabilityCase = CASE_ID,
    replica_id: str = ACTOR_ID,
):
    """The CASE_MANAGER's ``Add(CaseStatus)``, addressed to *replica_id*."""
    return add_status_to_case_activity(
        status, target=target, actor=CASE_MANAGER_ID, to=[replica_id]
    )


def _run_at_replica(
    dl: SqliteDataLayer,
    event: AddCaseStatusToCaseReceivedEvent,
    tree: py_trees.behaviour.Behaviour | None = None,
):
    """Run *tree* (default: the AddCaseStatus tree for *event*) at the replica.

    Returns ``(result, tree)``.
    """
    tree = tree or add_case_status_tree(
        sender_rule=_CASE_STATUS_RULE, request=event
    )
    bridge = BTBridge(
        datalayer=dl,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )
    result = bridge.execute_with_setup(
        tree=tree, actor_id=str(dl.actor_id), activity=event
    )
    return result, tree


def _ledger_entries(dl: SqliteDataLayer) -> list[CaseLedgerEntry]:
    return [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
    ]


def _status_ids(dl: SqliteDataLayer) -> list[str | None]:
    case = cast(VulnerabilityCase, dl.read(CASE_ID))
    return [_as_id(s) for s in case.case_statuses]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dl():
    # The node-level tests below run as ACTOR_ID, so this is ACTOR_ID's store.
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
    # ACTOR_ID's replica of a case the CASE_MANAGER holds; attributed_to
    # seeds the CLP-08 genesis.
    return as_VulnerabilityCase(
        id_=CASE_ID, name="BT Case", attributed_to=CASE_MANAGER_ID
    )


@pytest.fixture
def status_obj():
    return as_CaseStatus(id_=STATUS_ID, context=CASE_ID)


@pytest.fixture
def populated_dl(dl, case, status_obj):
    seed_case_manager_participant(dl, case, CASE_MANAGER_ID)
    seed_case_participant(dl, case, ACTOR_ID)
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
        """Full tree: an unresolvable status fails FilterCsEmDimensionNode
        before GuardedCommit → zero CaseLedgerEntries (#2704).

        Runs at a replica, from the CASE_MANAGER (RSH-04-005), so the sender
        guard admits it and the filter is what refuses it.
        """
        from unittest.mock import PropertyMock, patch

        case = VulnerabilityCase(
            id_=CASE_ID, name="2704 Case", attributed_to=CASE_MANAGER_ID
        )
        dl = _replica_store(case)
        # STATUS_ID intentionally NOT written to DL — _resolve_asserted() returns None.
        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        event = make_payload(_from_manager(status_obj))

        # Patch request.status to None so status_obj_fallback=None in the tree factory.
        with patch.object(
            type(event), "status", new_callable=PropertyMock, return_value=None
        ):
            result, tree = _run_at_replica(dl, event)

        assert result.status == Status.FAILURE
        assert door_guards_admitted(tree)
        # The case check (HP-08-007) now refuses it first; the filter's own
        # FAILURE is pinned by test_guard_fails_when_status_unresolvable.
        assert node_failed(tree, CarriedObjectInTargetCaseNode) or node_failed(
            tree, FilterCsEmDimensionNode
        ), (
            "An unresolvable status must be rejected by a precondition guard"
            " before GuardedCommit fires (CLP-10-009, #2704)"
        )
        assert _ledger_entries(dl) == []


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

        Runs at a replica, from the CASE_MANAGER (RSH-04-005), so the sender
        guard admits it and FinalizeCsFilterNode is what refuses it.
        """
        import copy as _copy
        from unittest.mock import patch

        case = VulnerabilityCase(
            id_=CASE_ID, name="2706 Case", attributed_to=CASE_MANAGER_ID
        )
        case.append_case_status(pxa=CS_pxa.Pxa)
        dl = _replica_store(case)
        # Asserted: pxa regression (pxa=pxa instead of Pxa), same EM
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=CS_pxa.pxa)
        )
        dl.create(status_obj)
        event = make_payload(_from_manager(status_obj))

        # Patch get_input on FilterCsPxaDimensionNode to return a DEEP COPY of
        # any dict, simulating a blackboard that never returns mutable
        # references.  A shallow dict() copy shares nested lists, so deep copy
        # is required to isolate the mutation from the stored object.
        _real_get_input = FilterCsPxaDimensionNode.get_input

        def _copy_returning(self_node, port_name, default=None):
            val = _real_get_input(self_node, port_name, default)
            return _copy.deepcopy(val) if isinstance(val, dict) else val

        with patch.object(
            FilterCsPxaDimensionNode, "get_input", new=_copy_returning
        ):
            result, tree = _run_at_replica(dl, event)

        # pxa regression with no EM change → whole refusal → FAILURE.
        # Without fix: copy mutation discarded → Finalize sees refused=[] → SUCCESS.
        # With fix:    _set_output writes updated acc → Finalize sees refused=['pxa'] → FAILURE.
        assert result.status == Status.FAILURE
        assert door_guards_admitted(tree)
        assert node_failed(tree, FinalizeCsFilterNode), (
            "A whole-refused PXA regression must fail FinalizeCsFilterNode."
            " FilterCsPxaDimensionNode must write the updated acc back via"
            " _set_output (#2706)"
        )
        assert _ledger_entries(dl) == []


# ---------------------------------------------------------------------------
# Full tree: add_case_status_tree, at a participant replica
# ---------------------------------------------------------------------------


def _capture_override(tree: py_trees.behaviour.Behaviour):
    """Wrap *tree* with a probe that captures the ledger payload override.

    The override is a within-execution hand-off (FinalizeCsFilterNode writes
    it, GuardedCommit consumes it) and the bridge resets it at the execution
    boundary (#3101, ADR-0087), so it is not readable after
    ``execute_with_setup`` returns.  A SUCCESS probe appended after the tree
    still sees Finalize's write on the accept path.  Returns
    ``(probed_tree, captured)``.
    """
    captured: dict[str, object] = {}

    class _CaptureOverride(py_trees.behaviour.Behaviour):
        def update(self) -> Status:
            captured["override"] = py_trees.blackboard.Blackboard.storage.get(
                "/ledger_payload_object_override"
            )
            return Status.SUCCESS

    probed = py_trees.composites.Sequence(
        name="AddCaseStatusToCaseBTWithProbe",
        memory=False,
        children=[tree, _CaptureOverride(name="CaptureOverride")],
    )
    return probed, captured


class TestAddCaseStatusTreeSenderRule:
    """Only the case's CASE_MANAGER sends ``Add(CaseStatus)``, and only to a
    participant (RSH-04-005): the factory's sender guard refuses anything
    else before a precondition guard runs."""

    @pytest.mark.spec("RSH-04-005")
    @pytest.mark.spec("HP-01-006")
    def test_a_participants_status_is_refused_at_a_replica(
        self, populated_dl, make_payload, status_obj
    ):
        peer = "https://example.org/actors/peer"
        case = cast(VulnerabilityCase, populated_dl.read(CASE_ID))
        seed_case_participant(populated_dl, case, peer)
        populated_dl.save(case)
        activity = add_status_to_case_activity(
            status_obj, target=CASE_ID, actor=peer, to=[ACTOR_ID]
        )

        result, tree = _run_at_replica(populated_dl, make_payload(activity))

        assert result.status == Status.FAILURE
        assert not door_guards_admitted(tree)
        assert STATUS_ID not in _status_ids(populated_dl)
        assert populated_dl.outbox_list() == []

    @pytest.mark.spec("RSH-04-005")
    @pytest.mark.spec("PCR-03-001")
    @pytest.mark.spec("HP-01-006")
    def test_a_replica_with_no_case_manager_refuses_every_sender(
        self, make_payload
    ):
        """With no CASE_MANAGER on its case there is nobody to admit it from,
        so even a stranger's public-awareness status is refused by the sender
        guard, with nothing appended, committed or sent."""
        case = VulnerabilityCase(
            id_=CASE_ID, name="No manager", attributed_to=ACTOR_ID
        )
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
        seed_case_participant(dl, case, ACTOR_ID)
        dl.create(case)
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=CS_pxa.Pxa)
        )
        dl.create(status_obj)
        activity = add_status_to_case_activity(
            status_obj,
            target=CASE_ID,
            actor="https://example.org/actors/stranger",
            to=[ACTOR_ID],
        )

        result, tree = _run_at_replica(dl, make_payload(activity))

        assert result.status == Status.FAILURE
        assert not door_guards_admitted(tree)
        assert STATUS_ID not in _status_ids(dl)
        assert _ledger_entries(dl) == []
        assert dl.outbox_list() == []

    @pytest.mark.spec("RSH-04-005")
    @pytest.mark.spec("HP-01-006")
    def test_a_status_sent_to_the_case_manager_is_refused(self, make_payload):
        """Not even the CASE_MANAGER's own: no sender is entitled at the
        CASE_MANAGER, so nothing is appended or committed."""
        case = VulnerabilityCase(
            id_=CASE_ID, name="At the manager", attributed_to=CASE_MANAGER_ID
        )
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ID)
        seed_case_manager_participant(dl, case, CASE_MANAGER_ID)
        seed_case_participant(dl, case, ACTOR_ID)
        dl.create(case)
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=CS_pxa.Pxa)
        )
        dl.create(status_obj)

        for sender in (ACTOR_ID, CASE_MANAGER_ID):
            activity = add_status_to_case_activity(
                status_obj, target=CASE_ID, actor=sender, to=[CASE_MANAGER_ID]
            )
            result, tree = _run_at_replica(dl, make_payload(activity))

            assert result.status == Status.FAILURE, sender
            assert not door_guards_admitted(tree), sender
            assert STATUS_ID not in _status_ids(dl), sender
            assert _ledger_entries(dl) == [], sender
            assert dl.outbox_list() == [], sender

    @pytest.mark.spec("RSH-04-005")
    @pytest.mark.spec("RSH-03-004")
    def test_the_tree_has_no_effects(self, populated_dl, make_payload):
        """No append, teardown or CSB-18 note: a replica takes the status from
        the ledger fan-out (RSH-08-003) and the CASE_MANAGER declared it, so
        nothing is asked (RSH-03-004)."""
        from vultron.core.behaviors.status.nodes.cs_invariant_diagnostic import (
            PxaEmInvariantDiagnosticNode,
        )

        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        tree = add_case_status_tree(
            sender_rule=_CASE_STATUS_RULE,
            request=make_payload(_from_manager(status_obj)),
        )
        node_types = {type(n) for n in tree.iterate()}
        assert ThreatTerminationBranchNode not in node_types
        assert PxaEmInvariantDiagnosticNode not in node_types


class TestAddCaseStatusTree:
    @pytest.mark.spec("RSH-04-005")
    @pytest.mark.spec("RSH-08-003")
    def test_happy_path_is_admitted_and_writes_nothing(
        self, populated_dl, make_payload, status_obj
    ):
        """Full Sequence at a replica: the CASE_MANAGER's new status passes
        every guard, and the replica appends nothing — it takes the status
        from the ledger fan-out (RSH-08-003, PCR-03-001)."""
        result, tree = _run_at_replica(
            populated_dl, make_payload(_from_manager(status_obj))
        )
        assert result.status == Status.SUCCESS
        assert door_guards_admitted(tree)
        assert STATUS_ID not in _status_ids(populated_dl)
        assert _ledger_entries(populated_dl) == []

    def test_idempotent_duplicate_fails_with_sentinel(
        self, populated_dl, make_payload, case, status_obj
    ):
        """Duplicate status → BT FAILURE with CASE_STATUS_ALREADY_PRESENT."""
        # Pre-load the status onto the case (use wire types for DL save)
        stored = cast(VulnerabilityCase, populated_dl.read(CASE_ID))
        stored.case_statuses.append(status_obj.id_)
        populated_dl.save(stored)

        result, tree = _run_at_replica(
            populated_dl, make_payload(_from_manager(status_obj))
        )
        assert result.status == Status.FAILURE
        assert door_guards_admitted(tree)
        assert BTBridge.get_failure_reason(tree) == CASE_STATUS_ALREADY_PRESENT

    @pytest.mark.spec("RSH-05-017")
    @pytest.mark.spec("RSH-05-023")
    def test_status_moving_em_alone_is_refused(self, make_payload):
        """A status whose only change is EM → refused in full; not appended.

        EM is derived from the embargo register and no status moves it
        (RSH-05-023): the asserted EM is refused and the case's carried
        forward, which leaves nothing new, so the tree FAILS (RSH-05-005).
        """
        case = as_VulnerabilityCase(
            id_=CASE_ID, name="EM Guard", attributed_to=CASE_MANAGER_ID
        )
        initial = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em=EmDimension(state=EM.NONE),
        )
        case.case_statuses.append(initial)  # type: ignore[arg-type]
        dl = _replica_store(case)

        bad_status = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em=EmDimension(state=EM.ACTIVE)
        )
        dl.create(bad_status)

        result, tree = _run_at_replica(
            dl, make_payload(_from_manager(bad_status, target=case))
        )
        assert result.status == Status.FAILURE
        assert door_guards_admitted(tree)
        assert node_failed(tree, FinalizeCsFilterNode)

        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert STATUS_ID not in status_ids
        assert updated_case.em_state == EM.NONE

    @pytest.mark.spec("CSB-17-012")
    def test_px_ephemeral_a_event_rejected_no_ledger_write(self, make_payload):
        """Full tree rejects A-event from pX state; no ledger write (CSB-17-012, ISSUE-2524).

        When the current PXA state is pXa (exploit public, public unaware),
        the CheckCsEphemeralStateNode guard must return FAILURE for any asserted
        CaseStatus that does not advance P.  The full tree must return FAILURE
        and no CaseStatus entry should be appended to the case.
        """
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Ephemeral pX Guard",
            attributed_to=CASE_MANAGER_ID,
        )
        # Auto-seeded baseline is pxa; advance to pXa (X exploit published,
        # P still false — the ephemeral state that requires P next).
        case.append_case_status(pxa=CS_pxa.pXa)
        dl = _replica_store(case)

        # Asserted status fires A-event only (pXa → pXA); P is NOT advanced.
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            pxa=PxaDimension(state=CS_pxa.pXA),
        )
        dl.create(asserted)

        result, tree = _run_at_replica(
            dl, make_payload(_from_manager(asserted))
        )
        assert result.status == Status.FAILURE
        assert door_guards_admitted(tree)
        assert node_failed(tree, CheckCsEphemeralStateNode)
        assert STATUS_ID not in _status_ids(dl)

    @pytest.mark.spec("RSH-05-015")
    @pytest.mark.spec("RSH-05-016")
    @pytest.mark.spec("RSH-05-023")
    @pytest.mark.spec("RSH-05-019")
    def test_em_move_with_pxa_advance_refuses_em_and_accepts_pxa(
        self, make_payload
    ):
        """EM move (NONE→PROPOSED) with a PXA advance → BT SUCCEEDS.

        Bug #2256: all-or-nothing CS validation discarded a valid dimension
        when another was refused.  Per-dimension adjudication refuses the
        asserted EM — a status never moves EM (RSH-05-023) — carries the
        case's EM forward, and still accepts the PXA advance: the filtered
        status the guards publish holds EM NONE and PXA Pxa.  The CASE_MANAGER
        side of the same split, on an adopted participant report, is
        ``test_an_adopted_report_never_moves_em``.
        """
        case = VulnerabilityCase(
            id_=CASE_ID, name="EM PXA Split", attributed_to=CASE_MANAGER_ID
        )
        # Auto-seeded CaseStatus has pxa=pxa and EM NONE.
        dl = _replica_store(case)

        # Sender asserts EM NONE→PROPOSED (refused) + PXA pxa→Pxa (valid)
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em=EmDimension(state=EM.PROPOSED),
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(asserted)
        event = make_payload(_from_manager(asserted))
        probed, captured = _capture_override(
            add_case_status_tree(sender_rule=_CASE_STATUS_RULE, request=event)
        )

        result, _ = _run_at_replica(dl, event, tree=probed)

        assert result.status == Status.SUCCESS
        fields = cast(dict, captured["override"])["fields"]
        assert fields == {"emState": EM.NONE.name, "pxaState": "Pxa"}
        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        assert updated_case.em_state == EM.NONE

    @pytest.mark.spec("RSH-05-023")
    def test_status_carrying_the_cases_em_passes_it(
        self, make_payload, caplog
    ):
        """An asserted EM identical to the case's is not refused (RSH-05-023)."""
        import logging

        case = VulnerabilityCase(
            id_=CASE_ID, name="EM Carried", attributed_to=CASE_MANAGER_ID
        )
        propose(case, f"{CASE_ID}/embargo_events/carried")
        dl = _replica_store(case)

        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em=EmDimension(state=EM.PROPOSED),
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(asserted)
        event = make_payload(_from_manager(asserted))
        probed, captured = _capture_override(
            add_case_status_tree(sender_rule=_CASE_STATUS_RULE, request=event)
        )

        with caplog.at_level(logging.WARNING):
            result, _ = _run_at_replica(dl, event, tree=probed)

        assert result.status == Status.SUCCESS
        assert not [
            r for r in caplog.records if "refused EM" in r.getMessage()
        ]
        # Nothing refused, so the guards publish no override: the status is
        # taken as asserted.
        assert captured["override"] is None
        updated_case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
        assert updated_case.em_state == EM.PROPOSED

    @pytest.mark.spec("RSH-05-019")
    @pytest.mark.spec("SL-03-001")
    def test_pxa_refusal_warning_names_case_id_not_status_id(
        self, make_payload, caplog
    ):
        """The PXA refusal WARNING reports the case ID, with the status ID labelled.

        Bug #3039: FilterCsPxaDimensionNode filled the ``for case '%s'``
        placeholder with the *status* ID, so an operator correlating the
        warning against case IDs saw a URI that matched no case.  The sibling
        EM refusal warning already reports ``case_id``; the two must agree.
        """
        import logging

        case = VulnerabilityCase(
            id_=CASE_ID, name="PXA Refusal Log", attributed_to=CASE_MANAGER_ID
        )
        case.append_case_status(pxa=CS_pxa.Pxa)
        dl = _replica_store(case)

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

        with caplog.at_level(logging.WARNING):
            result, tree = _run_at_replica(
                dl, make_payload(_from_manager(asserted))
            )
        assert result.status == Status.FAILURE
        assert door_guards_admitted(tree)

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
        self, make_payload, caplog
    ):
        """The EM refusal WARNING has the same shape as the PXA one (#3039).

        Case in the ``for case '%s'`` slot, status in its own labelled
        ``(status '%s')`` slot, so an operator can correlate either refusal
        the same way.
        """
        import logging

        case = VulnerabilityCase(
            id_=CASE_ID, name="EM Refusal Log", attributed_to=CASE_MANAGER_ID
        )
        case.append_case_status(pxa=CS_pxa.pxa)
        dl = _replica_store(case)

        # EM other than the case's (NONE → ACTIVE) + valid PXA advance → EM
        # refused, tree still SUCCEEDS (partial accept), refusal is logged.
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em=EmDimension(state=EM.ACTIVE),
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(asserted)

        with caplog.at_level(logging.WARNING):
            result, _ = _run_at_replica(
                dl, make_payload(_from_manager(asserted))
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
        self, make_payload
    ):
        """emState in BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE equals EM member .name.

        Regression guard for the FinalizeCsFilterNode serialization invariant:
        ``emState`` must equal ``filtered.em.state.name`` so that
        ``_coerce_em(emState)`` via ``EM[v]`` (name-based lookup) round-trips
        correctly.  Using ``str()`` is fragile because it returns .value, which
        equals .name only while no EM member has value ≠ name (RSH-05-012).
        """
        case = VulnerabilityCase(
            id_=CASE_ID, name="EM PXA Split", attributed_to=CASE_MANAGER_ID
        )
        propose(case, f"{CASE_ID}/embargo_events/serialized")
        dl = _replica_store(case)

        # EM PROPOSED→ACTIVE refused (carried forward as PROPOSED) + PXA
        # pxa→Pxa accepted: a partial accept, so Finalize writes the override.
        asserted = as_CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            em=EmDimension(state=EM.ACTIVE),
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(asserted)
        event = make_payload(_from_manager(asserted))
        probed, captured = _capture_override(
            add_case_status_tree(sender_rule=_CASE_STATUS_RULE, request=event)
        )

        result, _ = _run_at_replica(dl, event, tree=probed)
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
# Use-case level (integration with BT), at a participant replica
# ---------------------------------------------------------------------------


def _replica_with_status(
    status_obj: as_CaseStatus,
    *,
    preload: bool = False,
    initial: as_CaseStatus | None = None,
) -> SqliteDataLayer:
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="UC Case", attributed_to=CASE_MANAGER_ID
    )
    if initial is not None:
        case.case_statuses.append(initial)  # type: ignore[arg-type]
    if preload:
        case.case_statuses.append(status_obj)  # type: ignore[arg-type]
    dl = _replica_store(case)
    dl.create(status_obj)
    return dl


class TestAddCaseStatusToCaseReceivedUseCase:
    @pytest.mark.spec("RSH-04-005")
    @pytest.mark.spec("RSH-08-003")
    def test_use_case_admits_the_managers_status_and_writes_nothing(
        self, make_payload
    ):
        """The CASE_MANAGER's status is admitted at a replica, which appends
        nothing: it takes the status from the ledger fan-out."""
        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        dl = _replica_with_status(status_obj)

        result = AddCaseStatusToCaseReceivedUseCase(
            dl,
            make_payload(_from_manager(status_obj)),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED, result
        assert STATUS_ID not in _status_ids(dl)
        assert dl.outbox_list() == []

    def test_use_case_idempotent_logs_info(self, make_payload, caplog):
        """Duplicate status → SKIPPED; use case logs at INFO not WARNING."""
        import logging

        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        dl = _replica_with_status(status_obj, preload=True)

        with caplog.at_level(logging.DEBUG):
            result = AddCaseStatusToCaseReceivedUseCase(
                dl,
                make_payload(_from_manager(status_obj)),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert result.disposition is HandlerDisposition.SKIPPED, result
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
        """A status moving EM alone → REFUSED by the guards; WARNING logged."""
        import logging

        initial = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em=EmDimension(state=EM.NONE),
        )
        bad_status = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em=EmDimension(state=EM.ACTIVE)
        )
        dl = _replica_with_status(bad_status, initial=initial)

        with caplog.at_level(logging.DEBUG):
            result = AddCaseStatusToCaseReceivedUseCase(
                dl,
                make_payload(_from_manager(bad_status)),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        # The guards refused the content, not the sender (HP-01-006).
        assert "refused in full" in (result.reason or ""), result.reason
        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("AddCaseStatusToCaseBT" in m for m in warn_msgs), (
            "Expected WARNING for the refused status"
        )
        assert STATUS_ID not in _status_ids(dl)

    def test_use_case_missing_status_id_logs_warning(
        self, make_payload, caplog
    ):
        """Missing status_id in event → WARNING; no BT executed."""
        import logging
        from unittest.mock import PropertyMock, patch

        status_obj = as_CaseStatus(id_=STATUS_ID, context=CASE_ID)
        dl = _replica_with_status(status_obj)
        event = make_payload(_from_manager(status_obj))

        # Patch status_id to None to simulate the missing-ID edge case
        with patch.object(
            type(event),
            "status_id",
            new_callable=PropertyMock,
            return_value=None,
        ):
            with caplog.at_level(logging.DEBUG):
                result = AddCaseStatusToCaseReceivedUseCase(
                    dl, event, wire_render_port=As2WireRenderAdapter()
                ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        warn_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("missing" in m.lower() for m in warn_msgs)


# ---------------------------------------------------------------------------
# ThreatTerminationBranchNode (EmbargoTeardownAuthorizationGate, RSH-03-001 to RSH-03-003)
# ---------------------------------------------------------------------------


class TestThreatTerminationBranchNode:
    """RSH-03-001: fires teardown on P/X/A; RSH-03-002: no sender-role gate."""

    def _make_status_with_pxa(self, pxa_state: CS_pxa) -> as_CaseStatus:
        return as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=pxa_state)
        )

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
    @pytest.mark.spec("EMB-03-003")
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
        """All CS_pxa states except pxa trigger embargo teardown.

        The public, exploit or attack fact is what ends the embargo, whenever
        it becomes known, never a revision proposal (EMB-03-003).  The
        ``Remove`` is committed before the termination is applied
        (ADR-0124), so EM reaches EXITED with its entry recorded.
        """
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM

        status_obj = self._setup_dl_with_embargo(dl, pxa_state)
        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.EXITED
        assert updated.active_embargo is None

    @pytest.mark.spec("CLP-07-013")
    def test_a_teardown_that_cannot_be_committed_writes_nothing(self, dl):
        """No broadcast factory: the ``Remove`` cannot be built, so it is
        never committed and the embargo stays in force (#4653, #4714)."""
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM

        status_obj = self._setup_dl_with_embargo(dl, CS_pxa.Pxa)
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
        )
        # No trigger_activity in bridge → no Remove → FAILURE (BT-14-001)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.ACTIVE
        assert updated.active_embargo is not None

    @pytest.mark.spec("RSH-03-002")
    def test_no_sender_role_gate(self, dl):
        """RSH-03-002: a sender holding no role still triggers the teardown.

        Sender authorization was handled at StatusAdoptionGate, and the node
        takes no sender at all.
        """
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )

        status_obj = self._setup_dl_with_embargo(dl, CS_pxa.Pxa)
        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=status_obj,
            case_id=CASE_ID,
        )
        bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.EXITED

    def _run_replica(self, dl, status_obj) -> py_trees.common.Status:
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
            status_obj=status_obj, case_id=CASE_ID
        )
        return bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID).status

    @pytest.mark.spec("EP-09-008")
    def test_a_non_manager_running_the_branch_asks_the_manager(self, dl):
        """Run off the CASE_MANAGER, the branch asks rather than tears down.

        No received tree runs it there (RSH-03-004); this pins the node's
        own behaviour should one ever do so.
        """
        status_obj = self._setup_dl_with_embargo(
            dl, CS_pxa.Pxa, manager_id=CASE_MANAGER_ID
        )

        status = self._run_replica(dl, status_obj)

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
            EMBARGO_TEARDOWN_SEMANTIC_TYPE,
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
            semantic_type=EMBARGO_TEARDOWN_SEMANTIC_TYPE,
            payload_snapshot={"id": ask_id},
            prev_log_hash="0" * 64,
        )
        entry = record.to_ledger_entry()
        activity = announce_log_entry_activity(
            WireCaseLedgerEntry.model_validate(entry.model_dump(mode="json")),
            actor=CASE_MANAGER_ID,
            to=[ACTOR_ID],
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

        self._run_replica(dl, status_obj)

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
        self._run_replica(dl, status_obj)

        status = self._run_replica(dl, status_obj)

        assert status == Status.SUCCESS
        assert len(dl.outbox_list()) == 1

    @pytest.mark.spec("SYNC-11-003")
    def test_the_managers_committed_entry_clears_the_ask(self, dl):
        """AC-3: once the manager's entry arrives, a later signal asks anew."""
        status_obj = self._setup_dl_with_embargo(
            dl, CS_pxa.Pxa, manager_id=CASE_MANAGER_ID
        )
        self._run_replica(dl, status_obj)
        [first_ask_id] = dl.outbox_list()

        self._announce_managers_teardown_entry(dl, first_ask_id)

        assert self._ask_pending() is None
        self._run_replica(dl, status_obj)
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
        self, store_actor: str
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
        status_obj = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa=PxaDimension(state=CS_pxa.Pxa)
        )
        for obj in (embargo, invite, cm_participant, case, status_obj):
            dl.create(obj)

        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=status_obj, case_id=CASE_ID
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
    def test_a_non_manager_writes_and_sends_nothing(self):
        """A non-manager neither abandons the open proposal nor asks."""
        dl, bridge, node = self._setup(ACTOR_ID)

        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.PROPOSED
        assert updated.proposed_embargo_ids == [PROPOSED_EMBARGO_ID]
        assert dl.outbox_list() == []


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

        The node delegates to terminate_embargo_bt, which commits the
        ``Remove`` before it applies the termination (ADR-0124).
        """
        from typing import cast as c

        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
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
            trigger_activity=TriggerActivityAdapter(dl_new),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl_new),
        )
        # Runs as the case manager: the seeded case names CASE_MANAGER_ID as
        # its only participant, and teardown authority is the manager's.
        new_result = new_bridge.execute_with_setup(
            tree=new_node, actor_id=CASE_MANAGER_ID
        )
        assert new_result.status == Status.SUCCESS

        new_case = c(VulnerabilityCase, dl_new.read(CASE_ID))
        new_em_state = new_case.current_status.em.state
        new_embargo = new_case.active_embargo

        assert new_em_state == EM.EXITED, (
            f"EM={new_em_state}; CS.P teardown must reach EXITED"
            " (AC #8, issue #1844)"
        )
        assert new_embargo is None, "CS.P teardown must clear active_embargo"


# ---------------------------------------------------------------------------
# Regression: CLP-10-009 — validators in preconditions, before the commit
# ---------------------------------------------------------------------------


class TestCaseLedgerEntryCreation:
    """CLP-10-009 / ISSUE-2254 regression: add_case_status_tree runs its
    validators as precondition guards, before GuardedCommit.

    The commit itself is declined at a replica, the only receiver of
    ``Add(CaseStatus)`` (RSH-04-005, RSH-08-003); the CASE_MANAGER's own
    ``add_case_status_to_case`` entry for an adopted report is asserted in
    ``test_add_participant_status_bt.py``
    (``test_an_owners_public_awareness_is_adopted``).
    """

    @pytest.mark.spec("CLP-10-009")
    def test_invalid_em_transition_produces_no_ledger_entry(
        self, make_payload
    ):
        """An invalid EM transition is rejected in precondition_guards → zero
        CaseLedgerEntries (CLP-10-009: validators run before GuardedCommit).
        """
        case = VulnerabilityCase(
            id_=CASE_ID, name="Ledger Test Case", attributed_to=CASE_MANAGER_ID
        )
        initial = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/init",
            context=CASE_ID,
            em=EmDimension(state=EM.NONE),
        )
        case.case_statuses.append(str(initial.id_))
        dl = _replica_store(case)
        dl.create(initial)

        bad_status = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, em=EmDimension(state=EM.ACTIVE)
        )
        dl.create(bad_status)

        result, tree = _run_at_replica(
            dl, make_payload(_from_manager(bad_status))
        )
        assert result.status == Status.FAILURE
        assert door_guards_admitted(tree)
        assert node_failed(tree, FinalizeCsFilterNode)
        assert _ledger_entries(dl) == [], (
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
            trigger_activity=TriggerActivityAdapter(dl),
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


DIAG_CASE_ID = "https://example.org/cases/diag-3008"
DIAG_STATUS_ID = f"{DIAG_CASE_ID}/statuses/s1"
DIAG_CM_ID = "https://example.org/actors/diag-cm"


# ---------------------------------------------------------------------------
# RSH-03-004: the whole tree, at a replica, on the manager's declaration
# ---------------------------------------------------------------------------

REPLICA_ID = "https://example.org/actors/rsh-03-004-replica"
PEER_ID = "https://example.org/actors/rsh-03-004-peer"


class TestReplicaLeavesManagerDeclaredTeardownToItsEntry:
    """At a replica under an active embargo, the CASE_MANAGER's P/X/A status
    tears nothing down and asks for nothing: the tree has no teardown, and
    the manager's committed entry carries it (RSH-03-004, #4149).  A peer's
    status never reaches the guards at a replica: only the CASE_MANAGER
    emits ``Add(CaseStatus)``, so the sender guard refuses it (RSH-04-005,
    PCR-03-001, HP-01-006).
    """

    def _run(
        self, sender: str, expected: Status = Status.SUCCESS
    ) -> SqliteDataLayer:
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=REPLICA_ID)
        cm_participant = CaseParticipant(
            id_=f"{DIAG_CASE_ID}/participants/cm",
            context=DIAG_CASE_ID,
            attributed_to=DIAG_CM_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        embargo = as_EmbargoEvent(
            id_=f"{DIAG_CASE_ID}/embargo_events/e1",
            context=DIAG_CASE_ID,
            end_time=days_from_now_utc(45),
        )
        case = VulnerabilityCase(
            id_=DIAG_CASE_ID, name="Replica Case", attributed_to=DIAG_CM_ID
        )
        case.add_participant(cm_participant)
        activate(case, embargo.id_)
        for actor in (REPLICA_ID, PEER_ID):
            seed_case_participant(dl, case, actor)
        status_obj = as_CaseStatus(
            id_=DIAG_STATUS_ID,
            context=DIAG_CASE_ID,
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        dl.create(case)
        dl.create(cm_participant)
        dl.create(embargo)
        dl.create(status_obj)

        event = cast(
            AddCaseStatusToCaseReceivedEvent,
            extract_event(
                add_status_to_case_activity(
                    status_obj,
                    target=as_VulnerabilityCase(id_=DIAG_CASE_ID),
                    actor=sender,
                    to=[REPLICA_ID],
                )
            ),
        )
        tree = add_case_status_tree(
            sender_rule=_CASE_STATUS_RULE, request=event
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
        assert result.status == expected, result.feedback_message
        return dl

    @pytest.mark.spec("RSH-03-004")
    def test_the_managers_declaration_asks_nothing_at_a_replica(self):
        dl = self._run(sender=DIAG_CM_ID)

        updated = cast(VulnerabilityCase, dl.read(DIAG_CASE_ID))
        assert updated.current_status.em.state == EM.ACTIVE
        queued = [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]
        assert [a.type_ for a in queued] == [], [a.type_ for a in queued]

    @pytest.mark.spec("PCR-03-001")
    @pytest.mark.spec("HP-01-006")
    @pytest.mark.spec("RSH-04-005")
    def test_a_peers_declaration_is_refused_at_a_replica(self):
        """Even from a participant: only the CASE_MANAGER emits it."""
        dl = self._run(sender=PEER_ID, expected=Status.FAILURE)

        updated = cast(VulnerabilityCase, dl.read(DIAG_CASE_ID))
        assert updated.current_status.em.state == EM.ACTIVE
        assert dl.outbox_list() == []
