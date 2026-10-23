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

"""Unit tests for the RVV (Reporter + Vendor1 + Vendor2) multi-container CVD demo (D5-5).

Uses a single TestClient (one FastAPI app instance) to simulate three containers.
All three DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=rvv docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.helpers.sync as sync_module
import vultron.demo.scenario.rvv_demo as demo
from test.demo._helpers import (
    make_client,
    make_testclient_call,
    patch_chain_shared,
    stub_closure_gate,
)
from test.support.case_owner import CASE_OWNER_ID
from vultron.demo.actor_session import ActorSession
from vultron.demo.cli import main
from vultron.demo.helpers import closure, invite_chain
from vultron.demo.helpers.polling import (
    wait_for_contiguous_ledger_coverage,
    wait_for_semantic_type_in_ledger,
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
# Unit tests for seed_containers_rvv
# ---------------------------------------------------------------------------


@pytest.mark.spec("VP-08-004")
class TestSeedContainersRvv:
    """Test that seeding creates actors on all three containers."""

    def test_seed_creates_reporter_actor(self, client: TestClient, base: str):
        reporter_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        reporter, _vendor, _vendor2 = demo.seed_containers_rvv(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
        )
        assert reporter.id_ is not None
        assert reporter.name == "Reporter"

    def test_seed_creates_vendor_actor(self, client: TestClient, base: str):
        reporter_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        _reporter, vendor, _vendor2 = demo.seed_containers_rvv(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
        )
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_creates_vendor2_actor(self, client: TestClient, base: str):
        reporter_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        _reporter, _vendor, vendor2 = demo.seed_containers_rvv(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
        )
        assert vendor2.id_ is not None
        assert vendor2.name == "Vendor2"

    def test_seed_registers_cross_container_peers(
        self, client: TestClient, base: str
    ):
        reporter_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        _reporter, _vendor, _vendor2 = demo.seed_containers_rvv(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
        )

        actors = reporter_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Reporter" in actor_names
        assert "Vendor" in actor_names
        assert "Vendor2" in actor_names

    def test_seed_with_deterministic_ids(self, client: TestClient, base: str):
        reporter_client = make_client(base)
        vendor_client = make_client(base)
        vendor2_client = make_client(base)

        reporter_id = f"{base}/actors/reporter-rvv-det-test"
        vendor_id = f"{base}/actors/vendor-rvv-det-test"
        vendor2_id = f"{base}/actors/vendor2-rvv-det-test"

        reporter, vendor, vendor2 = demo.seed_containers_rvv(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
            reporter_actor_id=reporter_id,
            vendor_actor_id=vendor_id,
            vendor2_actor_id=vendor2_id,
        )

        assert reporter.id_ == reporter_id
        assert vendor.id_ == vendor_id
        assert vendor2.id_ == vendor2_id


# ---------------------------------------------------------------------------
# Unit tests for reset_containers
# ---------------------------------------------------------------------------


class TestResetContainersRvv:
    """Test container reset orchestration for RVV scenario."""

    def test_reset_containers_calls_reset_for_all_targets(self):
        reporter_client = MagicMock()
        vendor_client = MagicMock()
        vendor2_client = MagicMock()
        reporter_client.get.return_value = {}
        vendor_client.get.return_value = {}
        vendor2_client.get.return_value = {}
        case_actor_client = MagicMock()
        case_actor_client.get.return_value = {}

        with (
            patch(
                "vultron.demo.scenario.rvv_demo.reset_datalayer",
                return_value={"status": "ok"},
            ) as reset_mock,
            patch(
                "vultron.demo.helpers.seeding.seed_case_actor_identity"
            ) as seed_mock,
        ):
            demo.reset_containers(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                case_actor_client=case_actor_client,
            )

        reset_mock.assert_has_calls(
            [
                call(client=reporter_client),
                call(client=vendor_client),
                call(client=vendor2_client),
                call(client=case_actor_client),
            ]
        )
        # Vendor1 proposes the case to the dedicated CaseActor, so the reset
        # must re-create its identity (DEMOMA-06-004).
        seed_mock.assert_called_once_with(case_actor_client)


# ---------------------------------------------------------------------------
# CLI integration test
# ---------------------------------------------------------------------------


class TestRvvCliCommand:
    """Test that the 'rvv' CLI sub-command is registered and reachable."""

    def test_rvv_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvv", "--help"])
        assert result.exit_code == 0, result.output
        assert "Reporter" in result.output or "rvv" in result.output.lower()

    def test_rvv_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvv", "--help"])
        assert "--skip-health-check" in result.output

    def test_rvv_command_vendor2_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvv", "--help"])
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
        wait_for_reporter_log_entry would have returned True here, but
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

        The rv Demo Integration job intermittently failed with 2 cascading
        demo_check failures when wait_for_contiguous_ledger_coverage timed out
        after 15s in _phase_sync_verification under CI load (issue #1911).
        The second failure (the replica state check) cascaded because it ran
        immediately after and found an empty replica.

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
    """Regression: a bare wait_for_contiguous_ledger_coverage outside a demo
    context crashed the demo with exit code 1 when it timed out.

    The closure phase's coverage wait is each leaver's own-closure check in
    ``close_case_owner_last``, which runs the shared
    ``wait_for_replica_ledger_ending_at`` helper inside a ``demo_check``
    (DEMOMA-23-005, CM-23-004), so a timeout accumulates to _demo_failures and
    lets the ledger dump run (exit 0 with a failure summary).
    """

    def test_coverage_wait_timeout_accumulates_to_demo_failures_not_raises(
        self,
    ):
        """A timed-out coverage wait inside _phase_case_closure must NOT raise.

        Bug A: the bare wait_for_contiguous_ledger_coverage call propagated
        AssertionError through _phase_case_closure, crashing the demo runner.
        Every coverage wait now runs inside the shared helper's demo_check, so
        the timeout is recorded in _demo_failures and the phase returns
        normally.

        We verify this end to end: the primitive is patched *on the helper's
        module* to always raise AssertionError, the scenario's real closure
        phase calls the real helper, and the exception does not propagate.
        """
        import vultron.demo.utils as utils_module

        utils_module.reset_demo_failures()

        case_id = "https://example.org/cases/bug-a-regression"

        # Build minimal mocks that satisfy _phase_case_closure's calls
        # without triggering real HTTP.
        client = MagicMock()

        def _named_actor(name: str) -> MagicMock:
            a = MagicMock()
            a.id_ = f"https://example.org/actors/{name}"
            return a

        # Distinct actors: the closure phase refuses an owner that is also
        # listed among the participants that leave before it (CM-23-015).
        vendor, vendor2, reporter = (
            _named_actor("vendor"),
            _named_actor("vendor2"),
            _named_actor("reporter"),
        )

        case = MagicMock()
        case.id_ = case_id

        # _get_log_entries_for_case reads from /datalayer/CaseLedgerEntrys/
        # Return a single entry so the tail-read branch is taken.
        client.get.return_value = {
            "e0": {
                "case_id": case_id,
                "log_index": 0,
                "entry_hash": "hash0000",
                "semantic_type": "close_case",
            }
        }

        initial_failures = len(utils_module._demo_failures)
        # The CASE_MANAGER's ledger: one close_case per leaver, so each
        # leaver's own-closure check reaches the coverage wait.
        ledger = [
            {
                "case_id": case_id,
                "log_index": index,
                "semantic_type": "close_case",
                "payload_snapshot": {"actor": actor.id_},
            }
            for index, actor in enumerate((vendor2, reporter, vendor))
        ]
        real_own_closure = closure._verify_own_closure

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(closure, "_verify_own_closure", real_own_closure),
            patch.object(closure, "case_manager_ledger", return_value=ledger),
            patch(
                "vultron.demo.helpers.sync.wait_for_contiguous_ledger_coverage",
                side_effect=AssertionError(
                    "contiguous ledger coverage timeout"
                ),
            ),
        ):
            try:
                demo._phase_case_closure(
                    case_actor_client=MagicMock(),
                    reporter_client=client,
                    vendor_client=client,
                    vendor2_client=client,
                    vendor=vendor,
                    vendor_in_vendor=vendor,
                    vendor2=vendor2,
                    vendor2_in_vendor2=vendor2,
                    reporter=reporter,
                    reporter_in_reporter=reporter,
                    case=case,
                )
            except AssertionError as exc:
                pytest.fail(
                    f"Bug A regression: AssertionError propagated out of "
                    f"_phase_case_closure: {exc}"
                )

        # The failure must be accumulated, not raised: once per leaver.
        failures = utils_module._demo_failures[initial_failures:]
        assert len(failures) == 3, failures
        assert all("coverage timeout" in f for f in failures), failures


# ---------------------------------------------------------------------------
# Regression tests: Bug B — wait_for_semantic_type_in_ledger helper
# (issue #1772)
# ---------------------------------------------------------------------------


class TestWaitForSemanticTypeInLedger:
    """Regression: wait for an asynchronously committed entry to appear on the
    authoritative actor before reading the tail index for replica coverage.

    Without this wait, the tail excludes the entry; coverage 'succeeds' for
    the wrong tail; the dump runs before the entry replicates; the invariant
    harness fails.  (The close phase that #1772 found this in no longer reads
    the authority's tail: a closed participant is sent nothing after its own
    closure entries, CM-23-004.)
    """

    def _make_entries(self, case_id: str, semantic_types: list[str]) -> dict:
        return {
            f"e{i}": {
                "case_id": case_id,
                "log_index": i,
                "entry_hash": f"hash{i:04d}",
                "semantic_type": et,
            }
            for i, et in enumerate(semantic_types)
        }

    def test_returns_when_semantic_type_present(self):
        """Returns immediately when the target semantic_type is already in the log."""
        case_id = "https://example.org/cases/bug-b-present"
        client = MagicMock()
        client.get.return_value = self._make_entries(
            case_id, ["validate_report", "close_case"]
        )

        wait_for_semantic_type_in_ledger(
            client=client,
            case_id=case_id,
            semantic_type="close_case",
            timeout_seconds=1.0,
        )
        assert client.get.call_count >= 1

    def test_raises_when_semantic_type_absent(self):
        """Raises AssertionError when target semantic_type never appears."""
        case_id = "https://example.org/cases/bug-b-absent"
        client = MagicMock()
        client.get.return_value = self._make_entries(
            case_id,
            ["validate_report", "add_participant_status_to_participant"],
        )

        with pytest.raises(AssertionError, match="close_case"):
            wait_for_semantic_type_in_ledger(
                client=client,
                case_id=case_id,
                semantic_type="close_case",
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
                "semantic_type": "close_case",
            }
        }
        client.get.return_value = {**entries, **other_entries}

        with pytest.raises(AssertionError, match="close_case"):
            wait_for_semantic_type_in_ledger(
                client=client,
                case_id=case_id,
                semantic_type="close_case",
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_eventually_returns_when_event_arrives(self):
        """Returns once the semantic_type appears after a few polls."""
        case_id = "https://example.org/cases/bug-b-eventual"
        call_count = 0
        no_close_entries = {
            "e0": {
                "case_id": case_id,
                "log_index": 0,
                "entry_hash": "hash0000",
                "semantic_type": "validate_report",
            }
        }
        with_close_entries = {
            **no_close_entries,
            "e1": {
                "case_id": case_id,
                "log_index": 1,
                "entry_hash": "hash0001",
                "semantic_type": "close_case",
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

        wait_for_semantic_type_in_ledger(
            client=client,
            case_id=case_id,
            semantic_type="close_case",
            timeout_seconds=5.0,
            poll_interval=0.05,
        )
        assert call_count >= 3


# ---------------------------------------------------------------------------
# Milestone assertion tests — AC-4 of ISSUE-1976
# ---------------------------------------------------------------------------


class TestRvvMilestoneAssertions:
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

        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        reporter = self._actor("urn:test:reporter")
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
                "seed_containers_rvv",
                return_value=(reporter, vendor, vendor2),
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
            patch.object(demo, "wait_for_reporter_case"),
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                return_value=SimpleNamespace(activity=invite),
            ),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(invite_chain, "find_case_invite_for_actor"),
            patch_chain_shared(demo, "wait_for_case_on_container"),
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
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                case_actor_client=MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                reporter_id=None,
                vendor_id=None,
                vendor2_id=None,
            )
        mock_m1.assert_called()

    def test_phase_fix_lifecycle_calls_verify_fix_ready(self):
        """_phase_fix_lifecycle calls verify_fix_ready at M4/M5."""
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        with (
            patch.object(demo, "wait_for_participant_rm_state"),
            patch.object(ActorSession, "notify_fix_ready"),
            patch.object(demo, "wait_for_participant_vf_state"),
            patch.object(demo, "verify_fix_ready") as mock_m4,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_fix_lifecycle(
                reporter_client=reporter_client,
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

        reporter_client = self._client()
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
                ActorSession,
                "notify_fix_ready",
                side_effect=lambda *a, **kw: call_order.append("fix_ready"),
            ),
            patch.object(demo, "wait_for_participant_vf_state"),
            patch.object(demo, "verify_fix_ready"),
        ):
            demo._phase_fix_lifecycle(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                case=case,
            )

        assert len(rm_calls) == 2, (
            f"wait_for_participant_rm_state must be called once per vendor (got {len(rm_calls)}) (ADR-0058/CSB-18-001)"
        )
        assert all(
            c.get("expected_states") == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), (
            "expected_states must be {ACCEPTED, DEFERRED, CLOSED} for each vendor (CSB-18-001)"
        )
        assert "rm_wait" in call_order and "fix_ready" in call_order
        assert call_order.index("rm_wait") < call_order.index("fix_ready"), (
            "wait_for_participant_rm_state must precede actor_notifies_fix_ready (ADR-0058)"
        )

    def test_phase_publication_calls_verify_publicly_disclosed(self):
        """_phase_publication calls verify_publicly_disclosed at M6."""
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        reporter = self._actor("urn:test:reporter")
        reporter_in_reporter = self._actor("urn:test:reporter")
        case = self._case()

        with (
            patch.object(ActorSession, "notify_published"),
            patch.object(demo, "wait_for_case_em_terminated"),
            patch.object(demo, "wait_for_participant_vf_state"),
            patch.object(demo, "verify_publicly_disclosed") as mock_m6,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_publication(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                reporter=reporter,
                reporter_in_reporter=reporter_in_reporter,
                case=case,
            )
        mock_m6.assert_called()

    def test_phase_case_closure_runs_the_closure_milestone(self):
        """_phase_case_closure runs the shared closure milestone (CM-23-004).

        The milestone checks the CASE_MANAGER's store and each leaver's own
        replica inside ``close_case_owner_last``; the scenario only names it.
        """
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        reporter = self._actor("urn:test:reporter")
        reporter_in_reporter = self._actor("urn:test:reporter")
        case = self._case()
        case.id_ = "urn:test:case"
        vendor_client.get.return_value = {
            "e0": {
                "case_id": case.id_,
                "log_index": 0,
                "entry_hash": "h0",
                "semantic_type": "close_case",
            }
        }

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(demo, "close_case_owner_last") as mock_m7,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_case_closure(
                case_actor_client=MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                reporter=reporter,
                reporter_in_reporter=reporter_in_reporter,
                case=case,
            )
        mock_m7.assert_called_once()
        assert mock_m7.call_args.kwargs.get("milestone") == "M7"


@pytest.mark.spec("CLP-08-005")
class TestReporterCaseReplicaWaitBeforeVendor2Triage:
    """CLP-08-005: Reporter replica wait must precede invite-path RM triage in rvv."""

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

    def test_reporter_wait_before_vendor2_triage(self):
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        reporter = self._actor("urn:test:reporter")
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
            if client is reporter_client:
                call_order.append("reporter_wait")

        def _triage(**_kw):
            call_order.append("triage")

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_rvv",
                return_value=(reporter, vendor, vendor2),
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
            patch.object(demo, "wait_for_reporter_case"),
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                return_value=SimpleNamespace(activity=invite),
            ),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(invite_chain, "find_case_invite_for_actor"),
            patch_chain_shared(
                demo,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
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
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                case_actor_client=MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                reporter_id=None,
                vendor_id=None,
                vendor2_id=None,
            )

        assert "reporter_wait" in call_order, (
            "wait_for_case_on_container(reporter_client) never called"
        )
        assert "triage" in call_order, "run_invite_path_rm_triage never called"
        reporter_idx = next(
            i for i, v in enumerate(call_order) if v == "reporter_wait"
        )
        triage_idx = next(i for i, v in enumerate(call_order) if v == "triage")
        assert reporter_idx < triage_idx, (
            "Reporter replica wait must precede run_invite_path_rm_triage; "
            f"got order: {call_order}"
        )


class TestRvvParticipantWaitTimeout:
    """#2852: sync-verification must give the Vendor2 replica the late-joiner
    participant-propagation budget (>=30 s), not the 15 s default.

    Before the fix, rvv polled the reporter + vendor2 replicas with two bare
    wait_for_case_participants calls that omitted timeout_seconds, so Vendor2
    (a late joiner) used the 15 s default and could time out spuriously under
    CI load — the same failure class #2337 fixed for ledger coverage.  The fix
    routes both replicas through wait_for_participants_on_replicas, which
    grants late joiners 30 s (matching all sibling scenarios).
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

    def test_sync_verification_gives_vendor2_late_joiner_timeout(self):
        import vultron.demo.helpers.polling as polling_module

        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        reporter = self._actor("urn:test:reporter")
        vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        timeouts_by_client_id: dict[int, float] = {}

        def _capture(
            vendor_client, case_id, expected_actor_ids, timeout_seconds, **_kw
        ):
            timeouts_by_client_id[id(vendor_client)] = timeout_seconds

        with (
            patch.object(
                sync_module,
                "_get_log_entries_for_case",
                return_value=[
                    {"log_index": 5, "entry_hash": "abc123def456789a"}
                ],
            ),
            patch.object(sync_module, "wait_for_case_on_container"),
            patch.object(sync_module, "wait_for_contiguous_ledger_coverage"),
            # Patch the polling-module global so the real
            # wait_for_participants_on_replicas records the timeout it assigns.
            patch.object(
                polling_module, "wait_for_case_participants", _capture
            ),
            patch.object(sync_module, "verify_replica_state"),
        ):
            demo._phase_sync_verification(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                reporter=reporter,
                vendor2=vendor2,
                case=case,
            )

        assert timeouts_by_client_id.get(id(vendor2_client)) is not None, (
            "Vendor2 replica participant wait was never invoked in "
            "_phase_sync_verification"
        )
        assert timeouts_by_client_id[id(vendor2_client)] >= 30.0, (
            f"Vendor2 (late joiner) participant timeout is "
            f"{timeouts_by_client_id[id(vendor2_client)]}s — must be >=30 s; "
            f"the 15 s default times out spuriously under CI load (#2852)"
        )
        # Reporter is an early participant and uses the shorter default budget.
        assert timeouts_by_client_id[id(reporter_client)] < 30.0


class TestParticipantWaitInsideDemoCheck:
    """Regression (#3384/#3406): a bare wait_for_participants_on_replicas call in
    _phase_sync_verification crashed the whole run when a replica participant
    wait timed out.

    After the fix, wait_for_participants_on_replicas wraps each per-replica poll
    in a demo_check internally, so a timeout accumulates to _demo_failures and
    _phase_sync_verification returns normally — the subsequent
    verify_replica_state demo_check blocks still execute (DEMOCI-01-011).
    Mirrors TestCoverageWaitInsideDemoCheck, which covers the same failure class
    for bare ledger-coverage waits.
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

    def test_replica_participant_timeout_accumulates_and_does_not_propagate(
        self,
    ):
        """A timed-out replica participant wait must NOT crash the phase.

        Patch the low-level wait_for_case_participants (the polling-module
        global the real wait_for_participants_on_replicas calls) to always
        raise, then confirm _phase_sync_verification: (a) does not propagate the
        AssertionError, (b) records the timeout in _demo_failures, and (c) still
        reaches the downstream verify_replica_state demo_check blocks.
        """
        import vultron.demo.helpers.polling as polling_module
        import vultron.demo.utils as utils_module

        utils_module.reset_demo_failures()

        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        reporter = self._actor("urn:test:reporter")
        vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        def _timeout(*_args, **_kwargs):
            raise AssertionError("participant propagation timeout")

        verify_calls: list[dict] = []

        initial_failures = len(utils_module._demo_failures)

        with (
            patch.object(
                sync_module,
                "_get_log_entries_for_case",
                return_value=[
                    {"log_index": 5, "entry_hash": "abc123def456789a"}
                ],
            ),
            patch.object(sync_module, "wait_for_case_on_container"),
            patch.object(sync_module, "wait_for_contiguous_ledger_coverage"),
            # Patch the polling-module global so the real
            # wait_for_participants_on_replicas runs its internal demo_check
            # wrap around a raising per-replica poll.
            patch.object(
                polling_module, "wait_for_case_participants", _timeout
            ),
            patch.object(
                sync_module,
                "verify_replica_state",
                side_effect=lambda **kw: verify_calls.append(kw),
            ),
        ):
            try:
                demo._phase_sync_verification(
                    reporter_client=reporter_client,
                    vendor_client=vendor_client,
                    vendor2_client=vendor2_client,
                    vendor=vendor,
                    reporter=reporter,
                    vendor2=vendor2,
                    case=case,
                )
            except AssertionError as exc:
                pytest.fail(
                    "Replica participant-wait timeout propagated out of "
                    f"_phase_sync_verification: {exc}"
                )

        # (b) Both replica timeouts accumulated rather than crashing the run.
        new_failures = utils_module._demo_failures[initial_failures:]
        assert len(new_failures) == 2, (
            "Expected one accumulated failure per replica participant wait; "
            f"got {new_failures}"
        )
        assert all(
            "reflects all case participants" in f for f in new_failures
        ), new_failures

        # (c) Downstream verify_replica_state demo_check blocks still ran for
        # both the Reporter and Vendor2 replicas — the timeout did not skip them.
        assert len(verify_calls) == 2, (
            "verify_replica_state must still run after a replica participant "
            f"timeout; got {len(verify_calls)} call(s)"
        )
        replica_clients = {kw["replica_client"] for kw in verify_calls}
        assert replica_clients == {reporter_client, vendor2_client}


class TestRvvInviteChainSkipsDependents:
    """Phase 1 (Vendor1 invites Vendor2): failed trigger or lookup skips dependents.

    Before the fix ``invite_result.activity`` was read on a ``None`` sentinel
    after the suppressing ``demo_step`` (crash, #3038 sibling), and the
    delivery wait was a ``demo_check`` that let the accept run regardless
    (EDF-06-005).
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

    def _run(self, *, invite_trigger, invite_lookup):
        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        reporter = self._actor("urn:test:reporter")
        vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_rvv",
                return_value=(reporter, vendor, vendor2),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[
                    self._actor("urn:test:vendor"),
                    self._actor("urn:test:vendor2"),
                ],
            ),
            patch.object(
                demo,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock(id_="urn:test:offer")),
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_reporter_case"),
            patch.object(
                ActorSession, "invite_actor_to_case", **invite_trigger
            ),
            patch.object(ActorSession, "accept_case_invite") as accept_invite,
            patch.object(
                invite_chain, "find_case_invite_for_actor", **invite_lookup
            ) as find_invite,
            patch_chain_shared(
                demo, "wait_for_case_on_container"
            ) as replica_wait,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(demo, "run_invite_path_rm_triage"),
            patch.object(demo, "verify_case_active"),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                case_actor_client=MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                reporter_id=None,
                vendor_id=None,
                vendor2_id=None,
            )
        return find_invite, accept_invite, replica_wait, vendor2_client

    def test_invite_trigger_failure_skips_lookup_and_accept(self):
        find_invite, accept_invite, replica_wait, vendor2_client = self._run(
            invite_trigger={
                "side_effect": RuntimeError("invite trigger failed")
            },
            invite_lookup={"return_value": "urn:test:invite"},
        )
        find_invite.assert_not_called()
        accept_invite.assert_not_called()
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is vendor2_client
        ], "replica_wait ran for the skipped dependent: " + str(
            replica_wait.call_args_list
        )

    def test_invite_lookup_failure_skips_accept(self):
        _, accept_invite, replica_wait, vendor2_client = self._run(
            invite_trigger={
                "return_value": SimpleNamespace(
                    activity=MagicMock(id_="urn:test:invite")
                )
            },
            invite_lookup={
                "side_effect": AssertionError("timed out polling for Invite")
            },
        )
        accept_invite.assert_not_called()
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is vendor2_client
        ], "replica_wait ran for the skipped dependent: " + str(
            replica_wait.call_args_list
        )


# ---------------------------------------------------------------------------
# Dedicated case-actor container routing (#1876, DEMOMA-06-004/005)
# ---------------------------------------------------------------------------


class TestRvvDedicatedCaseActorRouting:
    """CASE_MANAGER reads and acts go to the dedicated case-actor container.

    The CaseActor is not hosted by Vendor1's container, and Vendor1's replica is
    not the CASE_MANAGER's store, so every authority read, the CASE_MANAGER's
    ``stub_summary`` seed and the canonical ledger dump name the case-actor
    client.
    """

    @staticmethod
    def _actor(id_: str) -> MagicMock:
        actor = MagicMock()
        actor.id_ = id_
        return actor

    def test_closure_reads_departures_through_case_actor_client(self):
        case_actor_client = MagicMock()
        vendor_client = MagicMock()
        case = MagicMock()
        case.id_ = "urn:test:case"
        vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        reporter = self._actor("urn:test:reporter")

        with (
            patch.object(demo, "close_case_owner_last") as close_mock,
        ):
            demo._phase_case_closure(
                reporter_client=MagicMock(),
                vendor_client=vendor_client,
                vendor2_client=MagicMock(),
                vendor=vendor,
                vendor_in_vendor=vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2,
                reporter=reporter,
                reporter_in_reporter=reporter,
                case=case,
                case_actor_client=case_actor_client,
            )

        assert (
            close_mock.call_args.kwargs["authority_client"]
            is case_actor_client
        )

    def test_report_submission_routes_case_manager_to_case_actor_client(self):
        case_actor_client = MagicMock()
        vendor_client = MagicMock()
        reporter = self._actor("urn:test:reporter")
        vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        case = MagicMock()
        case.id_ = "urn:test:case"

        with (
            patch.object(demo, "reset_containers") as reset_mock,
            patch.object(
                demo,
                "seed_containers_rvv",
                return_value=(reporter, vendor, vendor2),
            ),
            patch.object(
                demo, "get_actor_by_id", side_effect=[vendor, vendor2]
            ),
            patch.object(
                demo,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_reporter_case"),
            patch.object(demo, "wait_for_case_on_container"),
            patch.object(demo, "run_case_invite_chain") as chain_mock,
            patch.object(demo, "run_invite_path_rm_triage") as triage_mock,
            patch.object(demo, "verify_case_active"),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                reporter_client=MagicMock(),
                vendor_client=vendor_client,
                vendor2_client=MagicMock(),
                case_actor_client=case_actor_client,
                reporter_id=None,
                vendor_id=None,
                vendor2_id=None,
            )

        assert (
            reset_mock.call_args.kwargs["case_actor_client"]
            is case_actor_client
        )
        assert (
            chain_mock.call_args.kwargs["case_manager_client"]
            is case_actor_client
        )
        assert triage_mock.call_args.kwargs["auth_client"] is case_actor_client

    def test_dump_reads_case_actor_ledger_from_dedicated_container(
        self, tmp_path, monkeypatch
    ):
        def bound(slug: str) -> MagicMock:
            client = MagicMock()
            client.actor_id = f"https://example.org/actors/{slug}"
            client.get_list.return_value = [{"logIndex": 0}]
            return client

        vendor_client = bound("vendor")
        case_actor_client = bound("case-actor")
        case = demo.as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rvv-ca",
            actor_participant_index={
                "https://example.org/actors/case-actor": (
                    "https://example.org/cases/rvv-ca/participants/ca"
                )
            },
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            reporter_client=bound("reporter"),
            vendor_client=vendor_client,
            vendor2_client=bound("vendor2"),
            reporter=self._actor("https://example.org/actors/reporter"),
            vendor=self._actor("https://example.org/actors/vendor"),
            vendor2=self._actor("https://example.org/actors/vendor2"),
            case=case,
            case_actor_client=case_actor_client,
        )

        log_path = "/actors/case-actor/demo/cases/rvv-ca/log"
        assert any(
            log_path in c.args[0]
            for c in case_actor_client.get_list.call_args_list
        )
        assert not any(
            log_path in c.args[0]
            for c in vendor_client.get_list.call_args_list
        )
