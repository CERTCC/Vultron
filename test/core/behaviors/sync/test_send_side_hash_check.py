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

"""Send-side hash check: the CASE_MANAGER holds back an entry it cannot verify.

Every test here is a strict ``xfail`` for unbuilt behaviour (SYNC-03-009).
The implementation issue removes the ``xfail`` and adds a test for each send
site.
"""

from typing import cast

import pytest

from vultron.core.behaviors.sync.nodes.embargo_pause import send_ledger_suffix
from vultron.core.models.case_ledger import (
    CaseLedgerEntry,
    HashChainLedgerRecord,
)
from vultron.core.ports.sync_activity import SyncActivityPort

_CASE_ID = "https://example.org/cases/case-send-side-hash-001"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_PEER_ID = "https://example.org/actors/vendor"


class _RecordingSyncPort:
    """Records each ``Announce(CaseLedgerEntry)`` it is asked to queue."""

    def __init__(self) -> None:
        self.sent: list[int] = []

    def send_announce_log_entry(
        self, entry: CaseLedgerEntry, actor_id: str, to: list[str]
    ) -> bool:
        self.sent.append(entry.log_index)
        return True


def _chain(length: int) -> list[CaseLedgerEntry]:
    entries: list[CaseLedgerEntry] = []
    prev = "genesis"
    for log_index in range(length):
        entry = HashChainLedgerRecord(
            case_id=_CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/{log_index}",
            semantic_type="test_event",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev,
        ).to_ledger_entry()
        entries.append(entry)
        prev = entry.entry_hash
    return entries


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-03-009: no send-side hash check yet. Tracked by #5095.",
)
@pytest.mark.spec("SYNC-03-009")
def test_replay_stops_at_an_entry_whose_content_does_not_reproduce_its_hash() -> (
    None
):
    """Entries before the broken one go out; it and everything after do not."""
    entries = _chain(4)
    entries[2] = entries[2].model_copy(
        update={"payload_snapshot": {"log_index": "tampered"}}
    )
    port = _RecordingSyncPort()

    send_ledger_suffix(
        cast(SyncActivityPort, port),
        entries,
        after_index=-1,
        actor_id=_CASE_ACTOR_ID,
        peer_id=_PEER_ID,
    )

    assert port.sent == [0, 1]
