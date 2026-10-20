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

"""Whole accept or reject of a received ParticipantStatus (RSH-09, ADR-0107).

An inbound ``Add(ParticipantStatus, CaseParticipant)`` states the sender's whole
status.  The CASE_MANAGER records it exactly as received, or refuses all of it
and tells the sender every reason; it never records a status nobody sent.  This
replaced the per-dimension partial accept of RSH-05 (#3741).

Per specs/received-status-handling.yaml RSH-09.
"""

import dataclasses
import logging
from typing import Any, cast

import pytest
from py_trees.common import Status

from test.support.rm_declaration import (
    ACTOR_ID,
    CASE_ID,
    CASE_MANAGER_ID,
    PARTICIPANT_ID,
    STRANGER_ID,
    RMAnomalyProbe,
    RMDeclarationCase,
    assert_anomaly_flagged_and_noted,
    current_status as _current_status,
    received_cases,
    recorded_rm,
    seed_case as _seed_case,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.behaviors.status.nodes.participant_status_acceptance import (
    CheckParticipantStatusAcceptableNode,
    participant_status_refusals,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.behaviors.sync.nodes.participant_status_effect import (
    ApplyParticipantStatusFromLedgerNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    DDimension,
    EmDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    add_status_to_participant_activity,
    announce_log_entry_activity,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# The case, its participants and ``store_for`` are shared with the
# activity-typed RM handler tests, so both paths run against one table of
# cases (RSH-06-006) — see ``test/support/rm_declaration.py``.
ASSERTED_STATUS_ID = f"{PARTICIPANT_ID}/statuses/asserted"

_ZERO_HASH = "0" * 64

_VENDOR = [CVDRole.VENDOR]
_VENDOR_DEPLOYER = [CVDRole.VENDOR, CVDRole.DEPLOYER]


# ---------------------------------------------------------------------------
# Shape-agnostic accessors
#
# ``SqliteDataLayer.read`` returns core models while wire-shaped ledger
# snapshots use the flat ``rmState``/``vfState`` form.  These readers accept
# either and normalize to the enum member name, which both serializations
# carry, so the assertions describe protocol state, not serialization shape.
# ---------------------------------------------------------------------------


def _state_name(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "name", None) or str(value)


def _dim_state(obj: Any, core_field: str, wire_field: str) -> str | None:
    if isinstance(obj, dict):
        nested = obj.get(core_field)
        if isinstance(nested, dict):
            return _state_name(nested.get("state"))
        return _state_name(nested or obj.get(wire_field))
    nested = getattr(obj, core_field, None)
    if nested is not None and hasattr(nested, "state"):
        return _state_name(nested.state)
    return None


def _rm_of(obj: Any) -> str | None:
    return _dim_state(obj, "rm", "rmState")


def _vf_of(obj: Any) -> str | None:
    return _dim_state(obj, "vf", "vfState")


def _case_status_of(obj: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get("case_status") or obj.get("caseStatus")
    return getattr(obj, "case_status", None)


def _pxa_of(obj: Any) -> str | None:
    cs = _case_status_of(obj)
    return None if cs is None else _dim_state(cs, "pxa", "pxaState")


def _latest_status(dl: SqliteDataLayer, participant_id: str) -> Any:
    participant = cast(CaseParticipant, dl.read(participant_id))
    assert participant is not None
    assert participant.participant_statuses
    return participant.participant_statuses[-1]


def _status_ids(dl: SqliteDataLayer, participant_id: str) -> list[str]:
    participant = cast(CaseParticipant, dl.read(participant_id))
    assert participant is not None
    return [
        str(getattr(s, "id_", s)) for s in participant.participant_statuses
    ]


def _ledger_entries(dl: SqliteDataLayer) -> list[CaseLedgerEntry]:
    entries = [
        cast(CaseLedgerEntry, obj)
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
        and cast(CaseLedgerEntry, obj).case_id == CASE_ID
    ]
    return sorted(entries, key=lambda e: e.log_index)


def _receipt_entries(dl: SqliteDataLayer) -> list[CaseLedgerEntry]:
    """Return only the participant-status receipt entries, sorted."""
    return [
        e
        for e in _ledger_entries(dl)
        if e.semantic_type == "add_participant_status_to_participant"
    ]


def _case_status_count(dl: SqliteDataLayer) -> int:
    case = dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return len(case.case_statuses)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _asserted_status(
    rm_state: RM,
    vf_state: CS_vf | None,
    pxa_state: CS_pxa | None,
    status_id: str = ASSERTED_STATUS_ID,
    d_state: CS_d | None = None,
) -> as_ParticipantStatus:
    """The inbound status from the sender.

    ``pxa_state=None`` builds a status with **no** ``case_status`` at all — the
    normal shape when the sender has nothing to say about the case.
    """
    case_status = (
        None
        if pxa_state is None
        else as_CaseStatus(
            id_=f"{status_id}/cs",
            context=CASE_ID,
            em=EmDimension(state=EM.NONE),
            pxa=PxaDimension(state=pxa_state),
        )
    )
    return as_ParticipantStatus(
        id_=status_id,
        context=CASE_ID,
        rm=RmDimension(state=rm_state),
        vf=(VfDimension(state=vf_state) if vf_state is not None else None),
        d=(DDimension(state=d_state) if d_state is not None else None),
        case_status=case_status,
    )


def _with_d(status: as_ParticipantStatus, d_state: CS_d | None) -> Any:
    return status.model_copy(
        update={"d": None if d_state is None else DDimension(state=d_state)}
    )


def _run_tree(
    dl: SqliteDataLayer,
    asserted: as_ParticipantStatus,
    executing_actor_id: str,
    make_payload: Any,
    anomaly: dict | None = None,
) -> Any:
    """Run the full ``add_participant_status_tree`` for *asserted*.

    When *anomaly* is provided, the tree is wrapped in an
    :class:`RMAnomalyProbe` that records the ``BB_RM_ANOMALY`` the run
    published under ``anomaly["anomaly"]``.
    """
    activity = add_status_to_participant_activity(
        status=asserted,
        target=as_CaseParticipant(
            id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
        ),
        actor=ACTOR_ID,
        to=[executing_actor_id],
        context=as_VulnerabilityCase(id_=CASE_ID, name="Issue 2235 Case"),
    )
    event = make_payload(activity)
    bridge = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )
    tree: Any = add_participant_status_tree(
        request=event,
        case_id=CASE_ID,
        sender_rule=AddParticipantStatusToParticipantReceivedUseCase.sender_entitlement,
    )
    if anomaly is not None:
        tree = RMAnomalyProbe(tree, anomaly)
    result = bridge.execute_with_setup(
        tree=tree, actor_id=executing_actor_id, activity=event
    )
    # The bridge reports no reason of its own; the refusal reason is the one
    # the failing guard left, which the refusal notice carries (CLP-05-001).
    if result.status == Status.FAILURE and not result.feedback_message:
        result = dataclasses.replace(
            result, feedback_message=BTBridge.get_failure_reason(tree)
        )
    return result


def _refused(
    current: Any, asserted: Any, roles: Any = (), *, history: Any = ()
) -> list[str]:
    """Return the refused dimension names, in report order.

    *history* is any earlier recorded statuses, oldest first; *current* is
    the latest.
    """
    return [
        r.dimension
        for r in participant_status_refusals(
            [*history, current], asserted, roles=list(roles)
        )
    ]


# ---------------------------------------------------------------------------
# RSH-09-001: an accepted status is recorded exactly as received
# ---------------------------------------------------------------------------


class TestAcceptedStatusIsRecordedAsSent:
    """An accepted status reaches the participant and the ledger unchanged."""

    @pytest.mark.spec("RSH-09-001")
    def test_the_participant_and_the_ledger_hold_the_received_status(
        self, store_for, make_payload
    ):
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa)
        asserted = _asserted_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)
        assert result.status == Status.SUCCESS, result.feedback_message

        latest = _latest_status(dl, PARTICIPANT_ID)
        assert latest.id_ == ASSERTED_STATUS_ID
        assert (_rm_of(latest), _vf_of(latest), _pxa_of(latest)) == (
            RM.ACCEPTED.name,
            CS_vf.VF.name,
            CS_pxa.Pxa.name,
        )

        (entry,) = _receipt_entries(dl)
        snap = entry.payload_snapshot["object"]
        assert isinstance(snap, dict)
        assert snap["rmState"] == RM.ACCEPTED.name
        assert snap["vfState"] == CS_vf.VF.name
        assert snap["caseStatus"]["pxaState"] == CS_pxa.Pxa.name
        assert snap["caseStatus"].get("id") == f"{ASSERTED_STATUS_ID}/cs"
        assert snap.get("type") == "ParticipantStatus"
        # Nothing in the recorded object differs from the status as sent.
        assert snap == As2WireRenderAdapter().render(asserted)

    @pytest.mark.spec("RSH-09-001")
    def test_an_omitted_dimension_is_recorded_as_omitted(
        self, store_for, make_payload
    ):
        """The receiver's own values are not filled into what the sender left
        out: the recorded status is the one sent (ADR-0075, CLP-07-013)."""
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pXa)
        asserted = _asserted_status(RM.DEFERRED, None, None)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)
        assert result.status == Status.SUCCESS, result.feedback_message

        latest = _latest_status(dl, PARTICIPANT_ID)
        assert latest.id_ == ASSERTED_STATUS_ID
        assert latest.vf is None, "no vf was sent, so none is recorded"
        assert latest.case_status is None, (
            "no case status was sent, so none is recorded"
        )
        (entry,) = _receipt_entries(dl)
        snap = entry.payload_snapshot["object"]
        assert "vfState" not in snap
        assert "caseStatus" not in snap

    @pytest.mark.spec("RSH-09-001")
    def test_a_status_reaching_closed_records_its_vf_advance(
        self, store_for, make_payload
    ):
        """A vendor whose fix is ready as it closes has both recorded."""
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa)
        asserted = _asserted_status(RM.CLOSED, CS_vf.VF, CS_pxa.pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)
        assert result.status == Status.SUCCESS, result.feedback_message

        latest = _latest_status(dl, PARTICIPANT_ID)
        assert (_rm_of(latest), _vf_of(latest)) == (
            RM.CLOSED.name,
            CS_vf.VF.name,
        )


# ---------------------------------------------------------------------------
# RSH-09-002: a refused status is refused whole
# ---------------------------------------------------------------------------


class TestRefusedStatusIsRefusedWhole:
    """One refused dimension refuses the update; nothing of it is kept."""

    @pytest.mark.spec("RSH-09-002")
    def test_a_regressive_rm_refuses_the_forward_vf_and_pxa_with_it(
        self, store_for, make_payload
    ):
        """No part of the update is appended, committed or adopted.  The one
        entry is the CASE_MANAGER's own RSH-06-004 note on the regression
        (CLP-10-022)."""
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa)
        asserted = _asserted_status(RM.VALID, CS_vf.VF, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)
        statuses_before = _case_status_count(dl)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)

        assert result.status == Status.FAILURE
        assert ASSERTED_STATUS_ID not in _status_ids(dl, PARTICIPANT_ID)
        latest = _latest_status(dl, PARTICIPANT_ID)
        assert (_rm_of(latest), _vf_of(latest), _pxa_of(latest)) == (
            RM.ACCEPTED.name,
            CS_vf.Vf.name,
            CS_pxa.pxa.name,
        )
        assert _receipt_entries(dl) == []
        assert [e.semantic_type for e in _ledger_entries(dl)] == [
            "add_note_to_case"
        ]
        assert _case_status_count(dl) == statuses_before, (
            "a refused status adopts nothing into the case"
        )

    @pytest.mark.spec("RSH-09-002")
    def test_the_refusal_names_every_refused_dimension_and_why(
        self, store_for, make_payload
    ):
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.Pxa)
        asserted = _asserted_status(RM.VALID, CS_vf.Vf, CS_pxa.pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)

        assert result.status == Status.FAILURE
        reason = result.feedback_message
        for fragment in (
            "rm: ACCEPTED → VALID moves RM backwards",
            "vf: VF → Vf is not a forward move",
            "pxa: Pxa → pxa is not a forward move",
        ):
            assert fragment in reason, reason

    @pytest.mark.spec("RSH-09-002", "CM-23-018")
    def test_a_closed_participants_later_update_is_refused(
        self, store_for, make_payload
    ):
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.CLOSED, CS_vf.Vf, CS_pxa.pxa)
        asserted = _asserted_status(RM.CLOSED, CS_vf.VF, CS_pxa.pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)

        assert result.status == Status.FAILURE
        assert ASSERTED_STATUS_ID not in _status_ids(dl, PARTICIPANT_ID)
        assert _vf_of(_latest_status(dl, PARTICIPANT_ID)) == CS_vf.Vf.name
        assert _ledger_entries(dl) == []

    @pytest.mark.spec("RSH-09-004", "CSB-18-001")
    def test_an_impossible_status_is_never_committed(
        self, store_for, make_payload
    ):
        """#2906 end-to-end: a ready fix before the report is accepted never
        reaches the hash-chained ledger, so no replica is asked to apply a
        state it would refuse (RSH-09-006)."""
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.VALID, CS_vf.Vf, CS_pxa.pxa)
        asserted = _asserted_status(RM.VALID, CS_vf.VF, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)

        assert result.status == Status.FAILURE
        assert "vf:" in result.feedback_message
        assert _receipt_entries(dl) == []
        assert ASSERTED_STATUS_ID not in _status_ids(dl, PARTICIPANT_ID)


# ---------------------------------------------------------------------------
# CheckParticipantStatusAcceptableNode: when there is nothing to judge
# ---------------------------------------------------------------------------


class TestNothingToJudge:
    """The guard passes when it has nothing to judge the status against;
    the append subtree reports a missing participant or status itself."""

    @staticmethod
    def _node(fallback: Any = None) -> CheckParticipantStatusAcceptableNode:
        return CheckParticipantStatusAcceptableNode(
            participant_id=PARTICIPANT_ID,
            status_id=ASSERTED_STATUS_ID,
            status_obj_fallback=fallback,
        )

    @staticmethod
    def _tick(dl: SqliteDataLayer, node: Any) -> Status:
        bridge = BTBridge(datalayer=dl)
        return bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        ).status

    @pytest.mark.spec("RSH-09-001")
    def test_an_unknown_participant_passes(self, store_for):
        dl = store_for(CASE_MANAGER_ID)
        assert self._tick(dl, self._node()) == Status.SUCCESS

    @pytest.mark.spec("RSH-09-001")
    def test_a_redelivered_status_passes(self, store_for):
        """Idempotent re-delivery: the status is already on the participant."""
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.ACCEPTED, None, CS_pxa.pxa)
        _seed_case(dl, current, None)
        node = CheckParticipantStatusAcceptableNode(
            participant_id=PARTICIPANT_ID, status_id=current.id_
        )
        assert self._tick(dl, node) == Status.SUCCESS

    @pytest.mark.spec("RSH-09-001")
    def test_an_unresolvable_assertion_passes(self, store_for):
        dl = store_for(CASE_MANAGER_ID)
        _seed_case(dl, _current_status(RM.ACCEPTED, None, CS_pxa.pxa), None)
        assert self._tick(dl, self._node()) == Status.SUCCESS

    @pytest.mark.spec("RSH-09-003")
    def test_the_inline_status_is_judged_when_not_stored(self, store_for):
        """The fallback object is what the activity carried inline."""
        dl = store_for(CASE_MANAGER_ID)
        _seed_case(dl, _current_status(RM.ACCEPTED, None, CS_pxa.pxa), None)
        regressing = _asserted_status(RM.VALID, None, None)
        node = self._node(fallback=regressing)
        assert self._tick(dl, node) == Status.FAILURE
        assert "rm: ACCEPTED → VALID" in node.feedback_message


# ---------------------------------------------------------------------------
# RSH-09-003: the per-dimension acceptance rules
# ---------------------------------------------------------------------------


class TestAcceptanceRules:
    """Each rule refuses the whole status; an omission is not a claim."""

    @pytest.mark.spec("RSH-09-003")
    def test_a_forward_status_is_accepted(self):
        current = _current_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa)
        asserted = _asserted_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.PXa)
        assert _refused(current, asserted, _VENDOR) == []

    @pytest.mark.spec("RSH-09-003", "RSH-06-001")
    def test_a_non_adjacent_forward_rm_move_is_accepted(self):
        current = _current_status(RM.RECEIVED, None, CS_pxa.pxa)
        asserted = _asserted_status(RM.ACCEPTED, None, None)
        assert _refused(current, asserted) == []

    @pytest.mark.spec("RSH-09-003", "RSH-06-002")
    def test_a_backward_rm_move_is_refused(self):
        current = _current_status(RM.ACCEPTED, None, CS_pxa.pxa)
        asserted = _asserted_status(RM.VALID, None, None)
        assert _refused(current, asserted) == ["rm"]

    @pytest.mark.spec("RSH-09-003")
    def test_any_status_from_a_closed_participant_is_refused(self):
        """``CLOSED`` is terminal, a restated ``CLOSED`` included."""
        current = _current_status(RM.CLOSED, CS_vf.VF, CS_pxa.pxa)
        asserted = _asserted_status(RM.CLOSED, CS_vf.VF, CS_pxa.pxa)
        assert _refused(current, asserted, _VENDOR) == ["rm"]

    @pytest.mark.spec("RSH-09-003")
    def test_a_vf_value_needs_the_vendor_role(self):
        current = _current_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa)
        asserted = _asserted_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.pxa)
        assert _refused(current, asserted, [CVDRole.COORDINATOR]) == ["vf"]
        assert _refused(current, asserted, _VENDOR) == []

    @pytest.mark.spec("RSH-09-003")
    def test_a_d_value_needs_the_deployer_role(self):
        current = _with_d(
            _current_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.pxa), CS_d.d
        )
        asserted = _asserted_status(
            RM.ACCEPTED, CS_vf.VF, CS_pxa.pxa, d_state=CS_d.D
        )
        assert _refused(current, asserted, _VENDOR) == ["d"]
        assert _refused(current, asserted, _VENDOR_DEPLOYER) == []

    @pytest.mark.spec("RSH-09-003")
    def test_a_vf_regression_is_refused(self):
        current = _current_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.pxa)
        asserted = _asserted_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa)
        assert _refused(current, asserted, _VENDOR) == ["vf"]

    @pytest.mark.spec("RSH-09-003")
    def test_a_d_regression_is_refused(self):
        current = _with_d(
            _current_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.pxa), CS_d.D
        )
        asserted = _asserted_status(
            RM.ACCEPTED, CS_vf.VF, CS_pxa.pxa, d_state=CS_d.d
        )
        assert _refused(current, asserted, _VENDOR_DEPLOYER) == ["d"]

    @pytest.mark.spec("RSH-09-003")
    def test_a_pxa_regression_is_refused(self):
        current = _current_status(RM.ACCEPTED, None, CS_pxa.Pxa)
        asserted = _asserted_status(RM.ACCEPTED, None, CS_pxa.pxa)
        assert _refused(current, asserted) == ["pxa"]

    @pytest.mark.spec("RSH-09-003")
    def test_a_multi_step_pxa_advance_is_accepted(self):
        current = _current_status(RM.ACCEPTED, None, CS_pxa.pxa)
        asserted = _asserted_status(RM.ACCEPTED, None, CS_pxa.PXA)
        assert _refused(current, asserted) == []

    @pytest.mark.spec("RSH-09-003")
    def test_an_omitted_dimension_is_not_refused(self):
        """A sender that says nothing about vf, d or the case makes no claim
        to refuse, whatever the receiver holds for them."""
        current = _with_d(
            _current_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.PXa), CS_d.D
        )
        asserted = _asserted_status(RM.ACCEPTED, None, None)
        assert _refused(current, asserted, _VENDOR_DEPLOYER) == []

    @pytest.mark.spec("RSH-09-003")
    def test_an_omission_does_not_reset_the_baseline(self):
        """``VF`` recorded, then a status without ``vf``: a later ``vf`` is
        still a backward move from the last recorded ``VF``, and a P/X/A
        regression likewise reaches past a status that omitted it."""
        earlier = _current_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.Pxa)
        latest = _asserted_status(
            RM.ACCEPTED, None, None, status_id=f"{ASSERTED_STATUS_ID}-0"
        )
        assert latest.vf is None and latest.case_status is None
        asserted = _asserted_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa)
        assert _refused(latest, asserted, _VENDOR, history=[earlier]) == [
            "vf",
            "pxa",
        ]

    @pytest.mark.spec("RSH-09-003")
    def test_an_omitted_deployment_does_not_reset_the_baseline(self):
        """``D`` recorded, then a status without ``d``: a later ``d`` is still
        a backward move from the last recorded ``D``."""
        earlier = _asserted_status(
            RM.ACCEPTED,
            CS_vf.VF,
            CS_pxa.pxa,
            status_id=f"{ASSERTED_STATUS_ID}-earlier",
            d_state=CS_d.D,
        )
        latest = _asserted_status(
            RM.ACCEPTED,
            CS_vf.VF,
            CS_pxa.pxa,
            status_id=f"{ASSERTED_STATUS_ID}-0",
        )
        assert latest.d is None
        asserted = _asserted_status(
            RM.ACCEPTED, CS_vf.VF, CS_pxa.pxa, d_state=CS_d.d
        )
        assert _refused(
            latest, asserted, _VENDOR_DEPLOYER, history=[earlier]
        ) == ["d"]

    @pytest.mark.spec("RSH-09-003", "RSH-06-002")
    def test_a_status_without_rm_states_start_and_is_refused(self):
        """Every status carries an RM state: one that leaves ``rmState`` out
        states ``START``, so after acceptance it is a backward move.  Filling
        in the recorded RM instead would record a status nobody sent, and a
        replica copying it would read ``START`` (RSH-09-001)."""
        current = _current_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa)
        asserted = ParticipantStatus.model_validate(
            {"id": ASSERTED_STATUS_ID, "context": CASE_ID, "vfState": "VF"}
        )
        assert asserted.rm.state is RM.START
        # The ready fix is refused too: it entails an accepted report, and
        # the status as received states START (RSH-09-004).
        assert _refused(current, asserted, _VENDOR) == ["rm", "vf"]

    @pytest.mark.spec("RSH-09-003")
    def test_a_first_observation_has_nothing_to_regress_from(self):
        current = _current_status(RM.ACCEPTED, None, CS_pxa.pxa)
        asserted = _asserted_status(
            RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa, d_state=CS_d.d
        )
        assert _refused(current, asserted, _VENDOR_DEPLOYER) == []

    @pytest.mark.spec("RSH-09-002", "RSH-09-003")
    def test_every_failing_rule_is_reported(self):
        current = _current_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.Pxa)
        asserted = _asserted_status(RM.VALID, CS_vf.Vf, CS_pxa.pxa)
        assert _refused(current, asserted, _VENDOR) == ["rm", "vf", "pxa"]


# ---------------------------------------------------------------------------
# RSH-09-004: cross-machine entailments on the status as received
# ---------------------------------------------------------------------------


class TestCrossMachineEntailments:
    """An impossible combination refuses the status, whichever side moved."""

    @pytest.mark.spec("RSH-09-004", "CSB-18-001")
    def test_a_ready_fix_before_acceptance_is_refused(self):
        """Multi-step advances are legal (CSB-16-001), but a fix cannot be
        ready for a report the vendor has not accepted."""
        current = _current_status(RM.VALID, None, CS_pxa.pxa)
        asserted = _asserted_status(RM.VALID, CS_vf.VF, CS_pxa.pxa)
        assert _refused(current, asserted, _VENDOR) == ["vf"]

    @pytest.mark.spec("RSH-09-004")
    def test_a_ready_fix_after_acceptance_is_accepted(self):
        current = _current_status(RM.ACCEPTED, None, CS_pxa.pxa)
        asserted = _asserted_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.pxa)
        assert _refused(current, asserted, _VENDOR) == []

    @pytest.mark.spec("RSH-09-004", "CSB-18-001")
    def test_a_deployed_fix_before_acceptance_is_refused(self):
        current = _with_d(_current_status(RM.VALID, None, CS_pxa.pxa), CS_d.d)
        asserted = _asserted_status(RM.VALID, None, CS_pxa.pxa, d_state=CS_d.D)
        assert _refused(current, asserted, [CVDRole.DEPLOYER]) == ["d"]

    @pytest.mark.spec("RSH-09-004", "CSB-17-001")
    def test_a_deployed_fix_that_is_not_ready_is_refused(self):
        """Refused whether ``d`` moved or ``vf`` did: the status as received
        is impossible either way."""
        for current_d, asserted_d in ((CS_d.d, CS_d.D), (CS_d.D, CS_d.D)):
            current = _with_d(
                _current_status(RM.ACCEPTED, None, CS_pxa.pxa), current_d
            )
            asserted = _asserted_status(
                RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa, d_state=asserted_d
            )
            assert _refused(current, asserted, _VENDOR_DEPLOYER) == ["d"]

    @pytest.mark.spec("RSH-09-004", "CSB-18-001")
    def test_a_batched_advance_through_acceptance_is_accepted(self):
        """A peer advances ``VALID → ACCEPTED → DEFERRED`` and reports fix
        readiness in one message; ``DEFERRED`` is post-acceptance reachable,
        so the update is accepted (sound, not complete)."""
        current = _current_status(RM.VALID, CS_vf.Vf, CS_pxa.pxa)
        asserted = _asserted_status(RM.DEFERRED, CS_vf.VF, CS_pxa.pxa)
        assert _refused(current, asserted, _VENDOR) == []

    @pytest.mark.spec("RSH-09-004")
    def test_an_absent_dimension_is_unconstrained(self):
        """No entailment applies through a dimension the sender omitted."""
        current = _with_d(
            _current_status(RM.DEFERRED, None, CS_pxa.pxa), CS_d.D
        )
        asserted = _asserted_status(RM.DEFERRED, CS_vf.vf, CS_pxa.pxa)
        assert _refused(current, asserted, _VENDOR_DEPLOYER) == []


# ---------------------------------------------------------------------------
# RSH-06: RM anomaly detection (BB_RM_ANOMALY)
# ---------------------------------------------------------------------------


class TestRMGapAnomalyFlag:
    """CheckParticipantStatusAcceptableNode publishes BB_RM_ANOMALY (RSH-06)."""

    @pytest.mark.spec("RSH-06-001")
    def test_nonadjacent_forward_jump_sets_gap_anomaly(
        self, store_for, make_payload
    ):
        """RECEIVED → ACCEPTED (non-adjacent) sets BB_RM_ANOMALY='gap' (RSH-06-001)."""
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.RECEIVED, None, CS_pxa.pxa)
        asserted = _asserted_status(RM.ACCEPTED, None, None)
        _seed_case(dl, current, asserted)

        seen: dict = {}
        result = _run_tree(
            dl, asserted, CASE_MANAGER_ID, make_payload, anomaly=seen
        )

        assert result.status == Status.SUCCESS
        anomaly = seen["anomaly"]
        assert anomaly is not None, (
            "BB_RM_ANOMALY not set for non-adjacent RM gap"
        )
        assert anomaly["anomaly_type"] == "gap"
        assert anomaly["from_rm"] == RM.RECEIVED
        assert anomaly["to_rm"] == RM.ACCEPTED

    def test_adjacent_forward_transition_no_anomaly(
        self, store_for, make_payload
    ):
        """RECEIVED → VALID (adjacent) sets no BB_RM_ANOMALY (happy path)."""
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.RECEIVED, None, CS_pxa.pxa)
        asserted = _asserted_status(RM.VALID, None, None)
        _seed_case(dl, current, asserted)

        seen: dict = {}
        _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload, anomaly=seen)

        anomaly = seen["anomaly"]
        assert anomaly is None, (
            f"Expected no anomaly for adjacent transition, got {anomaly}"
        )

    @pytest.mark.spec("RSH-06-002")
    def test_backward_regression_refused_sets_regression_anomaly(
        self, store_for, make_payload
    ):
        """ACCEPTED → RECEIVED (backward) sets BB_RM_ANOMALY='regression' (RSH-06-002)."""
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(RM.ACCEPTED, None, CS_pxa.pxa)
        asserted = _asserted_status(RM.RECEIVED, None, None)
        _seed_case(dl, current, asserted)

        seen: dict = {}
        _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload, anomaly=seen)

        anomaly = seen["anomaly"]
        assert anomaly is not None, (
            "BB_RM_ANOMALY not set for backward regression"
        )
        assert anomaly["anomaly_type"] == "regression"
        assert anomaly["from_rm"] == RM.ACCEPTED
        assert anomaly["to_rm"] == RM.RECEIVED


class TestSharedRMAcceptanceRule:
    """The ``Add(ParticipantStatus)`` half of the shared RM table (RSH-06-006).

    ``test/core/behaviors/report/test_rm_declaration_adjudication.py`` runs the
    activity-typed handlers against the same rows; both must record the same
    RM state and flag the same anomaly.
    """

    @pytest.mark.spec("RSH-06-001")
    @pytest.mark.spec("RSH-06-002")
    @pytest.mark.spec("RSH-06-003")
    @pytest.mark.spec("RSH-06-004")
    @pytest.mark.spec("RSH-06-006")
    @pytest.mark.parametrize("case", received_cases())
    def test_status_path_applies_the_shared_rule(
        self, case: RMDeclarationCase, store_for, make_payload, caplog
    ):
        dl = store_for(CASE_MANAGER_ID)
        current = _current_status(case.current, CS_vf.Vf, CS_pxa.pxa)
        asserted = _asserted_status(case.declared, CS_vf.Vf, None)
        _seed_case(dl, current, asserted)

        seen: dict = {}
        with caplog.at_level(logging.WARNING):
            _run_tree(
                dl, asserted, CASE_MANAGER_ID, make_payload, anomaly=seen
            )

        assert recorded_rm(dl) == case.expected_rm
        assert (seen["anomaly"] or {}).get("anomaly_type") == case.anomaly
        # The anomaly is logged at WARNING (RSH-06-003), and the note follows
        # an accepted gap from the effect stage and a refused regression from
        # the refusal-effects stage (RSH-06-004, CLP-10-022).
        assert_anomaly_flagged_and_noted(case, dl, caplog.records)


# ---------------------------------------------------------------------------
# Ledger-apply path (replica side)
# ---------------------------------------------------------------------------


def _status_snapshot_entry(rm_state: str, vf_state: str) -> CaseLedgerEntry:
    """A canonical ``add_participant_status_to_participant`` entry."""
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/add-status-2235",
            semantic_type="add_participant_status_to_participant",
            payload_snapshot={
                "object": {
                    "id": ASSERTED_STATUS_ID,
                    "type": "ParticipantStatus",
                    "context": CASE_ID,
                    "rmState": rm_state,
                    "vfState": vf_state,
                },
                "target": {"id": PARTICIPANT_ID},
            },
            prev_log_hash=_ZERO_HASH,
        )
    )


def _announce_event(
    entry: CaseLedgerEntry,
) -> AnnounceLogEntryReceivedEvent:
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = announce_log_entry_activity(
        entry=wire_entry, actor=CASE_MANAGER_ID
    )
    return cast(AnnounceLogEntryReceivedEvent, extract_event(activity))


class TestLedgerApplyCopiesTheStatus:
    """A replicated entry's status is copied as carried (CM-23-016, ADR-0124)."""

    @staticmethod
    def _apply(dl: Any, actor_id: str = ACTOR_ID) -> Status:
        entry = _status_snapshot_entry(rm_state="VALID", vf_state="Vf")
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        return bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(
                name="ApplyParticipantStatusFromLedger"
            ),
            actor_id=actor_id,
            activity=_announce_event(entry),
        ).status

    @pytest.mark.spec("CM-23-016")
    def test_the_replicas_own_rm_is_never_carried_over_the_entrys(
        self, store_for
    ):
        """Replica at ACCEPTED + VF; the entry records VALID + Vf.

        The replica writes what the entry carries.  Carrying its own RM
        forward would give it a status no entry records, so two replicas at
        the same ledger position could disagree.
        """
        dl = store_for(ACTOR_ID)
        _seed_case(
            dl, _current_status(RM.ACCEPTED, CS_vf.Vf, CS_pxa.pxa), None
        )

        assert self._apply(dl) == Status.SUCCESS

        latest = _latest_status(dl, PARTICIPANT_ID)
        assert latest.id_ == ASSERTED_STATUS_ID
        assert _rm_of(latest) == RM.VALID.name
        assert _vf_of(latest) == CS_vf.Vf.name

    @pytest.mark.spec("CM-23-016")
    def test_two_fresh_replicas_write_identical_records(self, store_for):
        """One entry applied to two replicas: the same record, ids and times.

        A minted id or a clock read in the apply would make them differ.
        """
        current = _current_status(RM.RECEIVED, CS_vf.Vf, CS_pxa.pxa)
        replicas = [store_for(ACTOR_ID), store_for(STRANGER_ID)]
        for dl in replicas:
            _seed_case(dl, current.model_copy(deep=True), None)

        for dl, owner in zip(replicas, (ACTOR_ID, STRANGER_ID), strict=True):
            assert self._apply(dl, owner) == Status.SUCCESS

        # The seed gives each record its own birth status; what the entry
        # wrote is the status appended last.
        first, second = (
            _latest_status(dl, PARTICIPANT_ID).model_dump(mode="json")
            for dl in replicas
        )
        assert first == second
        assert first["id_"] == ASSERTED_STATUS_ID

    @pytest.mark.spec("CM-23-016")
    def test_a_status_already_stored_locally_is_appended_as_carried(
        self, store_for
    ):
        """A status object stored but not yet on the participant is attached.

        An out-of-order ``Announce`` of the object itself, or a replayed
        entry, can leave the object stored without the participant holding
        it; the entry still attaches the status it carries.
        """
        dl = store_for(ACTOR_ID)
        _seed_case(
            dl, _current_status(RM.RECEIVED, CS_vf.Vf, CS_pxa.pxa), None
        )
        dl.create(_asserted_status(RM.VALID, CS_vf.Vf, CS_pxa.pxa))
        assert ASSERTED_STATUS_ID not in _status_ids(dl, PARTICIPANT_ID)

        assert self._apply(dl) == Status.SUCCESS

        assert _status_ids(dl, PARTICIPANT_ID)[-1] == ASSERTED_STATUS_ID
        latest = _latest_status(dl, PARTICIPANT_ID)
        assert _rm_of(latest) == RM.VALID.name


class TestCompositeStateViolationsSharedHelper:
    """The emit, receive, and replica-apply paths share one entailment evaluator (#2906).

    ``composite_state_violations()`` is the single place the RM↔VF, RM↔D and
    VF↔D rules are composed, so the three protocol paths cannot drift apart.
    """

    @staticmethod
    def _violations(rm, vf, d):
        from vultron.core.states.composite_state_invariants import (
            composite_state_violations,
        )

        return composite_state_violations(rm, vf, d)

    def test_no_violations_for_a_consistent_state(self):

        assert self._violations(RM.ACCEPTED, CS_vf.VF, CS_d.D) == []

    def test_names_the_vf_dimension_for_an_rm_vf_violation(self):
        violations = self._violations(RM.VALID, CS_vf.VF, None)

        assert [v.dimension for v in violations] == ["vf"]
        assert "RM" in violations[0].message

    def test_names_the_d_dimension_for_an_rm_d_violation(self):

        violations = self._violations(RM.VALID, None, CS_d.D)

        assert [v.dimension for v in violations] == ["d"]

    def test_names_the_d_dimension_for_a_vf_d_violation(self):
        """VF↔D disqualifies D: deployment cannot precede readiness."""

        violations = self._violations(RM.ACCEPTED, CS_vf.Vf, CS_d.D)

        assert [v.dimension for v in violations] == ["d"]

    def test_absent_dimensions_are_unconstrained(self):
        """An absent dimension carries no claim, so no rule can be violated."""
        assert self._violations(RM.START, None, None) == []

    def test_reports_every_violated_rule_not_just_the_first(self):
        """Every violated rule is reported, across distinct dimensions.

        Both paths refuse the whole status, and the receive path names every
        violated rule in its refusal notice (RSH-09-002, EH-07-001).
        """
        violations = self._violations(RM.VALID, CS_vf.VF, CS_d.D)

        assert [v.dimension for v in violations] == ["vf", "d"], (
            "rm=VALID disqualifies both the F bit (RM↔VF) and the D bit"
            f" (RM↔D): {violations}"
        )

    def test_one_dimension_can_be_named_by_two_rules(self):
        """``d`` violates RM↔D and VF↔D at once; both are reported."""
        violations = self._violations(RM.VALID, CS_vf.Vf, CS_d.D)

        assert {v.dimension for v in violations} == {"d"}
        assert len(violations) == 2, (
            "RM↔D and VF↔D both disqualify d here; the refusal notice names"
            " each rule"
        )

    def test_emit_path_uses_the_shared_helper(self):
        """Regression guard: the emit path must not re-implement the rules.

        Since ADR-0086 the emit path reaches the entailments one level further
        out — ``participant_transition_violations()`` composes them alongside
        the per-dimension and role rules — so the guard is asserted there.  The
        per-node half of the ratchet lives in
        ``test/architecture/test_participant_status_validation.py``.
        """
        import inspect

        from vultron.core.states import participant_transitions

        source = inspect.getsource(participant_transitions)

        assert "composite_state_violations" in source
        for rule in (
            "violation_rm_vf_entailment",
            "violation_rm_d_entailment",
            "violation_vf_d_entailment",
        ):
            assert rule not in source, (
                f"{rule} is composed by composite_state_violations(); calling it"
                " directly here re-introduces the emit/receive/replica-apply divergence"
                " that #2906 fixed"
            )
