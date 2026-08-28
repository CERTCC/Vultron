#!/usr/bin/env python
"""Tests for ApplyCloseCaseFromLedgerNode.

Covers close_case ledger event advancing the departing actor to RM.CLOSED.
Per CM-23-003, CM-23-004, SYNC-02-002.
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
from vultron.core.behaviors.sync.nodes.close_case_effect import (
    ApplyCloseCaseFromLedgerNode,
)
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.core.models.case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

DEPARTING_ACTOR_ID = "https://example.org/actors/vendor"
DEPARTING_PARTICIPANT_ID = f"{CASE_ID}/participants/vendor"


def _make_close_case_entry(actor_id: str = DEPARTING_ACTOR_ID):
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/close-case",
            event_type="close_case",
            payload_snapshot={"actor": {"id": actor_id}},
            prev_log_hash="0" * 64,
        )
    )


@pytest.fixture
def case_with_participant(datalayer):
    participant = as_CaseParticipant(
        id_=DEPARTING_PARTICIPANT_ID,
        attributed_to=DEPARTING_ACTOR_ID,
        context=CASE_ID,
    )
    case = VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=OWNER_ACTOR_ID
    )
    case.add_participant(participant)
    datalayer.save(participant)
    datalayer.save(case)
    return case, participant


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("SYNC-12-002")
def test_apply_close_case_advances_actor_to_rm_closed(
    bridge, datalayer, case_actor, case_with_participant
):
    """Departing actor's latest participant status reaches RM.CLOSED."""
    assert case_with_participant is not None
    entry = _make_close_case_entry(DEPARTING_ACTOR_ID)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyCloseCaseFromLedgerNode(name="ApplyCloseCase"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
    updated_participant = datalayer.read(DEPARTING_PARTICIPANT_ID)
    assert updated_participant is not None
    rm_states = [
        ps.rm.state
        for ps in updated_participant.participant_statuses
        if hasattr(ps, "rm")
    ]
    assert RM.CLOSED in rm_states, (
        f"Expected RM.CLOSED in participant statuses after close_case;"
        f" got {rm_states}"
    )


@pytest.mark.spec("SYNC-12-003")
def test_apply_close_case_idempotent(
    bridge, datalayer, case_actor, case_with_participant
):
    """Applying close_case twice does not add duplicate RM.CLOSED statuses."""
    assert case_with_participant is not None
    entry = _make_close_case_entry(DEPARTING_ACTOR_ID)
    event = _make_event(entry, actor_id=case_actor.id_)

    for _ in range(2):
        result = bridge.execute_with_setup(
            tree=ApplyCloseCaseFromLedgerNode(name="ApplyCloseCase"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )
        assert result.status == Status.SUCCESS

    updated_participant = datalayer.read(DEPARTING_PARTICIPANT_ID)
    closed_count = sum(
        1
        for ps in updated_participant.participant_statuses
        if hasattr(ps, "rm") and ps.rm.state == RM.CLOSED
    )
    assert (
        closed_count == 1
    ), f"Expected exactly one RM.CLOSED status; got {closed_count}"


@pytest.mark.spec("SYNC-12-001")
def test_apply_close_case_skips_missing_case(bridge, case_actor):
    """Node returns SUCCESS when the case is not in the local DataLayer."""
    entry = _make_close_case_entry(DEPARTING_ACTOR_ID)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyCloseCaseFromLedgerNode(name="ApplyCloseCase"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS


@pytest.mark.spec("SYNC-12-001")
def test_apply_close_case_skips_unknown_actor(
    bridge, case_actor, case_with_participant
):
    """Node returns SUCCESS when actor is not in actor_participant_index."""
    assert case_with_participant is not None
    unknown_actor_id = "https://example.org/actors/unknown"
    entry = _make_close_case_entry(unknown_actor_id)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=ApplyCloseCaseFromLedgerNode(name="ApplyCloseCase"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
