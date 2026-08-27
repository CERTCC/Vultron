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

"""Regression guards for issues #2361 and #2337.

#2361: fv Demo Integration — M4/M5 vfd_state replication timeout
Two separate demo_check blocks both poll finder_client for vfd_state=VFd
independently.  Under CI load Docker replication takes >30 s intermittently,
both checks time out, and two CHECK FAILED entries are recorded instead of
one — burying the real signal and making the run appear to have two distinct
failures when only one causal event (replication lag) caused them.

Fix: wrap the shared finder poll and the M4/M5 milestones in a single
demo_gate; on timeout the gate records one GATE FAILED and the dependent
M4/M5 blocks are skipped entirely (ADR-0058).

#2337: fcvcv Demo Integration — intermittent Finder ledger-coverage timeout
demo_check with 15 s timeout for Finder/V1/C2 ledger coverage.  Under CI
load 15 s is too tight; the error log showed 0 of 29 entries present after
the check fired.  Fix: demo_gate (causal gate, not advisory check) and 30 s
timeout for non-V2 replicas (V2 retains 45 s as a late-joiner).
"""

from unittest.mock import MagicMock

import vultron.demo.scenario.fcvcv_demo as fcvcv_demo_module
import vultron.demo.scenario.fv_demo as fv_demo_module
import vultron.demo.utils as demo_utils
from vultron.demo.scenario.fcvcv_demo import _phase_sync_verification
from vultron.demo.scenario.fv_demo import _phase_fix_lifecycle
from vultron.demo.utils import reset_demo_failures

_CASE_ID = "urn:uuid:test-case-2361-0001"
_VENDOR_ID = "http://vendor:7999/api/v2/actors/vendor"


# ===========================================================================
# Issue #2361 — fv M4/M5 double failure when finder replication times out
# ===========================================================================


def test_fv_finder_timeout_records_single_gate_failure_not_two_check_failures(
    monkeypatch,
):
    """A single finder replication timeout must produce exactly one GATE FAILED.

    Before the fix two independent demo_check blocks each polled finder_client
    for vfd_state.  On timeout both recorded CHECK FAILED, producing two entries
    for a single causal event.  After the fix a single demo_gate wraps the
    shared finder poll; M4/M5 are nested inside and skipped on gate failure.

    Regression guard for #2361.
    """
    reset_demo_failures()

    vendor_client = MagicMock()
    vendor_client.base_url = "http://vendor:7999/api/v2"
    finder_client = MagicMock()
    finder_client.base_url = "http://finder:7999/api/v2"

    vendor = MagicMock()
    vendor.id_ = _VENDOR_ID
    vendor_in_vendor = MagicMock()
    case = MagicMock()
    case.id_ = _CASE_ID

    monkeypatch.setattr(
        fv_demo_module, "actor_notifies_fix_ready", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        fv_demo_module, "verify_fix_ready", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        fv_demo_module, "wait_for_participant_rm_state", lambda *a, **kw: None
    )

    def _vfd_poll(client, case_id, actor_id, expected_states, **kw):
        if client is finder_client:
            raise AssertionError(
                f"Timed out waiting for vfd_state on {client.base_url}"
            )
        # vendor_client polls resolve immediately

    monkeypatch.setattr(
        fv_demo_module, "wait_for_participant_vfd_state", _vfd_poll
    )

    _phase_fix_lifecycle(
        finder_client=finder_client,
        vendor_client=vendor_client,
        vendor=vendor,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )

    failures = demo_utils._demo_failures

    assert len(failures) == 1, (
        f"Expected exactly 1 failure when finder replication times out, "
        f"got {len(failures)}: {failures!r}. "
        f"Two separate CHECK FAILED entries indicate demo_check is still used "
        f"for M4/M5 instead of a shared demo_gate (#2361)."
    )
    assert "GATE FAILED" in failures[0], (
        f"Expected 'GATE FAILED' in the failure message, "
        f"got {failures[0]!r}. "
        f"Use demo_gate (not demo_check) for the causal finder precondition "
        f"(#2361, ADR-0058)."
    )


def test_fv_phase_fix_lifecycle_gates_on_rm_accepted(monkeypatch):
    """_phase_fix_lifecycle polls vendor RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (ADR-0058/CSB-18-001)."""
    from vultron.core.states.rm import RM

    reset_demo_failures()

    vendor_client = MagicMock()
    vendor_client.base_url = "http://vendor:7999/api/v2"
    finder_client = MagicMock()
    finder_client.base_url = "http://finder:7999/api/v2"
    vendor = MagicMock()
    vendor.id_ = _VENDOR_ID
    vendor_in_vendor = MagicMock()
    case = MagicMock()
    case.id_ = _CASE_ID

    call_order = []
    rm_calls = []

    def _rm_wait(*a, **kw):
        rm_calls.append(kw)
        call_order.append("rm_wait")

    monkeypatch.setattr(
        fv_demo_module, "wait_for_participant_rm_state", _rm_wait
    )
    monkeypatch.setattr(
        fv_demo_module,
        "actor_notifies_fix_ready",
        lambda *a, **kw: call_order.append("fix_ready"),
    )
    monkeypatch.setattr(
        fv_demo_module, "verify_fix_ready", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        fv_demo_module, "wait_for_participant_vfd_state", lambda *a, **kw: None
    )

    _phase_fix_lifecycle(
        finder_client=finder_client,
        vendor_client=vendor_client,
        vendor=vendor,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )

    assert (
        rm_calls
    ), "wait_for_participant_rm_state must be called (ADR-0058/CSB-18-001)"
    assert all(
        c.get("expected_states") == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
        for c in rm_calls
    ), "expected_states must be {ACCEPTED, DEFERRED, CLOSED} (CSB-18-001)"
    assert "rm_wait" in call_order and "fix_ready" in call_order
    assert call_order.index("rm_wait") < call_order.index(
        "fix_ready"
    ), "wait_for_participant_rm_state must precede actor_notifies_fix_ready (ADR-0058)"


# ===========================================================================
# Issue #2337 — fcvcv sync-verification gate semantics
# ===========================================================================


def test_fcvcv_sync_verification_uses_gate_not_check_for_ledger_coverage(
    monkeypatch,
):
    """Ledger coverage failures must say GATE FAILED, not CHECK FAILED.

    Before the fix demo_check was used for each replica's ledger coverage;
    on timeout it recorded CHECK FAILED but execution continued.  After the
    fix demo_gate is used so the failure is recorded as GATE FAILED.

    Regression guard for #2337.
    """
    reset_demo_failures()

    finder_client = MagicMock()
    finder_client.base_url = "http://finder:7999/api/v2"
    c1_client = MagicMock()
    c1_client.base_url = "http://c1:7999/api/v2"
    v1_client = MagicMock()
    v1_client.base_url = "http://v1:7999/api/v2"
    c2_client = MagicMock()
    c2_client.base_url = "http://c2:7999/api/v2"
    v2_client = MagicMock()
    v2_client.base_url = "http://v2:7999/api/v2"
    c1 = MagicMock()
    c1.id_ = "http://c1:7999/api/v2/actors/c1"
    finder = MagicMock()
    finder.id_ = "http://finder:7999/api/v2/actors/finder"
    case = MagicMock()
    case.id_ = _CASE_ID

    monkeypatch.setattr(
        fcvcv_demo_module,
        "_get_log_entries_for_case",
        lambda *a, **kw: [{"log_index": 5, "entry_hash": "abc123deadbeef0a"}],
    )

    def _ledger_coverage(
        client, case_id, expected_tail_index, timeout_seconds
    ):
        if client is finder_client:
            raise AssertionError(
                f"Timed out waiting for ledger coverage on {client.base_url}"
            )

    monkeypatch.setattr(
        fcvcv_demo_module,
        "wait_for_contiguous_ledger_coverage",
        _ledger_coverage,
    )
    monkeypatch.setattr(
        fcvcv_demo_module, "wait_for_case_participants", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        fcvcv_demo_module, "verify_replica_state", lambda *a, **kw: None
    )

    _phase_sync_verification(
        finder_client=finder_client,
        c1_client=c1_client,
        v1_client=v1_client,
        c2_client=c2_client,
        v2_client=v2_client,
        c1=c1,
        finder=finder,
        case=case,
        v1=MagicMock(),
        c2_in_c2=MagicMock(),
        v2=MagicMock(),
    )

    failures = demo_utils._demo_failures
    check_failures = [
        f for f in failures if "CHECK FAILED" in f and "ledger coverage" in f
    ]
    gate_failures = [
        f for f in failures if "GATE FAILED" in f and "ledger coverage" in f
    ]

    assert check_failures == [], (
        f"Found CHECK FAILED entries for ledger coverage: {check_failures!r}. "
        f"Ledger coverage must use demo_gate (not demo_check) per ADR-0058 (#2337)."
    )
    assert gate_failures, (
        f"No GATE FAILED entry found for ledger coverage in {failures!r}. "
        f"Expected demo_gate to record GATE FAILED on replication timeout (#2337)."
    )


def test_fcvcv_sync_verification_non_v2_timeout_is_at_least_30s(monkeypatch):
    """Non-V2 ledger coverage timeout must be at least 30 s.

    Before the fix the timeout for Finder/V1/C2 was 15 s — too tight for CI
    load.  After the fix it is 30 s.  V2 retains its 45 s as a late-joiner.

    Regression guard for #2337.
    """
    reset_demo_failures()

    finder_client = MagicMock()
    finder_client.base_url = "http://finder:7999/api/v2"
    c1_client = MagicMock()
    c1_client.base_url = "http://c1:7999/api/v2"
    v1_client = MagicMock()
    v1_client.base_url = "http://v1:7999/api/v2"
    c2_client = MagicMock()
    c2_client.base_url = "http://c2:7999/api/v2"
    v2_client = MagicMock()
    v2_client.base_url = "http://v2:7999/api/v2"
    c1 = MagicMock()
    c1.id_ = "http://c1:7999/api/v2/actors/c1"
    finder = MagicMock()
    finder.id_ = "http://finder:7999/api/v2/actors/finder"
    case = MagicMock()
    case.id_ = _CASE_ID

    monkeypatch.setattr(
        fcvcv_demo_module,
        "_get_log_entries_for_case",
        lambda *a, **kw: [{"log_index": 5, "entry_hash": "abc123deadbeef0a"}],
    )

    timeouts_by_client_id: dict[int, float] = {}

    def _ledger_coverage(
        client, case_id, expected_tail_index, timeout_seconds
    ):
        timeouts_by_client_id[id(client)] = timeout_seconds

    monkeypatch.setattr(
        fcvcv_demo_module,
        "wait_for_contiguous_ledger_coverage",
        _ledger_coverage,
    )
    monkeypatch.setattr(
        fcvcv_demo_module, "wait_for_case_participants", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        fcvcv_demo_module, "verify_replica_state", lambda *a, **kw: None
    )

    _phase_sync_verification(
        finder_client=finder_client,
        c1_client=c1_client,
        v1_client=v1_client,
        c2_client=c2_client,
        v2_client=v2_client,
        c1=c1,
        finder=finder,
        case=case,
        v1=MagicMock(),
        c2_in_c2=MagicMock(),
        v2=MagicMock(),
    )

    finder_timeout = timeouts_by_client_id.get(id(finder_client))
    assert (
        finder_timeout is not None
    ), "wait_for_contiguous_ledger_coverage was not called for finder_client"
    assert finder_timeout >= 30.0, (
        f"Finder ledger coverage timeout is {finder_timeout} s, expected >= 30.0 s. "
        f"CI load requires at least 30 s for non-V2 replicas (#2337)."
    )
