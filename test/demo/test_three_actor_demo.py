#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.

"""Unit tests for the three-actor multi-container demo (D5-3)."""

import importlib
import logging
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.three_actor_demo as demo
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
    """Tests for three-actor seeding."""

    def test_seed_containers_creates_local_actors(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)
        coordinator_client = _make_client(base)
        case_actor_client = _make_client(base)

        finder, vendor, coordinator, case_actor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
        )

        assert finder.name == "Finder"
        assert vendor.name == "Vendor"
        assert coordinator.name == "Coordinator"
        assert case_actor.name == "CaseActor"


class TestCoordinatorCreatesCase:
    """Tests for authoritative case creation on the CaseActor container."""

    def test_case_is_created_only_on_case_actor(
        self, client: TestClient, base: str
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)
        coordinator_client = _make_client(base)
        case_actor_client = _make_client(base)

        demo.reset_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
        )
        finder, _vendor, coordinator, case_actor = demo.seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
        )
        coordinator_in_coordinator = demo.get_actor_by_id(
            coordinator_client, coordinator.id_
        )

        report, _offer = demo.finder_submits_report_to_coordinator(
            coordinator_client=coordinator_client,
            finder=finder,
            coordinator=coordinator_in_coordinator,
        )
        case = demo.coordinator_creates_case_on_case_actor(
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            case_actor=case_actor,
            coordinator=coordinator_in_coordinator,
            report=report,
        )

        assert case.id_ is not None
        case_ids = case_actor_client.get("/datalayer/VulnerabilityCases/")
        assert case.id_ in case_ids


class TestRunThreeActorDemo:
    """Integration-style tests for the full demo flow."""

    def test_full_workflow_succeeds(
        self, client: TestClient, base: str, caplog
    ):
        finder_client = _make_client(base)
        vendor_client = _make_client(base)
        coordinator_client = _make_client(base)
        case_actor_client = _make_client(base)

        with caplog.at_level(logging.ERROR):
            demo.run_three_actor_demo(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
            )

        assert "ERROR SUMMARY" not in caplog.text, (
            "Expected three-actor demo to succeed, but got errors:\n"
            + caplog.text
        )

        case_records = case_actor_client.get("/datalayer/VulnerabilityCases/")
        final_cases = [
            demo.VulnerabilityCase(**case_data)
            for case_data in case_records.values()
        ]
        matching_cases = [
            case
            for case in final_cases
            if len(case.case_participants) == 3
            and case.current_status.em_state == demo.EM.ACTIVE
        ]
        assert len(matching_cases) == 1
        final_case = matching_cases[0]
        embargo_id = demo.ref_id(final_case.active_embargo)
        assert embargo_id is not None

        participant_records = case_actor_client.get(
            "/datalayer/CaseParticipants/"
        )
        for participant_id in final_case.actor_participant_index.values():
            participant = participant_records[participant_id]
            assert embargo_id in participant["accepted_embargo_ids"]


class TestThreeActorCLI:
    """Tests for CLI registration and invocation."""

    def test_cli_command_registered(self):
        from vultron.demo.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["three-actor", "--help"])
        assert result.exit_code == 0
        assert "three-actor" in result.output.lower()

    def test_cli_runs_demo(self, client: TestClient, base: str):
        from vultron.demo.cli import main

        patched_run = MagicMock()
        with patch(
            "vultron.demo.scenario.three_actor_demo.run_three_actor_demo",
            patched_run,
        ):
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "three-actor",
                    "--skip-health-check",
                    "--finder-url",
                    base,
                    "--vendor-url",
                    base,
                    "--coordinator-url",
                    base,
                    "--case-actor-url",
                    base,
                ],
            )

        assert result.exit_code == 0, result.output
        patched_run.assert_called_once()
