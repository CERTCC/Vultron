#!/usr/bin/env python
"""Tests for ApplyInviteAcceptFromLedgerNode.

Covers accept_invite_actor_to_case ledger event application.
Per SYNC-02-002, ADR-0022, DEMOMA-07-003.
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


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("SYNC-12-002")
def test_apply_invite_accept_adds_participant(
    bridge, datalayer, case_actor, case_with_actor
):
    """Invitee is added to case.actor_participant_index after invite-accept."""
    assert case_with_actor is not None
    entry = _make_invite_accept_entry(INVITEE_ACTOR_ID)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyInviteAcceptFromLedgerNode(name="ApplyInviteAccept"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
    updated = datalayer.read(CASE_ID)
    assert updated is not None
    assert INVITEE_ACTOR_ID in updated.actor_participant_index


@pytest.mark.spec("SYNC-12-003")
def test_apply_invite_accept_idempotent(
    bridge, datalayer, case_actor, case_with_actor
):
    """Applying the same invite-accept twice does not duplicate participant."""
    assert case_with_actor is not None
    entry = _make_invite_accept_entry(INVITEE_ACTOR_ID)
    event = _make_event(entry, actor_id=case_actor.id_)

    for _ in range(2):
        result = bridge.execute_with_setup(
            tree=ApplyInviteAcceptFromLedgerNode(name="ApplyInviteAccept"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )
        assert result.status == Status.SUCCESS

    updated = datalayer.read(CASE_ID)
    actor_ids = list(updated.actor_participant_index.keys())
    assert actor_ids.count(INVITEE_ACTOR_ID) == 1


@pytest.mark.spec("SYNC-12-001")
def test_apply_invite_accept_skips_missing_case(bridge, case_actor):
    """Node returns SUCCESS when the case is not in the local DataLayer."""
    entry = _make_invite_accept_entry(INVITEE_ACTOR_ID)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyInviteAcceptFromLedgerNode(name="ApplyInviteAccept"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS


@pytest.mark.spec("CM-17-003")
def test_apply_invite_accept_from_ledger_preserves_roles(
    bridge, datalayer, case_actor, case_with_actor
):
    """CM-17-003: ledger path sets case_roles from payload_snapshot object.roles.

    Before fix: stub CaseParticipant was created with no case_roles regardless
    of what the payload_snapshot["object"]["roles"] contained (ISSUE-2719 Bug 1
    sibling). After fix: roles are extracted and set on the participant.
    """
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=1,
            object_id="https://example.org/activities/accept-invite-with-roles",
            event_type="accept_invite_actor_to_case",
            payload_snapshot={
                "actor": {"id": INVITEE_ACTOR_ID},
                "object": {
                    "id": "https://example.org/activities/invite-001",
                    "type": "Invite",
                    "roles": ["vendor"],
                },
            },
            prev_log_hash="0" * 64,
        )
    )
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyInviteAcceptFromLedgerNode(name="ApplyInviteAccept"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
    updated = datalayer.read(CASE_ID)
    assert INVITEE_ACTOR_ID in updated.actor_participant_index

    from vultron.enums.roles import CVDRole

    participant_id = updated.actor_participant_index[INVITEE_ACTOR_ID]
    participant = datalayer.read(participant_id)
    assert participant is not None
    assert CVDRole.VENDOR in participant.case_roles
