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

"""Unit tests for the RCV three-actor CVD demo (DEMOMA-12).

Uses a single TestClient (one FastAPI app instance) to simulate three containers.
All three DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=rcv docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
import json
from unittest.mock import MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.rcv_demo as demo
from test.demo._helpers import (
    make_client,
    make_testclient_call,
)
from vultron.demo.cli import main
from vultron.demo.helpers import seeding
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
# Unit tests for seed_containers_rcv
# ---------------------------------------------------------------------------


class TestSeedContainersRcv:
    """Test that seeding creates actors on all three containers."""

    def test_seed_creates_all_three_actors(self, base: str):
        reporter, coordinator, vendor = seeding.seed_containers_rcv(
            reporter_client=make_client(base),
            coordinator_client=make_client(base),
            vendor_client=make_client(base),
        )
        assert reporter.id_ is not None
        assert reporter.name == "Reporter"
        assert coordinator.id_ is not None
        assert coordinator.name == "Coordinator"
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_registers_cross_container_peers(self, base: str):
        reporter_client = make_client(base)

        seeding.seed_containers_rcv(
            reporter_client=reporter_client,
            coordinator_client=make_client(base),
            vendor_client=make_client(base),
        )

        actors = reporter_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Reporter" in actor_names
        assert "Coordinator" in actor_names
        assert "Vendor" in actor_names

    def test_seed_with_deterministic_ids(self, base: str):
        reporter_id = f"{base}/actors/reporter-rcv-det-test"
        coordinator_id = f"{base}/actors/coordinator-rcv-det-test"
        vendor_id = f"{base}/actors/vendor-rcv-det-test"

        reporter, coordinator, vendor = seeding.seed_containers_rcv(
            reporter_client=make_client(base),
            coordinator_client=make_client(base),
            vendor_client=make_client(base),
            reporter_actor_id=reporter_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
        )

        assert reporter.id_ == reporter_id
        assert coordinator.id_ == coordinator_id
        assert vendor.id_ == vendor_id


# ---------------------------------------------------------------------------
# find_case_invite_for_actor tests
# ---------------------------------------------------------------------------


def _archived(rows: dict[str, dict]) -> dict[str, dict]:
    """*rows*, keyed by activity id, as intake archives them (DL-06-006).

    The invitee holds a received Invite only as a ``ReceivedActivityRecord``
    under its own key, never under the sender's id.
    """
    return {
        f"received-activity/{activity_id}": {
            "type": "ReceivedActivityRecord",
            "id": f"received-activity/{activity_id}",
            "received_body": json.dumps({"id": activity_id, **row}),
        }
        for activity_id, row in rows.items()
    }


@pytest.mark.spec("CM-17-001")
@pytest.mark.spec("CM-17-004")
class TestFindCaseInviteForActor:
    """Test the shared polling helper that locates the CaseActor Invite for the invitee."""

    CASE_ID = "urn:uuid:case-1"
    INVITEE_ID = "http://vendor:7999/api/v2/actors/vendor"

    def _invite(self, target, obj):
        return {"type": "Invite", "target": target, "object": obj}

    def test_matches_invite_with_dict_target_and_object(self):
        client = MagicMock()
        client.get.return_value = _archived(
            {
                "urn:uuid:invite-1": self._invite(
                    {"id": self.CASE_ID}, {"id": self.INVITEE_ID}
                )
            }
        )
        result = find_case_invite_for_actor(
            client=client,
            case_id=self.CASE_ID,
            invitee_id=self.INVITEE_ID,
            timeout_seconds=1.0,
        )
        assert result == "urn:uuid:invite-1"

    def test_matches_invite_with_bare_string_target_and_object(self):
        client = MagicMock()
        client.get.return_value = _archived(
            {"urn:uuid:invite-2": self._invite(self.CASE_ID, self.INVITEE_ID)}
        )
        result = find_case_invite_for_actor(
            client=client,
            case_id=self.CASE_ID,
            invitee_id=self.INVITEE_ID,
            timeout_seconds=1.0,
        )
        assert result == "urn:uuid:invite-2"

    def test_ignores_invite_for_other_case(self):
        client = MagicMock()
        client.get.return_value = _archived(
            {
                "urn:uuid:invite-3": self._invite(
                    {"id": "urn:uuid:other-case"}, {"id": self.INVITEE_ID}
                )
            }
        )
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
        client.get.return_value = _archived(
            {
                "urn:uuid:invite-4": self._invite(
                    {"id": self.CASE_ID}, {"id": "http://elsewhere/actors/x"}
                )
            }
        )
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
        client.get.return_value = _archived(
            {
                "urn:uuid:offer-1": {
                    "type": "Offer",
                    "target": {"id": self.CASE_ID},
                    "object": {"id": self.INVITEE_ID},
                }
            }
        )
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


class TestRcvCliCommand:
    """Test that the 'rcv' CLI sub-command is registered and reachable."""

    def test_rcv_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rcv", "--help"])
        assert result.exit_code == 0, result.output

    def test_rcv_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rcv", "--help"])
        assert "--skip-health-check" in result.output

    def test_rcv_command_reporter_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rcv", "--help"])
        assert "--reporter-url" in result.output

    def test_rcv_command_coordinator_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rcv", "--help"])
        assert "--coordinator-url" in result.output

    def test_rcv_command_vendor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rcv", "--help"])
        assert "--vendor-url" in result.output

    def test_rcv_command_reporter_id_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rcv", "--help"])
        assert "--reporter-id" in result.output

    def test_rcv_command_coordinator_id_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rcv", "--help"])
        assert "--coordinator-id" in result.output

    def test_rcv_command_vendor_id_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rcv", "--help"])
        assert "--vendor-id" in result.output
