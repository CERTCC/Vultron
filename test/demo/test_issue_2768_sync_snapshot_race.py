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

``verify_replica_state`` reads the authoritative and replica ledgers with two
separate point-in-time DataLayer dumps.  Under the single-writer regime
(notes/sync-ledger-replication.md) the authoritative CaseActor is the only
writer, so its ledger is *always* a superset of any replica's — a replica only
ever holds an index because the auth committed it earlier and fanned it out.

The only way the auth can *appear* to lack an index the replica holds is a
**stale auth snapshot**: if the auth ledger is read first, a concurrent auth
commit landing before the replica read makes the auth snapshot older than the
replica snapshot, and the compare-index lookup then wrongly accuses the replica
of being "ahead of auth".

The fix reads the replica snapshot first and the auth snapshot second, so the
auth read is guaranteed to cover every index the replica reported.  This test
models a concurrent commit between the two reads and asserts no spurious
failure; it fails if the reads are ever reordered so auth is read first.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import vultron.demo.helpers.sync as sync_module

_CASE_ID = "urn:uuid:test-case-2768-0001"


def test_verify_replica_state_survives_stale_auth_snapshot(monkeypatch):
    """A concurrent auth commit between the ledger reads must not fire the
    compare-index assertion (#2768)."""
    # Both stores hold a matching, minimal copy of the case.
    monkeypatch.setattr(
        sync_module, "_case_or_none", lambda client, cid: {"id_": cid}
    )
    fake_case_cls = SimpleNamespace(
        model_validate=lambda data: SimpleNamespace(
            id_=_CASE_ID, actor_participant_index={}, active_embargo=None
        )
    )
    monkeypatch.setattr(sync_module, "as_VulnerabilityCase", fake_case_cls)

    # Model a concurrent auth commit landing between the two snapshot reads.
    # The first read observes indices 0..7; by the second read index 8 has been
    # committed and fanned out, so it observes 0..8.  The entry hash for a given
    # index is identical on both sides (one canonical hash chain).  Because the
    # skew is temporal, the return value depends on call order, not the client:
    # reading the replica first (0..7) then auth (0..8) compares at index 7 and
    # succeeds; reading auth first (0..7) then replica (0..8) compares at index
    # 8, which the stale auth snapshot lacks, and trips the assertion.
    calls = {"n": 0}

    def _staggered_entries(client, cid):
        calls["n"] += 1
        highest = min(6 + calls["n"], 8)  # call 1 -> 7, call 2 -> 8
        return [
            {"log_index": i, "entry_hash": f"hash-{i}", "case_id": cid}
            for i in range(highest + 1)
        ]

    monkeypatch.setattr(
        sync_module, "_get_log_entries_for_case", _staggered_entries
    )

    # Must not raise: the replica snapshot is read first, so the later auth
    # snapshot is a superset of the replica's tail index.
    sync_module.verify_replica_state(
        auth_client=MagicMock(),
        replica_client=MagicMock(),
        case_id=_CASE_ID,
        vendor_actor_id="urn:uuid:vendor",
        reporter_actor_id="urn:uuid:reporter",
    )
