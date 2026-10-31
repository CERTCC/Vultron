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

#2361: rv Demo Integration — M4/M5 vfd_state replication timeout
Two separate demo_check blocks both poll reporter_client for vfd_state=VFd
independently.  Under CI load Docker replication takes >30 s intermittently,
both checks time out, and two CHECK FAILED entries are recorded instead of
one — burying the real signal and making the run appear to have two distinct
failures when only one causal event (replication lag) caused them.

Fix: wrap the shared reporter poll and the M4/M5 milestones in a single
demo_gate; on timeout the gate records one GATE FAILED and the dependent
M4/M5 blocks are skipped entirely (ADR-0058).

#2337: rcvcv Demo Integration — intermittent Reporter ledger-coverage timeout
demo_check with 15 s timeout for Reporter/V1/C2 ledger coverage.  Under CI
load 15 s is too tight; the error log showed 0 of 29 entries present after
the check fired.  Fix: demo_gate (causal gate, not advisory check) and a 30 s
budget for the non-V2 replicas; V2 keeps the late-joiner budget.

Since #3846 the coverage loop lives in
``vultron.demo.helpers.sync.wait_for_replica_ledger_coverage``, whose default
early-replica budget is ``LEDGER_COVERAGE_TIMEOUT`` (30 s) and whose late-joiner
budget is ``LATE_JOINER_COVERAGE_TIMEOUT`` (45 s), so the #2337 guards below run
the real helper (patching its collaborators on the sync module) and assert the
*parameters* the helper applies, not a literal.

Since #5534 ``rcvcv`` is composed, so its sync-verification phase is the
``every_replica_converges`` story fragment rather than
``_phase_sync_verification``; the guards drive that fragment against a
stand-in cast (:func:`~test.demo._helpers.story_state`).
"""

from unittest.mock import MagicMock

import vultron.demo.helpers.sync as sync_module
import vultron.demo.scenario.rv_demo as rv_demo_module
import vultron.demo.utils as demo_utils
from test.demo._helpers import mock_case, story_state
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.coordinated_story import REPORTER
from vultron.demo.helpers.polling import (
    LATE_JOINER_COVERAGE_TIMEOUT,
    LEDGER_COVERAGE_TIMEOUT,
)
from vultron.demo.scenario.rcvcv_demo import (
    C1,
    C2,
    V1,
    V2,
    every_replica_converges,
)
from vultron.demo.scenario.rv_demo import _phase_fix_lifecycle
from vultron.demo.utils import reset_demo_failures

_CASE_ID = "urn:uuid:test-case-2361-0001"
_VENDOR_ID = "http://vendor:7999/api/v2/actors/vendor"

#: The five cast names ``every_replica_converges`` reads, in ``ROLES`` order.
_RCVCV_CAST = (REPORTER, C1, V1, C2, V2)


def _rcvcv_state():
    """A story state for ``rcvcv``'s sync phase, one client per container.

    Each client carries its own ``base_url`` so a recorded gate failure names
    the replica it is about, which is what these guards read.
    """
    state = story_state(*_RCVCV_CAST, case=mock_case(_CASE_ID))
    for name, host in zip(
        _RCVCV_CAST,
        ("reporter", "c1", "v1", "c2", "v2"),
        strict=True,
    ):
        state.client(name).base_url = f"http://{host}:7999/api/v2"
    return state


# ===========================================================================
# Issue #2361 — rv M4/M5 double failure when reporter replication times out
# ===========================================================================


def test_rv_reporter_timeout_records_single_gate_failure_not_two_check_failures(
    monkeypatch,
):
    """A single reporter replication timeout must produce exactly one GATE FAILED.

    Before the fix two independent demo_check blocks each polled reporter_client
    for vfd_state.  On timeout both recorded CHECK FAILED, producing two entries
    for a single causal event.  After the fix a single demo_gate wraps the
    shared reporter poll; M4/M5 are nested inside and skipped on gate failure.

    Regression guard for #2361.
    """
    reset_demo_failures()

    vendor_client = MagicMock()
    vendor_client.base_url = "http://vendor:7999/api/v2"
    reporter_client = MagicMock()
    reporter_client.base_url = "http://reporter:7999/api/v2"

    vendor = MagicMock()
    vendor.id_ = _VENDOR_ID
    vendor_in_vendor = MagicMock()
    case = MagicMock()
    case.id_ = _CASE_ID

    monkeypatch.setattr(
        ActorSession, "notify_fix_ready", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        rv_demo_module, "verify_fix_ready", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        rv_demo_module, "wait_for_participant_rm_state", lambda *a, **kw: None
    )

    def _vfd_poll(client, case_id, actor_id, expected_states, **kw):
        if client is reporter_client:
            raise AssertionError(
                f"Timed out waiting for vfd_state on {client.base_url}"
            )
        # vendor_client polls resolve immediately

    monkeypatch.setattr(
        rv_demo_module, "wait_for_participant_vf_state", _vfd_poll
    )

    _phase_fix_lifecycle(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        vendor=vendor,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )

    failures = demo_utils._demo_failures

    assert len(failures) == 1, (
        f"Expected exactly 1 failure when reporter replication times out, "
        f"got {len(failures)}: {failures!r}. "
        f"Two separate CHECK FAILED entries indicate demo_check is still used "
        f"for M4/M5 instead of a shared demo_gate (#2361)."
    )
    assert "GATE FAILED" in failures[0], (
        f"Expected 'GATE FAILED' in the failure message, "
        f"got {failures[0]!r}. "
        f"Use demo_gate (not demo_check) for the causal reporter precondition "
        f"(#2361, ADR-0058)."
    )


def test_rv_phase_fix_lifecycle_gates_on_rm_accepted(monkeypatch):
    """_phase_fix_lifecycle polls vendor RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (ADR-0058/CSB-18-001)."""
    from vultron.core.states.rm import RM

    reset_demo_failures()

    vendor_client = MagicMock()
    vendor_client.base_url = "http://vendor:7999/api/v2"
    reporter_client = MagicMock()
    reporter_client.base_url = "http://reporter:7999/api/v2"
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
        rv_demo_module, "wait_for_participant_rm_state", _rm_wait
    )
    monkeypatch.setattr(
        ActorSession,
        "notify_fix_ready",
        lambda *a, **kw: call_order.append("fix_ready"),
    )
    monkeypatch.setattr(
        rv_demo_module, "verify_fix_ready", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        rv_demo_module, "wait_for_participant_vf_state", lambda *a, **kw: None
    )

    _phase_fix_lifecycle(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        vendor=vendor,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )

    assert rm_calls, (
        "wait_for_participant_rm_state must be called (ADR-0058/CSB-18-001)"
    )
    assert all(
        c.get("expected_states") == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
        for c in rm_calls
    ), "expected_states must be {ACCEPTED, DEFERRED, CLOSED} (CSB-18-001)"
    assert "rm_wait" in call_order and "fix_ready" in call_order
    assert call_order.index("rm_wait") < call_order.index("fix_ready"), (
        "wait_for_participant_rm_state must precede actor_notifies_fix_ready (ADR-0058)"
    )


# ===========================================================================
# Issue #2337 — rcvcv sync-verification gate semantics
# ===========================================================================


def test_rcvcv_sync_verification_uses_gate_not_check_for_ledger_coverage(
    monkeypatch,
):
    """Ledger coverage failures must say GATE FAILED, not CHECK FAILED.

    Before the fix demo_check was used for each replica's ledger coverage;
    on timeout it recorded CHECK FAILED but execution continued.  After the
    fix demo_gate is used so the failure is recorded as GATE FAILED.

    Regression guard for #2337.
    """
    reset_demo_failures()

    state = _rcvcv_state()
    reporter_client = state.client(REPORTER)

    monkeypatch.setattr(
        sync_module,
        "wait_for_case_on_container",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        sync_module,
        "_get_log_entries_for_case",
        lambda *a, **kw: [{"log_index": 5, "entry_hash": "abc123deadbeef0a"}],
    )

    def _ledger_coverage(
        client, case_id, expected_tail_index, timeout_seconds
    ):
        if client is reporter_client:
            raise AssertionError(
                f"Timed out waiting for ledger coverage on {client.base_url}"
            )

    monkeypatch.setattr(
        sync_module,
        "wait_for_contiguous_ledger_coverage",
        _ledger_coverage,
    )
    monkeypatch.setattr(
        sync_module,
        "wait_for_participants_on_replicas",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        sync_module, "verify_replica_state", lambda *a, **kw: None
    )

    every_replica_converges(state)

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


def test_rcvcv_sync_verification_non_v2_timeout_is_at_least_30s(monkeypatch):
    """Non-V2 ledger coverage timeout must be at least 30 s.

    Before the fix the timeout for Reporter/V1/C2 was 15 s — too tight for CI
    load.  Those replicas now receive the shared helper's
    ``LEDGER_COVERAGE_TIMEOUT`` and V2, the late joiner, its
    ``LATE_JOINER_COVERAGE_TIMEOUT`` (#3846).

    Regression guard for #2337.
    """
    reset_demo_failures()

    state = _rcvcv_state()
    reporter_client = state.client(REPORTER)
    v1_client = state.client(V1)
    c2_client = state.client(C2)
    v2_client = state.client(V2)

    monkeypatch.setattr(
        sync_module,
        "wait_for_case_on_container",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        sync_module,
        "_get_log_entries_for_case",
        lambda *a, **kw: [{"log_index": 5, "entry_hash": "abc123deadbeef0a"}],
    )

    timeouts_by_client_id: dict[int, float] = {}

    def _ledger_coverage(
        client, case_id, expected_tail_index, timeout_seconds
    ):
        timeouts_by_client_id[id(client)] = timeout_seconds

    monkeypatch.setattr(
        sync_module,
        "wait_for_contiguous_ledger_coverage",
        _ledger_coverage,
    )
    monkeypatch.setattr(
        sync_module,
        "wait_for_participants_on_replicas",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        sync_module, "verify_replica_state", lambda *a, **kw: None
    )

    every_replica_converges(state)

    reporter_timeout = timeouts_by_client_id.get(id(reporter_client))
    assert reporter_timeout is not None, (
        "wait_for_contiguous_ledger_coverage was not called for reporter_client"
    )
    assert reporter_timeout >= 30.0, (
        f"Reporter ledger coverage timeout is {reporter_timeout} s, expected >= 30.0 s. "
        f"CI load requires at least 30 s for non-V2 replicas (#2337)."
    )
    assert reporter_timeout == LEDGER_COVERAGE_TIMEOUT
    assert timeouts_by_client_id[id(v1_client)] == LEDGER_COVERAGE_TIMEOUT
    assert timeouts_by_client_id[id(c2_client)] == LEDGER_COVERAGE_TIMEOUT
    assert timeouts_by_client_id[id(v2_client)] == LATE_JOINER_COVERAGE_TIMEOUT
    assert timeouts_by_client_id[id(v2_client)] >= 45.0
