#!/usr/bin/env python
"""Tests for ApplyParticipantStatusFromLedgerNode.

Covers the critical round-trip serialization bug: a CORE ParticipantStatus
appended directly to as_CaseParticipant.participant_statuses was serialized with
default field values by Pydantic because the declared list element type
(WireParticipantStatus) governed serialization rather than the actual runtime
type.  The fix reads the saved status back from the DataLayer (which
reconstructs it as the vocabulary-typed wire-format class) before appending.

See: specs/multi-actor-demo.yaml DEMOMA-07-003 step 3.
"""

import uuid
from datetime import datetime, timezone
from typing import cast

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
)
from vultron.core.models.case_ledger import (
    compute_genesis_hash,
    HashChainLedgerRecord,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_vfd
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
    vfd_state: str = "VFd",
    rm_state: str = "ACCEPTED",
) -> dict:
    return {
        "object": {
            "id": status_id,
            "type": "ParticipantStatus",
            "vfdState": vfd_state,
            "rmState": rm_state,
            "context": CASE_ID,
        },
        "target": {
            "id": participant_id,
        },
    }


def _make_status_entry(
    status_id: str,
    participant_id: str,
    vfd_state: str = "VFd",
    rm_state: str = "ACCEPTED",
):
    snapshot = _make_participant_status_snapshot(
        status_id=status_id,
        participant_id=participant_id,
        vfd_state=vfd_state,
        rm_state=rm_state,
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


def test_apply_participant_status_roundtrip_preserves_vfd_state(
    bridge, datalayer, case_actor, participant
):
    """vfd_state must round-trip correctly through DataLayer save/read.

    Regression: CORE ParticipantStatus appended to list[WireParticipantStatus]
    was serialized with default values (vfd_state='vfd') rather than actual
    values.  After the fix the saved participant must have the correct vfd_state
    from the ledger entry payload snapshot.
    """
    status_id = f"urn:uuid:{uuid.uuid4()}"
    initial_count = len(participant.participant_statuses)

    entry = _make_status_entry(
        status_id=status_id,
        participant_id=participant.id_,
        vfd_state="VFd",
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
    assert new_status.vfd.state == CS_vfd.VFd
    assert new_status.rm.state == RM.ACCEPTED


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
