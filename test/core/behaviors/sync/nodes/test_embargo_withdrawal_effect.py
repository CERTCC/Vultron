#!/usr/bin/env python
"""Replaying a signatory's ``Leave(EmbargoEvent)`` on a replica (MSM-07-010).

Each test runs in the participant's replica store (``PARTICIPANT_ACTOR_ID``,
see ``conftest.py``) and applies the withdrawal entry the CASE_MANAGER
committed (EP-09-007, RSH-08-004).  Under the copy model the Leave carries
no row: every row it declines is the CASE_MANAGER's next
``Update(EmbargoConsent)`` entry, which the consent slot copies (ADR-0124),
so this slot re-runs no lifecycle logic and writes no row.
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
_SEMANTIC_TYPE = MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE.value


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
            "endTime": (now_utc() + timedelta(days=30)).isoformat(),
        },
    }
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=snapshot["id"],
            semantic_type=_SEMANTIC_TYPE,
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


def _register(datalayer) -> list[tuple[str, str]]:
    case = cast(VulnerabilityCase, datalayer.read(CASE_ID))
    return [(e.embargo_id, e.status.value) for e in case.embargo_register]


@pytest.mark.spec("MSM-07-010")
@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("CM-23-016")
def test_the_leave_writes_no_row_on_the_withdrawers_replica(
    datalayer, bridge, revising_replica
) -> None:
    """The declined rows follow as their own entries; the Leave moves none."""
    rows_before = {
        actor: _rows(datalayer, actor)
        for actor in (MANAGER_ACTOR_ID, OWNER_ACTOR_ID, PARTICIPANT_ACTOR_ID)
    }
    register_before = _register(datalayer)

    result, node = _run(bridge, _leave_entry())

    assert result.status == Status.SUCCESS
    assert "follows as its own entry" in node.feedback_message
    assert {
        actor: _rows(datalayer, actor) for actor in rows_before
    } == rows_before
    assert _register(datalayer) == register_before


@pytest.mark.spec("MSM-07-010")
@pytest.mark.spec("SYNC-12-001")
def test_a_repeat_of_the_leave_is_a_no_op(
    datalayer, bridge, revising_replica
) -> None:
    _run(bridge, _leave_entry())

    result, _ = _run(bridge, _leave_entry())

    assert result.status == Status.SUCCESS
    assert _rows(datalayer, PARTICIPANT_ACTOR_ID)[ACTIVE_EMBARGO_ID] == (
        "AGREED"
    )


@pytest.mark.spec("EMB-18-003")
def test_a_replica_missing_the_embargo_stores_it_from_the_leave(
    datalayer, bridge, revising_replica
) -> None:
    """The entry carries the embargo inline, so the replica stores it."""
    assert datalayer.delete("EmbargoEvent", ACTIVE_EMBARGO_ID)
    assert datalayer.read(ACTIVE_EMBARGO_ID) is None

    result, _ = _run(bridge, _leave_entry())

    assert result.status == Status.SUCCESS
    stored = datalayer.read(ACTIVE_EMBARGO_ID)
    assert isinstance(stored, EmbargoEvent)


@pytest.mark.spec("EP-09-007")
def test_a_leave_naming_no_embargo_fails(
    datalayer, bridge, revising_replica
) -> None:
    entry = _leave_entry()
    entry.payload_snapshot.pop("object")

    result, node = _run(bridge, entry)

    assert result.status == Status.FAILURE
    assert "names no embargo" in node.feedback_message


@pytest.mark.spec("MSM-07-010")
def test_a_replica_without_the_case_skips_the_entry(datalayer, bridge) -> None:
    """Regime 2 (ADR-0087): a replica with no copy of the case skips it."""
    result, _ = _run(bridge, _leave_entry())

    assert result.status == Status.SUCCESS
