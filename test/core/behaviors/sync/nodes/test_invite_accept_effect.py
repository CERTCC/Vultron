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
