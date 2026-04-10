#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.

"""Unit tests for the multi-vendor ownership-transfer demo (D5-4)."""

import importlib
import logging
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.multi_vendor_demo as demo
from test.demo._helpers import make_testclient_call


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    """Return the base URL for the single TestClient."""
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture(scope="module", autouse=True)
def patch_datalayer_call(client: TestClient, base: str):
    """Patch DataLayerClient.call for all tests in this module."""
    mp = MonkeyPatch()
    try:
        mp.setattr(
            demo.DataLayerClient, "call", make_testclient_call(client, base)
        )
        yield
    finally:
        mp.undo()
        importlib.reload(demo)


def _make_client(base: str) -> demo.DataLayerClient:
    """Return a client that routes through the patched TestClient."""
    return demo.DataLayerClient(base_url=base)


class TestSeedContainers:
    """Tests for multi-vendor container seeding."""

    def test_seed_containers_creates_all_local_actors(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)
        coordinator_client = _make_client(base)
        case_actor_client = _make_client(base)
        vendor2_client = _make_client(base)

        (
            finder,
            vendor,
            coordinator,
            case_actor,
            vendor2,
        ) = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            vendor2_client=vendor2_client,
        )

        assert finder.name == "Finder"
        assert vendor.name == "Vendor"
        assert coordinator.name == "Coordinator"
        assert case_actor.name == "CaseActor"
        assert vendor2.name == "Vendor2"


class TestVendorCreatesCase:
    """Tests for vendor-led case creation on the CaseActor container."""

    def test_vendor_creates_case_on_case_actor(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)
        coordinator_client = _make_client(base)
        case_actor_client = _make_client(base)
        vendor2_client = _make_client(base)

        demo.reset_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            vendor2_client=vendor2_client,
        )
        (
            finder,
            vendor,
            coordinator,
            case_actor,
            vendor2,
        ) = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            vendor2_client=vendor2_client,
        )
        vendor_in_vendor = demo.get_actor_by_id(vendor_client, vendor.id_)
        vendor_in_case_actor = demo.get_actor_by_id(
            case_actor_client, vendor.id_
        )

        report, report_offer = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder=finder,
            vendor=vendor_in_vendor,
        )
        demo.vendor_validates_report(
            vendor_client=vendor_client,
            vendor=vendor_in_vendor,
            offer_id=report_offer.id_,
        )
        case = demo.vendor_creates_case_on_case_actor(
            case_actor_client=case_actor_client,
            case_actor=case_actor,
            vendor=vendor_in_case_actor,
            report=report,
        )

        assert case.id_ is not None
        case_ids = case_actor_client.get("/datalayer/VulnerabilityCases/")
        assert case.id_ in case_ids

        case_data = case_actor_client.get(f"/datalayer/{case.id_}")
        stored_case = demo.VulnerabilityCase(**case_data)
        from vultron.demo.multi_vendor_demo import ref_id as _ref_id

        assert _ref_id(stored_case.attributed_to) == vendor_in_case_actor.id_


class TestOwnershipTransfer:
    """Tests for the vendor→coordinator ownership transfer workflow."""

    def test_vendor_offers_and_coordinator_accepts(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)
        coordinator_client = _make_client(base)
        case_actor_client = _make_client(base)
        vendor2_client = _make_client(base)

        demo.reset_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            vendor2_client=vendor2_client,
        )
        (
            finder,
            vendor,
            coordinator,
            case_actor,
            vendor2,
        ) = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            vendor2_client=vendor2_client,
        )
        vendor_in_case_actor = demo.get_actor_by_id(
            case_actor_client, vendor.id_
        )
        coordinator_in_coordinator = demo.get_actor_by_id(
            coordinator_client, coordinator.id_
        )

        report, _ = demo.finder_submits_report(
            vendor_client=vendor_client,
            finder=finder,
            vendor=demo.get_actor_by_id(vendor_client, vendor.id_),
        )
        case = demo.vendor_creates_case_on_case_actor(
            case_actor_client=case_actor_client,
            case_actor=case_actor,
            vendor=vendor_in_case_actor,
            report=report,
        )

        # Confirm initial owner is vendor
        case_data = case_actor_client.get(f"/datalayer/{case.id_}")
        initial_case = demo.VulnerabilityCase(**case_data)
        from vultron.demo.multi_vendor_demo import ref_id as _ref_id

        assert _ref_id(initial_case.attributed_to) == vendor_in_case_actor.id_

        offer = demo.vendor_offers_case_ownership_to_coordinator(
            case_actor_client=case_actor_client,
            coordinator_client=coordinator_client,
            case_actor=case_actor,
            vendor=vendor_in_case_actor,
            coordinator=coordinator_in_coordinator,
            case=case,
        )
        assert offer.id_ is not None

        demo.coordinator_accepts_case_ownership(
            case_actor_client=case_actor_client,
            case_actor=case_actor,
            coordinator=coordinator_in_coordinator,
            offer=offer,
            case=case,
        )

        # Verify case ownership transferred to coordinator
        updated_data = case_actor_client.get(f"/datalayer/{case.id_}")
        updated_case = demo.VulnerabilityCase(**updated_data)
        from vultron.demo.multi_vendor_demo import ref_id as _ref_id

        assert (
            _ref_id(updated_case.attributed_to)
            == coordinator_in_coordinator.id_
        )


class TestRunMultiVendorDemo:
    """Integration-style tests for the full multi-vendor demo flow."""

    def test_full_workflow_succeeds(
        self, client: TestClient, base: str, caplog
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)
        coordinator_client = _make_client(base)
        case_actor_client = _make_client(base)
        vendor2_client = _make_client(base)

        with caplog.at_level(logging.ERROR):
            final_case = demo.run_multi_vendor_demo(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                vendor2_client=vendor2_client,
            )

        assert "ERROR SUMMARY" not in caplog.text, (
            "Expected multi-vendor demo to succeed, but got errors:\n"
            + caplog.text
        )

        assert len(final_case.case_participants) == 3
        assert final_case.current_status.em_state == demo.EM.ACTIVE
        # Coordinator ownership was verified inside run_multi_vendor_demo
        # via verify_multi_vendor_case_state (would have raised on failure).


class TestMultiVendorCLI:
    """Tests for CLI registration and invocation of the multi-vendor command."""

    def test_cli_command_registered(self):
        from vultron.demo.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["multi-vendor", "--help"])
        assert result.exit_code == 0
        assert "multi-vendor" in result.output.lower()

    def test_cli_runs_demo(self, client: TestClient, base: str):
        from vultron.demo.cli import main

        patched_run = MagicMock()
        with patch(
            "vultron.demo.multi_vendor_demo.run_multi_vendor_demo", patched_run
        ):
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "multi-vendor",
                    "--skip-health-check",
                    "--finder-url",
                    base,
                    "--vendor-url",
                    base,
                    "--coordinator-url",
                    base,
                    "--case-actor-url",
                    base,
                    "--vendor2-url",
                    base,
                ],
            )

        assert result.exit_code == 0, result.output
        patched_run.assert_called_once()
