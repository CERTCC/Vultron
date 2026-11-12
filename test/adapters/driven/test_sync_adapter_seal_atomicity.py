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

"""The sync adapter stores, seals and queues an activity together or not at all.

Sealing signs the body (SIG-01-001), so it can now fail on a body that cannot
be canonicalized.  A failed seal must leave no stored activity and no queued
id behind, or the outbox would hold an id with nothing to deliver.
"""

import pytest

from test.support.act_clock import ACT_AT
from test.support.objects import authored_at
from vultron.adapters.driven import sync_activity_adapter
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.wire.as2.errors import VultronUnsignableJsonError

OWNER = "https://example.org/actors/owner"
PEER = "https://example.org/actors/peer"
CASE = "https://example.org/cases/seal-atomicity"


def _entry() -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE,
            log_index=1,
            object_id="urn:test:activity-1",
            semantic_type="add_note",
            payload_snapshot={"log_index": 1},
            prev_log_hash="0" * 64,
            received_at=ACT_AT,
        )
    )


def _refuse_to_sign(*_args: object, **_kwargs: object) -> str:
    raise VultronUnsignableJsonError("value cannot be canonicalized")


@pytest.mark.spec("SIG-01-001")
def test_a_body_that_cannot_be_signed_leaves_nothing_behind(monkeypatch):
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)
    monkeypatch.setattr(
        sync_activity_adapter, "seal_outbound_body", _refuse_to_sign
    )

    with pytest.raises(VultronUnsignableJsonError):
        SyncActivityAdapter(dl).send_announce_log_entry(
            _entry(), OWNER, [PEER], at=authored_at()
        )

    assert dl.outbox_list() == []
    assert dl.list_objects("Announce") == []


def test_a_signed_announce_is_stored_sealed_and_queued():
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)

    assert SyncActivityAdapter(dl).send_announce_log_entry(
        _entry(), OWNER, [PEER], at=authored_at()
    )

    [queued] = dl.outbox_list()
    assert dl.read(queued) is not None
    body = sync_activity_adapter.read_sealed_body_dict(dl, queued)
    assert body is not None and "proof" in body
