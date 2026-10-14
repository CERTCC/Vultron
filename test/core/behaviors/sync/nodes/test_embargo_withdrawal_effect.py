#!/usr/bin/env python
"""Replaying a signatory's ``Leave(EmbargoEvent)`` on a replica (MSM-07-010).

Each test runs in the participant's replica store (``PARTICIPANT_ACTOR_ID``,
see ``conftest.py``) and applies the withdrawal entry the CASE_MANAGER
committed (EP-09-007, RSH-08-004).
"""

from datetime import timedelta
from typing import Any, cast

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from test.support.embargo_register import activate, propose
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoWithdrawalFromLedgerNode,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState as ECS,
)
from vultron.enums.roles import CVDRole

MANAGER_ACTOR_ID = "https://example.org/actors/case-manager"
ACTIVE_EMBARGO_ID = f"{CASE_ID}/embargo_events/e0"
REVISION_ID = f"{CASE_ID}/embargo_events/e1"
_EVENT_TYPE = MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE.value


def _embargo(embargo_id: str, days: int) -> EmbargoEvent:
    return EmbargoEvent(
        id_=embargo_id,
        context=CASE_ID,
        end_time=now_utc() + timedelta(days=days),
    )


def _leave_entry(
    actor: str = PARTICIPANT_ACTOR_ID, embargo_id: str = ACTIVE_EMBARGO_ID
) -> CaseLedgerEntry:
    snapshot: dict[str, Any] = {
        "type": "Leave",
        "id": "https://example.org/activities/leave-e0",
        "actor": actor,
        "to": [MANAGER_ACTOR_ID],
        "context": CASE_ID,
        "object": {
            "type": "EmbargoEvent",
            "id": embargo_id,
            "context": CASE_ID,
        },
    }
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=snapshot["id"],
            event_type=_EVENT_TYPE,
            payload_snapshot=snapshot,
            prev_log_hash="0" * 64,
        )
    )


def _seat(
    datalayer, case: VulnerabilityCase, actor_id: str, rows: dict[str, ECS]
) -> str:
    participant = CaseParticipant(
        attributed_to=actor_id,
        context=CASE_ID,
        embargo_consents=[
            EmbargoConsent(embargo_id=e, state=s) for e, s in rows.items()
        ],
        case_roles=(
            [CVDRole.CASE_MANAGER] if actor_id == MANAGER_ACTOR_ID else []
        ),
    )
    case.add_participant(participant)
    datalayer.create(participant)
    return participant.id_


@pytest.fixture
def revising_replica(datalayer) -> VulnerabilityCase:
    """The participant is AGREED on the embargo in force and the revision."""
    datalayer.create(_embargo(ACTIVE_EMBARGO_ID, 30))
    datalayer.create(_embargo(REVISION_ID, 20))
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    activate(case, ACTIVE_EMBARGO_ID)
    propose(case, REVISION_ID)
    agreed = {ACTIVE_EMBARGO_ID: ECS.AGREED, REVISION_ID: ECS.AGREED}
    for actor_id in (MANAGER_ACTOR_ID, OWNER_ACTOR_ID, PARTICIPANT_ACTOR_ID):
        _seat(datalayer, case, actor_id, dict(agreed))
    datalayer.save(case)
    return case


def _run(bridge, entry: CaseLedgerEntry):
    node = ApplyEmbargoWithdrawalFromLedgerNode(name="ApplyWithdrawal")
    result = bridge.execute_with_setup(
        tree=node,
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=MANAGER_ACTOR_ID),
    )
    return result, node


def _rows(datalayer, actor_id: str) -> dict[str, str]:
    case = cast(VulnerabilityCase, datalayer.read(CASE_ID))
    participant = cast(
        CaseParticipant, datalayer.read(case.actor_participant_index[actor_id])
    )
    return {r.embargo_id: r.state.value for r in participant.embargo_consents}


@pytest.mark.spec("MSM-07-010", "EP-09-007", "RSH-08-004")
def test_replica_replays_its_own_withdrawal(
    datalayer, bridge, revising_replica
) -> None:
    """The withdrawer's replica declines the active and the agreed revision."""
    result, _ = _run(bridge, _leave_entry())

    assert result.status == Status.SUCCESS
    assert _rows(datalayer, PARTICIPANT_ACTOR_ID) == {
        ACTIVE_EMBARGO_ID: "DECLINED",
        REVISION_ID: "DECLINED",
    }
    # Nobody else's consent moves, and the embargo stays in force.
    assert _rows(datalayer, OWNER_ACTOR_ID)[ACTIVE_EMBARGO_ID] == "AGREED"
    case = cast(VulnerabilityCase, datalayer.read(CASE_ID))
    assert case.active_embargo_id == ACTIVE_EMBARGO_ID
    assert case.proposed_embargo_ids == [REVISION_ID]


@pytest.mark.spec("MSM-07-010", "SYNC-12-001")
def test_a_repeat_of_the_withdrawal_replays_as_a_no_op(
    datalayer, bridge, revising_replica
) -> None:
    """A row already DECLINED has nothing left to apply; the persist proceeds."""
    _run(bridge, _leave_entry())

    result, node = _run(bridge, _leave_entry())

    assert result.status == Status.SUCCESS
    assert "already applied" in node.feedback_message
    assert _rows(datalayer, PARTICIPANT_ACTOR_ID)[ACTIVE_EMBARGO_ID] == (
        "DECLINED"
    )


@pytest.mark.spec("MSM-07-010")
def test_a_withdrawal_naming_no_actor_fails(
    datalayer, bridge, revising_replica
) -> None:
    entry = _leave_entry()
    entry.payload_snapshot.pop("actor")

    result, node = _run(bridge, entry)

    assert result.status == Status.FAILURE
    assert "names no actor" in node.feedback_message
    assert _rows(datalayer, PARTICIPANT_ACTOR_ID)[ACTIVE_EMBARGO_ID] == (
        "AGREED"
    )


@pytest.mark.spec("MSM-07-010")
def test_a_withdrawal_by_an_actor_not_on_this_replica_is_skipped(
    datalayer, bridge, revising_replica
) -> None:
    """A partial replica holds no record for the actor (Regime 2, ADR-0087)."""
    result, node = _run(
        bridge, _leave_entry(actor="https://example.org/actors/stranger")
    )

    assert result.status == Status.SUCCESS
    assert "partial replica" in node.feedback_message


@pytest.mark.spec("MSM-07-010")
def test_a_replica_without_the_case_skips_the_entry(datalayer, bridge) -> None:
    result, _ = _run(bridge, _leave_entry())

    assert result.status == Status.SUCCESS
