#!/usr/bin/env python
"""Regression tests for ISSUE-2193: VulnerabilityReport replicated to new
case participants after ownership transfer.

After ownership transfers, a newly-owning or newly-invited participant may
join a case whose VulnerabilityReport was added *before* they appeared.
Their DataLayer is seeded purely via the case-ledger sync stream — there is
no prior ``Announce(VulnerabilityCase)`` carrying an embedded report object.

The detectable signal: when ``ApplyOfferReportFromLedgerNode`` processes the
historical ``add_report_to_case`` ledger entry it MUST store the
``VulnerabilityReport`` object so that ``SvcValidateReportUseCase`` can find it
without a 404.

The #2180 fix inside ``ApplyOfferReportFromLedgerNode`` (``a5cb0e24``)
performs exactly this reconstruction from the ledger snapshot.  These tests
confirm that fix covers the post-ownership-transfer path.
"""

import uuid
from datetime import UTC, datetime

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    _make_event,
    _to_persistable_entry,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_ledger import (
    HashChainLedgerRecord,
    compute_genesis_hash,
)
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_case_link import VultronReportCaseLink

_FIXED_CREATED_AT = datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)

ORIGINAL_CASE_ACTOR_ID = "https://example.org/actors/original-vendor"
NEW_OWNER_ACTOR_ID = "https://example.org/actors/new-owner-coordinator"
REPORTER_ACTOR_ID = "https://example.org/actors/finder"
CASE_ID = "https://example.org/cases/transfer-2193"
REPORT_ID = f"urn:uuid:{uuid.uuid4()}"
OFFER_ID = f"urn:uuid:{uuid.uuid4()}"

CASE_GENESIS_HASH = compute_genesis_hash(
    CASE_ID, _FIXED_CREATED_AT, ORIGINAL_CASE_ACTOR_ID
)


@pytest.fixture
def dl():
    datalayer = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=NEW_OWNER_ACTOR_ID,
    )
    yield datalayer
    datalayer.close()


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def new_owner_case_actor(dl):
    actor = CaseActor(
        name="New Owner",
        attributed_to=NEW_OWNER_ACTOR_ID,
        context=CASE_ID,
    )
    dl.create(actor)
    return actor


def _make_add_report_snapshot() -> dict:
    """Build a payload_snapshot for an add_report_to_case ledger entry.

    Mirrors build_add_report_to_case_snapshot: type=Add, object={full report},
    actor=original-case-actor, offerId, offerActorId=reporter.
    """
    return {
        "type": "Add",
        "actor": ORIGINAL_CASE_ACTOR_ID,
        "context": CASE_ID,
        "offerId": OFFER_ID,
        "offerActorId": REPORTER_ACTOR_ID,
        "object": {
            "id": REPORT_ID,
            "type": "VulnerabilityReport",
            "name": "Critical RCE in network stack",
            "content": "Remote code execution vulnerability discovered.",
            "attributedTo": REPORTER_ACTOR_ID,
        },
        "target": {
            "id": CASE_ID,
            "type": "VulnerabilityCase",
        },
    }


def _make_add_report_ledger_entry():
    snapshot = _make_add_report_snapshot()
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=2,
            object_id=REPORT_ID,
            event_type="add_report_to_case",
            payload_snapshot=snapshot,
            prev_log_hash=CASE_GENESIS_HASH,
        )
    )


class TestReportReplicatedToPostTransferParticipant:
    """ISSUE-2193: VulnerabilityReport reaches new participant via ledger sync.

    A new participant who joined after ownership transfer never received
    ``Announce(VulnerabilityCase)`` carrying an embedded report — the ledger
    snapshot is their only source.  ``ApplyOfferReportFromLedgerNode`` must
    reconstruct and store the ``VulnerabilityReport``.
    """

    def test_report_stored_from_add_report_to_case_ledger_entry(
        self, bridge, dl, new_owner_case_actor
    ) -> None:
        """VulnerabilityReport is stored when new owner processes historical ledger.

        Regression for ISSUE-2193: the new case participant has no prior report
        object (never received an embedded Announce); it receives only the
        historical add_report_to_case ledger snapshot.  After
        ApplyOfferReportFromLedgerNode processes that entry the report MUST be
        readable from the DataLayer.
        """
        from vultron.core.behaviors.sync.nodes.offer_report_effect import (
            ApplyOfferReportFromLedgerNode,
        )

        # Pre-condition: new participant's DataLayer is empty — no prior report.
        assert dl.read(REPORT_ID) is None

        entry = _make_add_report_ledger_entry()
        event = _make_event(entry, actor_id=new_owner_case_actor.id_)

        result = bridge.execute_with_setup(
            tree=ApplyOfferReportFromLedgerNode(
                name="ApplyOfferReportFromLedger"
            ),
            actor_id=NEW_OWNER_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.SUCCESS

        stored_report = dl.read(REPORT_ID)
        assert stored_report is not None, (
            "VulnerabilityReport MUST be stored by ApplyOfferReportFromLedgerNode "
            "when a post-ownership-transfer participant processes the historical "
            "add_report_to_case ledger entry — otherwise the report is missing "
            "(ISSUE-2193, fixed by #2180 / a5cb0e24)"
        )
        assert isinstance(stored_report, VulnerabilityReport)
        assert stored_report.id_ == REPORT_ID

    def test_no_offer_record_or_report_link_for_post_transfer_participant(
        self, bridge, dl, new_owner_case_actor
    ) -> None:
        """No OfferRecord or report link is created for a joined participant.

        The participant was never sent the reporter's Offer, so it holds no
        record of it and cannot answer it (CM-11-020, ADR-0121).
        """
        from vultron.core.behaviors.sync.nodes.offer_report_effect import (
            ApplyOfferReportFromLedgerNode,
        )

        entry = _make_add_report_ledger_entry()
        event = _make_event(entry, actor_id=new_owner_case_actor.id_)

        result = bridge.execute_with_setup(
            tree=ApplyOfferReportFromLedgerNode(
                name="ApplyOfferReportFromLedger"
            ),
            actor_id=NEW_OWNER_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.SUCCESS
        assert dl.read(VultronOfferRecord.build_id(OFFER_ID)) is None
        assert dl.read(VultronReportCaseLink.build_id(REPORT_ID)) is None

    def test_idempotent_on_repeated_ledger_replay(
        self, bridge, dl, new_owner_case_actor
    ) -> None:
        """Repeated processing of the same ledger entry does not raise."""
        from vultron.core.behaviors.sync.nodes.offer_report_effect import (
            ApplyOfferReportFromLedgerNode,
        )

        entry = _make_add_report_ledger_entry()
        event = _make_event(entry, actor_id=new_owner_case_actor.id_)

        for _ in range(2):
            result = bridge.execute_with_setup(
                tree=ApplyOfferReportFromLedgerNode(
                    name="ApplyOfferReportFromLedger"
                ),
                actor_id=NEW_OWNER_ACTOR_ID,
                activity=event,
            )
            assert result.status == Status.SUCCESS

        assert dl.read(REPORT_ID) is not None
        assert dl.list_objects("OfferRecord") == []
