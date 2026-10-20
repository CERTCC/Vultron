#!/usr/bin/env python

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

"""A replica's Announce of the ownership-transfer Offer entry writes nothing.

The CASE_MANAGER makes the one ownership-transfer Offer and ledgers it
(ADR-0148).  The transferee answers that Offer from its intake archive, the
owner holds its own proposal, and a bystander never answers, so no replica
keeps a record of the Offer: the ``offer_case_ownership_transfer`` entry has
no effect to apply.  The entry itself is still persisted (SYNC-12-001), and
nothing is written under the Offer's id, an id its sender chose (DL-06-006).
"""

import importlib
import uuid
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    _make_event,
    _to_persistable_entry,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.models.actor import VultronService
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE,
)
from vultron.core.models.registry import CORE_TYPE_MAP, CORE_VOCABULARY
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

OWNER_ID = "https://example.org/actors/original-owner"
REPLICA_ID = "https://example.org/actors/bystander"
TRANSFEREE_ID = "https://example.org/actors/transferee"
CASE_ID = "https://example.org/cases/ownership-offer-replay"


@pytest.fixture
def datalayer():
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=REPLICA_ID)
    yield dl
    dl.close()


@pytest.fixture
def case_actor(datalayer) -> VultronService:
    """The CaseActor that signs the replicated Announce(CaseLedgerEntry)."""
    actor = VultronService(
        name="Case Actor", attributed_to=OWNER_ID, context=CASE_ID
    )
    datalayer.create(actor)
    return actor


@pytest.fixture
def case_replica(datalayer) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ID)
    datalayer.save(case)
    return case


def _offer_entry(
    offer_id: str, case_manager_id: str, prev_hash: str
) -> HashChainLedgerRecord:
    """The CASE_MANAGER's ``offer_case_ownership_transfer`` entry.

    The Offer is the CASE_MANAGER's own, made on the owner's behalf
    (ADR-0148): its ``actor`` is the CASE_MANAGER, its ``attributedTo`` the
    owner.
    """
    return HashChainLedgerRecord(
        case_id=CASE_ID,
        log_index=0,
        object_id=offer_id,
        semantic_type=OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE,
        payload_snapshot={
            "type": "Offer",
            "id": offer_id,
            "actor": case_manager_id,
            "attributedTo": OWNER_ID,
            "context": CASE_ID,
            "object": {"id": CASE_ID, "type": "VulnerabilityCase"},
            "target": {"id": TRANSFEREE_ID, "type": "Actor"},
        },
        prev_log_hash=prev_hash,
    )


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("DL-06-006")
def test_offer_entry_persists_and_writes_nothing_else(
    datalayer, case_actor, case_replica
):
    offer_id = f"urn:uuid:{uuid.uuid4()}"
    entry = _to_persistable_entry(
        _offer_entry(offer_id, case_actor.id_, case_replica.genesis_hash)
    )
    event = _make_event(entry, actor_id=case_actor.id_, to=[REPLICA_ID])
    before = datalayer.count_all()

    result = BTBridge(datalayer=datalayer).execute_with_setup(
        tree=create_announce_log_entry_tree(
            sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
        ),
        actor_id=REPLICA_ID,
        activity=event,
        sync_port=MagicMock(spec=SyncActivityPort),
    )

    assert result.status == Status.SUCCESS
    # The entry is persisted (SYNC-12-001) ...
    (stored,) = datalayer.list_objects("CaseLedgerEntry")
    assert getattr(stored, "log_object_id", None) == offer_id
    # ... and nothing is written for the Offer, under its id or any other:
    # the only other new row is intake's archive of the Announce itself
    # (CLP-10-017).
    assert datalayer.read(offer_id) is None
    after = datalayer.count_all()
    grown = {
        type_: after[type_] - before.get(type_, 0)
        for type_ in after
        if after[type_] != before.get(type_, 0)
    }
    assert grown == {"CaseLedgerEntry": 1, "ReceivedActivityRecord": 1}


def test_no_replica_record_of_the_offer_exists():
    """The ledger-replayed Offer record is gone (ADR-0148, #4911)."""
    assert "VultronOwnershipTransferOfferRecord" not in CORE_VOCABULARY
    assert "VultronOwnershipTransferOfferRecord" not in CORE_TYPE_MAP
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(
            "vultron.core.models.ownership_transfer_offer_record"
        )
