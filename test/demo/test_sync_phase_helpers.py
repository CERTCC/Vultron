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

"""Helper-level tests for the shared replica sync-verification helpers.

``wait_for_replica_ledger_coverage`` and ``run_sync_verification_phase`` in
``vultron/demo/helpers/sync.py`` replace the per-scenario copies of the
read-authority-tail-then-poll-each-replica loop and of the sync-verification
phase body (DEMOMA-23-005, DEMOMA-23-007, #3846).  The eight per-scenario
"skip the coverage wait when the Finder case never arrives" tests collapsed
into this module.

Every test runs the real ``demo_gate`` / ``demo_check`` context managers —
patching them out with ``nullcontext`` would let the assertion propagate and
prove nothing (vultron/demo/AGENTS.md § causal gating, rule 8).
"""

import inspect
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.helpers.sync as sync_module
import vultron.demo.utils as demo_utils
from vultron.demo.helpers.polling import (
    CROSS_CONTAINER_TIMEOUT,
    LATE_JOINER_COVERAGE_TIMEOUT,
    LEDGER_COVERAGE_TIMEOUT,
    wait_for_contiguous_ledger_coverage,
)
from vultron.demo.helpers.sync import (
    run_sync_verification_phase,
    wait_for_replica_ledger_coverage,
)
from vultron.demo.utils import reset_demo_failures

_CASE_ID = "urn:uuid:test-case-3846-0001"
_TAIL = [{"log_index": 5, "entry_hash": "abc123def456789a"}]


@pytest.fixture(autouse=True)
def _clean_accumulator():
    reset_demo_failures()
    yield
    reset_demo_failures()


def _client(name: str) -> MagicMock:
    client = MagicMock(name=name)
    client.base_url = f"http://{name}:7999/api/v2"
    client.actor_id = f"http://{name}:7999/api/v2/actors/{name}"
    return client


def _capture_coverage_timeouts():
    """Return ``(timeouts_by_client_id, fake_wait)`` recording each call."""
    timeouts: dict[int, float] = {}

    def _fake(client, case_id, expected_tail_index, timeout_seconds):
        timeouts[id(client)] = timeout_seconds

    return timeouts, _fake


# ---------------------------------------------------------------------------
# wait_for_replica_ledger_coverage (DEMOMA-23-005)
# ---------------------------------------------------------------------------


class TestWaitForReplicaLedgerCoverage:
    def test_skips_every_replica_wait_when_authority_tail_is_empty(self):
        """No authority entries → nothing to cover → no per-replica poll.

        The one failure recorded names the *authority*: the writer is at
        fault, not the fan-out, so no replica-side check may be left to blame
        "replication did not complete" (EDF-06-005).
        """
        coverage = MagicMock()
        auth = _client("auth")
        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=[]
            ),
            patch.object(
                sync_module, "wait_for_contiguous_ledger_coverage", coverage
            ),
        ):
            wait_for_replica_ledger_coverage(
                auth_client=auth,
                replicas=[(_client("r1"), "R1"), (_client("r2"), "R2")],
                case_id=_CASE_ID,
            )
        coverage.assert_not_called()
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")
        assert auth.base_url in failure
        assert "holds no CaseLedgerEntry" in failure
        assert "R1" not in failure and "R2" not in failure

    def test_empty_authority_tail_is_a_temporal_check_failure_after_close(
        self,
    ):
        """Closure use: the authority-empty failure is a CHECK, not a gate."""
        auth = _client("auth")
        with patch.object(
            sync_module, "_get_log_entries_for_case", return_value=[]
        ):
            wait_for_replica_ledger_coverage(
                auth_client=auth,
                replicas=[(_client("r"), "Finder")],
                case_id=_CASE_ID,
                phase_label="close phase",
                causal=False,
            )
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("CHECK FAILED")
        assert auth.base_url in failure
        assert "close phase" in failure
        assert "EDF-06-006" in failure

    def test_polls_every_replica_in_order_against_the_authority_tail(self):
        replicas = [(_client(f"r{i}"), f"R{i}") for i in range(3)]
        calls: list[tuple[int, int]] = []

        def _fake(client, case_id, expected_tail_index, timeout_seconds):
            assert case_id == _CASE_ID
            calls.append((id(client), expected_tail_index))

        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=_TAIL
            ),
            patch.object(
                sync_module, "wait_for_contiguous_ledger_coverage", _fake
            ),
        ):
            wait_for_replica_ledger_coverage(
                auth_client=_client("auth"),
                replicas=replicas,
                case_id=_CASE_ID,
            )
        assert calls == [(id(c), 5) for c, _ in replicas]

    def test_budgets_never_fall_below_what_any_scenario_carried_before(self):
        """The shared defaults are the widest budgets the copies used (#1911, #2337).

        Before extraction the early-replica budget was the primitive's 30 s
        default in three scenarios (15 s fired under CI load, #1911) and every
        late joiner had 45 s; sharing the loop must not tighten either.
        """
        primitive_default = (
            inspect.signature(wait_for_contiguous_ledger_coverage)
            .parameters["timeout_seconds"]
            .default
        )
        assert LEDGER_COVERAGE_TIMEOUT == primitive_default >= 30.0
        assert LATE_JOINER_COVERAGE_TIMEOUT >= 45.0
        assert LATE_JOINER_COVERAGE_TIMEOUT > LEDGER_COVERAGE_TIMEOUT

    def test_late_joiner_gets_late_joiner_budget_and_others_the_default(self):
        """Late joiners catch up from genesis and get the extended budget."""
        early, late = _client("early"), _client("late")
        timeouts, fake = _capture_coverage_timeouts()
        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=_TAIL
            ),
            patch.object(
                sync_module, "wait_for_contiguous_ledger_coverage", fake
            ),
        ):
            wait_for_replica_ledger_coverage(
                auth_client=_client("auth"),
                replicas=[(early, "Early"), (late, "Late")],
                case_id=_CASE_ID,
                late_joiners=(late,),
            )
        assert timeouts[id(late)] == LATE_JOINER_COVERAGE_TIMEOUT
        assert timeouts[id(early)] == LEDGER_COVERAGE_TIMEOUT

    def test_default_timeout_parameter_is_honoured_for_early_replicas(self):
        """A scenario may pass another named constant; late joiners keep theirs."""
        early, late = _client("early"), _client("late")
        timeouts, fake = _capture_coverage_timeouts()
        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=_TAIL
            ),
            patch.object(
                sync_module, "wait_for_contiguous_ledger_coverage", fake
            ),
        ):
            wait_for_replica_ledger_coverage(
                auth_client=_client("auth"),
                replicas=[(early, "Early"), (late, "Late")],
                case_id=_CASE_ID,
                late_joiners=(late,),
                default_timeout=CROSS_CONTAINER_TIMEOUT,
            )
        assert timeouts[id(early)] == CROSS_CONTAINER_TIMEOUT
        assert timeouts[id(late)] == LATE_JOINER_COVERAGE_TIMEOUT

    def test_replica_timeout_is_accumulated_and_the_loop_continues(self):
        """A raising per-replica wait is recorded, not propagated (DEMOCI-01-011)."""
        first, second = _client("first"), _client("second")
        polled: list[int] = []

        def _fake(client, case_id, expected_tail_index, timeout_seconds):
            polled.append(id(client))
            if client is first:
                raise AssertionError("Timed out waiting for coverage")

        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=_TAIL
            ),
            patch.object(
                sync_module, "wait_for_contiguous_ledger_coverage", _fake
            ),
        ):
            wait_for_replica_ledger_coverage(
                auth_client=_client("auth"),
                replicas=[(first, "First"), (second, "Second")],
                case_id=_CASE_ID,
            )
        assert polled == [id(first), id(second)]
        failures = demo_utils._demo_failures
        assert len(failures) == 1
        assert "First ledger coverage" in failures[0]

    def test_returns_only_the_replicas_whose_wait_passed(self):
        """The covered list lets a caller gate dependent steps (EDF-06-005)."""
        first, second = _client("first"), _client("second")

        def _fake(client, case_id, expected_tail_index, timeout_seconds):
            if client is first:
                raise AssertionError("Timed out waiting for coverage")

        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=_TAIL
            ),
            patch.object(
                sync_module, "wait_for_contiguous_ledger_coverage", _fake
            ),
        ):
            covered = wait_for_replica_ledger_coverage(
                auth_client=_client("auth"),
                replicas=[(first, "First"), (second, "Second")],
                case_id=_CASE_ID,
            )
        assert covered == [second]

    def test_empty_authority_tail_covers_no_replica(self):
        """Nothing to cover → nothing covered → dependent checks are skipped."""
        replicas = [(_client("r1"), "R1"), (_client("r2"), "R2")]
        with patch.object(
            sync_module, "_get_log_entries_for_case", return_value=[]
        ):
            covered = wait_for_replica_ledger_coverage(
                auth_client=_client("auth"),
                replicas=replicas,
                case_id=_CASE_ID,
            )
        assert covered == []

    def test_causal_wait_records_gate_failure(self):
        """Pre-notes use: a coverage timeout is a GATE FAILED (EDF-06-005)."""
        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=_TAIL
            ),
            patch.object(
                sync_module,
                "wait_for_contiguous_ledger_coverage",
                side_effect=AssertionError("timed out"),
            ),
        ):
            wait_for_replica_ledger_coverage(
                auth_client=_client("auth"),
                replicas=[(_client("r"), "Finder")],
                case_id=_CASE_ID,
                causal=True,
            )
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")
        assert "Finder ledger coverage (sync-verification phase)" in failure

    def test_temporal_wait_records_check_failure_labelled_temporal(self):
        """Post-closure use: demo_check, labelled temporal (EDF-06-006)."""
        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=_TAIL
            ),
            patch.object(
                sync_module,
                "wait_for_contiguous_ledger_coverage",
                side_effect=AssertionError("timed out"),
            ),
        ):
            wait_for_replica_ledger_coverage(
                auth_client=_client("auth"),
                replicas=[(_client("r"), "Finder")],
                case_id=_CASE_ID,
                phase_label="close phase",
                causal=False,
            )
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("CHECK FAILED")
        assert "Finder ledger coverage (close phase)" in failure
        assert "temporal" in failure
        assert "EDF-06-006" in failure


# ---------------------------------------------------------------------------
# run_sync_verification_phase (DEMOMA-23-007)
# ---------------------------------------------------------------------------


def _phase_patches(**overrides):
    """Patch every collaborator of the phase helper on the sync module."""
    defaults = {
        "wait_for_case_on_container": MagicMock(),
        "_get_log_entries_for_case": MagicMock(return_value=_TAIL),
        "wait_for_contiguous_ledger_coverage": MagicMock(),
        "wait_for_participants_on_replicas": MagicMock(),
        "verify_replica_state": MagicMock(),
    }
    defaults.update(overrides)
    return defaults


def _run_phase(mocks, **kwargs):
    """Run the phase helper with every collaborator in *mocks* patched."""
    with ExitStack() as stack:
        for name, replacement in mocks.items():
            stack.enter_context(patch.object(sync_module, name, replacement))
        run_sync_verification_phase(**kwargs)


class TestRunSyncVerificationPhase:
    def _kwargs(self, finder, auth, replicas, **extra):
        base = dict(
            auth_client=auth,
            auth_label="Authority",
            auth_actor_id="urn:test:authority",
            finder_client=finder,
            finder_actor_id="urn:test:finder",
            replicas=replicas,
            case_id=_CASE_ID,
        )
        base.update(extra)
        return base

    def test_skips_coverage_wait_when_finder_case_not_seeded(self):
        """The SYNC-15 gate skips the coverage waits when the Finder lacks the case.

        Collapses the eight identical per-scenario tests (AC-5, #3846).
        """
        finder, auth, other = _client("finder"), _client("auth"), _client("o")
        mocks = _phase_patches(
            wait_for_case_on_container=MagicMock(
                side_effect=AssertionError("timed out waiting for case")
            )
        )
        _run_phase(
            mocks,
            **self._kwargs(
                finder, auth, [(finder, "Finder"), (other, "Other")]
            ),
        )
        mocks["wait_for_contiguous_ledger_coverage"].assert_not_called()
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")
        assert "SYNC-15" in failure

    def test_composes_gate_coverage_participants_and_state_checks_in_order(
        self,
    ):
        finder, auth, late = _client("finder"), _client("auth"), _client("l")
        order: list[str] = []
        mocks = _phase_patches(
            wait_for_case_on_container=MagicMock(
                side_effect=lambda **kw: order.append("finder-case")
            ),
            wait_for_contiguous_ledger_coverage=MagicMock(
                side_effect=lambda **kw: order.append("coverage")
            ),
            wait_for_participants_on_replicas=MagicMock(
                side_effect=lambda **kw: order.append("participants")
            ),
            verify_replica_state=MagicMock(
                side_effect=lambda **kw: order.append("state")
            ),
        )
        _run_phase(
            mocks,
            **self._kwargs(
                finder,
                auth,
                [(finder, "Finder"), (late, "Late")],
                expected_participant_ids={"a", "b"},
                late_joiners=(late,),
                state_checks=[(finder, "Finder"), (late, "Late")],
            ),
        )
        assert order == [
            "finder-case",
            "coverage",
            "coverage",
            "participants",
            "state",
            "state",
        ]
        mocks["wait_for_case_on_container"].assert_called_once_with(
            client=finder, case_id=_CASE_ID
        )
        mocks["wait_for_participants_on_replicas"].assert_called_once_with(
            replica_clients=[finder, late],
            case_id=_CASE_ID,
            expected_actor_ids={"a", "b"},
            late_joiners=(late,),
        )
        state_calls = mocks["verify_replica_state"].call_args_list
        assert [c.kwargs["replica_client"] for c in state_calls] == [
            finder,
            late,
        ]
        assert all(c.kwargs["auth_client"] is auth for c in state_calls)
        assert all(
            c.kwargs["vendor_actor_id"] == "urn:test:authority"
            and c.kwargs["reporter_actor_id"] == "urn:test:finder"
            for c in state_calls
        )
        assert demo_utils._demo_failures == []

    def test_declares_no_participant_wait_when_no_participants_expected(self):
        """fcv-reject declares no participant set: no participant poll runs."""
        finder, auth = _client("finder"), _client("auth")
        mocks = _phase_patches()
        _run_phase(mocks, **self._kwargs(finder, auth, [(finder, "Finder")]))
        mocks["wait_for_participants_on_replicas"].assert_not_called()
        mocks["verify_replica_state"].assert_not_called()
        mocks["wait_for_contiguous_ledger_coverage"].assert_called_once()

    def test_late_joiners_and_coverage_budgets_reach_the_coverage_loop(self):
        finder, auth, late = _client("finder"), _client("auth"), _client("l")
        timeouts, fake = _capture_coverage_timeouts()
        mocks = _phase_patches(wait_for_contiguous_ledger_coverage=fake)
        _run_phase(
            mocks,
            **self._kwargs(
                finder,
                auth,
                [(finder, "Finder"), (late, "Late")],
                late_joiners=(late,),
            ),
        )
        assert timeouts[id(finder)] == LEDGER_COVERAGE_TIMEOUT
        assert timeouts[id(late)] == LATE_JOINER_COVERAGE_TIMEOUT

    def test_state_check_is_skipped_for_a_replica_whose_coverage_gate_failed(
        self,
    ):
        """One causal event → one recorded failure, not a cascade (#1911, #2361).

        Successor to fv's ``test_sync_verification_skips_replica_check_when_
        ledger_coverage_times_out``: the state comparison depends on coverage,
        so an unmet coverage gate must prevent it (EDF-06-005) — for the failed
        replica only; a replica that covered is still compared.
        """
        finder, auth, other = _client("finder"), _client("auth"), _client("o")

        def _coverage(client, case_id, expected_tail_index, timeout_seconds):
            if client is finder:
                raise AssertionError("Timed out waiting for coverage")

        mocks = _phase_patches(wait_for_contiguous_ledger_coverage=_coverage)
        _run_phase(
            mocks,
            **self._kwargs(
                finder,
                auth,
                [(finder, "Finder"), (other, "Other")],
                state_checks=[(finder, "Finder"), (other, "Other")],
            ),
        )
        compared = [
            c.kwargs["replica_client"]
            for c in mocks["verify_replica_state"].call_args_list
        ]
        assert compared == [other]
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")
        assert "Finder ledger coverage" in failure

    def test_state_checks_are_skipped_when_the_finder_gate_fails(self):
        finder, auth = _client("finder"), _client("auth")
        mocks = _phase_patches(
            wait_for_case_on_container=MagicMock(
                side_effect=AssertionError("timed out waiting for case")
            )
        )
        _run_phase(
            mocks,
            **self._kwargs(
                finder,
                auth,
                [(finder, "Finder")],
                state_checks=[(finder, "Finder")],
            ),
        )
        mocks["verify_replica_state"].assert_not_called()
        assert len(demo_utils._demo_failures) == 1

    def test_state_checks_are_skipped_when_the_authority_tail_is_empty(self):
        """An empty authority ledger is one GATE FAILED naming the authority.

        The replica-state comparison is not run: it could only add a second,
        misattributed failure ("Replica has no CaseLedgerEntry") for a fault
        that sits with the writer (EDF-06-005).
        """
        finder, auth = _client("finder"), _client("auth")
        mocks = _phase_patches(
            _get_log_entries_for_case=MagicMock(return_value=[]),
        )
        _run_phase(
            mocks,
            **self._kwargs(
                finder,
                auth,
                [(finder, "Finder")],
                state_checks=[(finder, "Finder")],
            ),
        )
        mocks["wait_for_contiguous_ledger_coverage"].assert_not_called()
        mocks["verify_replica_state"].assert_not_called()
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")
        assert auth.base_url in failure

    def test_state_check_failure_is_accumulated_with_authority_label(self):
        finder, auth = _client("finder"), _client("auth")
        mocks = _phase_patches(
            verify_replica_state=MagicMock(
                side_effect=AssertionError("hash mismatch")
            )
        )
        _run_phase(
            mocks,
            **self._kwargs(
                finder,
                auth,
                [(finder, "Finder")],
                auth_label="Vendor1",
                state_checks=[(finder, "Finder")],
            ),
        )
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("CHECK FAILED")
        assert "Finder replica matches authoritative Vendor1 state" in failure
