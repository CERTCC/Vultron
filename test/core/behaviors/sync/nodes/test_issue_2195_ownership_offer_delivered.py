#!/usr/bin/env python
"""Ratchet probe for ISSUE-2195.

#2195: "ownership-transfer Offer object never delivered to the receiving
Coordinator's DataLayer."  In fvcv-handoff, the source actor's forwarded
``_OfferCaseOwnershipTransferActivity`` (keyed by its offer id) never lands in
the receiving Coordinator's DataLayer, so ``accept-case-ownership-transfer``
404s: ``SvcAcceptCaseOwnershipTransferUseCase._prepare`` calls
``self._dl.read(request.offer_id)`` (vultron/core/use_cases/triggers/actor.py
~line 360) and raises
``VultronNotFoundError("_OfferCaseOwnershipTransferActivity", offer_id)``.
Live signature: repeated ``GET /api/v2/datalayer/<offer_id> -> 404``.

WHY A NODE-LEVEL PROBE (and its limits)
---------------------------------------
On the wire, the forwarded Offer reaches the Coordinator via the CaseActor's
outbox -> HTTP inbox delivery, where ``OfferCaseOwnershipTransferReceived-
UseCase._idempotent_create`` would store it.  That delivery hop is an
HTTP-outbox concern with no pure core node, so the authoritative end-to-end
signal for #2195 is the fvcv-handoff CI job (the demo's
``find_ownership_transfer_offer_for_actor(coordinator_client, ...)`` poll).

This test therefore asserts the CLOSEST faithful core-layer analog, exactly as
the task and the sibling #2193 probe prescribe: a Coordinator replica processes
the replicated ``Announce(CaseLedgerEntry)`` for the ownership-transfer *offer*
through the canonical ``create_announce_log_entry_tree`` and must end up with
the offer object readable from its DataLayer.  It does NOT: the announce tree
has effect slots for embargo / participant-status / note / invite-accept /
close-case / offer-report / ownership-transfer-*accept* (which only updates
``attributed_to``), but NO slot materializes the offer object for an
``offer_case_ownership_transfer`` entry.  This mirrors the pre-#2180/#2187 gap
where the report object was not backfilled from its ledger snapshot until
``ApplyOfferReportFromLedgerNode`` learned to reconstruct it.

The ``xfail(strict=True)`` marker resolves the probe objectively:

- ``xfailed``  -> the gap is real on HEAD (offer object NOT materialized).
- ``xpassed``  -> #2195 is fixed (a ledger-backfill effect now stores it);
                  remove the xfail marker.

Harness: SqliteDataLayer in-memory + BTBridge, mirroring
test_issue_2193_report_replicated_post_transfer.py and test_announce_tree.py.
NO Docker.
"""

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
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# Populate the vocabulary registry as an import side-effect.
_ = as_VulnerabilityCase

# The CaseActor (owner) that signs the replicated Announce(CaseLedgerEntry)s.
OWNER_ACTOR_ID = "https://example.org/actors/original-owner"
# The actor being offered ownership (the Coordinator, in fvcv-handoff terms).
COORDINATOR_ACTOR_ID = "https://example.org/actors/coordinator"
# The Coordinator's own participant identity that owns this replica.
PARTICIPANT_ACTOR_ID = COORDINATOR_ACTOR_ID
CASE_ID = "https://example.org/cases/ownership-2195"
# The forwarded _OfferCaseOwnershipTransferActivity id — the exact id the
# accept trigger later does dl.read(offer_id) on and 404s.
OFFER_ID = f"urn:uuid:{uuid.uuid4()}"


@pytest.fixture
def datalayer():
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=PARTICIPANT_ACTOR_ID,
    )
    yield dl
    dl.close()


@pytest.fixture
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def case_actor(datalayer):
    """The CaseActor that signs the replicated Announce(CaseLedgerEntry)s."""
    actor = VultronCaseActor(
        name="Case Actor",
        attributed_to=OWNER_ACTOR_ID,
        context=CASE_ID,
    )
    datalayer.create(actor)
    return actor


@pytest.fixture
def case_replica(datalayer):
    """Seed a case replica on the Coordinator (genesis anchor).

    Models the freshly-seeded case state the Coordinator holds before it
    replays the replicated ledger stream — the ownership-transfer offer object
    was never seeded here.
    """
    case = as_VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    datalayer.save(case)
    return case


def _offer_ownership_transfer_record(prev_hash: str) -> HashChainLedgerRecord:
    """Ownership-transfer *offer* ledger entry (event_type from StrEnum value).

    ``MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER.value`` is
    ``"offer_case_ownership_transfer"`` — the exact event_type
    ``CommitCaseLedgerEntryNode`` writes for the forwarded Offer.  The snapshot
    embeds the full forwarded Offer activity (id=OFFER_ID, target=Coordinator,
    object=case) so a future backfill effect would have everything it needs.
    """
    return HashChainLedgerRecord(
        case_id=CASE_ID,
        log_index=0,
        object_id=OFFER_ID,
        event_type="offer_case_ownership_transfer",
        payload_snapshot={
            "type": "Offer",
            "id": OFFER_ID,
            "actor": OWNER_ACTOR_ID,
            "context": CASE_ID,
            "object": {"id": CASE_ID, "type": "VulnerabilityCase"},
            "target": {"id": COORDINATOR_ACTOR_ID, "type": "Actor"},
        },
        prev_log_hash=prev_hash,
    )


def test_ownership_offer_object_materialized_on_coordinator_replica(
    bridge, datalayer, case_actor, case_replica
):
    """The forwarded Offer object MUST be readable on the Coordinator replica.

    The Coordinator replays the replicated ledger stream:
      1. offer_case_ownership_transfer  (the forwarded Offer)
    After processing that Announce(CaseLedgerEntry), the
    ``_OfferCaseOwnershipTransferActivity`` keyed by OFFER_ID MUST be readable
    from the Coordinator's DataLayer — otherwise ``accept-case-ownership-
    transfer`` 404s in SvcAcceptCaseOwnershipTransferUseCase._prepare (#2195).
    """
    tree = create_announce_log_entry_tree

    offer_record = _offer_ownership_transfer_record(case_replica.genesis_hash)
    offer_entry = _to_persistable_entry(offer_record)
    offer_event = _make_event(offer_entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=offer_event,
        sync_port=MagicMock(spec=SyncActivityPort),
    )

    # Sanity: the replicated entry was accepted and persisted cleanly — the
    # probe is about the OFFER OBJECT, not ledger acceptance.
    assert result.status == Status.SUCCESS

    # KEY ASSERTION (#2195): the forwarded ownership-transfer Offer object must
    # be materialized on the Coordinator's replica, keyed by its offer id.
    stored_offer = datalayer.read(OFFER_ID)
    assert stored_offer is not None and not isinstance(
        stored_offer, CaseLedgerEntry
    ), (
        "The _OfferCaseOwnershipTransferActivity must be readable on the "
        "Coordinator's DataLayer (keyed by offer_id) after it processes the "
        "Announce(CaseLedgerEntry) for the ownership-transfer offer — "
        "otherwise accept-case-ownership-transfer 404s on dl.read(offer_id) "
        "(#2195)."
    )

    # Presence alone is not enough: _prepare reads the case URI back off the
    # stored record and raises VultronNotFoundError when it cannot resolve one.
    # Without this second assertion the probe passes on a record that still
    # 404s the accept trigger — it merely moves the 404 one line down.
    assert (
        _as_id(
            getattr(stored_offer, "case_id", None)
            or getattr(stored_offer, "object_", None)
        )
        == CASE_ID
    ), (
        "The materialized offer must name the case it offers, so "
        "SvcAcceptCaseOwnershipTransferUseCase._prepare can recover case_id "
        "from it (#2195)."
    )
