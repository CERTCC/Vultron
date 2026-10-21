#!/usr/bin/env python
r"""End-to-end: a held ledger Announce converges through the inbox replay.

A held ``Announce(CaseLedgerEntry)`` that a commit or a case seed makes
appliable is replayed as its own delivery (SYNC-14-009, ADR-0135).  These
tests drive the real chain: ``run_inbox_pipeline``, the FastAPI ingress and
dispatch adapters, the real dispatcher and port factories, the received use
cases and the ``InboxReplayAdapter``.  The only thing they assert about the
mechanism is what reaches the store: every entry in the chain, and an
archive that holds exactly the ``Announce``\ s that were delivered, each
once, as they arrived, and nothing nobody sent.
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from test.support.case_manager import add_case_manager_participant
from test.support.received import delivered_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import (
    ledger_entry_to_wire,
)
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    run_inbox_pipeline,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.core.services.held_ledger_announces import held_ledger_announces
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    announce_log_entry_activity,
    announce_vulnerability_case_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

pytestmark = pytest.mark.integration

_CASE_MANAGER = "https://example.org/actors/case-manager-rp"
_RECEIVER = "https://example.org/actors/receiver-rp"
_CASE_ID = "https://example.org/cases/case-replay"


@pytest.fixture(autouse=True)
def clear_actor_locks():
    from vultron.adapters.driving.fastapi import inbox_orchestration

    inbox_orchestration._actor_inbox_locks.clear()
    yield
    inbox_orchestration._actor_inbox_locks.clear()


@pytest.fixture
def dl():
    """The receiving replica's own store (ADR-0073)."""
    db = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    yield db
    db.close()


@pytest.fixture
def dispatcher() -> ActivityDispatcher:
    """The production dispatcher, with the production port factories."""
    return make_dispatcher()


def _case() -> VulnerabilityCase:
    return VulnerabilityCase(id_=_CASE_ID, attributed_to=_CASE_MANAGER)


def _chain(genesis_hash: str, length: int) -> list[CaseLedgerEntry]:
    entries: list[CaseLedgerEntry] = []
    prev = genesis_hash
    for index in range(length):
        record = HashChainLedgerRecord(
            case_id=_CASE_ID,
            log_index=index,
            object_id=f"https://example.org/activities/rp-{index}",
            semantic_type="test_event",
            payload_snapshot={"index": index},
            prev_log_hash=prev,
        )
        entry = _to_persistable_entry(record)
        entries.append(entry)
        prev = entry.entry_hash
    return entries


def _body(activity: as_Activity) -> dict[str, Any]:
    return delivered_body(activity)


def _announce_entry(entry: CaseLedgerEntry) -> dict[str, Any]:
    """The CASE_MANAGER's fan-out of *entry* to the receiver."""
    return _body(
        announce_log_entry_activity(
            ledger_entry_to_wire(entry), actor=_CASE_MANAGER, to=[_RECEIVER]
        )
    )


def _deliver(
    dl: SqliteDataLayer,
    dispatcher: ActivityDispatcher,
    body: dict[str, Any],
) -> None:
    """Run one inbound POST's background task to completion."""
    asyncio.run(
        run_inbox_pipeline(body, dl, _RECEIVER, dispatcher, AsyncMock())
    )


def _stored(dl: SqliteDataLayer, entries: list[CaseLedgerEntry]) -> list[bool]:
    return [dl.read(entry.id_) is not None for entry in entries]


def _assert_archive_is_what_was_delivered(
    dl: SqliteDataLayer, delivered: list[dict[str, Any]]
) -> None:
    """Intake archived each delivered body once, as it arrived, and nothing
    else: no record of an Announce nobody sent (CLP-10-017, VM-08-002)."""
    archived = {
        record.activity_id: record.received_body
        for record in dl.list_objects("ReceivedActivityRecord")
        if isinstance(record, ReceivedActivityRecord)
    }
    expected = {
        body["id"]: parse_activity(body).received_evidence_json
        for body in delivered
    }
    assert archived == expected
    # Every held body was consumed by its replay (IO-03-004).
    assert dl.list_objects("DeferredInboxActivity") == []
    assert held_ledger_announces(dl, _CASE_ID) == []


@pytest.mark.spec("SYNC-14-003")
@pytest.mark.spec("SYNC-14-008")
@pytest.mark.spec("SYNC-14-009")
@pytest.mark.spec("CLP-10-017")
def test_out_of_order_pair_converges_through_the_replay(dl, dispatcher):
    case = _case()
    add_case_manager_participant(dl, case, _CASE_MANAGER)
    e0, e1 = _chain(case.genesis_hash, 2)
    announce_e0, announce_e1 = _announce_entry(e0), _announce_entry(e1)

    # e1 arrives first: a forward gap, so its Announce is held as received
    # (SYNC-14-001).
    _deliver(dl, dispatcher, announce_e1)
    assert _stored(dl, [e0, e1]) == [False, False]
    [held] = held_ledger_announces(dl, _CASE_ID)
    assert held.activity_id == announce_e1["id"]

    # e0 closes the gap; its delivery replays e1's Announce, and the same
    # inbox loop then runs it as a delivery of its own.
    _deliver(dl, dispatcher, announce_e0)

    assert _stored(dl, [e0, e1]) == [True, True]
    assert dl.inbox_list() == []
    _assert_archive_is_what_was_delivered(dl, [announce_e1, announce_e0])


@pytest.mark.spec("SYNC-15-005")
@pytest.mark.spec("SYNC-14-009")
@pytest.mark.spec("CLP-10-017")
def test_pre_genesis_entries_converge_through_the_replay(dl, dispatcher):
    # The CASE_MANAGER's case embeds its own participant record, as every
    # seeded replica does (CP-09-004); the entries chain from its genesis.
    manager = CaseParticipant(
        attributed_to=_CASE_MANAGER,
        context=_CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case = VulnerabilityCase(
        id_=_CASE_ID,
        attributed_to=_CASE_MANAGER,
        case_participants=[manager],
        actor_participant_index={_CASE_MANAGER: manager.id_},
    )
    entries = _chain(case.genesis_hash, 2)
    # The receiver was invited by the CASE_MANAGER, so it trusts that
    # actor's case Announce before it holds the case (PCR-03-004).
    dl.save(
        VultronPendingCaseInbox(
            case_id=_CASE_ID, case_actor_id=_CASE_MANAGER, invite_anchored=True
        )
    )

    # Both entries arrive before the case is seeded (SYNC-15-004).
    announces = [_announce_entry(entry) for entry in entries]
    for body in announces:
        _deliver(dl, dispatcher, body)
    assert _stored(dl, entries) == [False, False]
    assert len(held_ledger_announces(dl, _CASE_ID)) == 2

    # The CASE_MANAGER's case Announce seeds the case; the seed replays the
    # genesis entry's Announce, whose own commit replays the next.
    seed = _body(
        announce_vulnerability_case_activity(
            case, actor=_CASE_MANAGER, to=[_RECEIVER], context=_CASE_ID
        )
    )
    _deliver(dl, dispatcher, seed)

    assert dl.read(_CASE_ID) is not None
    assert _stored(dl, entries) == [True, True]
    _assert_archive_is_what_was_delivered(dl, [*announces, seed])
