#!/usr/bin/env python
"""Tests for ApplyParticipantStatusFromLedgerNode and EmitImpossibleStateFaultNode.

Covers the participant-status round-trip: a ratcheted ParticipantStatus is saved
to the DataLayer and then appended directly to the participant record.  The node
uses the in-memory ``status_obj`` rather than re-reading from the DataLayer,
since ParticipantStatus has no reference fields that rehydrate_fields would
expand (ADR-0034 makes the read-back vestigial).

Also covers RSH-05-021: an entry whose effective composite state violates the
RM↔VF, RM↔D, or VF↔D entailments must be refused (FAILURE, no DataLayer write)
and ``Create(ProcessingFault)`` must be emitted to the CaseActor via the
Selector(Apply, EmitFaultThenFail) tree structure in ``announce_tree.py``.

See: specs/multi-actor-demo.yaml DEMOMA-07-003 step 3,
     specs/received-status-handling.yaml RSH-05-021.
"""

import uuid
from datetime import datetime, timezone
from typing import cast
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from vultron.core.behaviors.sync.nodes.participant_status_effect import (
    ApplyParticipantStatusFromLedgerNode,
    EmitImpossibleStateFaultNode,
)
from vultron.core.models.case_ledger import (
    compute_genesis_hash,
    HashChainLedgerRecord,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

_FIXED_CREATED_AT = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
CASE_GENESIS_HASH = compute_genesis_hash(
    CASE_ID, _FIXED_CREATED_AT, OWNER_ACTOR_ID
)

VENDOR_ACTOR_ID = "https://example.org/actors/vendor"
VENDOR_PARTICIPANT_ID = f"urn:uuid:{uuid.uuid4()}"
STATUS_ID = f"urn:uuid:{uuid.uuid4()}"


def _make_participant(
    participant_id: str = VENDOR_PARTICIPANT_ID,
) -> as_CaseParticipant:
    return as_CaseParticipant(
        id_=participant_id,
        attributed_to=VENDOR_ACTOR_ID,
        context=CASE_ID,
    )


def _make_participant_status_snapshot(
    status_id: str,
    participant_id: str,
    vf_state: str = "VF",
    rm_state: str = "ACCEPTED",
    d_state: str | None = None,
) -> dict:
    obj: dict = {
        "id": status_id,
        "type": "ParticipantStatus",
        "vfState": vf_state,
        "rmState": rm_state,
        "context": CASE_ID,
    }
    if d_state is not None:
        obj["dState"] = d_state
    return {
        "object": obj,
        "target": {
            "id": participant_id,
        },
    }


def _make_status_entry(
    status_id: str,
    participant_id: str,
    vf_state: str = "VF",
    rm_state: str = "ACCEPTED",
    d_state: str | None = None,
):
    snapshot = _make_participant_status_snapshot(
        status_id=status_id,
        participant_id=participant_id,
        vf_state=vf_state,
        rm_state=rm_state,
        d_state=d_state,
    )
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/add-status",
            event_type="add_participant_status_to_participant",
            payload_snapshot=snapshot,
            prev_log_hash=CASE_GENESIS_HASH,
        )
    )


@pytest.fixture
def participant(datalayer):
    p = _make_participant()
    datalayer.save(p)
    return p


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("SYNC-12-002")
def test_apply_participant_status_roundtrip_preserves_vf_state(
    bridge, datalayer, case_actor, participant
):
    """vf_state must round-trip correctly through DataLayer save/read.

    Regression: CORE ParticipantStatus appended to list[WireParticipantStatus]
    was serialized with default values rather than actual values.  After the fix
    the saved participant must have the correct vf_state from the ledger entry
    payload snapshot.
    """
    status_id = f"urn:uuid:{uuid.uuid4()}"
    initial_count = len(participant.participant_statuses)

    entry = _make_status_entry(
        status_id=status_id,
        participant_id=participant.id_,
        vf_state="VF",
        rm_state="ACCEPTED",
    )
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyParticipantStatusFromLedgerNode(
            name="ApplyParticipantStatusFromLedger"
        ),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS

    updated = cast(as_CaseParticipant, datalayer.read(participant.id_))
    assert updated is not None
    assert len(updated.participant_statuses) == initial_count + 1

    new_status = cast(ParticipantStatus, updated.participant_statuses[-1])
    assert new_status.vf is not None
    assert new_status.vf.state == CS_vf.VF
    assert new_status.rm.state == RM.ACCEPTED


@pytest.mark.spec("SYNC-12-003")
def test_apply_participant_status_idempotent(
    bridge, datalayer, case_actor, participant
):
    """Applying the same status twice must not duplicate entries."""
    status_id = f"urn:uuid:{uuid.uuid4()}"
    initial_count = len(participant.participant_statuses)
    entry = _make_status_entry(
        status_id=status_id,
        participant_id=participant.id_,
    )
    event = _make_event(entry, actor_id=case_actor.id_)

    for _ in range(2):
        result = bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(
                name="ApplyParticipantStatusFromLedger"
            ),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )
        assert result.status == Status.SUCCESS

    updated = cast(as_CaseParticipant, datalayer.read(participant.id_))
    assert updated is not None
    assert len(updated.participant_statuses) == initial_count + 1


@pytest.mark.spec("SYNC-12-001")
def test_apply_participant_status_skips_missing_participant(
    bridge, case_actor
):
    """Node returns SUCCESS without error when participant not found locally."""
    status_id = f"urn:uuid:{uuid.uuid4()}"
    nonexistent_participant_id = f"urn:uuid:{uuid.uuid4()}"
    entry = _make_status_entry(
        status_id=status_id,
        participant_id=nonexistent_participant_id,
    )
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyParticipantStatusFromLedgerNode(
            name="ApplyParticipantStatusFromLedger"
        ),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# RSH-05-021: composite-state entailment enforcement on the replica-apply path
# ---------------------------------------------------------------------------


class TestApplyParticipantStatusCompositeStateViolation:
    """ApplyParticipantStatusFromLedgerNode refuses impossible composite states.

    RSH-05-021: if the entry's effective state violates composite-state
    entailments (RM↔VF, RM↔D, VF↔D), the node MUST return FAILURE and MUST NOT
    write to the DataLayer.
    """

    @pytest.mark.spec("RSH-05-021")
    def test_valid_composite_state_succeeds(
        self, bridge, datalayer, case_actor, participant
    ):
        """A well-formed entry (rm=ACCEPTED, vf=VF) is applied successfully."""
        status_id = f"urn:uuid:{uuid.uuid4()}"
        initial_count = len(participant.participant_statuses)
        entry = _make_status_entry(
            status_id=status_id,
            participant_id=participant.id_,
            rm_state="ACCEPTED",
            vf_state="VF",
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(
                name="ApplyParticipantStatusFromLedger"
            ),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.SUCCESS
        updated = cast(as_CaseParticipant, datalayer.read(participant.id_))
        assert len(updated.participant_statuses) == initial_count + 1

    @pytest.mark.spec("RSH-05-021")
    def test_impossible_state_rm_valid_vf_ready_fails(
        self, bridge, datalayer, case_actor, participant
    ):
        """rm=VALID + vf=VF violates RM↔VF entailment — FAILURE, no DataLayer write."""
        initial_count = len(participant.participant_statuses)
        status_id = f"urn:uuid:{uuid.uuid4()}"
        entry = _make_status_entry(
            status_id=status_id,
            participant_id=participant.id_,
            rm_state="VALID",
            vf_state="VF",
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(
                name="ApplyParticipantStatusFromLedger"
            ),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.FAILURE
        updated = cast(as_CaseParticipant, datalayer.read(participant.id_))
        assert (
            len(updated.participant_statuses) == initial_count
        ), "FAILURE must not write to DataLayer"

    @pytest.mark.spec("RSH-05-021")
    def test_impossible_state_vf_not_ready_d_deployed_fails(
        self, bridge, datalayer, case_actor, participant
    ):
        """vf=Vf + d=D violates VF↔D entailment — FAILURE, no DataLayer write."""
        initial_count = len(participant.participant_statuses)
        status_id = f"urn:uuid:{uuid.uuid4()}"
        entry = _make_status_entry(
            status_id=status_id,
            participant_id=participant.id_,
            rm_state="ACCEPTED",
            vf_state="Vf",
            d_state="D",
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(
                name="ApplyParticipantStatusFromLedger"
            ),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.FAILURE
        updated = cast(as_CaseParticipant, datalayer.read(participant.id_))
        assert (
            len(updated.participant_statuses) == initial_count
        ), "FAILURE must not write to DataLayer"

    @pytest.mark.spec("RSH-05-007")
    def test_rm_ratchet_interacts_correctly_with_composite_state_check(
        self, bridge, datalayer, case_actor, participant
    ):
        """RSH-05-007 ratchet runs before RSH-05-021 composite-state check.

        Apply a valid entry first to establish rm=ACCEPTED on the replica.
        Then send an entry asserting rm=VALID (which would regress) + vf=VF.
        The ratchet carries rm forward to ACCEPTED, producing rm=ACCEPTED+vf=VF
        which is a valid composite state — so the node returns SUCCESS.

        This verifies that the two invariants compose correctly: ratchet first,
        entailment check on the effective (post-ratchet) state.
        """
        initial_count = len(participant.participant_statuses)

        status_id_1 = f"urn:uuid:{uuid.uuid4()}"
        entry1 = _make_status_entry(
            status_id=status_id_1,
            participant_id=participant.id_,
            rm_state="ACCEPTED",
            vf_state="VF",
        )
        result1 = bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(name="Apply1"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=_make_event(entry1, actor_id=case_actor.id_),
        )
        assert result1.status == Status.SUCCESS

        status_id_2 = f"urn:uuid:{uuid.uuid4()}"
        entry2 = _make_status_entry(
            status_id=status_id_2,
            participant_id=participant.id_,
            rm_state="VALID",
            vf_state="VF",
        )
        result2 = bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(name="Apply2"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=_make_event(entry2, actor_id=case_actor.id_),
        )
        assert result2.status == Status.SUCCESS, (
            "After ratcheting rm=VALID → rm=ACCEPTED the effective state is "
            "rm=ACCEPTED+vf=VF which is valid — the entailment check must use "
            "the post-ratchet state, not the raw asserted state"
        )
        updated = cast(as_CaseParticipant, datalayer.read(participant.id_))
        assert len(updated.participant_statuses) == initial_count + 2


class TestEmitImpossibleStateFaultNode:
    """EmitImpossibleStateFaultNode emits the fault and returns FAILURE."""

    @pytest.mark.spec("RSH-05-021")
    def test_emits_fault_with_impossible_state_class(
        self, datalayer, case_actor
    ):
        """Node emits ProcessingFault with ImpossibleState class and returns FAILURE."""
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.ports.trigger_activity import TriggerActivityPort
        from vultron.core.models.fault_classes import (
            VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE,
        )

        trigger_activity = MagicMock(spec=TriggerActivityPort)
        trigger_activity.emit_processing_fault.return_value = (
            f"urn:uuid:{uuid.uuid4()}"
        )
        trigger_bridge = BTBridge(
            datalayer=datalayer, trigger_activity=trigger_activity
        )

        status_id = f"urn:uuid:{uuid.uuid4()}"
        entry = _make_status_entry(
            status_id=status_id,
            participant_id=f"urn:uuid:{uuid.uuid4()}",
            rm_state="VALID",
            vf_state="VF",
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = trigger_bridge.execute_with_setup(
            tree=EmitImpossibleStateFaultNode(name="EmitImpossibleStateFault"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.FAILURE
        trigger_activity.emit_processing_fault.assert_called_once()
        call_kwargs = trigger_activity.emit_processing_fault.call_args.kwargs
        assert (
            call_kwargs["failure_class"]
            == VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE
        )
        assert case_actor.id_ in call_kwargs["to"]

    @pytest.mark.spec("RSH-05-021")
    def test_returns_failure_without_trigger_activity(
        self, bridge, case_actor
    ):
        """Node still returns FAILURE gracefully when no TriggerActivityPort is wired."""
        status_id = f"urn:uuid:{uuid.uuid4()}"
        entry = _make_status_entry(
            status_id=status_id,
            participant_id=f"urn:uuid:{uuid.uuid4()}",
            rm_state="VALID",
            vf_state="VF",
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=EmitImpossibleStateFaultNode(name="EmitImpossibleStateFault"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.FAILURE
