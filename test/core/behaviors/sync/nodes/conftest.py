#!/usr/bin/env python
"""Shared fixtures for sync node tests."""

from typing import cast

import pytest

from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.actor import VultronService
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

OWNER_ACTOR_ID = "https://example.org/actors/vendor"
PARTICIPANT_ACTOR_ID = "https://example.org/actors/reporter"
CASE_ID = "https://example.org/cases/case-sync"

_ZERO_HASH: str = "0" * 64  # arbitrary prev_log_hash for test chains


@pytest.fixture
def datalayer():
    """The participant's own replica store (ADR-0073).

    These effect nodes apply an announced ledger entry to the replica of the
    actor executing them, and that actor is PARTICIPANT_ACTOR_ID for every file
    in this package except ``test_conditions.py``, which runs as the owner and
    shadows this fixture with its own store.  ``actor_id=case_actor.id_``
    elsewhere in these files is the *event's* author, not the executing actor.
    """
    return SqliteDataLayer("sqlite:///:memory:", actor_id=PARTICIPANT_ACTOR_ID)


@pytest.fixture
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def case_obj(datalayer):
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    datalayer.save(case)
    return case


@pytest.fixture
def case_actor(datalayer):
    actor = VultronService(
        name="Case Actor",
        attributed_to=OWNER_ACTOR_ID,
        context=CASE_ID,
    )
    datalayer.create(actor)
    return actor


def _make_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/log-{log_index}",
            semantic_type="test_event",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev_hash,
        )
    )


def _make_event(
    entry: CaseLedgerEntry, actor_id: str, to: list[str] | None = None
) -> AnnounceLogEntryReceivedEvent:
    """The CaseActor's ``Announce(CaseLedgerEntry)`` of *entry*, extracted.

    Pass *to* when the event runs a whole received tree, whose addressee door
    guard refuses a copy that does not name the replica (HP-01-005).
    """
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = announce_log_entry_activity(
        entry=wire_entry, actor=actor_id, **({"to": to} if to else {})
    )
    return cast(AnnounceLogEntryReceivedEvent, received_event(activity))
