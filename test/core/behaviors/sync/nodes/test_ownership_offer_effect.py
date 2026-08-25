#!/usr/bin/env python
"""Unit tests for the OfferOwnershipTransferEffects slot nodes (#2195).

Covers ``IsOfferOwnershipTransferEventNode`` and
``ApplyOfferOwnershipTransferFromLedgerNode`` directly, plus the
``VultronOwnershipTransferOfferRecord`` round-trip they depend on.

The end-to-end path through ``create_announce_log_entry_tree`` is covered by
test_issue_2195_ownership_offer_delivered.py; this module pins the individual
node contracts that the tree-level probe cannot distinguish — in particular the
SYNC-12-001 status contract:

- nothing to apply (no offer id, no case id) -> SUCCESS, nothing stored
- effect failed (DataLayer write raised)     -> FAILURE, so the surrounding
  Selector blocks PersistReceivedLogEntry

See CM-21-005, SYNC-02-002, SYNC-12-001, ADR-0035 DL-06-002.
"""

import uuid
from typing import Any, cast

import pytest
from py_trees.common import Status
from pydantic import ValidationError

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.sync.nodes.ownership_offer_effect import (
    ApplyOfferOwnershipTransferFromLedgerNode,
    IsOfferOwnershipTransferEventNode,
)
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.ownership_transfer_offer_record import (
    VultronOwnershipTransferOfferRecord,
)
from vultron.core.models.registry import CORE_VOCABULARY

_ZERO_HASH = "0" * 64
OFFER_EVENT = "offer_case_ownership_transfer"

# Distinguishes "caller did not specify object" (use the realistic inline dict)
# from "caller explicitly passed None" (exercise the no-case-id path).
_DEFAULT_OBJECT = object()


def _offer_entry(
    offer_id: str,
    object_field: Any = _DEFAULT_OBJECT,
    event_type: str = OFFER_EVENT,
):
    """Return a ledger entry for an ownership-transfer offer.

    ``object_field`` defaults to the inline-dict form the real snapshot uses.
    Pass a bare URI string or ``None`` to exercise the other shapes.
    """
    snapshot: dict[str, Any] = {
        "type": "Offer",
        "id": offer_id,
        "actor": "https://example.org/actors/original-owner",
        "context": CASE_ID,
    }
    if object_field is _DEFAULT_OBJECT:
        snapshot["object"] = {"id": CASE_ID, "type": "VulnerabilityCase"}
    else:
        snapshot["object"] = object_field

    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=offer_id,
            event_type=event_type,
            payload_snapshot=snapshot,
            prev_log_hash=_ZERO_HASH,
        )
    )


def _run_effect(bridge, entry, case_actor):
    return bridge.execute_with_setup(
        tree=ApplyOfferOwnershipTransferFromLedgerNode(
            name="ApplyOfferOwnershipTransferFromLedger"
        ),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=case_actor.id_),
    )


# ---------------------------------------------------------------------------
# IsOfferOwnershipTransferEventNode
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-12-001")
def test_condition_succeeds_on_offer_event(bridge, case_actor):
    """SUCCESS when the entry's event_type is offer_case_ownership_transfer."""
    entry = _offer_entry(offer_id=f"urn:uuid:{uuid.uuid4()}")
    result = bridge.execute_with_setup(
        tree=IsOfferOwnershipTransferEventNode(
            name="IsOfferOwnershipTransfer"
        ),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=case_actor.id_),
    )
    assert result.status == Status.SUCCESS


@pytest.mark.spec("SYNC-12-001")
def test_condition_fails_on_other_event(bridge, case_actor):
    """FAILURE for any other event_type — the Inverter arm handles routing."""
    entry = _offer_entry(
        offer_id=f"urn:uuid:{uuid.uuid4()}",
        event_type="accept_case_ownership_transfer",
    )
    result = bridge.execute_with_setup(
        tree=IsOfferOwnershipTransferEventNode(
            name="IsOfferOwnershipTransfer"
        ),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=case_actor.id_),
    )
    assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# ApplyOfferOwnershipTransferFromLedgerNode — happy paths
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("SYNC-12-002")
def test_effect_stores_record_from_inline_object(
    bridge, datalayer, case_actor
):
    """The offer is materialized keyed by offer_id, naming the offered case."""
    offer_id = f"urn:uuid:{uuid.uuid4()}"
    assert _run_effect(bridge, _offer_entry(offer_id), case_actor).status == (
        Status.SUCCESS
    )

    stored = cast(
        VultronOwnershipTransferOfferRecord, datalayer.read(offer_id)
    )
    assert isinstance(stored, VultronOwnershipTransferOfferRecord)
    assert stored.id_ == offer_id
    assert stored.offer_id == offer_id
    assert stored.case_id == CASE_ID


@pytest.mark.spec("SYNC-12-001")
def test_effect_accepts_bare_string_object(bridge, datalayer, case_actor):
    """`object` may be a bare URI string rather than an inline dict."""
    offer_id = f"urn:uuid:{uuid.uuid4()}"
    entry = _offer_entry(offer_id, object_field=CASE_ID)
    assert _run_effect(bridge, entry, case_actor).status == Status.SUCCESS

    stored = cast(
        VultronOwnershipTransferOfferRecord, datalayer.read(offer_id)
    )
    assert stored.case_id == CASE_ID


@pytest.mark.spec("SYNC-12-003")
def test_effect_is_idempotent(bridge, datalayer, case_actor):
    """A replayed entry is a no-op, not an overwrite or an error."""
    offer_id = f"urn:uuid:{uuid.uuid4()}"
    entry = _offer_entry(offer_id)

    for _ in range(2):
        assert _run_effect(bridge, entry, case_actor).status == Status.SUCCESS

    stored = cast(
        VultronOwnershipTransferOfferRecord, datalayer.read(offer_id)
    )
    assert stored.case_id == CASE_ID


# ---------------------------------------------------------------------------
# Nothing-to-apply paths -> SUCCESS, nothing stored
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-12-001")
def test_effect_declines_to_store_record_without_case_id(
    bridge, datalayer, case_actor
):
    """No resolvable case id -> SUCCESS but NOTHING stored (#2195).

    Storing a record that cannot name its case would satisfy
    ``_prepare``'s ``dl.read(offer_id)`` and then fail one line later on the
    case lookup — converting a "missing offer" 404 into a "missing case" 404
    rather than fixing anything.
    """
    offer_id = f"urn:uuid:{uuid.uuid4()}"
    entry = _offer_entry(offer_id, object_field=None)

    assert _run_effect(bridge, entry, case_actor).status == Status.SUCCESS
    assert datalayer.read(offer_id) is None


@pytest.mark.spec("SYNC-12-001")
def test_effect_falls_back_to_log_object_id(bridge, datalayer, case_actor):
    """A snapshot with no ``id`` key falls back to the entry's log_object_id.

    A ledger entry always carries a non-empty ``object_id``, so the offer id is
    recoverable even from a snapshot that omits it — which is why the
    "no offer id at all" branch cannot be reached through a well-formed entry.
    """
    offer_id = f"urn:uuid:{uuid.uuid4()}"
    entry = _offer_entry(offer_id)
    del entry.payload_snapshot["id"]

    assert _run_effect(bridge, entry, case_actor).status == Status.SUCCESS

    stored = cast(
        VultronOwnershipTransferOfferRecord, datalayer.read(offer_id)
    )
    assert stored is not None
    assert stored.offer_id == offer_id
    assert stored.case_id == CASE_ID


# ---------------------------------------------------------------------------
# Effect-failed path -> FAILURE (SYNC-12-001)
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("SYNC-12-002")
def test_effect_fails_when_datalayer_write_raises(
    bridge, datalayer, case_actor, monkeypatch
):
    """A well-formed effect that cannot be written MUST fail (SYNC-12-001).

    Returning SUCCESS here would let PersistReceivedLogEntry commit the ledger
    entry without its effect ever having been applied.
    """
    offer_id = f"urn:uuid:{uuid.uuid4()}"

    def _boom(_obj):
        raise RuntimeError("datalayer unavailable")

    monkeypatch.setattr(datalayer, "save", _boom)

    result = _run_effect(bridge, _offer_entry(offer_id), case_actor)
    assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# VultronOwnershipTransferOfferRecord
# ---------------------------------------------------------------------------


def test_record_is_registered_in_core_vocabulary():
    """Registration under the class name is what makes the read round-trip."""
    assert (
        CORE_VOCABULARY.get("VultronOwnershipTransferOfferRecord")
        is VultronOwnershipTransferOfferRecord
    )


@pytest.mark.parametrize("bad_case_id", ["", None])
def test_record_rejects_missing_or_empty_case_id(bad_case_id):
    """case_id is a required non-empty URI (CS-08-002, ARCH-10-001)."""
    with pytest.raises(ValidationError):
        VultronOwnershipTransferOfferRecord(
            offer_id=f"urn:uuid:{uuid.uuid4()}",
            case_id=bad_case_id,
        )


def test_record_round_trips_through_datalayer():
    """case_id survives save/read — the fact _prepare depends on."""
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=PARTICIPANT_ACTOR_ID,
    )
    try:
        offer_id = f"urn:uuid:{uuid.uuid4()}"
        dl.save(
            VultronOwnershipTransferOfferRecord(
                offer_id=offer_id, case_id=CASE_ID
            )
        )
        back = dl.read(offer_id)
        assert isinstance(back, VultronOwnershipTransferOfferRecord)
        assert back.case_id == CASE_ID
    finally:
        dl.close()


# ---------------------------------------------------------------------------
# #2225 — the adapter must be able to accept from a SYNC-only replica
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-12-001")
def test_effect_records_offer_actor_and_target(bridge, datalayer, case_actor):
    """actor/target are recorded so the adapter can rebuild the wire Offer."""
    offer_id = f"urn:uuid:{uuid.uuid4()}"
    entry = _offer_entry(offer_id)
    entry.payload_snapshot["target"] = {
        "id": "https://example.org/actors/transferee",
        "type": "Actor",
    }

    assert _run_effect(bridge, entry, case_actor).status == Status.SUCCESS

    stored = cast(
        VultronOwnershipTransferOfferRecord, datalayer.read(offer_id)
    )
    assert stored.actor_id == "https://example.org/actors/original-owner"
    assert stored.target_id == "https://example.org/actors/transferee"


@pytest.mark.spec("SYNC-12-001")
def test_adapter_accepts_transfer_from_sync_only_replica(
    bridge, datalayer, case_actor, case_obj
):
    """accept_case_ownership_transfer works when only the core record exists.

    Regression for #2225: the replica's DataLayer holds a
    VultronOwnershipTransferOfferRecord at offer_id, not the wire
    _OfferCaseOwnershipTransferActivity that
    accept_case_ownership_transfer_activity requires.  Before the adapter
    learned to rebuild the wire Offer, this raised a ValidationError surfaced
    to the demo as `422 ... accept_case_ownership_transfer_activity: invalid
    arguments`.
    """
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    transferee = "https://example.org/actors/transferee"
    offer_id = f"urn:uuid:{uuid.uuid4()}"
    entry = _offer_entry(offer_id)
    entry.payload_snapshot["target"] = {"id": transferee, "type": "Actor"}

    assert _run_effect(bridge, entry, case_actor).status == Status.SUCCESS
    assert isinstance(
        datalayer.read(offer_id), VultronOwnershipTransferOfferRecord
    )

    activity_id, activity = TriggerActivityAdapter(
        datalayer
    ).accept_case_ownership_transfer(offer_id=offer_id, actor=transferee)

    assert activity_id
    assert activity["type"] == "Accept"
    # The Accept must carry the Offer inline, with the case inline inside it.
    assert activity["object"]["id"] == offer_id
    assert activity["object"]["object"]["id"] == CASE_ID
    # to: falls back to the offering actor recorded on the core record.
    assert activity["to"] == ["https://example.org/actors/original-owner"]
