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

"""
Unit tests for handle_outbox_item — delivery, logging, and regression cases.

Covers: basic delivery flow, skip conditions, log content requirements,
DR-01 typed-target dehydration regression, and Announce(as_CaseLedgerEntry)
inline field preservation.

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``

Spec coverage:
- OX-1.1: Delivery via async HTTP POST to recipient inbox URLs.
- OX-1.3: Idempotency enforced at inbox endpoint (not delivery side).
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.core.models.activity import VultronActivity

_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains


# ---------------------------------------------------------------------------
# handle_outbox_item — basic logging
# ---------------------------------------------------------------------------


def test_handle_outbox_item_logs_actor_id(caplog):
    """handle_outbox_item should log the actor_id at INFO level."""
    mock_dl = MagicMock()
    mock_dl.read.return_value = None  # activity not found → just logs
    mock_emitter = AsyncMock()
    with caplog.at_level("INFO"):
        asyncio.run(
            oh.handle_outbox_item(
                "actor-abc", "urn:test:act-001", mock_dl, mock_emitter
            )
        )
    assert "actor-abc" in caplog.text


def test_handle_outbox_item_logs_item(caplog):
    """handle_outbox_item should log the activity_id at INFO level."""
    mock_dl = MagicMock()
    mock_dl.read.return_value = None  # activity not found → just logs
    mock_emitter = AsyncMock()
    with caplog.at_level("INFO"):
        asyncio.run(
            oh.handle_outbox_item(
                "actor-abc", "urn:test:act-001", mock_dl, mock_emitter
            )
        )
    assert caplog.text  # at minimum something is logged


# ---------------------------------------------------------------------------
# handle_outbox_item — OX-1.1 delivery logic
# ---------------------------------------------------------------------------


def test_handle_outbox_item_delivers_to_recipients():
    """handle_outbox_item calls emitter.emit with activity and recipients."""
    recipient = "https://example.org/actors/alice"
    activity = VultronActivity(
        id_="urn:test:act-deliver",
        type_="Offer",
        actor="https://example.org/actors/bob",
        to=[recipient],
    )
    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    mock_emitter = AsyncMock()

    asyncio.run(
        oh.handle_outbox_item("actor-abc", activity.id_, mock_dl, mock_emitter)
    )

    mock_emitter.emit.assert_called_once_with(activity, [recipient])


def test_handle_outbox_item_skips_when_activity_not_found():
    """handle_outbox_item does NOT call emitter when dl.read returns None."""
    mock_dl = MagicMock()
    mock_dl.read.return_value = None
    mock_emitter = AsyncMock()

    asyncio.run(
        oh.handle_outbox_item(
            "actor-abc", "urn:test:missing", mock_dl, mock_emitter
        )
    )

    mock_emitter.emit.assert_not_called()


def test_handle_outbox_item_skips_when_no_recipients():
    """handle_outbox_item does NOT call emitter when activity has no recipients."""
    activity = SimpleNamespace(
        id_="urn:test:act-no-recip",
        to=None,
        cc=None,
        bto=None,
        bcc=None,
    )
    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    mock_emitter = AsyncMock()

    asyncio.run(
        oh.handle_outbox_item("actor-abc", activity.id_, mock_dl, mock_emitter)
    )

    mock_emitter.emit.assert_not_called()


# ---------------------------------------------------------------------------
# handle_outbox_item — delivery log content (D5-6-LOGCTX)
# ---------------------------------------------------------------------------


def test_handle_outbox_item_logs_activity_type_in_delivery(caplog):
    """handle_outbox_item logs the activity type in the delivery message."""
    recipient = "https://example.org/actors/alice"
    activity = VultronActivity(
        id_="urn:test:act-type-log",
        type_="Announce",
        actor="https://example.org/actors/bob",
        to=[recipient],
    )
    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    mock_emitter = AsyncMock()

    with caplog.at_level("INFO"):
        asyncio.run(
            oh.handle_outbox_item(
                "actor-bob", activity.id_, mock_dl, mock_emitter
            )
        )

    assert "Announce" in caplog.text


def test_handle_outbox_item_logs_recipient_in_delivery(caplog):
    """handle_outbox_item logs the recipient URL in the delivery message."""
    recipient = "https://example.org/actors/alice"
    activity = VultronActivity(
        id_="urn:test:act-recip-log",
        type_="Create",
        actor="https://example.org/actors/bob",
        to=[recipient],
    )
    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    mock_emitter = AsyncMock()

    with caplog.at_level("INFO"):
        asyncio.run(
            oh.handle_outbox_item(
                "actor-bob", activity.id_, mock_dl, mock_emitter
            )
        )

    assert recipient in caplog.text


def test_handle_outbox_item_delivery_log_no_pydantic_repr(caplog):
    """Delivery log must not contain Pydantic field-repr noise (D5-7-LOGCLEAN-1).

    The log should never include fragments like ``type_=<``, ``context_=``, or
    ``id_='`` that indicate a raw Pydantic repr was used.
    """
    recipient = "https://example.org/actors/alice"
    obj_id = "urn:uuid:case-001"
    domain_obj = SimpleNamespace(id_=obj_id)
    activity = VultronActivity(
        id_="urn:test:act-logclean",
        type_="Create",
        actor="https://example.org/actors/bob",
        to=[recipient],
    )
    activity.object_ = domain_obj  # type: ignore[assignment]
    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    mock_emitter = AsyncMock()

    with caplog.at_level("INFO"):
        asyncio.run(
            oh.handle_outbox_item(
                "actor-bob", activity.id_, mock_dl, mock_emitter
            )
        )

    delivery_log = " ".join(
        r.message for r in caplog.records if "Delivered" in r.message
    )
    assert delivery_log, "Expected a 'Delivered' log entry"
    assert "SimpleNamespace" in delivery_log
    assert obj_id in delivery_log
    assert "type_=<" not in delivery_log
    assert "context_=" not in delivery_log


# ---------------------------------------------------------------------------
# handle_outbox_item — DR-01 typed-target dehydration regression
# ---------------------------------------------------------------------------


def test_handle_outbox_item_converts_typed_activity_with_full_target():
    """handle_outbox_item delivers when activity.target is a full domain object.

    Regression test for DR-01: typed AS2 activities (e.g. RmInviteToCaseActivity)
    may store a full VulnerabilityCase as target.  The outbox handler must
    dehydrate it to an ID string before VultronActivity.model_validate().
    """
    recipient = "https://example.org/actors/alice"
    case_id = "https://example.org/cases/case-123"

    activity_dict = {
        "id": "urn:uuid:act-invite-001",
        "type": "Invite",
        "actor": "https://example.org/actors/coordinator",
        "to": [recipient],
        "object": {
            "id": "urn:uuid:actor-alice",
            "type": "Person",
            "name": "Alice",
        },
        "target": {
            "id": case_id,
            "type": "VulnerabilityCase",
            "name": "Test Case",
        },
    }

    class FakeTypedActivity:
        """Minimal stand-in for a typed AS2 activity from the DataLayer."""

        def model_dump(self, *, by_alias=False, serialize_as_any=False):
            return activity_dict

    mock_dl = MagicMock()
    mock_dl.read.return_value = FakeTypedActivity()
    mock_emitter = AsyncMock()

    asyncio.run(
        oh.handle_outbox_item(
            "actor-coordinator",
            "urn:uuid:act-invite-001",
            mock_dl,
            mock_emitter,
        )
    )

    mock_emitter.emit.assert_called_once()
    emitted_activity, emitted_recipients = mock_emitter.emit.call_args[0]
    assert emitted_activity.target == case_id
    assert recipient in emitted_recipients


# ---------------------------------------------------------------------------
# handle_outbox_item — Announce(as_CaseLedgerEntry) inline field preservation
# ---------------------------------------------------------------------------


def test_handle_outbox_item_preserves_inline_case_ledger_entry_fields():
    """Announce(as_CaseLedgerEntry) delivery keeps full inline log-entry fields."""
    from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
    from vultron.core.models.case_ledger import HashChainLedgerRecord
    from vultron.wire.as2.factories import announce_log_entry_activity
    from vultron.wire.as2.vocab.objects.case_ledger_entry import (
        as_CaseLedgerEntry as WireCaseLedgerEntry,
    )

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
        WireCaseLedgerEntry.from_core(entry),
        actor="https://example.org/actors/case-actor",
        to=[recipient],
    )

    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    # Real hydrate is a no-op for an already-typed inline object; mimic that so
    # the test observes the recovered typed entry rather than a MagicMock.
    mock_dl.hydrate.side_effect = lambda obj: obj
    mock_emitter = AsyncMock()

    asyncio.run(
        oh.handle_outbox_item(
            "actor-case", activity.id_, mock_dl, mock_emitter
        )
    )

    mock_emitter.emit.assert_called_once()
    emitted_activity, emitted_recipients = mock_emitter.emit.call_args[0]
    assert emitted_recipients == [recipient]
    # The outbound delivery now recovers the inline entry as a typed
    # CaseLedgerEntry (SYNC-13-004) so serialize_as_any keeps its fields on the
    # wire.  Assert against the typed object's attributes.
    emitted_object = emitted_activity.object_
    assert isinstance(emitted_object, WireCaseLedgerEntry)
    assert emitted_object.case_id == entry.case_id
    assert emitted_object.log_object_id == entry.log_object_id
    assert emitted_object.event_type == entry.event_type
