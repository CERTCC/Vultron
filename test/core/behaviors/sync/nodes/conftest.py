#!/usr/bin/env python
"""Shared fixtures for sync node tests."""

from typing import cast

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

OWNER_ACTOR_ID = "https://example.org/actors/vendor"
PARTICIPANT_ACTOR_ID = "https://example.org/actors/reporter"
CASE_ID = "https://example.org/cases/case-sync"

_ZERO_HASH: str = "0" * 64  # arbitrary prev_log_hash for test chains


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def datalayer():
    return SqliteDataLayer("sqlite:///:memory:")


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
    actor = VultronCaseActor(
        name="Case Actor",
        attributed_to=OWNER_ACTOR_ID,
        context=CASE_ID,
    )
    datalayer.create(actor)
    return actor


def _make_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> VultronCaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/log-{log_index}",
            event_type="test_event",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev_hash,
        )
    )


def _make_event(
    entry: VultronCaseLedgerEntry, actor_id: str
) -> AnnounceLogEntryReceivedEvent:
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = announce_log_entry_activity(entry=wire_entry, actor=actor_id)
    return cast(AnnounceLogEntryReceivedEvent, extract_event(activity))
