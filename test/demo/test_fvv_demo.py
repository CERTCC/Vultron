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
from vultron.demo.helpers.polling import (
    wait_for_contiguous_ledger_coverage,
    wait_for_event_type_in_ledger,
)

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


@pytest.mark.spec("VP-08-004")
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
                call(client=finder_client),
                call(client=vendor_client),
                call(client=vendor2_client),
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

    def test_default_timeout_is_sufficient_for_ci_load(self):
        """Default timeout must be >= 30s to survive CI scheduling latency.

        The fv Demo Integration job intermittently failed with 2 cascading
        demo_check failures when wait_for_contiguous_ledger_coverage timed out
        after 15s in _phase_sync_verification under CI load (issue #1911).
        The second failure (verify_finder_replica_state) cascades because it
        runs immediately after and finds an empty replica.

        Regression: ensure the default is at least 30s so the inter-container
        Announce(CaseLedgerEntry) fan-out has time to complete under load.
        """
        import inspect

        sig = inspect.signature(wait_for_contiguous_ledger_coverage)
        default_timeout = sig.parameters["timeout_seconds"].default
        assert default_timeout >= 30.0, (
            f"wait_for_contiguous_ledger_coverage default timeout is "
            f"{default_timeout}s — must be >= 30s to tolerate CI load "
            f"(issue #1911)"
        )


# ---------------------------------------------------------------------------
# Regression tests: Bug A — coverage-wait timeout must not crash demo
# (issue #1772, #1802)
# ---------------------------------------------------------------------------


class TestCoverageWaitInsideDemoCheck:
    """Regression: bare wait_for_contiguous_ledger_coverage outside demo_check
    crashes demo with exit code 1 when it times out.

    After the fix, a timeout should accumulate to _demo_failures and allow
    _phase_dump_case_ledgers to run (exit 0 with a failure summary).
    """

    def test_coverage_wait_timeout_accumulates_to_demo_failures_not_raises(
        self,
    ):
        """A timed-out coverage wait inside _phase_case_closure must NOT raise.

        Bug A: the bare wait_for_contiguous_ledger_coverage call propagated
        AssertionError through _phase_case_closure, crashing the demo runner.
        After the fix, every coverage wait is inside a demo_check context,
        so the timeout is recorded in _demo_failures and the phase returns
        normally.

        We verify this by patching wait_for_contiguous_ledger_coverage to
        always raise AssertionError and confirming _phase_case_closure does
        not propagate the exception.
        """
        import vultron.demo.utils as utils_module  # noqa: PLC0415

        utils_module.reset_demo_failures()

        case_id = "https://example.org/cases/bug-a-regression"

        # Build minimal mocks that satisfy _phase_case_closure's early calls
        # (actor_closes_case, wait_for_all_participants_rm_closed, verify_case_closed,
        # _get_log_entries_for_case) without triggering real HTTP.
        client = MagicMock()
        actor = MagicMock()
        actor.id_ = "https://example.org/actors/test-actor"

        case = MagicMock()
        case.id_ = case_id

        # _get_log_entries_for_case reads from /datalayer/CaseLedgerEntrys/
        # Return a single entry so the tail-read branch is taken.
        client.get.return_value = {
            "e0": {
                "case_id": case_id,
                "log_index": 0,
                "entry_hash": "hash0000",
                "event_type": "close_case",
            }
        }

        initial_failures = len(utils_module._demo_failures)

        with (
            patch("vultron.demo.scenario.fvv_demo.actor_closes_case"),
            patch(
                "vultron.demo.scenario.fvv_demo.wait_for_all_participants_rm_closed"
            ),
            patch("vultron.demo.scenario.fvv_demo.verify_case_closed"),
            patch(
                "vultron.demo.scenario.fvv_demo.wait_for_event_type_in_ledger"
            ),
            patch(
                "vultron.demo.scenario.fvv_demo.wait_for_contiguous_ledger_coverage",
                side_effect=AssertionError(
                    "contiguous ledger coverage timeout"
                ),
            ),
        ):
            try:
                demo._phase_case_closure(
                    finder_client=client,
                    vendor_client=client,
                    vendor2_client=client,
                    vendor=actor,
                    vendor_in_vendor=actor,
                    vendor2=actor,
                    vendor2_in_vendor2=actor,
                    finder=actor,
                    finder_in_finder=actor,
                    case=case,
                )
            except AssertionError as exc:
                pytest.fail(
                    f"Bug A regression: AssertionError propagated out of "
                    f"_phase_case_closure: {exc}"
                )

        # The failure must be accumulated, not raised.
        assert (
            len(utils_module._demo_failures) > initial_failures
        ), "Expected the coverage-wait timeout to be recorded in _demo_failures"


# ---------------------------------------------------------------------------
# Regression tests: Bug B — wait_for_event_type_in_ledger helper
# (issue #1772)
# ---------------------------------------------------------------------------


class TestWaitForEventTypeInLedger:
    """Regression: the close phase must wait for close_case to appear on the
    authoritative actor before reading the tail index for replica coverage.

    Without this wait, the tail excludes close_case (committed asynchronously
    after the last RM.CLOSED); coverage 'succeeds' for the wrong tail; the
    dump runs before close_case replicates; invariant harness fails.
    """

    def _make_entries(self, case_id: str, event_types: list[str]) -> dict:
        return {
            f"e{i}": {
                "case_id": case_id,
                "log_index": i,
                "entry_hash": f"hash{i:04d}",
                "event_type": et,
            }
            for i, et in enumerate(event_types)
        }

    def test_returns_when_event_type_present(self):
        """Returns immediately when the target event_type is already in the log."""
        case_id = "https://example.org/cases/bug-b-present"
        client = MagicMock()
        client.get.return_value = self._make_entries(
            case_id, ["validate_report", "close_case"]
        )

        wait_for_event_type_in_ledger(
            client=client,
            case_id=case_id,
            event_type="close_case",
            timeout_seconds=1.0,
        )
        assert client.get.call_count >= 1

    def test_raises_when_event_type_absent(self):
        """Raises AssertionError when target event_type never appears."""
        case_id = "https://example.org/cases/bug-b-absent"
        client = MagicMock()
        client.get.return_value = self._make_entries(
            case_id,
            ["validate_report", "add_participant_status_to_participant"],
        )

        with pytest.raises(AssertionError, match="close_case"):
            wait_for_event_type_in_ledger(
                client=client,
                case_id=case_id,
                event_type="close_case",
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_ignores_entries_from_other_cases(self):
        """Does not count close_case entries from other cases."""
        case_id = "https://example.org/cases/bug-b-target"
        other_case_id = "https://example.org/cases/bug-b-other"
        client = MagicMock()
        entries = self._make_entries(case_id, ["validate_report"])
        other_entries = {
            "other-e0": {
                "case_id": other_case_id,
                "log_index": 0,
                "entry_hash": "hashOther",
                "event_type": "close_case",
            }
        }
        client.get.return_value = {**entries, **other_entries}

        with pytest.raises(AssertionError, match="close_case"):
            wait_for_event_type_in_ledger(
                client=client,
                case_id=case_id,
                event_type="close_case",
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_eventually_returns_when_event_arrives(self):
        """Returns once the event_type appears after a few polls."""
        case_id = "https://example.org/cases/bug-b-eventual"
        call_count = 0
        no_close_entries = {
            "e0": {
                "case_id": case_id,
                "log_index": 0,
                "entry_hash": "hash0000",
                "event_type": "validate_report",
            }
        }
        with_close_entries = {
            **no_close_entries,
            "e1": {
                "case_id": case_id,
                "log_index": 1,
                "entry_hash": "hash0001",
                "event_type": "close_case",
            },
        }

        def _get_side_effect(path: str):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return no_close_entries
            return with_close_entries

        client = MagicMock()
        client.get.side_effect = _get_side_effect

        wait_for_event_type_in_ledger(
            client=client,
            case_id=case_id,
            event_type="close_case",
            timeout_seconds=5.0,
            poll_interval=0.05,
        )
        assert call_count >= 3


# ---------------------------------------------------------------------------
# Milestone assertion tests — AC-4 of ISSUE-1976
# ---------------------------------------------------------------------------


class TestFvvMilestoneAssertions:
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

    @pytest.mark.spec("CM-12-001")
    @pytest.mark.spec("VP-02-015")
    def test_phase_report_submission_calls_verify_case_active(self):
        """_phase_report_submission calls verify_case_active at M1."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        finder = self._actor("urn:test:finder")
        vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        invite = MagicMock()
        invite.id_ = "urn:test:invite"
        case = self._case()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fvv",
                return_value=(finder, vendor, vendor2),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[vendor_in_vendor, vendor2_in_vendor2],
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_finder_case"),
            patch.object(
                demo,
                "post_to_trigger",
                return_value={"activity": {"id": invite.id_}},
            ),
            patch.object(demo, "find_case_invite_for_actor"),
            patch.object(demo, "wait_for_case_on_container"),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(demo, "run_invite_path_rm_triage"),
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
            mock_ta.model_validate.return_value = invite
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                finder_id=None,
                vendor_id=None,
                vendor2_id=None,
            )
        mock_m1.assert_called()

    def test_phase_fix_lifecycle_calls_verify_fix_ready(self):
        """_phase_fix_lifecycle calls verify_fix_ready at M4/M5."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        with (
            patch.object(demo, "wait_for_participant_rm_state"),
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
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                case=case,
            )
        mock_m4.assert_called()

    def test_phase_fix_lifecycle_gates_on_rm_accepted(self):
        """_phase_fix_lifecycle polls each vendor RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (ADR-0058/CSB-18-001)."""
        from vultron.core.states.rm import RM

        finder_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        call_order = []
        rm_calls = []

        def _rm_wait(*a, **kw):
            rm_calls.append(kw)
            call_order.append("rm_wait")

        with (
            patch.object(demo, "wait_for_participant_rm_state", _rm_wait),
            patch.object(
                demo,
                "actor_notifies_fix_ready",
                side_effect=lambda *a, **kw: call_order.append("fix_ready"),
            ),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_fix_ready"),
        ):
            demo._phase_fix_lifecycle(
                finder_client=finder_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                case=case,
            )

        assert (
            len(rm_calls) == 2
        ), f"wait_for_participant_rm_state must be called once per vendor (got {len(rm_calls)}) (ADR-0058/CSB-18-001)"
        assert all(
            c.get("expected_states") == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), "expected_states must be {ACCEPTED, DEFERRED, CLOSED} for each vendor (CSB-18-001)"
        assert "rm_wait" in call_order and "fix_ready" in call_order
        assert call_order.index("rm_wait") < call_order.index(
            "fix_ready"
        ), "wait_for_participant_rm_state must precede actor_notifies_fix_ready (ADR-0058)"

    def test_phase_publication_calls_verify_publicly_disclosed(self):
        """_phase_publication calls verify_publicly_disclosed at M6."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
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
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
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
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
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
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                finder=finder,
                finder_in_finder=finder_in_finder,
                case=case,
            )
        mock_m7.assert_called()


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaWaitBeforeVendor2Triage:
    """CLP-08-005: Finder replica wait must precede invite-path RM triage in fvv."""

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

    def test_finder_wait_before_vendor2_triage(self):
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        finder = self._actor("urn:test:finder")
        vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        invite = MagicMock()
        invite.id_ = "urn:test:invite"
        case = self._case()

        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kw):
            if client is finder_client:
                call_order.append("finder_wait")

        def _triage(**_kw):
            call_order.append("triage")

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fvv",
                return_value=(finder, vendor, vendor2),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[vendor_in_vendor, vendor2_in_vendor2],
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_finder_case"),
            patch.object(
                demo,
                "post_to_trigger",
                return_value={"activity": {"id": invite.id_}},
            ),
            patch.object(demo, "find_case_invite_for_actor"),
            patch.object(
                demo,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(
                demo, "run_invite_path_rm_triage", side_effect=_triage
            ),
            patch.object(demo, "verify_case_active"),
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
            mock_ta.model_validate.return_value = invite
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                finder_id=None,
                vendor_id=None,
                vendor2_id=None,
            )

        assert (
            "finder_wait" in call_order
        ), "wait_for_case_on_container(finder_client) never called"
        assert "triage" in call_order, "run_invite_path_rm_triage never called"
        finder_idx = next(
            i for i, v in enumerate(call_order) if v == "finder_wait"
        )
        triage_idx = next(i for i, v in enumerate(call_order) if v == "triage")
        assert finder_idx < triage_idx, (
            "Finder replica wait must precede run_invite_path_rm_triage; "
            f"got order: {call_order}"
        )
