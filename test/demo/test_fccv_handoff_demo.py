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

"""Unit tests for the FCCV-handoff four-actor CVD demo (DEMOMA-14).

Uses a single TestClient (one FastAPI app instance) to simulate five containers.
All DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=fccv-handoff docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
from unittest.mock import MagicMock, call, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fccv_handoff_demo as demo
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
# Unit tests for seed_containers_fccv
# ---------------------------------------------------------------------------


class TestSeedContainersFccv:
    """Test that seeding creates actors on all four containers."""

    def test_seed_creates_all_four_actors(self, base: str):
        from vultron.demo.helpers.seeding import seed_containers_fccv

        finder, c1, c2, vendor = seed_containers_fccv(
            finder_client=make_client(base),
            c1_client=make_client(base),
            c2_client=make_client(base),
            vendor_client=make_client(base),
        )
        assert finder.id_ is not None
        assert finder.name == "Finder"
        assert c1.id_ is not None
        assert c1.name == "Coordinator1"
        assert c2.id_ is not None
        assert c2.name == "Coordinator2"
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_registers_cross_container_peers(self, base: str):
        from vultron.demo.helpers.seeding import seed_containers_fccv

        finder_client = make_client(base)

        seed_containers_fccv(
            finder_client=finder_client,
            c1_client=make_client(base),
            c2_client=make_client(base),
            vendor_client=make_client(base),
        )

        actors = finder_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Finder" in actor_names
        assert "Coordinator1" in actor_names
        assert "Coordinator2" in actor_names
        assert "Vendor" in actor_names

    def test_seed_with_deterministic_ids(self, base: str):
        from vultron.demo.helpers.seeding import seed_containers_fccv

        finder_id = f"{base}/actors/finder-fccv-det-test"
        c1_id = f"{base}/actors/c1-fccv-det-test"
        c2_id = f"{base}/actors/c2-fccv-det-test"
        vendor_id = f"{base}/actors/vendor-fccv-det-test"

        finder, c1, c2, vendor = seed_containers_fccv(
            finder_client=make_client(base),
            c1_client=make_client(base),
            c2_client=make_client(base),
            vendor_client=make_client(base),
            reporter_actor_id=finder_id,
            c1_actor_id=c1_id,
            c2_actor_id=c2_id,
            vendor_actor_id=vendor_id,
        )

        assert finder.id_ == finder_id
        assert c1.id_ == c1_id
        assert c2.id_ == c2_id
        assert vendor.id_ == vendor_id


# ---------------------------------------------------------------------------
# Unit tests for reset_containers
# ---------------------------------------------------------------------------


class TestResetContainersFccv:
    """Test container reset orchestration for FCCV-handoff scenario."""

    def test_reset_containers_calls_reset_for_all_targets(self):
        finder_client = MagicMock()
        c1_client = MagicMock()
        c2_client = MagicMock()
        case_actor_client = MagicMock()
        vendor_client = MagicMock()
        finder_client.get.return_value = {}
        c1_client.get.return_value = {}
        c2_client.get.return_value = {}
        case_actor_client.get.return_value = {}
        vendor_client.get.return_value = {}

        with patch(
            "vultron.demo.scenario.fccv_handoff_demo.reset_datalayer",
            return_value={"status": "ok"},
        ) as reset_mock:
            demo.reset_containers(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                case_actor_client=case_actor_client,
                vendor_client=vendor_client,
            )

        reset_mock.assert_has_calls(
            [
                call(client=finder_client, init=False),
                call(client=c1_client, init=False),
                call(client=c2_client, init=False),
                call(client=case_actor_client, init=False),
                call(client=vendor_client, init=False),
            ]
        )


# ---------------------------------------------------------------------------
# Unit tests for _wait_for_case_attributed_to
# ---------------------------------------------------------------------------


class TestWaitForCaseAttributedTo:
    """Test the polling helper that waits for case attributed_to to match."""

    def test_returns_immediately_when_attributed_to_matches(self):
        client = MagicMock()
        client.get.return_value = {
            "attributedTo": {"id": "http://c2/actors/c2"}
        }
        demo._wait_for_case_attributed_to(
            client=client,
            case_id="urn:uuid:case-1",
            expected_attributed_to="http://c2/actors/c2",
            timeout_seconds=1.0,
        )
        assert client.get.call_count >= 1

    def test_raises_on_timeout_when_attributed_to_never_matches(self):
        client = MagicMock()
        client.get.return_value = {
            "attributedTo": {"id": "http://c1/actors/c1"}
        }
        with pytest.raises(AssertionError, match="Timed out waiting"):
            demo._wait_for_case_attributed_to(
                client=client,
                case_id="urn:uuid:case-1",
                expected_attributed_to="http://c2/actors/c2",
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_accepts_bare_string_attributed_to(self):
        client = MagicMock()
        client.get.return_value = {"attributedTo": "http://c2/actors/c2"}
        demo._wait_for_case_attributed_to(
            client=client,
            case_id="urn:uuid:case-1",
            expected_attributed_to="http://c2/actors/c2",
            timeout_seconds=1.0,
        )
        assert client.get.call_count >= 1


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestFccvHandoffCliCommand:
    """Test that the 'fccv-handoff' CLI sub-command is registered and reachable."""

    def test_fccv_handoff_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert result.exit_code == 0, result.output
        assert "Finder" in result.output or "fccv" in result.output.lower()

    def test_fccv_handoff_command_finder_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--finder-url" in result.output

    def test_fccv_handoff_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--skip-health-check" in result.output

    def test_fccv_handoff_command_c1_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--c1-url" in result.output

    def test_fccv_handoff_command_c2_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--c2-url" in result.output

    def test_fccv_handoff_command_vendor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--vendor-url" in result.output

    def test_fccv_handoff_command_case_actor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--case-actor-url" in result.output
