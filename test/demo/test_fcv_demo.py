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

"""Unit tests for the FCV three-actor CVD demo (DEMOMA-12).

Uses a single TestClient (one FastAPI app instance) to simulate three containers.
All three DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=fcv docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
from unittest.mock import MagicMock, call, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fcv_demo as demo
from test.demo._helpers import make_client, make_testclient_call
from vultron.demo.cli import main
from vultron.demo.helpers.polling import find_case_invite_for_actor

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
# Unit tests for seed_containers_fcv
# ---------------------------------------------------------------------------


class TestSeedContainersFcv:
    """Test that seeding creates actors on all three containers."""

    def test_seed_creates_all_three_actors(self, base: str):
        finder, coordinator, vendor = demo.seed_containers_fcv(
            finder_client=make_client(base),
            coordinator_client=make_client(base),
            vendor_client=make_client(base),
        )
        assert finder.id_ is not None
        assert finder.name == "Finder"
        assert coordinator.id_ is not None
        assert coordinator.name == "Coordinator"
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_registers_cross_container_peers(self, base: str):
        finder_client = make_client(base)

        demo.seed_containers_fcv(
            finder_client=finder_client,
            coordinator_client=make_client(base),
            vendor_client=make_client(base),
        )

        actors = finder_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Finder" in actor_names
        assert "Coordinator" in actor_names
        assert "Vendor" in actor_names

    def test_seed_with_deterministic_ids(self, base: str):
        finder_id = f"{base}/actors/finder-fcv-det-test"
        coordinator_id = f"{base}/actors/coordinator-fcv-det-test"
        vendor_id = f"{base}/actors/vendor-fcv-det-test"

        finder, coordinator, vendor = demo.seed_containers_fcv(
            finder_client=make_client(base),
            coordinator_client=make_client(base),
            vendor_client=make_client(base),
            reporter_actor_id=finder_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
        )

        assert finder.id_ == finder_id
        assert coordinator.id_ == coordinator_id
        assert vendor.id_ == vendor_id


# ---------------------------------------------------------------------------
# Unit tests for reset_containers
# ---------------------------------------------------------------------------


class TestResetContainersFcv:
    """Test container reset orchestration for FCV scenario."""

    def test_reset_containers_calls_reset_for_all_targets(self):
        finder_client = MagicMock()
        coordinator_client = MagicMock()
        vendor_client = MagicMock()
        finder_client.get.return_value = {}
        coordinator_client.get.return_value = {}
        vendor_client.get.return_value = {}

        with patch(
            "vultron.demo.scenario.fcv_demo.reset_datalayer",
            return_value={"status": "ok"},
        ) as reset_mock:
            demo.reset_containers(
                finder_client=finder_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
            )

        reset_mock.assert_has_calls(
            [
                call(client=finder_client, init=False),
                call(client=coordinator_client, init=False),
                call(client=vendor_client, init=False),
            ]
        )

    def test_reset_includes_case_actor_when_provided(self):
        finder_client = MagicMock()
        coordinator_client = MagicMock()
        vendor_client = MagicMock()
        case_actor_client = MagicMock()

        with patch(
            "vultron.demo.scenario.fcv_demo.reset_datalayer",
            return_value={"status": "ok"},
        ) as reset_mock:
            demo.reset_containers(
                finder_client=finder_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
            )

        called_clients = [
            c.kwargs["client"] for c in reset_mock.call_args_list
        ]
        assert case_actor_client in called_clients


# ---------------------------------------------------------------------------
# find_case_invite_for_actor tests
# ---------------------------------------------------------------------------


class TestFindCaseInviteForActor:
    """Test the shared polling helper that locates the CaseActor Invite for the invitee."""

    CASE_ID = "urn:uuid:case-1"
    INVITEE_ID = "http://vendor:7999/api/v2/actors/vendor"

    def _invite(self, target, obj):
        return {"type": "Invite", "target": target, "object": obj}

    def test_matches_invite_with_dict_target_and_object(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-1": self._invite(
                {"id": self.CASE_ID}, {"id": self.INVITEE_ID}
            )
        }
        result = find_case_invite_for_actor(
            client=client,
            case_id=self.CASE_ID,
            invitee_id=self.INVITEE_ID,
            timeout_seconds=1.0,
        )
        assert result == "urn:uuid:invite-1"

    def test_matches_invite_with_bare_string_target_and_object(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-2": self._invite(self.CASE_ID, self.INVITEE_ID)
        }
        result = find_case_invite_for_actor(
            client=client,
            case_id=self.CASE_ID,
            invitee_id=self.INVITEE_ID,
            timeout_seconds=1.0,
        )
        assert result == "urn:uuid:invite-2"

    def test_ignores_invite_for_other_case(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-3": self._invite(
                {"id": "urn:uuid:other-case"}, {"id": self.INVITEE_ID}
            )
        }
        with pytest.raises(AssertionError, match="Timed out waiting"):
            find_case_invite_for_actor(
                client=client,
                case_id=self.CASE_ID,
                invitee_id=self.INVITEE_ID,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_ignores_invite_for_other_actor(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-4": self._invite(
                {"id": self.CASE_ID}, {"id": "http://elsewhere/actors/x"}
            )
        }
        with pytest.raises(AssertionError, match="Timed out waiting"):
            find_case_invite_for_actor(
                client=client,
                case_id=self.CASE_ID,
                invitee_id=self.INVITEE_ID,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_ignores_non_invite_activities(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:offer-1": {
                "type": "Offer",
                "target": {"id": self.CASE_ID},
                "object": {"id": self.INVITEE_ID},
            }
        }
        with pytest.raises(AssertionError, match="Timed out waiting"):
            find_case_invite_for_actor(
                client=client,
                case_id=self.CASE_ID,
                invitee_id=self.INVITEE_ID,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestFcvCliCommand:
    """Test that the 'fcv' CLI sub-command is registered and reachable."""

    def test_fcv_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert result.exit_code == 0, result.output

    def test_fcv_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--skip-health-check" in result.output

    def test_fcv_command_finder_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--finder-url" in result.output

    def test_fcv_command_coordinator_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--coordinator-url" in result.output

    def test_fcv_command_vendor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--vendor-url" in result.output

    def test_fcv_command_finder_id_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--finder-id" in result.output

    def test_fcv_command_coordinator_id_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--coordinator-id" in result.output

    def test_fcv_command_vendor_id_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--vendor-id" in result.output
