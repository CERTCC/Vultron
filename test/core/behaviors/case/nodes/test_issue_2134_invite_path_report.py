#!/usr/bin/env python
"""Regression tests for ISSUE-2134: invite-path RM triage without spoofing.

These tests verify that an invited actor can perform report validation after
receiving Announce(VulnerabilityCase) with embedded VulnerabilityReport objects
and the Offer(VulnerabilityReport) ledger backfill — WITHOUT requiring the
seed_offer_record_for_actor spoof endpoint.

Three failing conditions are tested:

1. SeedAnnouncedCaseNode stores embedded VulnerabilityReport objects (CBT-01-007).
2. ApplyOfferReportFromLedgerNode creates a VultronOfferRecord from an
   Offer(VulnerabilityReport) ledger entry (via the canonical ledger backfill).
3. (Integration) After both fixes, dl.read(VultronOfferRecord.build_id(offer_id))
   is not None for the invited actor — prerequisite for validate-report.
"""

import uuid
from datetime import datetime, timezone
from typing import cast

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    _make_event,
    _to_persistable_entry,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.announce import SeedAnnouncedCaseNode
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger import (
    HashChainLedgerRecord,
    compute_genesis_hash,
)
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import announce_vulnerability_case_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_FIXED_CREATED_AT = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

CASE_OWNER_ACTOR_ID = "https://example.org/actors/case-owner"
INVITED_ACTOR_ID = "https://example.org/actors/invited-vendor"
REPORTER_ACTOR_ID = "https://example.org/actors/reporter"
CASE_ID = "https://example.org/cases/invite-path-2134"
REPORT_ID = f"urn:uuid:{uuid.uuid4()}"
OFFER_ID = f"urn:uuid:{uuid.uuid4()}"

CASE_GENESIS_HASH = compute_genesis_hash(
    CASE_ID, _FIXED_CREATED_AT, CASE_OWNER_ACTOR_ID
)


@pytest.fixture
def invited_dl():
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=INVITED_ACTOR_ID,
    )
    yield dl
    dl.close()


@pytest.fixture
def invited_bridge(invited_dl):
    return BTBridge(datalayer=invited_dl)


def _make_wire_report() -> as_VulnerabilityReport:
    return as_VulnerabilityReport(
        id_=REPORT_ID,
        attributed_to=REPORTER_ACTOR_ID,
        content="Test vulnerability report",
    )


def _make_wire_case_with_embedded_report() -> as_VulnerabilityCase:
    """Return as_VulnerabilityCase with full embedded as_VulnerabilityReport (CBT-01-007)."""
    wire_report = _make_wire_report()
    return as_VulnerabilityCase(
        id_=CASE_ID,
        name="Invite Path Test Case",
        attributed_to=CASE_OWNER_ACTOR_ID,
        vulnerability_reports=[wire_report],
    )


def _make_announce_event(
    case_obj: as_VulnerabilityCase,
) -> AnnounceVulnerabilityCaseReceivedEvent:
    activity = announce_vulnerability_case_activity(
        case_obj, actor=CASE_OWNER_ACTOR_ID, context=CASE_ID
    )
    event = extract_event(activity)
    assert event.semantic_type == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
    return cast(AnnounceVulnerabilityCaseReceivedEvent, event)


def _make_offer_report_snapshot() -> dict:
    """Build a payload_snapshot for an add_report_to_case ledger entry.

    Mirrors what build_add_report_to_case_snapshot produces when offer_id is
    known: type=Add, object={id=REPORT_ID, type=VulnerabilityReport},
    actor=case-owner, offerId=OFFER_ID, offerActorId=REPORTER_ACTOR_ID.
    """
    return {
        "type": "Add",
        "actor": CASE_OWNER_ACTOR_ID,
        "context": CASE_ID,
        "offerId": OFFER_ID,
        "offerActorId": REPORTER_ACTOR_ID,
        "object": {
            "id": REPORT_ID,
            "type": "VulnerabilityReport",
            "content": "Test vulnerability report",
            "attributedTo": REPORTER_ACTOR_ID,
        },
        "target": {
            "id": CASE_ID,
            "type": "VulnerabilityCase",
        },
    }


def _make_offer_report_ledger_entry():
    """Build a VultronCaseLedgerEntry for an add_report_to_case canonical event."""
    snapshot = _make_offer_report_snapshot()
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=1,
            object_id=REPORT_ID,
            event_type="add_report_to_case",
            payload_snapshot=snapshot,
            prev_log_hash=CASE_GENESIS_HASH,
        )
    )


# ---------------------------------------------------------------------------
# Test 1: SeedAnnouncedCaseNode must store embedded VulnerabilityReport objects
# ---------------------------------------------------------------------------


class TestSeedAnnouncedCaseNodeStoresEmbeddedReports:
    """CBT-01-007: SeedAnnouncedCaseNode must store embedded VulnerabilityReport objects.

    When Announce(VulnerabilityCase) carries full VulnerabilityReport objects
    (not bare ID strings), SeedAnnouncedCaseNode must persist each embedded
    report so that invited actors have the report object available locally.

    This test FAILS before the fix (SeedAnnouncedCaseNode does not iterate
    vulnerability_reports) and PASSES after.
    """

    def test_stores_embedded_vulnerability_report(
        self, invited_bridge, invited_dl
    ) -> None:
        """Embedded VulnerabilityReport is saved to DataLayer during case seeding."""
        assert invited_dl.read(REPORT_ID) is None

        case_with_embedded_report = _make_wire_case_with_embedded_report()
        # Verify the case actually carries a full object, not a bare string.
        assert len(case_with_embedded_report.vulnerability_reports) == 1
        assert isinstance(
            case_with_embedded_report.vulnerability_reports[0],
            as_VulnerabilityReport,
        )

        announce_event = _make_announce_event(case_with_embedded_report)
        # Production path: pass the wire object directly (not to_core() —
        # to_core() collapses reports to string IDs, losing embedded objects).
        # AnnounceVulnerabilityCaseReceivedUseCase.execute() passes the wire
        # case_obj unchanged to SeedAnnouncedCaseNode.
        tree = SeedAnnouncedCaseNode(
            case_id=CASE_ID,
            case_obj=case_with_embedded_report,
            request=announce_event,
        )
        result = invited_bridge.execute_with_setup(
            tree=tree, actor_id=INVITED_ACTOR_ID, activity=announce_event
        )

        assert result.status == Status.SUCCESS
        # The report must be saved in the invited actor's DataLayer.
        stored_report = invited_dl.read(REPORT_ID)
        assert stored_report is not None, (
            "SeedAnnouncedCaseNode must store embedded VulnerabilityReport "
            "objects from Announce(VulnerabilityCase) (CBT-01-007, ISSUE-2134)"
        )

    def test_idempotent_when_report_already_present(
        self, invited_bridge, invited_dl
    ) -> None:
        """SUCCESS without error when embedded report is already in DataLayer."""
        existing_report = VulnerabilityReport(
            id_=REPORT_ID,
            attributed_to=REPORTER_ACTOR_ID,
        )
        invited_dl.save(existing_report)

        case_with_embedded_report = _make_wire_case_with_embedded_report()
        announce_event = _make_announce_event(case_with_embedded_report)

        tree = SeedAnnouncedCaseNode(
            case_id=CASE_ID,
            case_obj=case_with_embedded_report,
            request=announce_event,
        )
        result = invited_bridge.execute_with_setup(
            tree=tree, actor_id=INVITED_ACTOR_ID, activity=announce_event
        )

        assert result.status == Status.SUCCESS
        # Report still readable — no double-write clobber.
        assert invited_dl.read(REPORT_ID) is not None


# ---------------------------------------------------------------------------
# Test 2: ApplyOfferReportFromLedgerNode must create VultronOfferRecord
# ---------------------------------------------------------------------------


class TestApplyOfferReportFromLedgerNode:
    """ApplyOfferReportFromLedgerNode creates VultronOfferRecord from ledger entry.

    When an invited actor receives the canonical Offer(VulnerabilityReport)
    ledger entry (backfilled as part of invite/sync flow), a VultronOfferRecord
    keyed by VultronOfferRecord.build_id(offer_id) MUST be created in the
    DataLayer.

    This test FAILS before the fix (no ApplyOfferReportFromLedgerNode exists)
    and PASSES after.
    """

    @pytest.fixture
    def datalayer(self):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=INVITED_ACTOR_ID,
        )
        yield dl
        dl.close()

    @pytest.fixture
    def bridge(self, datalayer):
        return BTBridge(datalayer=datalayer)

    @pytest.fixture
    def case_actor(self, datalayer):
        actor = VultronCaseActor(
            name="Case Actor",
            attributed_to=CASE_OWNER_ACTOR_ID,
            context=CASE_ID,
        )
        datalayer.create(actor)
        return actor

    def test_creates_offer_record_from_ledger_entry(
        self, bridge, datalayer, case_actor
    ) -> None:
        """VultronOfferRecord is created when Offer(VulnerabilityReport) entry arrives."""
        offer_record_id = VultronOfferRecord.build_id(OFFER_ID)
        assert datalayer.read(offer_record_id) is None

        from vultron.core.behaviors.sync.nodes.offer_report_effect import (
            ApplyOfferReportFromLedgerNode,
        )

        entry = _make_offer_report_ledger_entry()
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=ApplyOfferReportFromLedgerNode(
                name="ApplyOfferReportFromLedger"
            ),
            actor_id=INVITED_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.SUCCESS
        offer_record = datalayer.read(offer_record_id)
        assert offer_record is not None, (
            "ApplyOfferReportFromLedgerNode must create VultronOfferRecord "
            "when Offer(VulnerabilityReport) ledger entry is received "
            "(ISSUE-2134)"
        )
        assert isinstance(offer_record, VultronOfferRecord)
        assert offer_record.offer_id == OFFER_ID
        assert offer_record.report_id == REPORT_ID
        assert offer_record.offer_actor_id == REPORTER_ACTOR_ID

    def test_stores_report_object_from_ledger_snapshot_when_absent(
        self, bridge, datalayer, case_actor
    ) -> None:
        """The full report object is reconstructed from the ledger snapshot.

        Regression for #2180: when the report is added to the case *after* the
        case was announced to an invited participant, the Announce(VulnerabilityCase)
        carried no embedded report (CBT-01-007 path is empty), so the report
        object only ever reaches the participant inside the add_report_to_case
        ledger snapshot.  ApplyOfferReportFromLedgerNode must therefore store the
        report object too — otherwise _reconstitute_offer 404s on the report
        lookup even though the offer record exists.
        """
        from vultron.core.behaviors.sync.nodes.offer_report_effect import (
            ApplyOfferReportFromLedgerNode,
        )

        # The report object was never seeded (no embedded report in a prior
        # case announce) — the ledger snapshot is the only source.
        assert datalayer.read(REPORT_ID) is None

        entry = _make_offer_report_ledger_entry()
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=ApplyOfferReportFromLedgerNode(
                name="ApplyOfferReportFromLedger"
            ),
            actor_id=INVITED_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.SUCCESS
        stored_report = datalayer.read(REPORT_ID)
        assert stored_report is not None, (
            "ApplyOfferReportFromLedgerNode must store the VulnerabilityReport "
            "reconstructed from the add_report_to_case ledger snapshot when the "
            "report was not previously seeded (#2180)"
        )
        assert isinstance(stored_report, VulnerabilityReport)
        assert stored_report.id_ == REPORT_ID

    def test_idempotent_when_offer_record_already_exists(
        self, bridge, datalayer, case_actor
    ) -> None:
        """SUCCESS without overwrite when VultronOfferRecord already present."""
        from vultron.core.behaviors.sync.nodes.offer_report_effect import (
            ApplyOfferReportFromLedgerNode,
        )

        existing = VultronOfferRecord(
            offer_id=OFFER_ID,
            report_id=REPORT_ID,
            offer_actor_id=REPORTER_ACTOR_ID,
        )
        datalayer.save(existing)

        entry = _make_offer_report_ledger_entry()
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=ApplyOfferReportFromLedgerNode(
                name="ApplyOfferReportFromLedger"
            ),
            actor_id=INVITED_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.SUCCESS

    def test_skips_non_offer_report_entries(
        self, bridge, datalayer, case_actor
    ) -> None:
        """Node returns SUCCESS without creating any record for non-offer entries."""
        from vultron.core.behaviors.sync.nodes.offer_report_effect import (
            ApplyOfferReportFromLedgerNode,
        )

        # Use an invite_actor_to_case entry, not an offer entry.
        non_offer_entry = _to_persistable_entry(
            HashChainLedgerRecord(
                case_id=CASE_ID,
                log_index=2,
                object_id="https://example.org/activities/invite-01",
                event_type="invite_actor_to_case",
                payload_snapshot={
                    "type": "Invite",
                    "id": "https://example.org/activities/invite-01",
                    "actor": CASE_OWNER_ACTOR_ID,
                    "context": CASE_ID,
                    "object": {
                        "id": INVITED_ACTOR_ID,
                        "type": "Organization",
                    },
                    "target": {
                        "id": CASE_ID,
                        "type": "VulnerabilityCase",
                    },
                },
                prev_log_hash=CASE_GENESIS_HASH,
            )
        )
        event = _make_event(non_offer_entry, actor_id=case_actor.id_)

        # No offer record should be created for invite events.
        offer_record_id = VultronOfferRecord.build_id(
            "https://example.org/activities/invite-01"
        )
        assert datalayer.read(offer_record_id) is None

        result = bridge.execute_with_setup(
            tree=ApplyOfferReportFromLedgerNode(
                name="ApplyOfferReportFromLedger"
            ),
            actor_id=INVITED_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.SUCCESS
        assert datalayer.read(offer_record_id) is None


# ---------------------------------------------------------------------------
# Test 3: Integration — offer record available for validate-report
# ---------------------------------------------------------------------------


class TestInvitePathReportAvailableWithoutSpoof:
    """Integration: after both fixes, invited actor can validate report.

    After receiving:
      - Announce(VulnerabilityCase) with embedded VulnerabilityReport
      - Offer(VulnerabilityReport) ledger backfill entry

    The invited actor's DataLayer must contain:
      - VulnerabilityReport object
      - VultronOfferRecord keyed by VultronOfferRecord.build_id(offer_id)

    These are the prerequisites for SvcValidateReportUseCase without spoofing.
    """

    @pytest.fixture
    def datalayer(self):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=INVITED_ACTOR_ID,
        )
        yield dl
        dl.close()

    @pytest.fixture
    def bridge(self, datalayer):
        return BTBridge(datalayer=datalayer)

    @pytest.fixture
    def case_actor(self, datalayer):
        actor = VultronCaseActor(
            name="Case Actor",
            attributed_to=CASE_OWNER_ACTOR_ID,
            context=CASE_ID,
        )
        datalayer.create(actor)
        return actor

    def test_report_and_offer_record_available_after_announce_and_backfill(
        self, bridge, datalayer, case_actor
    ) -> None:
        """Both VulnerabilityReport and VultronOfferRecord available without spoofing."""
        from vultron.core.behaviors.sync.nodes.offer_report_effect import (
            ApplyOfferReportFromLedgerNode,
        )

        # Step 1: invited actor receives Announce(VulnerabilityCase) with
        # embedded VulnerabilityReport.
        case_with_report = _make_wire_case_with_embedded_report()
        announce_event = _make_announce_event(case_with_report)

        seed_tree = SeedAnnouncedCaseNode(
            case_id=CASE_ID,
            case_obj=case_with_report,
            request=announce_event,
        )
        seed_result = bridge.execute_with_setup(
            tree=seed_tree,
            actor_id=INVITED_ACTOR_ID,
            activity=announce_event,
        )
        assert seed_result.status == Status.SUCCESS

        # Step 2: invited actor receives the Offer(VulnerabilityReport)
        # canonical ledger backfill entry.
        offer_entry = _make_offer_report_ledger_entry()
        offer_event = _make_event(offer_entry, actor_id=case_actor.id_)

        apply_result = bridge.execute_with_setup(
            tree=ApplyOfferReportFromLedgerNode(
                name="ApplyOfferReportFromLedger"
            ),
            actor_id=INVITED_ACTOR_ID,
            activity=offer_event,
        )
        assert apply_result.status == Status.SUCCESS

        # Both prerequisites for validate-report must now be satisfied.
        stored_report = datalayer.read(REPORT_ID)
        assert stored_report is not None, (
            "VulnerabilityReport must be in invited actor's DataLayer "
            "after Announce(VulnerabilityCase) with embedded report (ISSUE-2134)"
        )

        offer_record_id = VultronOfferRecord.build_id(OFFER_ID)
        offer_record = datalayer.read(offer_record_id)
        assert offer_record is not None, (
            "VultronOfferRecord must be in invited actor's DataLayer "
            "after Offer(VulnerabilityReport) ledger backfill (ISSUE-2134)"
        )
        assert isinstance(offer_record, VultronOfferRecord)
        assert offer_record.offer_id == OFFER_ID
        assert offer_record.report_id == REPORT_ID
