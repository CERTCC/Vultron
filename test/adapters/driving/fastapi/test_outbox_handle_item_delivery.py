#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""
Unit tests for handle_outbox_item — delivery, logging, and skip conditions.

The handler delivers the *sealed body* of an outbox row exactly as sealed
(VM-08-003).  These tests hand it a ``DataLayer`` double whose ``read``
answers the sealed-body id, and assert on what reaches the emitter.

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``

Spec coverage:
- OX-03-001: Activities in the outbox are delivered to recipient inboxes.
- VM-08-003: the delivered payload is the sealed blob, unchanged.
- SYNC-02-004: an Announce(CaseLedgerEntry) keeps its inline entry on the wire.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.adapters.outbox_sealed_body import (
    SealedOutboundBody,
    dump_outbound_body,
    sealed_body_id,
)

_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains

RECIPIENT = "https://example.org/actors/alice"
SENDER = "https://example.org/actors/bob"


def _sealed(activity_id: str, body: dict) -> SealedOutboundBody:
    """A sealed body for *activity_id* carrying *body* (id filled in)."""
    return SealedOutboundBody(
        id_=sealed_body_id(activity_id),
        activity_id=activity_id,
        body=json.dumps({"id": activity_id, **body}),
    )


def _dl_with(sealed: SealedOutboundBody | None) -> MagicMock:
    """A DataLayer double that answers the sealed-body id with *sealed*."""
    mock_dl = MagicMock()
    mock_dl.read.side_effect = lambda id_: (
        sealed if sealed is not None and id_ == sealed.id_ else None
    )
    return mock_dl


def _deliver(actor_id: str, activity_id: str, dl, emitter) -> None:
    asyncio.run(oh.handle_outbox_item(actor_id, activity_id, dl, emitter))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_handle_outbox_item_logs_actor_id(caplog):
    """handle_outbox_item should log the actor_id at INFO level."""
    mock_emitter = AsyncMock()
    with caplog.at_level("INFO"):
        _deliver("actor-abc", "urn:test:act-001", _dl_with(None), mock_emitter)
    assert "actor-abc" in caplog.text


def test_handle_outbox_item_logs_item(caplog):
    """handle_outbox_item should log the activity_id at INFO level."""
    mock_emitter = AsyncMock()
    with caplog.at_level("INFO"):
        _deliver("actor-abc", "urn:test:act-001", _dl_with(None), mock_emitter)
    assert "urn:test:act-001" in caplog.text


def test_handle_outbox_item_logs_activity_type_in_delivery(caplog):
    """handle_outbox_item logs the activity type in the delivery message."""
    sealed = _sealed(
        "urn:test:act-type-log",
        {"type": "Announce", "actor": SENDER, "to": [RECIPIENT], "object": {}},
    )
    with caplog.at_level("INFO"):
        _deliver(
            "actor-bob", sealed.activity_id, _dl_with(sealed), AsyncMock()
        )
    assert "Announce" in caplog.text


def test_handle_outbox_item_logs_recipient_in_delivery(caplog):
    """handle_outbox_item logs the recipient URL in the delivery message."""
    sealed = _sealed(
        "urn:test:act-recip-log",
        {"type": "Create", "actor": SENDER, "to": [RECIPIENT], "object": {}},
    )
    with caplog.at_level("INFO"):
        _deliver(
            "actor-bob", sealed.activity_id, _dl_with(sealed), AsyncMock()
        )
    assert RECIPIENT in caplog.text


def test_handle_outbox_item_delivery_log_summarises_the_object(caplog):
    """Delivery log names the object by type and id, not by a raw dump."""
    obj_id = "urn:uuid:case-001"
    sealed = _sealed(
        "urn:test:act-logclean",
        {
            "type": "Create",
            "actor": SENDER,
            "to": [RECIPIENT],
            "object": {"type": "VulnerabilityCase", "id": obj_id, "name": "x"},
        },
    )
    with caplog.at_level("INFO"):
        _deliver(
            "actor-bob", sealed.activity_id, _dl_with(sealed), AsyncMock()
        )

    delivery_log = " ".join(
        r.message for r in caplog.records if "Delivered" in r.message
    )
    assert delivery_log, "Expected a 'Delivered' log entry"
    assert f"VulnerabilityCase {obj_id}" in delivery_log
    assert '"name"' not in delivery_log


# ---------------------------------------------------------------------------
# Delivery and skip conditions
# ---------------------------------------------------------------------------


@pytest.mark.spec("OX-03-001")
@pytest.mark.spec("VM-08-003")
def test_handle_outbox_item_delivers_the_sealed_body_verbatim():
    """The emitter receives the sealed text itself, byte for byte."""
    sealed = _sealed(
        "urn:test:act-deliver",
        {"type": "Offer", "actor": SENDER, "to": [RECIPIENT], "object": {}},
    )
    mock_emitter = AsyncMock()

    _deliver("actor-abc", sealed.activity_id, _dl_with(sealed), mock_emitter)

    mock_emitter.emit.assert_called_once_with(
        sealed.activity_id, sealed.body, [RECIPIENT]
    )


def test_handle_outbox_item_drops_a_row_with_no_sealed_body(caplog):
    """A queued id nobody sealed has nothing to deliver: ERROR, no emit."""
    mock_emitter = AsyncMock()
    with caplog.at_level("ERROR"):
        _deliver(
            "actor-abc", "urn:test:act-gone", _dl_with(None), mock_emitter
        )
    mock_emitter.emit.assert_not_called()
    assert any(
        "No sealed body" in r.message and r.levelname == "ERROR"
        for r in caplog.records
    )


@pytest.mark.spec("OX-08-001")
def test_handle_outbox_item_refuses_a_to_that_names_nobody():
    """``to`` present but unusable (``[""]``) is refused like an absent one.

    Refusing here keeps the row from being silently consumed: before, it passed
    the non-empty-list check and was dropped at DEBUG.
    """
    from vultron.errors import VultronOutboxToFieldMissingError

    sealed = _sealed(
        "urn:test:act-nobody",
        {"type": "Offer", "actor": SENDER, "to": [""], "object": {}},
    )
    mock_emitter = AsyncMock()
    with pytest.raises(VultronOutboxToFieldMissingError):
        _deliver(
            "actor-abc", sealed.activity_id, _dl_with(sealed), mock_emitter
        )
    mock_emitter.emit.assert_not_called()


# ---------------------------------------------------------------------------
# What is sealed is what is delivered — the shapes the old re-read path lost
# ---------------------------------------------------------------------------


@pytest.mark.spec("VM-08-003")
@pytest.mark.spec("CM-17-002")
def test_handle_outbox_item_keeps_the_case_stub_target_inline():
    """An Invite's stub ``target`` reaches the emitter as the factory built it.

    The old path read the activity record back, rehydrated ``target`` into
    the full stored case and then collapsed it to a bare URI — so the stub
    with the embargo enrichment CM-17-002 requires never reached the wire.
    """
    case_id = "https://example.org/cases/case-123"
    stub = {"id": case_id, "type": "VulnerabilityCase", "activeEmbargo": {}}
    sealed = _sealed(
        "urn:uuid:act-invite-001",
        {
            "type": "Invite",
            "actor": "https://example.org/actors/coordinator",
            "to": [RECIPIENT],
            "object": {"id": "urn:uuid:actor-alice", "type": "Person"},
            "target": stub,
        },
    )
    mock_emitter = AsyncMock()

    _deliver(
        "actor-coordinator", sealed.activity_id, _dl_with(sealed), mock_emitter
    )

    _, body, recipients = mock_emitter.emit.call_args[0]
    assert json.loads(body)["target"] == stub
    assert recipients == [RECIPIENT]


@pytest.mark.spec("SYNC-02-004")
@pytest.mark.spec("SYNC-13-004")
def test_handle_outbox_item_preserves_inline_case_ledger_entry_fields():
    """Announce(as_CaseLedgerEntry) delivery keeps the full inline entry."""
    from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
    from vultron.core.models.case_ledger import HashChainLedgerRecord
    from vultron.wire.as2.factories import announce_log_entry_activity

    recipient = "https://example.org/actors/participant"
    chain_entry = HashChainLedgerRecord(
        case_id="https://example.org/cases/case-sync-2",
        log_index=0,
        object_id="https://example.org/activities/logged-2",
        event_type="log_entry_committed",
        payload_snapshot={"state": "replicated"},
        prev_log_hash=_ZERO_HASH,
    )
    entry = _to_persistable_entry(chain_entry)
    activity = announce_log_entry_activity(
        entry,
        actor="https://example.org/actors/case-actor",
        to=[recipient],
    )
    sealed = SealedOutboundBody(
        id_=sealed_body_id(activity.id_),
        activity_id=activity.id_,
        body=dump_outbound_body(activity),
    )
    mock_emitter = AsyncMock()

    _deliver("actor-case", activity.id_, _dl_with(sealed), mock_emitter)

    _, body, recipients = mock_emitter.emit.call_args[0]
    assert recipients == [recipient]
    emitted_object = json.loads(body)["object"]
    assert emitted_object["type"] == "CaseLedgerEntry"
    assert emitted_object["caseId"] == entry.case_id
    assert emitted_object["logObjectId"] == entry.log_object_id
    assert emitted_object["eventType"] == entry.event_type
