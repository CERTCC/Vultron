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

"""Unit tests for the two-actor (Finder + Vendor) multi-container demo (D5-1-G5).

Uses a single TestClient (one FastAPI app instance) to simulate two containers.
Both DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.  This validates the
demo script logic while tolerating the single-process constraint of unit tests.

True multi-container isolation is validated by the acceptance test runnable via:
    docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
import logging

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

import vultron.demo.two_actor_demo as demo
from test.demo._helpers import make_testclient_call

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    """Return the base URL for the single TestClient, matching /api/v2 prefix."""
    return str(client.base_url).rstrip("/") + "/api/v2"


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
# Helpers
# ---------------------------------------------------------------------------


def _make_client(base: str) -> demo.DataLayerClient:
    """Return a DataLayerClient that routes through the patched TestClient."""
    return demo.DataLayerClient(base_url=base)


# ---------------------------------------------------------------------------
# Unit tests for individual workflow functions
# ---------------------------------------------------------------------------


class TestSeedContainers:
    """Test that seeding functions create actors on each container."""

    def test_seed_containers_creates_finder_actor(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
        )
        assert finder.id_ is not None
        assert finder.name == "Finder"

    def test_seed_containers_creates_vendor_actor(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
        )
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_containers_registers_peers(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

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
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder_id = f"{base}/actors/finder-det-test"
        vendor_id = f"{base}/actors/vendor-det-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )

        assert finder.id_ == finder_id
        assert vendor.id_ == vendor_id


class TestResetContainers:
    """Test container reset orchestration for reproducible D5-2 runs."""

    def test_reset_containers_calls_reset_for_all_targets(self):
        from unittest.mock import MagicMock, call, patch

        finder_client = MagicMock()
        vendor_client = MagicMock()
        case_actor_client = MagicMock()
        finder_client.get.return_value = {}
        vendor_client.get.return_value = {}
        case_actor_client.get.return_value = {}

        with patch(
            "vultron.demo.two_actor_demo.reset_datalayer",
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
        dc = _make_client(base)
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
        dc = _make_client(base)
        with pytest.raises(ValueError, match="not found"):
            demo.get_actor_by_id(dc, "http://nonexistent.example/actors/xyz")


class TestFinderSubmitsReport:
    """Test that finder_submits_report creates report and offer in vendor container."""

    def test_report_and_offer_stored(self, client: TestClient, base: str):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder_id = f"{base}/actors/finder-sub-test"
        vendor_id = f"{base}/actors/vendor-sub-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_actor_id=finder_id,
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
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder_id = f"{base}/actors/finder-val-test"
        vendor_id = f"{base}/actors/vendor-val-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_actor_id=finder_id,
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
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder_id = f"{base}/actors/finder-casen-test"
        vendor_id = f"{base}/actors/vendor-casen-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_actor_id=finder_id,
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

        case = demo.find_case_for_offer(vendor_client, offer.id_)
        assert (
            case is not None
        ), "Expected VulnerabilityCase to exist after validate-report"
        assert case.id_ is not None


class TestVendorEngagesCase:
    """Test that vendor engages case via trigger endpoint."""

    def test_engage_case_succeeds(self, client: TestClient, base: str):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder_id = f"{base}/actors/finder-eng-test"
        vendor_id = f"{base}/actors/vendor-eng-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_actor_id=finder_id,
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
        case = demo.find_case_for_offer(vendor_client, offer.id_)
        assert case is not None

        result = demo.vendor_engages_case(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            case_id=case.id_,
        )
        assert result is not None


class TestVendorInvitesFinder:
    """Test that vendor can invite finder to the case."""

    def test_invite_delivered_to_finder_inbox(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder_id = f"{base}/actors/finder-inv-test"
        vendor_id = f"{base}/actors/vendor-inv-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
        finder_in_vendor = demo.get_actor_by_id(vendor_client, finder.id_)

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
        case = demo.find_case_for_offer(vendor_client, offer.id_)
        assert case is not None

        invite = demo.vendor_invites_finder(
            vendor_client=vendor_client,
            finder_client=finder_client,
            vendor=vendor_in_vendor,
            finder=finder_in_vendor,
            case=case,
        )

        assert invite.id_ is not None
        # Invite should be stored in the Finder container's DataLayer.
        demo.verify_object_stored(finder_client, invite.id_)


class TestFinderAcceptsInvite:
    """Test that finder can accept the case invitation."""

    def test_acceptance_delivered_to_vendor_inbox(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder_id = f"{base}/actors/finder-acc-test"
        vendor_id = f"{base}/actors/vendor-acc-test"

        finder, vendor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
        finder_in_vendor = demo.get_actor_by_id(vendor_client, finder.id_)

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
        case = demo.find_case_for_offer(vendor_client, offer.id_)
        assert case is not None

        invite = demo.vendor_invites_finder(
            vendor_client=vendor_client,
            finder_client=finder_client,
            vendor=vendor_in_vendor,
            finder=finder_in_vendor,
            case=case,
        )

        finder_in_finder = demo.get_actor_by_id(finder_client, finder.id_)
        vendor_in_finder = demo.get_actor_by_id(finder_client, vendor.id_)

        accept = demo.finder_accepts_invite(
            vendor_client=vendor_client,
            finder=finder_in_finder,
            vendor=vendor_in_finder,
            invite=invite,
        )

        assert accept.id_ is not None
        demo.verify_object_stored(vendor_client, accept.id_)


# ---------------------------------------------------------------------------
# Full workflow integration test
# ---------------------------------------------------------------------------


class TestRunTwoActorDemo:
    """Test the complete two-actor workflow via run_two_actor_demo."""

    def test_full_workflow_succeeds(
        self, client: TestClient, base: str, caplog
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)

        finder_id = f"{base}/actors/finder-full-test"
        vendor_id = f"{base}/actors/vendor-full-test"

        with caplog.at_level(logging.ERROR):
            demo.run_two_actor_demo(
                finder_client=finder_client,
                vendor_client=vendor_client,
                finder_id=finder_id,
                vendor_id=vendor_id,
            )

        assert "ERROR SUMMARY" not in caplog.text, (
            "Expected demo to succeed, but got errors:\n" + caplog.text
        )


# ---------------------------------------------------------------------------
# CLI integration test
# ---------------------------------------------------------------------------


class TestTwoActorCLI:
    """Test the two-actor CLI sub-command registration and invocation."""

    def test_cli_command_registered(self):
        from click.testing import CliRunner
        from vultron.demo.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["two-actor", "--help"])
        assert result.exit_code == 0
        assert (
            "two-actor" in result.output.lower()
            or "finder" in result.output.lower()
        )

    def test_cli_runs_demo(self, client: TestClient, base: str):
        from unittest.mock import patch, MagicMock
        from click.testing import CliRunner
        from vultron.demo.cli import main

        finder_id = f"{base}/actors/finder-cli-test"
        vendor_id = f"{base}/actors/vendor-cli-test"
        case_actor_url = f"{base}/case-actor"

        patched_run = MagicMock()
        with patch(
            "vultron.demo.two_actor_demo.run_two_actor_demo", patched_run
        ):
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "two-actor",
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
