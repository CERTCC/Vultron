#!/usr/bin/env python
"""Ratchet probe for ISSUE-2193.

#2193: "VulnerabilityReport not replicated to new case participants after
ownership transfer."  After a case ownership transfer, a newly-owning /
participant actor may lack the ``VulnerabilityReport`` in its DataLayer,
producing a 404 at validate-report.

This test is an OBJECTIVE PROBE, not a spec: it models a fresh replica (the
post-ownership-transfer participant) that processes the replicated ledger
stream through the canonical ``create_announce_log_entry_tree`` — an ownership
transfer entry followed by the ``add_report_to_case`` entry — and then asserts
that ``datalayer.read(<report_id>)`` is not None on that replica.

The gap MAY already be closed by #2187's ledger-snapshot report backfill in
``ApplyOfferReportFromLedgerNode`` (offer_report_effect.py ~lines 114-143),
which reconstructs the report from the ``add_report_to_case`` snapshot.  The
``xfail(strict=True)`` marker on the key assertion resolves this objectively:

- ``xfailed``  -> the gap is real on HEAD (report NOT replicated).
- ``xpassed``  -> #2193 is already fixed by #2187 (report IS replicated).

Harness: SqliteDataLayer in-memory + BTBridge, mirroring
test_issue_2134_invite_path_report.py and test_announce_tree.py.  NO Docker.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    _make_event,
    _to_persistable_entry,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# Populate the vocabulary registry as an import side-effect.
_ = as_VulnerabilityCase

OWNER_ACTOR_ID = "https://example.org/actors/original-owner"
NEW_OWNER_ACTOR_ID = "https://example.org/actors/new-owner"
REPORTER_ACTOR_ID = "https://example.org/actors/reporter"
PARTICIPANT_ACTOR_ID = "https://example.org/actors/post-transfer-participant"
CASE_ID = "https://example.org/cases/transfer-2193"
REPORT_ID = f"urn:uuid:{uuid.uuid4()}"
OFFER_ID = f"urn:uuid:{uuid.uuid4()}"


@pytest.fixture
def datalayer():
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=PARTICIPANT_ACTOR_ID,
    )
    yield dl
    dl.close()


@pytest.fixture
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def case_actor(datalayer):
    """The CaseActor that signs the replicated Announce(CaseLedgerEntry)s."""
    actor = VultronCaseActor(
        name="Case Actor",
        attributed_to=OWNER_ACTOR_ID,
        context=CASE_ID,
    )
    datalayer.create(actor)
    return actor


@pytest.fixture
def case_replica(datalayer):
    """Seed a case replica on the post-transfer participant (genesis anchor).

    Models the freshly-seeded case state the participant holds *before* it
    replays the replicated ledger stream — the report was never seeded here.
    """
    case = as_VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    datalayer.save(case)
    return case


def _ownership_transfer_record(prev_hash: str) -> HashChainLedgerRecord:
    return HashChainLedgerRecord(
        case_id=CASE_ID,
        log_index=0,
        object_id="https://example.org/activities/ownership-0",
        event_type="accept_case_ownership_transfer",
        payload_snapshot={"actor": NEW_OWNER_ACTOR_ID},
        prev_log_hash=prev_hash,
    )


def _add_report_record(prev_hash: str) -> HashChainLedgerRecord:
    """add_report_to_case entry with the full report embedded in the snapshot.

    Mirrors build_add_report_to_case_snapshot: type=Add, embedded object with
    the VulnerabilityReport, offerId + offerActorId so the offer-record path is
    reached and the report-backfill block (#2187) can execute.
    """
    return HashChainLedgerRecord(
        case_id=CASE_ID,
        log_index=1,
        object_id=REPORT_ID,
        event_type="add_report_to_case",
        payload_snapshot={
            "type": "Add",
            "actor": NEW_OWNER_ACTOR_ID,
            "context": CASE_ID,
            "offerId": OFFER_ID,
            "offerActorId": REPORTER_ACTOR_ID,
            "object": {
                "id": REPORT_ID,
                "type": "VulnerabilityReport",
                "content": "Test vulnerability report",
                "attributedTo": REPORTER_ACTOR_ID,
            },
            "target": {"id": CASE_ID, "type": "VulnerabilityCase"},
        },
        prev_log_hash=prev_hash,
    )


# NOTE: The xfail(strict=True) probe marker for #2193 was REMOVED because this
# test XPASSED on HEAD — #2193 is already fixed by #2187's ledger-snapshot
# report backfill in ApplyOfferReportFromLedgerNode (offer_report_effect.py
# ~lines 114-143).  This now stands as a plain passing regression test guarding
# that fix; re-add the strict xfail only if the backfill is ever removed.
def test_report_replicated_to_post_transfer_participant(
    bridge, datalayer, case_actor, case_replica
):
    """Report IS present on the replica after processing the replicated stream.

    The post-transfer participant replays the canonical ledger stream:
      1. accept_case_ownership_transfer  (attributed_to -> new owner)
      2. add_report_to_case              (report backfill, #2187)
    After (2), the VulnerabilityReport MUST be readable from the replica's
    DataLayer, otherwise validate-report 404s (#2193).
    """
    tree = create_announce_log_entry_tree

    # --- Step 1: ownership transfer entry (chains from the genesis anchor).
    transfer_record = _ownership_transfer_record(case_replica.genesis_hash)
    transfer_entry = _to_persistable_entry(transfer_record)
    transfer_event = _make_event(transfer_entry, actor_id=case_actor.id_)

    transfer_result = bridge.execute_with_setup(
        tree=tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=transfer_event,
        sync_port=MagicMock(spec=SyncActivityPort),
    )
    assert transfer_result.status == Status.SUCCESS
    updated_case = datalayer.read(CASE_ID)
    assert updated_case is not None
    # Sanity: the ownership transfer applied on the replica.
    assert updated_case.attributed_to == NEW_OWNER_ACTOR_ID

    # The report was never seeded on this replica.
    assert datalayer.read(REPORT_ID) is None

    # --- Step 2: add_report_to_case entry (chains from the transfer entry).
    report_record = _add_report_record(transfer_record.entry_hash)
    report_entry = _to_persistable_entry(report_record)
    report_event = _make_event(report_entry, actor_id=case_actor.id_)

    report_result = bridge.execute_with_setup(
        tree=tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=report_event,
        sync_port=MagicMock(spec=SyncActivityPort),
    )
    assert report_result.status == Status.SUCCESS

    # KEY ASSERTION (#2193): the report must be replicated to the
    # post-transfer participant's DataLayer.
    stored_report = datalayer.read(REPORT_ID)
    assert stored_report is not None, (
        "VulnerabilityReport must be replicated to the post-ownership-transfer "
        "participant after it processes the add_report_to_case ledger entry "
        "(#2193) — otherwise validate-report 404s on the report lookup."
    )
