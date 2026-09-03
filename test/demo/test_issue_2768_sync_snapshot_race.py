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

"""Regression guard for issue #2768.

``verify_replica_state`` compares a participant's copy of a case's activity
ledger against the authoritative (case-owner) copy.  In a multi-party case the
two ledgers grow independently and new entries propagate between participants
with a delay (SYNC fanout, see notes/sync-ledger-replication.md), so at any
single instant the authoritative copy may not yet hold an entry a replica has
already received — the entry is still *in flight*, not missing.

Issue #2768 originally read this as a snapshot read-ordering artifact.  It is
not: the fcvcv / fvcv-handoff demos showed the authoritative ledger genuinely
lacking the replica's tail index even when read last (freshest), because the
entry had reached the replica but not yet the authoritative copy.  Reordering
the two reads cannot fix an entry that is still arriving.

The fix waits for the authoritative ledger to catch up to the replica's tail
index (a bounded poll) and only reports divergence if it never does.  These
tests assert both halves of that behavior:

* a transiently-lagging authoritative ledger that catches up must **not** raise
  (the #2768 spurious failure), and
* an authoritative ledger that never gains the replica's tail entry **must**
  raise (genuine hash-chain divergence is still caught).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import vultron.demo.helpers.sync as sync_module

_CASE_ID = "urn:uuid:test-case-2768-0001"


def _entries_up_to(highest: int) -> list[dict]:
    """One canonical hash chain covering indices ``0..highest``."""
    return [
        {"log_index": i, "entry_hash": f"hash-{i}", "case_id": _CASE_ID}
        for i in range(highest + 1)
    ]


def _stub_case_reads(monkeypatch):
    """Make the case-existence and participant/embargo checks (steps 1-3) pass
    so control reliably reaches the log-consistency section under test."""
    monkeypatch.setattr(
        sync_module, "_case_or_none", lambda client, cid: {"id_": cid}
    )
    fake_case_cls = SimpleNamespace(
        model_validate=lambda data: SimpleNamespace(
            id_=_CASE_ID, actor_participant_index={}, active_embargo=None
        )
    )
    monkeypatch.setattr(sync_module, "as_VulnerabilityCase", fake_case_cls)


def test_verify_replica_state_waits_for_lagging_auth_ledger(monkeypatch):
    """An entry still in flight to the authoritative ledger must not be reported
    as divergence — the check waits for it to arrive (#2768)."""
    _stub_case_reads(monkeypatch)

    auth_client = MagicMock(name="auth")
    replica_client = MagicMock(name="replica")

    # The replica already holds index 8 (freshly fanned out to it). The
    # authoritative ledger is one entry behind on the first read and catches up
    # on the next — the entry was in flight, not missing.
    auth_reads = {"n": 0}

    def _entries(client, cid):
        if client is replica_client:
            return _entries_up_to(8)
        auth_reads["n"] += 1
        return _entries_up_to(7 if auth_reads["n"] == 1 else 8)

    monkeypatch.setattr(sync_module, "_get_log_entries_for_case", _entries)

    # Must not raise: the authoritative ledger covers index 8 by the second read.
    sync_module.verify_replica_state(
        auth_client=auth_client,
        replica_client=replica_client,
        case_id=_CASE_ID,
        vendor_actor_id="urn:uuid:vendor",
        reporter_actor_id="urn:uuid:reporter",
        auth_coverage_timeout_seconds=5.0,
        poll_interval_seconds=0.0,
    )
    # Proves the check re-read the authoritative ledger rather than asserting on
    # the first, still-lagging read.
    assert auth_reads["n"] >= 2


def test_verify_replica_state_reports_unrecoverable_divergence(monkeypatch):
    """If the authoritative ledger never gains the replica's tail entry, that is
    genuine divergence and must still be reported, not masked by the wait."""
    _stub_case_reads(monkeypatch)

    auth_client = MagicMock(name="auth")
    replica_client = MagicMock(name="replica")

    def _entries(client, cid):
        if client is replica_client:
            return _entries_up_to(8)
        return _entries_up_to(7)  # authoritative ledger never gains index 8

    monkeypatch.setattr(sync_module, "_get_log_entries_for_case", _entries)

    with pytest.raises(AssertionError, match="hash-chain divergence"):
        sync_module.verify_replica_state(
            auth_client=auth_client,
            replica_client=replica_client,
            case_id=_CASE_ID,
            vendor_actor_id="urn:uuid:vendor",
            reporter_actor_id="urn:uuid:reporter",
            auth_coverage_timeout_seconds=0.05,
            poll_interval_seconds=0.01,
        )
