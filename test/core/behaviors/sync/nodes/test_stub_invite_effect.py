#!/usr/bin/env python
"""Tests for ApplyStubInviteFromLedgerNode.

A replica builds the invitee's inert participant record from the stub Invite's
ledger entry with the CASE_MANAGER's own builder (CM-11-006, CM-31-012).
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
from test.support.embargo_register import activate
from vultron.core.behaviors.sync.nodes.stub_invite_effect import (
    ApplyStubInviteFromLedgerNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.inert_invitee import (
    build_inert_invitee_participant,
)
from vultron.core.states.cs import CS_vf
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import rm_invite_to_case_activity

INVITEE_ACTOR_ID = "https://example.org/actors/vendor2"
MANAGER_ID = "https://example.org/actors/manager"
EMBARGO_ID = f"{CASE_ID}/embargo_events/active"


def _stub_invite_entry(roles: list[str] | None, log_index: int = 0):
    """A ledger entry whose snapshot is a real stub Invite blob."""
    invite = rm_invite_to_case_activity(
        INVITEE_ACTOR_ID,
        CASE_ID,
        roles=roles,
        actor=MANAGER_ID,
        to=[INVITEE_ACTOR_ID],
    )
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=invite.id_,
            event_type="invite_actor_to_case",
            payload_snapshot=invite.model_dump(
                mode="json", by_alias=True, exclude_none=True
            ),
            prev_log_hash="0" * 64,
        )
    )


def _apply(bridge, case_actor, entry):
    return bridge.execute_with_setup(
        tree=ApplyStubInviteFromLedgerNode(name="ApplyStubInvite"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=case_actor.id_),
    )


def _held_or_none(datalayer):
    case = datalayer.read(CASE_ID)
    record_id = case.actor_participant_index.get(INVITEE_ACTOR_ID)
    return case, (datalayer.read(record_id) if record_id else None)


def _held(datalayer) -> tuple[VulnerabilityCase, CaseParticipant]:
    case, record = _held_or_none(datalayer)
    assert isinstance(record, CaseParticipant)
    return case, record


@pytest.mark.spec("CM-11-006")
@pytest.mark.spec("CM-31-012")
def test_stub_invite_entry_creates_the_inert_record(
    bridge, datalayer, case_actor, case_obj
):
    """AC-1: joined=False, the named roles, RM RECEIVED, VF v for a vendor."""
    result = _apply(bridge, case_actor, _stub_invite_entry(["vendor"]))

    assert result.status == Status.SUCCESS
    _, record = _held(datalayer)
    assert record is not None
    assert record.joined is False
    assert record.case_roles == [CVDRole.VENDOR]
    status = record.participant_statuses[-1]
    assert status.rm.state == RM.RECEIVED
    assert status.vf is not None
    assert status.vf.state == CS_vf.vf


@pytest.mark.spec("CM-11-006")
def test_a_non_vendor_record_carries_no_vf(
    bridge, datalayer, case_actor, case_obj
):
    result = _apply(bridge, case_actor, _stub_invite_entry(["coordinator"]))

    assert result.status == Status.SUCCESS
    _, record = _held(datalayer)
    assert record.case_roles == [CVDRole.COORDINATOR]
    assert record.participant_statuses[-1].vf is None


@pytest.mark.spec("CM-11-006")
def test_active_embargo_gives_the_invited_consent_row(
    bridge, datalayer, case_actor
):
    """The consent row comes from the replica's own case at that position."""
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    activate(case, EMBARGO_ID)
    datalayer.save(case)

    result = _apply(bridge, case_actor, _stub_invite_entry(["vendor"]))

    assert result.status == Status.SUCCESS
    _, record = _held(datalayer)
    assert record.consent_for(EMBARGO_ID) == EmbargoConsentState.INVITED


@pytest.mark.spec("CM-11-006")
def test_replica_record_equals_the_case_manager_builders(
    bridge, datalayer, case_actor
):
    """The replica makes no choice of its own: same builder, same record."""
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    activate(case, EMBARGO_ID)
    datalayer.save(case)
    expected = build_inert_invitee_participant(
        case, INVITEE_ACTOR_ID, [CVDRole.VENDOR]
    )

    _apply(bridge, case_actor, _stub_invite_entry(["vendor"]))

    _, record = _held(datalayer)
    assert record.id_ == expected.id_
    assert record.joined == expected.joined
    assert record.case_roles == expected.case_roles
    assert record.consent_for(EMBARGO_ID) == expected.consent_for(EMBARGO_ID)
    assert [
        (s.rm.state, s.vf.state if s.vf else None)
        for s in record.participant_statuses
    ] == [
        (s.rm.state, s.vf.state if s.vf else None)
        for s in expected.participant_statuses
    ]


@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("SYNC-12-003")
def test_the_same_entry_twice_leaves_one_record(
    bridge, datalayer, case_actor, case_obj
):
    """AC-4: idempotent."""
    entry = _stub_invite_entry(["vendor"])
    for _ in range(2):
        assert _apply(bridge, case_actor, entry).status == Status.SUCCESS

    case, record = _held(datalayer)
    assert list(case.actor_participant_index) == [INVITEE_ACTOR_ID]
    assert record.joined is False


@pytest.mark.spec("CM-11-015")
def test_a_replacement_stub_changes_a_record_already_held(
    bridge, datalayer, case_actor, case_obj
):
    """The CASE_MANAGER reuses the same record, so the replica leaves it be."""
    _apply(bridge, case_actor, _stub_invite_entry(["vendor"]))
    _, record = _held(datalayer)
    record.joined = True
    datalayer.save(record)

    result = _apply(bridge, case_actor, _stub_invite_entry(["finder"], 1))

    assert result.status == Status.SUCCESS
    case, after = _held(datalayer)
    assert list(case.actor_participant_index) == [INVITEE_ACTOR_ID]
    assert after.joined is True
    assert after.case_roles == [CVDRole.VENDOR]


@pytest.mark.spec("CM-11-019")
def test_an_entry_with_no_roles_fails_with_a_reason(
    bridge, datalayer, case_actor, case_obj
):
    result = _apply(bridge, case_actor, _stub_invite_entry(None))

    assert result.status == Status.FAILURE
    assert "roles" in (result.feedback_message or "")
    assert _held_or_none(datalayer)[1] is None


@pytest.mark.spec("SYNC-12-001")
def test_missing_case_replica_is_skipped(bridge, case_actor):
    result = _apply(bridge, case_actor, _stub_invite_entry(["vendor"]))
    assert result.status == Status.SUCCESS
