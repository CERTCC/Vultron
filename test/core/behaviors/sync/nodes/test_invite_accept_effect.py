#!/usr/bin/env python
"""Tests for ApplyInviteAcceptFromLedgerNode.

The Accept entry makes on the invitee's existing inert record the changes the
CASE_MANAGER makes at the stub Accept: consent to the embargo in force, joined,
and a vendor's VF to ``Vf``.  It never creates a record (CM-11-006, CM-11-021,
CM-31-012).  Per SYNC-02-002, ADR-0022, DEMOMA-07-003, ADR-0124.
"""

from datetime import UTC, datetime

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
from vultron.core.behaviors.sync.nodes.invite_accept_effect import (
    ApplyInviteAcceptFromLedgerNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.inert_invitee import (
    build_inert_invitee_participant,
    derived_status_id,
)
from vultron.core.states.cs import CS_vf
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

INVITEE_ACTOR_ID = "https://example.org/actors/vendor2"
INVITE_ID = f"{CASE_ID}/invitations/stub-1"
ACCEPT_ID = "https://example.org/activities/accept-invite"
EMBARGO_ID = f"{CASE_ID}/embargo_events/active"
INVITED_AT = datetime(2026, 10, 9, 12, 0, 0, tzinfo=UTC)
ACCEPTED_AT = datetime(2026, 10, 9, 13, 0, 0, tzinfo=UTC)


def _make_invite_accept_entry(
    invitee_id: str = INVITEE_ACTOR_ID, published: str | None = None
):
    snapshot: dict[str, object] = {"actor": {"id": invitee_id}}
    snapshot["published"] = (
        ACCEPTED_AT.isoformat() if published is None else published
    )
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=ACCEPT_ID,
            event_type="accept_invite_actor_to_case",
            payload_snapshot=snapshot,
            prev_log_hash="0" * 64,
        )
    )


@pytest.fixture
def case_with_actor(datalayer):
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    datalayer.save(case)
    return case


def _seat(datalayer, roles, embargo: bool = False) -> CaseParticipant:
    """The replica's inert record, as the stub Invite's entry leaves it."""
    case = datalayer.read(CASE_ID)
    if embargo:
        activate(case, EMBARGO_ID)
    record = build_inert_invitee_participant(
        case,
        INVITEE_ACTOR_ID,
        roles,
        invite_id=INVITE_ID,
        published=INVITED_AT,
    )
    datalayer.create(record)
    case.add_participant(record)
    datalayer.save(case)
    return record


@pytest.fixture
def inert_invitee(datalayer, case_with_actor):
    return _seat(datalayer, [CVDRole.VENDOR])


def _apply(bridge, case_actor, entry=None):
    event = _make_event(
        entry or _make_invite_accept_entry(), actor_id=case_actor.id_
    )
    return bridge.execute_with_setup(
        tree=ApplyInviteAcceptFromLedgerNode(name="ApplyInviteAccept"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )


def _stored(datalayer, record: CaseParticipant) -> CaseParticipant:
    stored = datalayer.read(record.id_)
    assert isinstance(stored, CaseParticipant)
    return stored


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
    record = _stored(datalayer, inert_invitee)
    assert record.joined is True
    assert record.id_ == inert_invitee.id_
    assert record.case_roles == [CVDRole.VENDOR]
    assert record.updated == ACCEPTED_AT


@pytest.mark.spec("CM-11-009")
@pytest.mark.spec("CM-31-012")
def test_accept_advances_a_vendor_to_vf_with_derived_id_and_time(
    bridge, datalayer, case_actor, inert_invitee
):
    assert _apply(bridge, case_actor).status == Status.SUCCESS

    statuses = _stored(datalayer, inert_invitee).participant_statuses
    assert [s.vf.state for s in statuses if s.vf] == [CS_vf.vf, CS_vf.Vf]
    aware = statuses[-1]
    assert aware.id_ == derived_status_id(
        ACCEPT_ID, INVITEE_ACTOR_ID, "vendor-aware"
    )
    assert aware.published == ACCEPTED_AT
    assert aware.updated == ACCEPTED_AT
    assert aware.rm.state == RM.RECEIVED


@pytest.mark.spec("CM-18-005")
@pytest.mark.spec("CM-31-012")
@pytest.mark.parametrize("roles", [[CVDRole.VENDOR], [CVDRole.COORDINATOR]])
def test_accept_signs_the_embargo_in_force_for_every_role(
    bridge, datalayer, case_actor, case_with_actor, roles
):
    record = _seat(datalayer, roles, embargo=True)
    assert record.consent_for(EMBARGO_ID) == EmbargoConsentState.INVITED

    assert _apply(bridge, case_actor).status == Status.SUCCESS

    after = _stored(datalayer, record)
    assert after.consent_for(EMBARGO_ID) == EmbargoConsentState.ACCEPTED
    assert after.is_signatory(EMBARGO_ID)


@pytest.mark.spec("CM-31-012")
def test_accept_with_no_embargo_adds_no_consent_row(
    bridge, datalayer, case_actor, inert_invitee
):
    assert _apply(bridge, case_actor).status == Status.SUCCESS

    assert _stored(datalayer, inert_invitee).embargo_consents == []


@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("CM-11-009")
@pytest.mark.parametrize(
    "roles",
    [[CVDRole.COORDINATOR], [CVDRole.FINDER], [CVDRole.OBSERVER]],
)
def test_accept_writes_no_vf_for_a_non_vendor(
    bridge, datalayer, case_actor, case_with_actor, roles
):
    """VF is vendor-only; the Accept adds no status to any other invitee."""
    record = _seat(datalayer, roles)
    before = len(record.participant_statuses)

    assert _apply(bridge, case_actor).status == Status.SUCCESS

    after = _stored(datalayer, record)
    assert after.joined is True
    assert len(after.participant_statuses) == before
    assert all(s.vf is None for s in after.participant_statuses)


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


@pytest.mark.spec("CLP-15-006")
def test_accept_entry_without_published_fails_and_changes_nothing(
    bridge, datalayer, case_actor, inert_invitee
):
    """A time the entry does not carry is never replaced by the clock."""
    before = _stored(datalayer, inert_invitee).model_dump(mode="json")
    entry = _make_invite_accept_entry(published="")

    result = _apply(bridge, case_actor, entry)

    assert result.status == Status.FAILURE
    assert "published" in (result.feedback_message or "")
    assert _stored(datalayer, inert_invitee).model_dump(mode="json") == before


@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("SYNC-12-003")
def test_accept_applied_twice_leaves_one_joined_record(
    bridge, datalayer, case_actor, case_with_actor
):
    """AC-4: a replay changes nothing the first application did not."""
    record = _seat(datalayer, [CVDRole.VENDOR], embargo=True)
    assert _apply(bridge, case_actor).status == Status.SUCCESS
    once = _stored(datalayer, record).model_dump(mode="json")

    assert _apply(bridge, case_actor).status == Status.SUCCESS

    updated = datalayer.read(CASE_ID)
    assert list(updated.actor_participant_index) == [INVITEE_ACTOR_ID]
    assert _stored(datalayer, record).model_dump(mode="json") == once


@pytest.mark.spec("SYNC-12-001")
def test_apply_invite_accept_skips_missing_case(bridge, case_actor):
    """Node returns SUCCESS when the case is not in the local DataLayer."""
    assert _apply(bridge, case_actor).status == Status.SUCCESS
