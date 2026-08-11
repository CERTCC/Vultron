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
from datetime import datetime, timezone

import pytest

from test.core.behaviors.sync.nodes.conftest import (
    _make_event,
    _to_persistable_entry,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger import (
    HashChainLedgerRecord,
    compute_genesis_hash,
)
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport

_FIXED_CREATED_AT = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

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
    datalayer = SqliteDataLayer("sqlite:///:memory:")
    yield datalayer
    datalayer.close()


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def new_owner_case_actor(dl):
    actor = VultronCaseActor(
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
    reconstruct and store the ``VulnerabilityReport`` so that validate-report
    does not 404.
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

        assert result.status is not None

        stored_report = dl.read(REPORT_ID)
        assert stored_report is not None, (
            "VulnerabilityReport MUST be stored by ApplyOfferReportFromLedgerNode "
            "when a post-ownership-transfer participant processes the historical "
            "add_report_to_case ledger entry — otherwise validate-report 404s "
            "(ISSUE-2193, fixed by #2180 / a5cb0e24)"
        )
        assert isinstance(stored_report, VulnerabilityReport)
        assert stored_report.id_ == REPORT_ID

    def test_offer_record_created_for_post_transfer_participant(
        self, bridge, dl, new_owner_case_actor
    ) -> None:
        """VultronOfferRecord is created so validate-report can find the offer.

        The offer record keyed by VultronOfferRecord.build_id(offer_id) must
        exist in the new participant's DataLayer after ledger processing.
        """
        from vultron.core.behaviors.sync.nodes.offer_report_effect import (
            ApplyOfferReportFromLedgerNode,
        )

        offer_record_id = VultronOfferRecord.build_id(OFFER_ID)
        assert dl.read(offer_record_id) is None

        entry = _make_add_report_ledger_entry()
        event = _make_event(entry, actor_id=new_owner_case_actor.id_)

        result = bridge.execute_with_setup(
            tree=ApplyOfferReportFromLedgerNode(
                name="ApplyOfferReportFromLedger"
            ),
            actor_id=NEW_OWNER_ACTOR_ID,
            activity=event,
        )

        assert result.status is not None

        offer_record = dl.read(offer_record_id)
        assert offer_record is not None, (
            "VultronOfferRecord must be created for the post-transfer participant "
            "when add_report_to_case ledger entry is processed (ISSUE-2193)"
        )
        assert isinstance(offer_record, VultronOfferRecord)
        assert offer_record.offer_id == OFFER_ID
        assert offer_record.report_id == REPORT_ID
        assert offer_record.offer_actor_id == REPORTER_ACTOR_ID

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
            assert result.status is not None

        assert dl.read(REPORT_ID) is not None
        assert dl.read(VultronOfferRecord.build_id(OFFER_ID)) is not None
