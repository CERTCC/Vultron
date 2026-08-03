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

"""Unit tests for the FVCV-handoff five-actor CVD demo (DEMOMA-15).

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=fvcv-handoff docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
from unittest.mock import MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fvcv_handoff_demo as demo
from test.demo._helpers import make_testclient_call
from vultron.demo.cli import main


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture(scope="module", autouse=True)
def patch_datalayer_call(client: TestClient, base: str):
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
# Unit tests for _phase_dump_case_ledgers
# ---------------------------------------------------------------------------


class TestPhaseDumpCaseLedgersFvcv:
    """Tests for the case-ledger dump phase in the FVCV-handoff demo."""

    def test_writes_jsonl_files_for_all_four_actors(
        self, tmp_path, monkeypatch
    ):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        coordinator_client = MagicMock()
        vendor2_client = MagicMock()
        finder_client.get_list.return_value = [{"logIndex": 0}]
        vendor_client.get_list.return_value = [{"logIndex": 0}]
        coordinator_client.get_list.return_value = [{"logIndex": 0}]
        vendor2_client.get_list.return_value = [{"logIndex": 0}]

        case = demo.as_VulnerabilityCase(
            id_="https://example.org/cases/fvcv-test-case"
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            case=case,
        )

        case_slug = "https_example.org_cases_fvcv-test-case"
        assert (
            tmp_path
            / "fvcv-handoff"
            / "finder"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "fvcv-handoff"
            / "vendor"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "fvcv-handoff"
            / "coordinator"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "fvcv-handoff"
            / "vendor2"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()

    def test_includes_case_actor_when_in_participant_index(
        self, tmp_path, monkeypatch
    ):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        coordinator_client = MagicMock()
        vendor2_client = MagicMock()
        finder_client.get_list.return_value = [{"logIndex": 0}]
        vendor_client.get_list.return_value = [{"logIndex": 0}]
        coordinator_client.get_list.return_value = [{"logIndex": 0}]
        vendor2_client.get_list.return_value = [{"logIndex": 0}]

        case = demo.as_VulnerabilityCase(
            id_="https://example.org/cases/fvcv-with-ca",
            actor_participant_index={
                "https://example.org/actors/case-actor-fvcv": (
                    "https://example.org/cases/fvcv-with-ca/participants/case-actor"
                )
            },
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            case=case,
        )

        assert any(
            "/actors/case-actor-fvcv/demo/cases/fvcv-with-ca/log"
            in call.args[0]
            for call in vendor_client.get_list.call_args_list
        )


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestFvcvHandoffCliCommand:
    """Test that the 'fvcv-handoff' CLI sub-command is registered and reachable."""

    def test_fvcv_handoff_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert result.exit_code == 0, result.output

    def test_fvcv_handoff_command_finder_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--finder-url" in result.output

    def test_fvcv_handoff_command_vendor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--vendor-url" in result.output

    def test_fvcv_handoff_command_coordinator_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--coordinator-url" in result.output

    def test_fvcv_handoff_command_vendor2_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--vendor2-url" in result.output

    def test_fvcv_handoff_command_case_actor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--case-actor-url" in result.output

    def test_fvcv_handoff_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--skip-health-check" in result.output
