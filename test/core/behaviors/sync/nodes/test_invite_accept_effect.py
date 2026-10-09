#!/usr/bin/env python
"""Tests for ApplyInviteAcceptFromLedgerNode.

The Accept entry marks the invitee's existing inert record joined and never
creates one (CM-11-006, CM-11-021, CM-31-012).  Per SYNC-02-002, ADR-0022,
DEMOMA-07-003.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from vultron.core.behaviors.sync.nodes.invite_accept_effect import (
    ApplyInviteAcceptFromLedgerNode,
)
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.inert_invitee import (
    build_inert_invitee_participant,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

INVITEE_ACTOR_ID = "https://example.org/actors/vendor2"


def _make_invite_accept_entry(invitee_id: str = INVITEE_ACTOR_ID):
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/accept-invite",
            event_type="accept_invite_actor_to_case",
            payload_snapshot={"actor": {"id": invitee_id}},
            prev_log_hash="0" * 64,
        )
    )


@pytest.fixture
def case_with_actor(datalayer):
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=OWNER_ACTOR_ID
    )
    datalayer.save(case)
    return case


@pytest.fixture
def inert_invitee(datalayer, case_with_actor):
    """The replica's inert record, as the stub Invite's entry leaves it."""
    record = CaseParticipant(
        id_=f"{CASE_ID}/participants/vendor2",
        attributed_to=INVITEE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
        joined=False,
    )
    datalayer.create(record)
    case = datalayer.read(CASE_ID)
    case.add_participant(record)
    datalayer.save(case)
    return record


def _apply(bridge, case_actor):
    event = _make_event(_make_invite_accept_entry(), actor_id=case_actor.id_)
    return bridge.execute_with_setup(
        tree=ApplyInviteAcceptFromLedgerNode(name="ApplyInviteAccept"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )


@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("CM-11-006")
def test_accept_marks_the_existing_record_joined(
    bridge, datalayer, case_actor, inert_invitee
):
    """AC-2: the held inert record becomes joined and none is created."""
    result = _apply(bridge, case_actor)

    assert result.status == Status.SUCCESS
    updated = datalayer.read(CASE_ID)
    assert list(updated.actor_participant_index) == [INVITEE_ACTOR_ID]
    record = datalayer.read(updated.actor_participant_index[INVITEE_ACTOR_ID])
    assert record.joined is True
    assert record.id_ == inert_invitee.id_
    assert record.case_roles == [CVDRole.VENDOR]


@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("CM-11-021")
def test_accept_with_no_record_fails_with_a_reason_and_builds_none(
    bridge, datalayer, case_actor, case_with_actor
):
    """AC-3: a replica with no record has a broken invariant; it builds none."""
    result = _apply(bridge, case_actor)

    assert result.status == Status.FAILURE
    assert INVITEE_ACTOR_ID in (result.feedback_message or "")
    assert "no participant record" in (result.feedback_message or "")
    updated = datalayer.read(CASE_ID)
    assert INVITEE_ACTOR_ID not in updated.actor_participant_index
    assert datalayer.read(f"{CASE_ID}/participants/vendor2") is None


@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("SYNC-12-003")
def test_accept_applied_twice_leaves_one_joined_record(
    bridge, datalayer, case_actor, inert_invitee
):
    """AC-4: a replay changes nothing the first application did not."""
    for _ in range(2):
        assert _apply(bridge, case_actor).status == Status.SUCCESS

    updated = datalayer.read(CASE_ID)
    assert list(updated.actor_participant_index) == [INVITEE_ACTOR_ID]
    record = datalayer.read(updated.actor_participant_index[INVITEE_ACTOR_ID])
    assert record.joined is True


@pytest.mark.spec("SYNC-12-001")
def test_apply_invite_accept_skips_missing_case(bridge, case_actor):
    """Node returns SUCCESS when the case is not in the local DataLayer."""
    assert _apply(bridge, case_actor).status == Status.SUCCESS


@pytest.mark.spec("CM-11-009")
def test_accept_writes_no_vf_for_a_non_vendor(
    bridge, datalayer, case_actor, case_with_actor
):
    """VF is vendor-only; the Accept entry never adds a status of any kind."""
    record = build_inert_invitee_participant(
        case_with_actor, INVITEE_ACTOR_ID, [CVDRole.COORDINATOR]
    )
    datalayer.create(record)
    case = datalayer.read(CASE_ID)
    case.add_participant(record)
    datalayer.save(case)
    before = len(record.participant_statuses)

    assert _apply(bridge, case_actor).status == Status.SUCCESS

    after = datalayer.read(record.id_)
    assert after.joined is True
    assert len(after.participant_statuses) == before
    assert all(s.vf is None for s in after.participant_statuses)
