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
from vultron.demo.helpers.polling import wait_for_contiguous_ledger_coverage

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


# ---------------------------------------------------------------------------
# Regression tests: wait_for_contiguous_ledger_coverage (issue #1363)
# ---------------------------------------------------------------------------


class TestWaitForContiguousLedgerCoverage:
    """Regression tests for the pre-dump ledger coverage gate (issue #1363).

    The bug: _phase_case_closure waited only for the tail entry hash before
    dumping logs.  Because Announce(CaseLedgerEntry) activities arrive
    independently, an intermediate entry (e.g. logIndex=17) could arrive after
    the tail, leaving the JSONL with a gap.

    wait_for_contiguous_ledger_coverage closes this race by verifying that
    ALL indices 0…expected_tail_index are present before the dump proceeds.
    """

    def _make_raw_entries(self, case_id: str, indices: list[int]) -> dict:
        """Build the dict structure returned by GET /datalayer/CaseLedgerEntrys/."""
        return {
            f"entry-{i}": {
                "case_id": case_id,
                "log_index": i,
                "entry_hash": f"hash{i:04d}",
            }
            for i in indices
        }

    def test_returns_when_all_indices_present(self):
        """Returns immediately when indices 0…N are all present (happy path)."""
        case_id = "https://example.org/cases/test-coverage-1"
        client = MagicMock()
        client.get.return_value = self._make_raw_entries(
            case_id, list(range(5))
        )

        wait_for_contiguous_ledger_coverage(
            client=client,
            case_id=case_id,
            expected_tail_index=4,
            timeout_seconds=1.0,
        )
        assert client.get.call_count >= 1

    def test_raises_when_intermediate_index_missing(self):
        """Raises AssertionError when an intermediate entry (the bug) is absent.

        Simulates the race: indices 0…16, 18…20 are present but index 17 is
        missing, reproducing the exact failure from issue #1363.
        """
        case_id = "https://example.org/cases/test-coverage-2"
        indices_with_gap = list(range(17)) + list(range(18, 21))
        client = MagicMock()
        client.get.return_value = self._make_raw_entries(
            case_id, indices_with_gap
        )

        with pytest.raises(AssertionError, match="contiguous ledger coverage"):
            wait_for_contiguous_ledger_coverage(
                client=client,
                case_id=case_id,
                expected_tail_index=20,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_raises_when_tail_present_but_early_entries_missing(self):
        """Raises when the tail arrived but early entries are absent.

        This is the exact race: tail (logIndex=N) arrives first via
        Announce, but logIndex=17 (or similar) arrives later.
        wait_for_finder_log_entry would have returned True here, but
        wait_for_contiguous_ledger_coverage correctly waits.
        """
        case_id = "https://example.org/cases/test-coverage-3"
        # Present: only the tail entry (index=5), missing 0-4
        client = MagicMock()
        client.get.return_value = self._make_raw_entries(case_id, [5])

        with pytest.raises(AssertionError, match="contiguous ledger coverage"):
            wait_for_contiguous_ledger_coverage(
                client=client,
                case_id=case_id,
                expected_tail_index=5,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_ignores_entries_for_other_cases(self):
        """Does not count entries from other cases toward coverage."""
        case_id = "https://example.org/cases/target-case"
        other_case_id = "https://example.org/cases/other-case"
        client = MagicMock()
        # Indices 0-3 belong to the target case; 4-9 belong to another case
        target_entries = self._make_raw_entries(case_id, list(range(4)))
        other_entries = self._make_raw_entries(
            other_case_id, list(range(4, 10))
        )
        client.get.return_value = {**target_entries, **other_entries}

        with pytest.raises(AssertionError, match="contiguous ledger coverage"):
            wait_for_contiguous_ledger_coverage(
                client=client,
                case_id=case_id,
                expected_tail_index=5,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_raises_when_no_entries_present(self):
        """Raises when the DataLayer returns no entries at all."""
        case_id = "https://example.org/cases/test-coverage-4"
        client = MagicMock()
        client.get.return_value = {}

        with pytest.raises(AssertionError, match="contiguous ledger coverage"):
            wait_for_contiguous_ledger_coverage(
                client=client,
                case_id=case_id,
                expected_tail_index=3,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )
