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

"""Unit tests for the FV (Finder + Vendor) multi-container demo (D5-1-G5).

Uses a single TestClient (one FastAPI app instance) to simulate two containers.
Both DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.  This validates the
demo script logic while tolerating the single-process constraint of unit tests.

True multi-container isolation is validated by the acceptance test runnable via:
    docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
import logging
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fv_demo as demo
from test.demo._helpers import make_client, make_testclient_call
from vultron.adapters.utils import strip_id_prefix
from vultron.demo.cli import main
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    """Return the base URL for the single TestClient, matching /api/v2 prefix."""
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture(scope="module", autouse=True)
def configure_vendor_default_roles():
    """Set VULTRON_ACTOR__DEFAULT_CASE_ROLES=["vendor"] for this module.

    In Docker the vendor container is started with this env var so the case
    owner participant gets CVDRole.VENDOR alongside CVDRole.CASE_OWNER.
    TestClient doesn't inherit Docker env vars, so we replicate the setting
    here (mirrors docker/docker-compose-multi-actor.yml vendor service config).
    """
    from vultron.config.app import reload_config

    mp = MonkeyPatch()
    try:
        mp.setenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", '["vendor"]')
        reload_config()
        yield
    finally:
        mp.undo()
        reload_config()


@pytest.fixture(scope="module", autouse=True)
def patch_datalayer_call(client: TestClient, base: str):
    """Patch DataLayerClient.call at the class level for all tests in this module.

    Uses the same pattern as test_receive_report_demo.py: monkeypatch the class
    method so all instances (finder and vendor clients) route through the single
    TestClient.  Module-scoped so the patch is applied once and torn down after
    all tests complete.
    """
    mp = MonkeyPatch()
    try:
        mp.setattr(
            demo.DataLayerClient, "call", make_testclient_call(client, base)
        )
        yield
    finally:
        mp.undo()
        importlib.reload(demo)


# ---------------------------------------------------------------------------
# ADR-0041 test helpers
# ---------------------------------------------------------------------------


def _extract_offer_ids(
    client: "demo.DataLayerClient", offer: as_Offer
) -> tuple[str | None, str | None]:
    """Return (report_id, reporter_id) extracted from *offer*'s raw data."""
    offer_data = client.get(f"/datalayer/{offer.id_}")
    if not offer_data:
        return None, None
    report_id = None
    reporter_id = None
    obj_ = offer_data.get("object_") or offer_data.get("object")
    if isinstance(obj_, dict):
        report_id = obj_.get("id_") or obj_.get("id")
    elif isinstance(obj_, str):
        report_id = obj_
    act_ = offer_data.get("actor")
    if isinstance(act_, dict):
        reporter_id = act_.get("id") or act_.get("id_")
    elif isinstance(act_, str):
        reporter_id = act_
    return report_id, reporter_id


def _find_case_for_report(
    client: "demo.DataLayerClient", report_id: str | None
) -> str | None:
    """Return the case_id linked to *report_id*, or ``None`` if not found."""
    cases_data = client.get("/datalayer/VulnerabilityCases/")
    if not cases_data or not report_id:
        return None
    for cid in cases_data:
        case_data = client.get(f"/datalayer/{cid}")
        if not case_data:
            continue
        reports = (
            case_data.get("vulnerabilityReports")
            or case_data.get("vulnerability_reports")
            or []
        )
        for r in reports:
            r_id = r if isinstance(r, str) else (r.get("id_") or r.get("id"))
            if r_id == report_id:
                return str(cid)
    return None


def _create_case_from_offer(
    client: "demo.DataLayerClient",
    actor: "demo.as_Actor",
    offer: as_Offer,
    dl=None,
) -> as_VulnerabilityCase:
    """Return a VulnerabilityCase with actor as CASE_OWNER+VENDOR participant.

    Under ADR-0041, validate-report sends a CaseProposal to the CaseActor but
    in single-server tests the CaseProposal round-trip cannot complete (nested
    ASGI delivery is blocked at depth > 0 to prevent deadlocks).  This helper
    creates the case via trigger/create-case and then seeds the actor as
    CASE_OWNER + VENDOR participant directly in the DataLayer so that
    downstream BT nodes (CheckVendorRoleNode, ResolveCaseManagerNode, etc.)
    find the expected participant state.

    Args:
        client: DataLayerClient for the vendor container.
        actor: The vendor actor that will be the CASE_OWNER.
        offer: The Offer activity whose report_id links to the case.
        dl: DataLayer instance for seeding.  Pass an isolated DataLayer when
            using ``IsolatedActorApp``; defaults to the shared module-level DL.

    Returns:
        The as_VulnerabilityCase with actor registered as CASE_OWNER+VENDOR.
    """
    from vultron.demo.helpers.seeding import seed_case_participants_for_demo

    report_id, reporter_id = _extract_offer_ids(client, offer)

    # Under ADR-0041, validate-report triggers CaseProposal → CaseActor.
    # When delivery works (e.g. _TestClientRouter in isolated tests),
    # the case is created by CaseActor before we get here.  Detect that and
    # skip trigger/create-case to avoid creating a duplicate case.
    case_id = _find_case_for_report(client, report_id)

    if not case_id:
        # CaseProposal round-trip hasn't completed (nested ASGI depth guard in
        # single-server mode).  Create the case manually via the trigger.
        actor_slug = (
            actor.id_.rstrip("/").rsplit("/", 1)[-1] if actor.id_ else ""
        )
        body: dict[str, Any] = {
            "name": "Test case",
            "content": "Created by _create_case_from_offer for test setup.",
            "report_id": report_id,
        }
        if reporter_id:
            body["to"] = [reporter_id]
        resp = client.post(
            f"/actors/{actor_slug}/trigger/create-case",
            json=body,
        )
        assert resp is not None, "trigger/create-case returned no response"
        case_id = _find_case_for_report(client, report_id)

    if not case_id:
        # Last resort: take the most-recent case (no report linkage found).
        cases_data = client.get("/datalayer/VulnerabilityCases/")
        assert cases_data, "No VulnerabilityCases found"
        case_id = next(reversed(cases_data))

    # Seed vendor, reporter, and CaseActor participants directly in the DataLayer.
    # Under ADR-0041 the CaseActor normally creates participants via
    # case_proposal_received_tree, but nested ASGI delivery is blocked in
    # single-server tests (depth > 0 guard prevents deadlocks).
    seed_case_participants_for_demo(
        case_id=case_id,
        vendor_actor_id=actor.id_,
        reporter_actor_id=reporter_id,
        report_id=report_id,
        dl=dl,
    )

    case_data = client.get(f"/datalayer/{case_id}")
    return as_VulnerabilityCase.model_validate(case_data)


# ---------------------------------------------------------------------------
# Unit tests for individual workflow functions
# ---------------------------------------------------------------------------


class TestSeedContainers:
    """Test that seeding functions create actors on each container."""

    def test_seed_containers_creates_finder_actor(
        self, client: TestClient, base: str
    ):
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
        )
        assert finder.id_ is not None
        assert finder.name == "Finder"

    def test_seed_containers_creates_vendor_actor(
        self, client: TestClient, base: str
    ):
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
        )
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_containers_registers_peers(
        self, client: TestClient, base: str
    ):
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
        )

        # Both Finder and Vendor should be visible via the single TestClient.
        actors = finder_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Finder" in actor_names
        assert vendor.name in actor_names

    def test_seed_with_deterministic_ids(self, client: TestClient, base: str):
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder_id = f"{base}/actors/finder-det-test"
        vendor_id = f"{base}/actors/vendor-det-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )

        assert finder.id_ == finder_id
        assert vendor.id_ == vendor_id


class TestResetContainers:
    """Test container reset orchestration for reproducible D5-2 runs."""

    def test_reset_containers_calls_reset_for_all_targets(self):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        case_actor_client = MagicMock()
        finder_client.get.return_value = {}
        vendor_client.get.return_value = {}
        case_actor_client.get.return_value = {}

        with patch(
            "vultron.demo.scenario.fv_demo.reset_datalayer",
            return_value={"status": "ok"},
        ) as reset_mock:
            demo.reset_containers(
                finder_client=finder_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
            )

        reset_mock.assert_has_calls(
            [
                call(client=finder_client, init=False),
                call(client=vendor_client, init=False),
                call(client=case_actor_client, init=False),
            ]
        )


class TestGetActorById:
    """Test get_actor_by_id fetches actors by full URI."""

    def test_returns_actor_with_matching_id(
        self, client: TestClient, base: str
    ):
        dc = make_client(base)
        actor_id = f"{base}/actors/test-get-actor-by-id"
        created = demo.seed_actor(
            client=dc,
            name="TestActor",
            actor_type="Organization",
            actor_id=actor_id,
        )
        fetched = demo.get_actor_by_id(dc, created.id_)
        assert fetched.id_ == created.id_

    def test_raises_when_actor_not_found(self, client: TestClient, base: str):
        dc = make_client(base)
        with pytest.raises(ValueError, match="not found"):
            demo.get_actor_by_id(dc, "http://nonexistent.example/actors/xyz")


class TestFinderSubmitsReport:
    """Test that finder_submits_report creates report and offer in vendor container."""

    def test_report_and_offer_stored(self, client: TestClient, base: str):
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder_id = f"{base}/actors/finder-sub-test"
        vendor_id = f"{base}/actors/vendor-sub-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)

        report, offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )

        assert report.id_ is not None
        assert offer.id_ is not None
        # Both should be fetchable from the vendor container.
        demo.verify_object_stored(vendor_client, report.id_)
        demo.verify_object_stored(vendor_client, offer.id_)


class TestVendorValidatesReport:
    """Test that vendor validates report via trigger endpoint."""

    def test_validate_report_succeeds(self, client: TestClient, base: str):
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder_id = f"{base}/actors/finder-val-test"
        vendor_id = f"{base}/actors/vendor-val-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)

        _, offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )

        result = demo.vendor_validates_report(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            offer_id=offer.id_,
        )
        assert result is not None

    def test_case_created_after_validation(
        self, client: TestClient, base: str
    ):
        """Under ADR-0041, validate-report writes a pending VultronReportCaseLink.

        The vendor defers VulnerabilityCase creation to the CaseActor.  After
        validate-report the DataLayer holds a VultronReportCaseLink (not a
        VulnerabilityCase) — the case is created when Create(VulnerabilityCase)
        arrives from the CaseActor.
        """
        from vultron.core.models.report_case_link import VultronReportCaseLink

        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder_id = f"{base}/actors/finder-casen-test"
        vendor_id = f"{base}/actors/vendor-casen-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)

        _, offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )
        demo.vendor_validates_report(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            offer_id=offer.id_,
        )

        # ADR-0041: the vendor goes through the CaseProposal path — it writes
        # a VultronReportCaseLink and sends Create(as_CaseProposal) to the
        # CaseActor.  In this single-app test, the CaseActor is on the same
        # server (same netloc) so the round-trip completes synchronously, and
        # the VulnerabilityCase may already exist.  What matters is that the
        # VultronReportCaseLink was written (proposal was sent per CP-04-001).
        offer_data = vendor_client.get(f"/datalayer/{offer.id_}")
        obj_ = (
            offer_data.get("object_") or offer_data.get("object")
            if offer_data
            else None
        )
        report_id = None
        if isinstance(obj_, dict):
            report_id = obj_.get("id_") or obj_.get("id")
        elif isinstance(obj_, str):
            report_id = obj_
        assert report_id is not None, "Could not extract report_id from offer"
        link_id = VultronReportCaseLink.build_id(report_id)
        link_data = vendor_client.get(f"/datalayer/{link_id}")
        assert link_data is not None, (
            f"Expected a VultronReportCaseLink at '{link_id}' after"
            " validate-report (ADR-0041 pending proposal marker, CP-04-001)"
        )


class TestFinderAsksQuestion:
    """Test that finder can post a question note to the case."""

    def _setup_case_with_two_participants(
        self, client: TestClient, base: str, suffix: str
    ):
        """Shared setup: returns (finder_client, vendor_client, case, finder, vendor)."""
        finder_client = make_client(base)
        vendor_client = make_client(base)
        finder_id = f"{base}/actors/finder-{suffix}"
        vendor_id = f"{base}/actors/vendor-{suffix}"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)

        _, offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )
        demo.vendor_validates_report(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            offer_id=offer.id_,
        )
        # ADR-0041: no case after validate-report; create one directly for setup.
        case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)

        case_data = vendor_client.get(f"/datalayer/{case.id_}")
        case = as_VulnerabilityCase(**case_data)
        return finder_client, vendor_client, case, finder, vendor

    def test_question_note_stored_in_vendor(
        self, client: TestClient, base: str
    ):
        finder_client, vendor_client, case, finder, vendor = (
            self._setup_case_with_two_participants(client, base, "qnote-test")
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
        finder_in_finder = demo.get_actor_by_id(finder_client, finder.id_)

        question_note = demo.finder_asks_question(
            vendor_client=vendor_client,
            finder_client=finder_client,
            vendor=vendor_in_vendor,
            finder=finder_in_finder,
            case=case,
        )

        assert question_note.id_ is not None
        demo.verify_object_stored(vendor_client, question_note.id_)

    def test_vendor_reply_note_stored(self, client: TestClient, base: str):
        finder_client, vendor_client, case, finder, vendor = (
            self._setup_case_with_two_participants(client, base, "rreply-test")
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
        finder_in_finder = demo.get_actor_by_id(finder_client, finder.id_)
        vendor_in_finder = demo.get_actor_by_id(finder_client, vendor.id_)

        question_note = demo.finder_asks_question(
            vendor_client=vendor_client,
            finder_client=finder_client,
            vendor=vendor_in_vendor,
            finder=finder_in_finder,
            case=case,
        )

        reply_note = demo.vendor_replies_to_question(
            vendor_client=vendor_client,
            finder_client=finder_client,
            vendor=vendor_in_vendor,
            finder=vendor_in_finder,
            case=case,
            question_note=question_note,
        )

        assert reply_note.id_ is not None
        demo.verify_object_stored(vendor_client, reply_note.id_)


# ---------------------------------------------------------------------------
# wait_for_finder_case tests
# ---------------------------------------------------------------------------


class TestWaitForFinderCase:
    """Test wait_for_finder_case polling helper (D5-6-DEMOAUDIT)."""

    def test_succeeds_when_case_already_present(
        self, client: TestClient, base: str
    ):
        """Succeeds immediately when case ID is already in the DataLayer.

        In single-server integration tests both actors share the same DataLayer,
        so after validate-report the case is immediately visible to the finder.
        """
        finder_client = make_client(base)
        vendor_client = make_client(base)
        finder_id = f"{base}/actors/finder-wfc-present"
        vendor_id = f"{base}/actors/vendor-wfc-present"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)

        _, offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )
        demo.vendor_validates_report(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            offer_id=offer.id_,
        )
        # ADR-0041: no case after validate-report; create one directly for setup.
        case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)

        # In single-server mode the case is in the shared DataLayer, so the
        # finder can see it immediately.  wait_for_finder_case should return
        # without raising.
        demo.wait_for_finder_case(
            finder_client=finder_client,
            case_id=case.id_,
            timeout_seconds=2.0,
        )

    def test_raises_when_case_never_arrives(
        self, client: TestClient, base: str
    ):
        """Raises AssertionError when the case does not appear within timeout."""
        finder_client = make_client(base)
        with pytest.raises(AssertionError, match="Timed out"):
            demo.wait_for_finder_case(
                finder_client=finder_client,
                case_id="https://example.org/non-existent-case-wfc",
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


# ---------------------------------------------------------------------------
# SYNC-2 log replication helper tests
# ---------------------------------------------------------------------------


class TestTriggerLogCommit:
    """Tests for trigger_log_commit demo helper."""

    def test_returns_entry_hash_string(self, client: TestClient, base: str):
        """trigger_log_commit returns a non-empty hash string."""
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder, vendor = demo.seed_containers(
            finder_client=finder_client, vendor_client=vendor_client
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
        _, offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder_client=finder_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )
        demo.vendor_validates_report(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            offer_id=offer.id_,
        )
        # ADR-0041: no case after validate-report; create one directly for setup.
        case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)

        entry_hash = demo.trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
            event_type="test_commit",
        )

        assert isinstance(entry_hash, str)
        assert len(entry_hash) > 0

    def test_sequential_commits_return_different_hashes(
        self, client: TestClient, base: str
    ):
        """Two sequential log commits produce distinct entry hashes."""
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder, vendor = demo.seed_containers(
            finder_client=finder_client, vendor_client=vendor_client
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
        _, offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder_client=finder_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )
        demo.vendor_validates_report(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            offer_id=offer.id_,
        )
        # ADR-0041: no case after validate-report; create one directly for setup.
        case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)

        h1 = demo.trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
            event_type="event_a",
        )
        h2 = demo.trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
            event_type="event_b",
        )

        assert h1 != h2


class TestWaitForFinderLogEntry:
    """Tests for wait_for_finder_log_entry polling helper."""

    def test_returns_when_entry_present(self, client: TestClient, base: str):
        """Returns immediately when the log entry exists in the DataLayer."""
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder, vendor = demo.seed_containers(
            finder_client=finder_client, vendor_client=vendor_client
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
        _, offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder_client=finder_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )
        demo.vendor_validates_report(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            offer_id=offer.id_,
        )
        # ADR-0041: no case after validate-report; create one directly for setup.
        case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)

        entry_hash = demo.trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
            event_type="test_wait",
        )

        # In single-server mode the vendor DataLayer is shared, so the entry
        # appears immediately after the commit.
        demo.wait_for_finder_log_entry(
            finder_client=vendor_client,
            case_id=case.id_,
            entry_hash=entry_hash,
            timeout_seconds=2.0,
        )

    def test_raises_when_entry_never_arrives(
        self, client: TestClient, base: str
    ):
        """Raises AssertionError when the entry does not appear within timeout."""
        finder_client = make_client(base)
        with pytest.raises(AssertionError, match="Timed out"):
            demo.wait_for_finder_log_entry(
                finder_client=finder_client,
                case_id="https://example.org/non-existent-case",
                entry_hash="deadbeef" * 8,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


class TestVerifyFinderReplicaState:
    """Tests for verify_finder_replica_state."""

    def test_passes_when_replica_matches(self, client: TestClient, base: str):
        """Passes without error when vendor and finder share the same DataLayer.

        In single-server mode both clients share the same TinyDB, so the
        replica state is always consistent immediately after the log commit.
        """
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder, vendor = demo.seed_containers(
            finder_client=finder_client, vendor_client=vendor_client
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
        _, offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder_client=finder_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )
        demo.vendor_validates_report(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            offer_id=offer.id_,
        )
        # ADR-0041: no case after validate-report; create one directly for setup.
        case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)

        demo.trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
            event_type="demo_verification",
        )

        # Should not raise — single server means replica is trivially consistent
        demo.verify_finder_replica_state(
            finder_client=vendor_client,
            vendor_client=vendor_client,
            case_id=case.id_,
            vendor_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
        )

    def test_raises_when_vendor_case_missing(
        self, client: TestClient, base: str
    ):
        """Raises AssertionError when vendor has no record of the given case_id."""
        vendor_client = make_client(base)

        with pytest.raises(AssertionError):
            demo.verify_finder_replica_state(
                finder_client=vendor_client,
                vendor_client=vendor_client,
                case_id="https://example.org/non-existent-case-vrfs",
                vendor_actor_id="https://example.org/vendor",
                reporter_actor_id="https://example.org/finder",
            )


# ---------------------------------------------------------------------------
# Tests for fix-lifecycle and closure step functions
# ---------------------------------------------------------------------------


def _setup_case_with_3_participants(base: str):
    """Helper: seed, submit report, validate, and return (finder, vendor, case).

    Returns a tuple of (finder_client, vendor_client, finder, vendor, case).
    The shared DataLayer will have 3 participants (Vendor + Finder + Case Actor).
    """
    finder_client = make_client(base)
    vendor_client = make_client(base)

    finder, vendor = demo.seed_containers(
        finder_client=finder_client,
        vendor_client=vendor_client,
    )
    vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
    _, offer = demo.finder_submits_report(
        vendor_client=vendor_client,
        finder_client=finder_client,
        finder=finder,
        vendor=vendor_in_vendor,
    )
    demo.vendor_validates_report(
        vendor_client=vendor_client,
        vendor=vendor_in_vendor,
        offer_id=offer.id_,
    )
    # ADR-0041: no case after validate-report; create one directly for setup.
    case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)
    return finder_client, vendor_client, finder, vendor_in_vendor, case


class TestActorNotifiesFixReady:
    """Tests for actor_notifies_fix_ready."""

    def test_returns_response(self, client: TestClient, base: str):
        """Returns a response dict from the trigger endpoint."""
        finder_client, vendor_client, finder, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        result = demo.actor_notifies_fix_ready(
            client=vendor_client,
            actor=vendor,
            case_id=case.id_,
        )
        # trigger endpoint returns a dict (accepted/queued)
        assert result is not None

    def test_raises_on_invalid_case(self, client: TestClient, base: str):
        """Records failure when case is not found (accumulate-not-reraise, DEMOCI-01-003)."""
        import vultron.demo.utils as demo_utils
        from vultron.demo.utils import reset_demo_failures

        reset_demo_failures()
        finder_client, vendor_client, finder, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        # With the accumulator pattern, no exception propagates; failure is recorded.
        demo.actor_notifies_fix_ready(
            client=vendor_client,
            actor=vendor,
            case_id="https://example.org/does-not-exist",
        )
        assert any(
            "does-not-exist" in f or "404" in f or "STEP FAILED" in f
            for f in demo_utils._demo_failures
        )
        reset_demo_failures()


class TestActorNotifiesFixDeployed:
    """Tests for actor_notifies_fix_deployed guard (CheckDeployerRoleNode).

    Vendor-only actors (CVDRole.VENDOR, no CVDRole.DEPLOYER) MUST be blocked
    from the VFD transition per CSB-15-002.  The notify-fix-deployed endpoint
    returns HTTP 422 when the DEPLOYER guard fires.
    """

    def test_vendor_blocked_from_vfd(self, client: TestClient, base: str):
        """Vendor-only actor is blocked from VFD (d→D) by CheckDeployerRoleNode."""
        from vultron.demo.utils import post_to_trigger

        finder_client, vendor_client, finder, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        demo.actor_notifies_fix_ready(
            client=vendor_client,
            actor=vendor,
            case_id=case.id_,
        )
        # Call post_to_trigger directly so make_testclient_call's AssertionError
        # for 4xx responses propagates (demo_step would swallow it).
        with pytest.raises(AssertionError) as exc_info:
            post_to_trigger(
                client=vendor_client,
                actor_id=vendor.id_,
                behavior="notify-fix-deployed",
                body={"case_id": case.id_},
                path_prefix="demo",
            )
        assert "422" in str(
            exc_info.value
        ), "Expected HTTP 422 when vendor-only actor attempts VFD transition"


class TestActorNotifiesPublished:
    """Tests for actor_notifies_published."""

    def test_returns_response(self, client: TestClient, base: str):
        """Returns a response dict from the trigger endpoint."""
        finder_client, vendor_client, finder, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        result = demo.actor_notifies_published(
            client=vendor_client,
            actor=vendor,
            case_id=case.id_,
        )
        assert result is not None


class TestActorClosesCase:
    """Tests for actor_closes_case."""

    def test_returns_response(self, client: TestClient, base: str):
        """Returns a response dict from the trigger endpoint."""
        finder_client, vendor_client, finder, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        result = demo.actor_closes_case(
            client=vendor_client,
            actor=vendor,
            case_id=case.id_,
        )
        assert result is not None


class TestWaitForParticipantVfdState:
    """Tests for wait_for_participant_vfd_state."""

    def test_times_out_for_unknown_actor(self, client: TestClient, base: str):
        """Raises AssertionError when the actor is not a participant."""
        finder_client, vendor_client, finder, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        from vultron.core.states.cs import CS_vfd

        with pytest.raises(AssertionError, match="Timed out"):
            demo.wait_for_participant_vfd_state(
                client=vendor_client,
                case_id=case.id_,
                actor_id="https://example.org/non-existent-actor",
                expected_states={CS_vfd.VFD},
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


class TestWaitForCaseEmTerminated:
    """Tests for wait_for_case_em_terminated."""

    def test_times_out_when_not_terminated(
        self, client: TestClient, base: str
    ):
        """Raises AssertionError when embargo is still ACTIVE."""
        _, vendor_client, _, vendor, case = _setup_case_with_3_participants(
            base
        )

        with pytest.raises(AssertionError, match="Timed out"):
            demo.wait_for_case_em_terminated(
                client=vendor_client,
                case_id=case.id_,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


class TestWaitForAllParticipantsRmClosed:
    """Tests for wait_for_all_participants_rm_closed."""

    def test_times_out_when_participants_not_closed(
        self, client: TestClient, base: str
    ):
        """Raises AssertionError when participants are not RM.CLOSED."""
        _, vendor_client, _, vendor, case = _setup_case_with_3_participants(
            base
        )

        with pytest.raises(AssertionError, match="Timed out"):
            demo.wait_for_all_participants_rm_closed(
                client=vendor_client,
                case_id=case.id_,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_case_manager_does_not_block_rm_closure_check(
        self, client: TestClient, base: str
    ):
        """CASE_MANAGER participant is excluded from the RM closure check.

        Close vendor and finder; the Case Actor (CASE_MANAGER role) must not
        block ``_all_fetchable_participants_rm_closed`` from returning True,
        whether or not the Case Actor has auto-closed.
        """
        finder_client, vendor_client, finder, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        # RM protocol: VALID → ACCEPTED → CLOSED.  Engage both actors so
        # CreateParticipantStatusNode's transition validation passes.
        demo.vendor_engages_case(
            vendor_client=vendor_client, vendor=vendor, case_id=case.id_
        )
        demo.receiver_engages_case(
            receiver_client=finder_client, receiver=finder, case_id=case.id_
        )
        demo.actor_closes_case(
            client=vendor_client, actor=vendor, case_id=case.id_
        )
        demo.actor_closes_case(
            client=finder_client, actor=finder, case_id=case.id_
        )
        case_data = vendor_client.get(f"/datalayer/{case.id_}")
        refreshed_case = as_VulnerabilityCase.model_validate(case_data)
        result = demo._all_fetchable_participants_rm_closed(
            vendor_client, refreshed_case
        )
        assert result is True

    def test_url_based_actor_keys_handled_gracefully(
        self, client: TestClient, base: str
    ):
        """URL-based actor IDs in actor_participant_index keys are fetchable.

        Regression test for #610.  The Case Actor's actor ID (index key) is an
        HTTP URL; its participant record is stored under a ``urn:uuid:`` ID
        (index value).  After the fix (``/{key:path}`` catch-all route), both
        the Service object (HTTP-URL key) and the CaseParticipant (urn:uuid:
        key) are fetchable via the DataLayer endpoint.
        ``_all_fetchable_participants_rm_closed`` must also handle this layout
        without error.
        """
        from urllib.parse import quote

        finder_client, vendor_client, finder, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        case_data = vendor_client.get(f"/datalayer/{case.id_}")
        fetched_case = as_VulnerabilityCase.model_validate(case_data)

        # actor_participant_index keys are actor IDs; the CaseActor key is an
        # HTTP URL while participant IDs (values) are urn:uuid: URNs.
        url_based_actor_ids = [
            actor_id
            for actor_id in fetched_case.actor_participant_index.keys()
            if actor_id.startswith("http")
        ]
        assert (
            url_based_actor_ids
        ), "Expected at least one URL-based actor ID (Case Actor) in index keys"

        # The CaseActor Service object (HTTP-URL key) must be fetchable.
        actor_id = url_based_actor_ids[0]
        encoded = quote(actor_id, safe="")
        result = vendor_client.get(f"/datalayer/{encoded}")
        assert (
            isinstance(result, dict) and result.get("id") == actor_id
        ), f"Expected Service record for URL-format ID {actor_id!r}, got {result!r}"

        # _all_fetchable_participants_rm_closed must also handle this layout
        # without error.
        try:
            demo._all_fetchable_participants_rm_closed(
                vendor_client, fetched_case
            )
        except Exception as exc:
            pytest.fail(
                f"_all_fetchable_participants_rm_closed crashed on"
                f" URL-based actor ID {actor_id!r}: {exc}"
            )


class TestVerifyM1State:
    """Tests for verify_m1_state."""

    def test_passes_with_3_participants(self, client: TestClient, base: str):
        """Passes when both DataLayers share 3 participants and EM.ACTIVE."""
        finder_client, vendor_client, finder, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        demo.wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_count=3,
        )
        demo.wait_for_finder_case(
            finder_client=finder_client,
            case_id=case.id_,
        )
        # In single-server mode both clients share the same DataLayer
        demo.verify_m1_state(
            vendor_client=vendor_client,
            finder_client=vendor_client,
            case_id=case.id_,
            vendor_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
        )

    def test_raises_when_participant_missing(
        self, client: TestClient, base: str
    ):
        """Raises AssertionError when a required participant is absent."""
        _, vendor_client, _, vendor, case = _setup_case_with_3_participants(
            base
        )

        with pytest.raises(AssertionError):
            demo.verify_m1_state(
                vendor_client=vendor_client,
                finder_client=vendor_client,
                case_id=case.id_,
                vendor_actor_id=vendor.id_,
                reporter_actor_id="https://example.org/non-existent-reporter",
            )


# ---------------------------------------------------------------------------
# Full workflow integration test
# ---------------------------------------------------------------------------


# The full FV workflow runs every phase through report submission, case
# activation, embargo, fix development, and case closure — including several
# polling waits on asynchronous background-task replication.  It takes ~50s
# locally, so the previous 30s bound expired mid-run in ``_phase_case_closure``
# and presented as a hang rather than a failure.  180s leaves headroom for
# slower CI runners without masking a genuine deadlock.
@pytest.mark.timeout(180)
class TestRunTwoActorDemo:
    """Test the complete FV workflow via run_fv_demo."""

    def test_full_workflow_succeeds(
        self, client: TestClient, base: str, caplog
    ):
        finder_client = make_client(base)
        vendor_client = make_client(base)

        finder_id = f"{base}/actors/finder-full-test"
        vendor_id = f"{base}/actors/vendor-full-test"

        with caplog.at_level(logging.ERROR):
            demo.run_fv_demo(
                finder_client=finder_client,
                vendor_client=vendor_client,
                finder_id=finder_id,
                vendor_id=vendor_id,
            )

        assert "ERROR SUMMARY" not in caplog.text, (
            "Expected demo to succeed, but got errors:\n" + caplog.text
        )


class TestDumpCaseLogs:
    """Case-log dump behavior for participant and case-actor outputs."""

    def test_falls_back_to_vendor_case_actor_sub_actor(
        self, tmp_path, monkeypatch
    ):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        finder_client.get_list.return_value = [{"logIndex": 0}]
        vendor_client.get_list.return_value = [{"logIndex": 0}]

        case = demo.as_VulnerabilityCase(
            id_="https://example.org/cases/case-dump-fallback",
            actor_participant_index={
                "https://example.org/actors/vendor": (
                    "https://example.org/cases/case-dump-fallback/"
                    "participants/vendor"
                ),
                "https://example.org/actors/finder": (
                    "https://example.org/cases/case-dump-fallback/"
                    "participants/finder"
                ),
                "https://example.org/actors/case-actor-demo": (
                    "https://example.org/cases/case-dump-fallback/"
                    "participants/case-actor"
                ),
            },
        )
        finder = demo.as_Actor(
            id_="https://example.org/actors/finder", name="Finder"
        )
        vendor = demo.as_Actor(
            id_="https://example.org/actors/vendor", name="Vendor"
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder=finder,
            vendor=vendor,
            case=case,
            case_actor_client=None,
        )

        case_slug = "https_example.org_cases_case-dump-fallback"
        assert (
            tmp_path / "fv" / "finder" / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path / "fv" / "vendor" / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path / "fv" / "case-actor" / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert any(
            "/actors/case-actor-demo/demo/cases/case-dump-fallback/log"
            in call.args[0]
            for call in vendor_client.get_list.call_args_list
        )

    def test_prefers_dedicated_case_actor_client_when_provided(
        self, tmp_path, monkeypatch
    ):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        case_actor_client = MagicMock()
        finder_client.get_list.return_value = [{"logIndex": 0}]
        vendor_client.get_list.return_value = [{"logIndex": 0}]
        case_actor_client.get_list.return_value = [{"logIndex": 0}]

        case = demo.as_VulnerabilityCase(
            id_="https://example.org/cases/case-dump-dedicated"
        )
        finder = demo.as_Actor(
            id_="https://example.org/actors/finder", name="Finder"
        )
        vendor = demo.as_Actor(
            id_="https://example.org/actors/vendor", name="Vendor"
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder=finder,
            vendor=vendor,
            case=case,
            case_actor_client=case_actor_client,
        )

        case_actor_client.get_list.assert_called_once_with(
            "/actors/case-actor/demo/cases/case-dump-dedicated/log"
        )

    def test_falls_back_when_dedicated_case_actor_log_is_empty(
        self, tmp_path, monkeypatch
    ):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        case_actor_client = MagicMock()
        finder_client.get_list.return_value = [{"logIndex": 0}]
        vendor_client.get_list.return_value = [{"logIndex": 0}]
        case_actor_client.get_list.return_value = []

        case = demo.as_VulnerabilityCase(
            id_="https://example.org/cases/case-dump-empty-dedicated",
            actor_participant_index={
                "https://example.org/actors/case-actor-fallback": (
                    "https://example.org/cases/case-dump-empty-dedicated/"
                    "participants/case-actor"
                )
            },
        )
        finder = demo.as_Actor(
            id_="https://example.org/actors/finder", name="Finder"
        )
        vendor = demo.as_Actor(
            id_="https://example.org/actors/vendor", name="Vendor"
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder=finder,
            vendor=vendor,
            case=case,
            case_actor_client=case_actor_client,
        )

        assert any(
            "/actors/case-actor-fallback/demo/cases/"
            "case-dump-empty-dedicated/log" in call.args[0]
            for call in vendor_client.get_list.call_args_list
        )


# ---------------------------------------------------------------------------
# CLI integration test
# ---------------------------------------------------------------------------


class TestTwoActorCLI:
    """Test the fv CLI sub-command registration and invocation."""

    def test_cli_command_registered(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fv", "--help"])
        assert result.exit_code == 0
        assert (
            "fv" in result.output.lower() or "finder" in result.output.lower()
        )

    def test_cli_runs_demo(self, client: TestClient, base: str):
        finder_id = f"{base}/actors/finder-cli-test"
        vendor_id = f"{base}/actors/vendor-cli-test"
        case_actor_url = f"{base}/case-actor"

        patched_run = MagicMock()
        with patch(
            "vultron.demo.scenario.fv_demo.run_fv_demo",
            patched_run,
        ):
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "fv",
                    "--skip-health-check",
                    "--finder-url",
                    base,
                    "--vendor-url",
                    base,
                    "--case-actor-url",
                    case_actor_url,
                    "--finder-id",
                    finder_id,
                    "--vendor-id",
                    vendor_id,
                ],
            )
        assert result.exit_code == 0, result.output
        patched_run.assert_called_once()
        assert (
            patched_run.call_args.kwargs["case_actor_client"].base_url
            == case_actor_url
        )


# ---------------------------------------------------------------------------
# DataLayer isolation tests (#530)
# ---------------------------------------------------------------------------


class TestDeliveryIsolation:
    """Verify per-actor DataLayer isolation: state only crosses between actors
    via the outbox→inbox delivery path (#530).

    These tests use two isolated FastAPI app instances (created via
    ``create_app()``) each with their own in-memory ``SqliteDataLayer``.
    A ``_TestClientRouter`` replaces each app's HTTP fallback emitter so that
    outbound deliveries are routed to the correct actor's TestClient inbox
    in-process rather than making real HTTP requests.

    Passing these tests confirms that:
    - Finder's DataLayer is empty before Vendor delivers via the outbox path.
    - After Vendor processes Finder's report and delivers the case announcement,
      Finder's DataLayer contains the case (received via inbox delivery, not
      through shared DataLayer state).
    """

    @pytest.fixture
    def delivery_setup(self):
        """Two isolated actor apps wired with cross-app TestClient delivery.

        Patches VULTRON_SERVER__BASE_URL and VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL
        to the vendor's routable base URL so that WritePendingReportCaseLinkNode
        builds the CaseActor ID correctly (ADR-0041, CP-04-002) and ASGI delivery
        routes to the vendor app's inbox endpoints.

        Uses an explicit MonkeyPatch (not the pytest monkeypatch fixture) so
        that reload_config() in teardown runs AFTER undo() — the pytest
        monkeypatch fixture auto-undoes after the explicit yield teardown block,
        which would leave the config stale (pointing at http://vendor.test) for
        the next test class.
        """
        from _pytest.monkeypatch import MonkeyPatch

        from test.demo.conftest import (
            _TestClientRouter,
            create_isolated_actor_app,
        )
        from vultron.adapters.driving.fastapi.outbox_handler import (
            configure_default_emitter,
            get_default_emitter,
        )
        from vultron.config import reload_config

        _VENDOR_BASE = "http://vendor.test"
        mp = MonkeyPatch()
        mp.setenv("VULTRON_SERVER__BASE_URL", f"{_VENDOR_BASE}/api/v2")
        mp.setenv(
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", f"{_VENDOR_BASE}/api/v2"
        )
        reload_config()

        router = _TestClientRouter()
        finder_isolated = create_isolated_actor_app(
            base_url="http://finder.test",
            router=router,
        )
        vendor_isolated = create_isolated_actor_app(
            base_url=_VENDOR_BASE,
            router=router,
        )

        from vultron.config import get_config

        config_base_url = get_config().server.base_url.rstrip("/")
        router.register(config_base_url, vendor_isolated.client)

        previous_emitter = get_default_emitter()
        configure_default_emitter(router)  # type: ignore[arg-type]

        with finder_isolated.client as finder_tc:
            with vendor_isolated.client as vendor_tc:
                yield finder_isolated, vendor_isolated, finder_tc, vendor_tc

        configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
        finder_isolated.dl.close()
        vendor_isolated.dl.close()
        mp.undo()
        reload_config()

    def test_finder_dl_empty_before_delivery(self, delivery_setup):
        """Finder's DataLayer contains no cases before any delivery occurs."""
        finder_isolated, _vendor_isolated, finder_tc, _vendor_tc = (
            delivery_setup
        )

        # Create Finder actor on finder's app.
        finder_base = finder_isolated.base_url + "/api/v2"
        finder_id = f"{finder_base}/actors/finder-isolation-test"
        resp = finder_tc.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Finder",
                "id": finder_id,
            },
        )
        assert resp.status_code in (200, 201)

        # Finder's DataLayer should have no as_VulnerabilityCase records.
        cases = finder_isolated.dl.get_all("VulnerabilityCase")
        assert cases == [], (
            f"Expected no cases in Finder's isolated DataLayer before"
            f" delivery, but found: {cases}"
        )

    def test_vendor_dl_isolated_from_finder(self, delivery_setup):
        """Objects created in Vendor's DataLayer are not visible in Finder's."""
        finder_isolated, vendor_isolated, _finder_tc, vendor_tc = (
            delivery_setup
        )

        vendor_base = vendor_isolated.base_url + "/api/v2"
        vendor_id = f"{vendor_base}/actors/vendor-isolation-test"
        resp = vendor_tc.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Vendor",
                "id": vendor_id,
            },
        )
        assert resp.status_code in (200, 201)

        # Vendor's actor must NOT be visible in Finder's DataLayer.
        actor_in_finder = finder_isolated.dl.read(vendor_id)
        assert actor_in_finder is None, (
            "Vendor's actor should not be in Finder's isolated DataLayer,"
            " but it was found."
        )

    def test_case_delivered_to_finder_via_inbox(self, delivery_setup):
        """After Vendor validates the report, Finder receives the case via delivery.

        This is the core delivery-path test for #530.  Without the fix,
        Finder's DataLayer would remain empty because delivery was never
        exercised.  With the fix, the outbox→inbox chain runs in-process
        via ``_TestClientRouter`` and Finder's isolated DataLayer receives the
        case announcement.
        """
        import types

        finder_isolated, vendor_isolated, finder_tc, vendor_tc = delivery_setup

        finder_base = finder_isolated.base_url + "/api/v2"
        vendor_base = vendor_isolated.base_url + "/api/v2"

        finder_id = f"{finder_base}/actors/finder-delivery-test"
        vendor_id = f"{vendor_base}/actors/vendor-delivery-test"

        # Create actors on their respective isolated apps.
        r = finder_tc.post(
            "/api/v2/actors/",
            json={"type": "Organization", "name": "Finder", "id": finder_id},
        )
        assert r.status_code in (200, 201)
        r = vendor_tc.post(
            "/api/v2/actors/",
            json={"type": "Organization", "name": "Vendor", "id": vendor_id},
        )
        assert r.status_code in (200, 201)

        # Build DataLayerClient wrappers routed to their respective apps.
        finder_dc = demo.DataLayerClient(base_url=finder_base)
        vendor_dc = demo.DataLayerClient(base_url=vendor_base)
        object.__setattr__(
            finder_dc,
            "call",
            types.MethodType(
                make_testclient_call(finder_tc, finder_base), finder_dc
            ),
        )
        object.__setattr__(
            vendor_dc,
            "call",
            types.MethodType(
                make_testclient_call(vendor_tc, vendor_base), vendor_dc
            ),
        )

        finder_actor = demo.get_actor_by_id(finder_dc, finder_id)
        vendor_actor = demo.get_actor_by_id(vendor_dc, vendor_id)

        # Finder registers Vendor as a peer on Finder's app so the report
        # offer can be constructed with the correct vendor actor reference.
        r = finder_tc.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Vendor",
                "id": vendor_id,
            },
        )
        # 409 is OK — vendor may already be registered; 200/201 also fine.

        # Vendor registers Finder as a peer on Vendor's app.
        r = vendor_tc.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Finder",
                "id": finder_id,
            },
        )

        # Finder submits a report offer directly to Vendor's inbox.
        _report, offer = demo.finder_submits_report(
            vendor_client=vendor_dc,
            finder=finder_actor,
            vendor=vendor_actor,
        )
        assert offer.id_ is not None

        # Vendor validates the report — under ADR-0041 this writes a
        # VultronReportCaseLink and sends Create(as_CaseProposal) to CaseActor.
        vendor_actor_fresh = demo.get_actor_by_id(vendor_dc, vendor_id)
        demo.vendor_validates_report(
            vendor_client=vendor_dc,
            vendor=vendor_actor_fresh,
            offer_id=offer.id_,
        )

        # ADR-0041: the vendor sends Create(as_CaseProposal) to the CaseActor.
        # In this two-app setup the CaseActor runs on the vendor app, so the
        # proposal round-trip may complete synchronously.  Use _create_case_from_offer
        # which checks for an existing case first and only calls trigger/create-case
        # if the round-trip hasn't completed yet.
        case = _create_case_from_offer(
            vendor_dc, vendor_actor_fresh, offer, dl=vendor_isolated.dl
        )
        assert (
            case is not None
        ), "Expected VulnerabilityCase after validate-report or trigger/create-case"

        # The case announcement should have been delivered to Finder's inbox
        # via the outbox→_TestClientRouter→inbox chain.  Finder's isolated
        # DataLayer must contain the case.
        finder_case = finder_isolated.dl.read(case.id_)
        assert finder_case is not None, (
            f"Expected as_VulnerabilityCase '{case.id_}' to be delivered to"
            f" Finder's isolated DataLayer via the outbox→inbox path,"
            f" but Finder's DataLayer has no record of it.  This indicates"
            f" the delivery path is broken or the DataLayers are incorrectly"
            f" shared (#530)."
        )


# ---------------------------------------------------------------------------
# In-process case-ledger invariant helpers (#950)
# ---------------------------------------------------------------------------


def _log_event_type(entry: dict) -> str:
    """Return eventType from a log entry dict (accepts camelCase alias)."""
    return str(entry.get("eventType", entry.get("event_type", "")))


def _log_payload(entry: dict) -> dict:
    """Return payloadSnapshot from a log entry dict."""
    snap = entry.get("payloadSnapshot", entry.get("payload_snapshot", {}))
    return snap if isinstance(snap, dict) else {}


def _participant_id_and_rm(
    snapshot: dict,
) -> tuple[str | None, str | None]:
    """Extract participant id and RM state from a participant-status snapshot.

    Historical logs may encode ``ParticipantStatus`` directly in the
    snapshot or nest it under an ``Add`` activity's ``object``.
    Accepts both camelCase (wire) and snake_case field names.
    """
    p_id = snapshot.get("attributedTo") or snapshot.get("attributed_to")
    rm_state = snapshot.get("rmState") or snapshot.get("rm_state")
    if p_id and rm_state:
        return str(p_id), str(rm_state)

    nested = snapshot.get("object")
    if isinstance(nested, dict):
        nested_id = nested.get("attributedTo") or nested.get("attributed_to")
        nested_rm = nested.get("rmState") or nested.get("rm_state")
        if nested_id and nested_rm:
            return str(nested_id), str(nested_rm)

    return None, None


def _fetch_case_log(
    client: demo.DataLayerClient,
    case: demo.as_VulnerabilityCase,
) -> list[dict]:
    """Return case ledger entries from the demo DataLayer API endpoint.

    Calls ``GET /actors/{route_key}/demo/cases/{case_key}/log``.  In the
    single-DataLayer test environment the endpoint returns all
    ``CaseLedgerEntry`` objects for *case* regardless of which actor route key
    is supplied (``actor_id`` is ignored server-side; see
    ``demo_triggers.demo_get_case_ledger``).  The case-actor route key is
    preferred when available so that the path is realistic, but the returned
    entries represent the *combined* case log, not a per-actor replica.

    Returns an empty list when no case-actor participant can be located.
    """
    case_key = strip_id_prefix(case.id_ or "")
    case_actor_route_key = next(
        (
            strip_id_prefix(actor_id)
            for actor_id in (case.actor_participant_index or {})
            if strip_id_prefix(actor_id).startswith("case-actor")
        ),
        None,
    )
    if case_actor_route_key is None:
        return []
    log_path = f"/actors/{case_actor_route_key}/demo/cases/{case_key}/log"
    return client.get_list(log_path)


# ---------------------------------------------------------------------------
# In-process case-ledger invariant tests (#950)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def completed_workflow(
    client: TestClient, base: str
) -> tuple[demo.DataLayerClient, demo.as_VulnerabilityCase]:
    """Run the full FV workflow and return (vendor_client, case).

    Uses deterministic actor IDs (``finder-ledger-inv`` /
    ``vendor-ledger-inv``) to avoid collisions with other test classes
    sharing the same module-scoped DataLayer.
    """
    finder_client = make_client(base)
    vendor_client = make_client(base)

    finder_id = f"{base}/actors/finder-ledger-inv"
    vendor_id = f"{base}/actors/vendor-ledger-inv"

    finder, vendor = demo.seed_containers(
        finder_client=finder_client,
        vendor_client=vendor_client,
        reporter_actor_id=finder_id,
        vendor_actor_id=vendor_id,
    )
    vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)

    _, offer = demo.finder_submits_report(
        vendor_client=vendor_client,
        finder=finder,
        vendor=vendor_in_vendor,
    )
    demo.vendor_validates_report(
        vendor_client=vendor_client,
        vendor=vendor_in_vendor,
        offer_id=offer.id_,
    )

    # ADR-0041: no case after validate-report; create one directly for setup.
    case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)
    assert (
        case is not None
    ), "Expected as_VulnerabilityCase after trigger/create-case"
    # Refresh case to get actor_participant_index populated.
    case_data = vendor_client.get(f"/datalayer/{case.id_}")
    case = as_VulnerabilityCase(**case_data)

    # Fix lifecycle: vendor-only actor stops at VFd (CSB-15-002).
    demo.actor_notifies_fix_ready(
        client=vendor_client, actor=vendor_in_vendor, case_id=case.id_
    )
    demo.actor_notifies_published(
        client=vendor_client, actor=vendor_in_vendor, case_id=case.id_
    )

    # Case closure — both actors must close so RM=CLOSED for all.
    finder_in_finder = demo.get_actor_by_id(finder_client, finder.id_)
    demo.actor_closes_case(
        client=vendor_client, actor=vendor_in_vendor, case_id=case.id_
    )
    demo.actor_closes_case(
        client=finder_client, actor=finder_in_finder, case_id=case.id_
    )

    # Final refresh to pick up any post-closure case-actor state.
    case_data = vendor_client.get(f"/datalayer/{case.id_}")
    case = as_VulnerabilityCase(**case_data)

    return vendor_client, case


class TestCaseLedgerInvariants:
    """In-process case-ledger invariant checks for the FV scenario.

    Adapts invariants 5 and 7 from ``test/ci/test_case_ledger_invariants.py``
    to run against the live in-process DataLayer state rather than parsed JSONL
    files.  Tests run in sub-second time without any Docker requirement.

    Each assertion carries a comment pointing to the corresponding CI
    invariant number (AC: issue #950 acceptance criteria item 4).

    Auto-marked ``integration`` by the demo conftest hook.
    Spec: CLP-07.
    """

    #: Baseline event types that must appear in the combined case log after a
    #: complete FV CVD run.  These are the types observed in the
    #: single-DataLayer in-process test environment and do not correspond
    #: directly to CI invariant 5 (whose full set requires CaseActor
    #: commit-path completeness — see issue #789).
    _REQUIRED_EVENT_TYPES: frozenset[str] = frozenset(
        {
            "add_participant_status_to_participant",  # participant tracking — CI invariant 7
            # offer_case_manager_role removed: ADR-0041 removes SendOfferCaseManagerRoleNode;
            # CaseActor self-assigns CASE_MANAGER natively without the offer/accept round-trip.
        }
    )

    def test_add_participant_status_entries_present(
        self,
        completed_workflow: tuple[
            demo.DataLayerClient, demo.as_VulnerabilityCase
        ],
    ) -> None:
        """Combined case log contains at least one add_participant_status entry.

        Checks the combined case log (all actors share one DataLayer in this
        test environment).  Corresponds to the presence pre-condition of CI
        invariant 7 from test/ci/test_case_ledger_invariants.py.
        Spec: CLP-07.
        """
        vendor_client, case = completed_workflow
        entries = _fetch_case_log(vendor_client, case)

        # CI invariant 7 — presence of add_participant_status entries.
        status_entries = [
            e
            for e in entries
            if _log_event_type(e) == "add_participant_status_to_participant"
        ]
        assert status_entries, (
            "Expected at least one add_participant_status_to_participant entry"
            " in the combined case log, but none were found. "
            f"(total entries: {len(entries)}, "
            f"event types: {sorted({_log_event_type(e) for e in entries})})"
        )

    def test_all_participants_rm_closed_at_scenario_end(
        self,
        completed_workflow: tuple[
            demo.DataLayerClient, demo.as_VulnerabilityCase
        ],
    ) -> None:
        """All tracked participants end in RM=CLOSED at scenario completion.

        Scans add_participant_status and close_case entries in the combined
        case log to determine the final RM state per participant.
        ``add_participant_status_to_participant`` entries carry the RM state
        explicitly; ``close_case`` entries signal RM=CLOSED for the departing
        actor recorded in ``payloadSnapshot.actor`` (ADR-0050, CM-23-002/003).
        Corresponds to CI invariant 7 (terminal RM state check) from
        test/ci/test_case_ledger_invariants.py.
        Spec: CLP-07.
        """
        vendor_client, case = completed_workflow
        entries = _fetch_case_log(vendor_client, case)

        # CI invariant 7 — last RM state per participant must be CLOSED.
        latest_rm: dict[str, str] = {}
        for entry in entries:
            event_type = _log_event_type(entry)
            payload = _log_payload(entry)
            if event_type == "add_participant_status_to_participant":
                p_id, rm_state = _participant_id_and_rm(payload)
                if p_id and rm_state:
                    latest_rm[p_id] = rm_state
            elif event_type == "close_case":
                # close_case entries signal RM=CLOSED for the departing actor
                # (ADR-0050: Leave(VulnerabilityCase) is the canonical closure path).
                actor_id = payload.get("actor") or payload.get("attributedTo")
                if isinstance(actor_id, dict):
                    actor_id = actor_id.get("id")
                if actor_id:
                    latest_rm[str(actor_id)] = "CLOSED"

        assert latest_rm, (
            "No add_participant_status_to_participant or close_case entries"
            " found in combined case log; cannot verify terminal RM states."
        )

        not_closed = {
            p: s
            for p, s in latest_rm.items()
            if s.upper() not in ("CLOSED", "RM.CLOSED")
        }
        assert (
            not not_closed
        ), f"Participants not in RM=CLOSED at scenario end: {not_closed}"

    def test_required_event_types_present_in_case_actor_log(
        self,
        completed_workflow: tuple[
            demo.DataLayerClient, demo.as_VulnerabilityCase
        ],
    ) -> None:
        """Combined case log contains the required baseline event types.

        Verifies a baseline set of event types observed in the single-DataLayer
        in-process test environment.  This does not directly correspond to CI
        invariant 5 (whose full EXPECTED_EVENT_TYPES set requires CaseActor
        commit-path completeness per issue #789); it confirms that the
        participant-tracking and report-intake paths produce log entries.
        Spec: CLP-07.
        """
        vendor_client, case = completed_workflow
        entries = _fetch_case_log(vendor_client, case)

        # Baseline event-type presence check (participant tracking + report intake).
        found = {_log_event_type(e) for e in entries}
        missing = self._REQUIRED_EVENT_TYPES - found
        assert not missing, (
            f"Required eventTypes missing from combined case log: {sorted(missing)}\n"
            f"Found: {sorted(found)}"
        )


# ---------------------------------------------------------------------------
# AC-4: Milestone assertion tests
# ---------------------------------------------------------------------------


class TestFvMilestoneAssertions:
    """Verify that _phase_* functions call the required milestone helpers.

    All network/DataLayer calls are patched so no real HTTP is performed.
    """

    def _actor(self, id_: str = "urn:test:actor"):
        a = MagicMock()
        a.id_ = id_
        return a

    def _case(self, id_: str = "urn:test:case"):
        c = MagicMock()
        c.id_ = id_
        return c

    def _client(self):
        c = MagicMock()
        c.get.return_value = {}
        return c

    def test_phase_report_submission_calls_verify_case_active(self):
        """_phase_report_submission calls verify_case_active at M1."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        case_actor_client = self._client()
        finder = self._actor("urn:test:finder")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        case = self._case()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers",
                return_value=(finder, vendor),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                return_value=vendor_in_vendor,
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(demo, "vendor_validates_report"),
            patch.object(
                demo,
                "_report_id_from_offer_data",
                return_value="urn:test:report",
            ),
            patch.object(
                demo,
                "post_to_trigger",
                return_value={"activity": {"id": "urn:test:activity"}},
            ),
            patch.object(demo, "find_case_for_offer", return_value=case),
            patch.object(demo, "seed_case_participants_for_demo"),
            patch.object(demo, "vendor_engages_case"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_finder_case"),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(demo, "verify_case_active") as mock_m1,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                finder_id=None,
                vendor_id=None,
            )
        mock_m1.assert_called()

    def test_phase_fix_lifecycle_calls_verify_fix_ready(self):
        """_phase_fix_lifecycle calls verify_fix_ready at M4/M5."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        case = self._case()

        with (
            patch.object(demo, "actor_notifies_fix_ready"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_fix_ready") as mock_m4,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_fix_lifecycle(
                finder_client=finder_client,
                vendor_client=vendor_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                case=case,
            )
        mock_m4.assert_called()

    def test_phase_publication_calls_verify_publicly_disclosed(self):
        """_phase_publication calls verify_publicly_disclosed at M6."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        finder = self._actor("urn:test:finder")
        finder_in_finder = self._actor("urn:test:finder")
        case = self._case()

        with (
            patch.object(demo, "actor_notifies_published"),
            patch.object(demo, "wait_for_case_em_terminated"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_publicly_disclosed") as mock_m6,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_publication(
                finder_client=finder_client,
                vendor_client=vendor_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                finder=finder,
                finder_in_finder=finder_in_finder,
                case=case,
            )
        mock_m6.assert_called()

    def test_phase_case_closure_calls_verify_case_closed(self):
        """_phase_case_closure calls verify_case_closed at M7."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        finder = self._actor("urn:test:finder")
        finder_in_finder = self._actor("urn:test:finder")
        case = self._case()
        case.id_ = "urn:test:case"
        vendor_client.get.return_value = {
            "e0": {
                "case_id": case.id_,
                "log_index": 0,
                "entry_hash": "h0",
                "event_type": "close_case",
            }
        }

        with (
            patch.object(demo, "actor_closes_case"),
            patch.object(demo, "wait_for_all_participants_rm_closed"),
            patch.object(demo, "verify_case_closed") as mock_m7,
            patch.object(demo, "wait_for_event_type_in_ledger"),
            patch.object(demo, "wait_for_contiguous_ledger_coverage"),
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_case_closure(
                finder_client=finder_client,
                vendor_client=vendor_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                finder=finder,
                finder_in_finder=finder_in_finder,
                case=case,
            )
        mock_m7.assert_called()
