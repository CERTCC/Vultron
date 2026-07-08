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

"""Unit tests for the FVV (Finder + Vendor1 + Vendor2) multi-container CVD demo (D5-5).

Uses a single TestClient (one FastAPI app instance) to simulate three containers.
All three DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=fvv docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
from unittest.mock import MagicMock, call, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fvv_demo as demo
from test.demo._helpers import make_client, make_testclient_call
from vultron.demo.cli import main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    """Return the base URL for the single TestClient, matching /api/v2 prefix."""
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture(scope="module", autouse=True)
def patch_datalayer_call(client: TestClient, base: str):
    """Patch DataLayerClient.call at the class level for all tests in this module."""
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
# Unit tests for seed_containers_fvv
# ---------------------------------------------------------------------------


class TestSeedContainersFvv:
    """Test that seeding creates actors on all three containers."""

    def test_seed_creates_finder_actor(self, client: TestClient, base: str):
        finder_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        finder, vendor, vendor2 = demo.seed_containers_fvv(
            finder_client=finder_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
        )
        assert finder.id_ is not None
        assert finder.name == "Finder"

    def test_seed_creates_vendor_actor(self, client: TestClient, base: str):
        finder_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        finder, vendor, vendor2 = demo.seed_containers_fvv(
            finder_client=finder_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
        )
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_creates_vendor2_actor(self, client: TestClient, base: str):
        finder_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        finder, vendor, vendor2 = demo.seed_containers_fvv(
            finder_client=finder_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
        )
        assert vendor2.id_ is not None
        assert vendor2.name == "Vendor2"

    def test_seed_registers_cross_container_peers(
        self, client: TestClient, base: str
    ):
        finder_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        finder, vendor, vendor2 = demo.seed_containers_fvv(
            finder_client=finder_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
        )

        actors = finder_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Finder" in actor_names
        assert "Vendor" in actor_names
        assert "Vendor2" in actor_names

    def test_seed_with_deterministic_ids(self, client: TestClient, base: str):
        finder_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        finder_id = f"{base}/actors/finder-fvv-det-test"
        vendor_id = f"{base}/actors/vendor-fvv-det-test"
        vendor2_id = f"{base}/actors/vendor2-fvv-det-test"

        finder, vendor, vendor2 = demo.seed_containers_fvv(
            finder_client=finder_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
            vendor2_actor_id=vendor2_id,
        )

        assert finder.id_ == finder_id
        assert vendor.id_ == vendor_id
        assert vendor2.id_ == vendor2_id


# ---------------------------------------------------------------------------
# Unit tests for reset_containers
# ---------------------------------------------------------------------------


class TestResetContainersFvv:
    """Test container reset orchestration for FVV scenario."""

    def test_reset_containers_calls_reset_for_all_targets(self):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        vendor2_client = MagicMock()
        finder_client.get.return_value = {}
        vendor_client.get.return_value = {}
        vendor2_client.get.return_value = {}

        with patch(
            "vultron.demo.scenario.fvv_demo.reset_datalayer",
            return_value={"status": "ok"},
        ) as reset_mock:
            demo.reset_containers(
                finder_client=finder_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
            )

        reset_mock.assert_has_calls(
            [
                call(client=finder_client, init=False),
                call(client=vendor_client, init=False),
                call(client=vendor2_client, init=False),
            ]
        )


# ---------------------------------------------------------------------------
# CLI integration test
# ---------------------------------------------------------------------------


class TestFvvCliCommand:
    """Test that the 'fvv' CLI sub-command is registered and reachable."""

    def test_fvv_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvv", "--help"])
        assert result.exit_code == 0, result.output
        assert "Finder" in result.output or "fvv" in result.output.lower()

    def test_fvv_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvv", "--help"])
        assert "--skip-health-check" in result.output

    def test_fvv_command_vendor2_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvv", "--help"])
        assert "--vendor2-url" in result.output
