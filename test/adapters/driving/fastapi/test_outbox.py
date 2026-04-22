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
Unit tests for the outbox handler module.

Tests call outbox handler functions directly (no HTTP layer) to verify
the processing loop behavior.  Each test passes a mock DataLayer directly
(the handler signature changed in ACT-2 to accept ``dl`` as a parameter).

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``

Spec coverage:
- OX-01-001: Actor MUST have an outbox collection.
- OX-01-002: Outbox MUST preserve insertion order (FIFO).
- OX-03-001: Activities in outbox MUST be delivered to recipient inboxes.
- OX-03-002/003: Delivery occurs after handler; MUST NOT block HTTP response.
- OX-1.1: Delivery via async HTTP POST to recipient inbox URLs.
- OX-1.3: Idempotency enforced at inbox endpoint (not delivery side).
"""

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.core.models.activity import VultronActivity
from vultron.errors import VultronOutboxObjectIntegrityError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_queue(*ids: str) -> list[str]:
    """Return a mutable list of activity ID strings."""
    return list(ids)


def _mock_dl_with_queue(
    queue: list[str], actor: SimpleNamespace | None = SimpleNamespace()
) -> MagicMock:
    """Return a MagicMock DataLayer backed by ``queue`` for outbox ops."""
    mock_dl = MagicMock()
    mock_dl.read.return_value = actor
    mock_dl.find_actor_by_short_id.return_value = actor
    mock_dl.outbox_list.side_effect = lambda: list(queue)
    mock_dl.outbox_pop.side_effect = lambda: queue.pop(0) if queue else None
    mock_dl.outbox_append.side_effect = lambda x: queue.append(x)
    return mock_dl


# ---------------------------------------------------------------------------
# handle_outbox_item
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
# outbox_handler — happy paths
# ---------------------------------------------------------------------------


def test_outbox_handler_processes_all_items(monkeypatch):
    """outbox_handler drains the actor's outbox entirely on success."""
    ids = [f"urn:test:item-{i}" for i in range(3)]
    queue = _make_queue(*ids)
    mock_dl = _mock_dl_with_queue(queue)

    processed = []

    async def fake_handle(actor_id, activity_id, dl, emitter):
        processed.append(activity_id)

    monkeypatch.setattr(oh, "handle_outbox_item", fake_handle)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    assert queue == []
    assert processed == ids


def test_outbox_handler_preserves_fifo_order(monkeypatch):
    """outbox_handler processes items in FIFO order (OX-01-002)."""
    ids = [f"urn:test:item-{i}" for i in range(4)]
    queue = _make_queue(*ids)
    mock_dl = _mock_dl_with_queue(queue)

    processed = []

    async def fake_handle(actor_id, activity_id, dl, emitter):
        processed.append(activity_id)

    monkeypatch.setattr(oh, "handle_outbox_item", fake_handle)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    assert processed == ids


def test_outbox_handler_empty_outbox_does_nothing(monkeypatch):
    """outbox_handler with empty outbox processes no items."""
    queue: list[str] = []
    mock_dl = _mock_dl_with_queue(queue)

    processed = []

    async def fake_handle(actor_id, activity_id, dl, emitter):
        processed.append(activity_id)

    monkeypatch.setattr(oh, "handle_outbox_item", fake_handle)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    assert processed == []


# ---------------------------------------------------------------------------
# outbox_handler — error handling
# ---------------------------------------------------------------------------


def test_outbox_handler_retries_and_aborts_after_too_many_errors(monkeypatch):
    """outbox_handler puts item back on error and aborts after > 3 errors."""
    queue = _make_queue("urn:test:bad-item")
    mock_dl = _mock_dl_with_queue(queue)

    async def always_raise(actor_id, activity_id, dl, emitter):
        raise RuntimeError("delivery failed")

    monkeypatch.setattr(oh, "handle_outbox_item", always_raise)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    # item should be back in the queue after the retry limit is hit
    assert "urn:test:bad-item" in queue


def test_outbox_handler_returns_early_when_actor_not_found(
    monkeypatch, caplog
):
    """outbox_handler must return early (not raise) when actor is None."""
    queue: list[str] = []
    mock_dl = _mock_dl_with_queue(
        queue, actor=cast(SimpleNamespace | None, None)
    )
    mock_dl.read.return_value = None
    mock_dl.find_actor_by_short_id.return_value = None

    with caplog.at_level("WARNING"):
        asyncio.run(oh.outbox_handler("missing-actor", mock_dl))

    assert "missing-actor" in caplog.text


def test_outbox_handler_continues_after_one_error(monkeypatch):
    """outbox_handler continues processing subsequent items after a single error."""
    queue = _make_queue("urn:test:bad", "urn:test:good")
    mock_dl = _mock_dl_with_queue(queue)

    call_count = [0]
    processed = []

    async def sometimes_raise(actor_id, activity_id, dl, emitter):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("first item fails once")
        processed.append(activity_id)

    monkeypatch.setattr(oh, "handle_outbox_item", sometimes_raise)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    assert "urn:test:good" in processed


def test_outbox_handler_resolves_actor_by_short_id(monkeypatch):
    """outbox_handler falls back to find_actor_by_short_id when full ID lookup fails."""
    queue: list[str] = []
    mock_dl = _mock_dl_with_queue(queue)
    mock_dl.read.return_value = None  # full-ID lookup fails
    mock_dl.find_actor_by_short_id.return_value = SimpleNamespace(
        id_="https://example.org/actors/bob"
    )

    asyncio.run(oh.outbox_handler("bob", mock_dl))

    # Should have attempted short-ID lookup
    mock_dl.find_actor_by_short_id.assert_called_once_with("bob")


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


def test_extract_recipients_deduplicates():
    """_extract_recipients returns each actor ID at most once."""
    alice = "https://example.org/actors/alice"
    activity = SimpleNamespace(
        to=[alice],
        cc=[alice],  # duplicate
        bto=None,
        bcc=None,
    )
    recipients = oh._extract_recipients(activity)
    assert recipients == [alice]


def test_extract_recipients_handles_embedded_object():
    """_extract_recipients extracts id_ from embedded actor objects."""
    alice_id = "https://example.org/actors/alice"
    alice_obj = SimpleNamespace(id_=alice_id)
    activity = SimpleNamespace(
        to=[alice_obj],
        cc=None,
        bto=None,
        bcc=None,
    )
    recipients = oh._extract_recipients(activity)
    assert recipients == [alice_id]


def test_extract_recipients_returns_empty_for_no_fields():
    """_extract_recipients returns [] when all addressing fields are None."""
    activity = SimpleNamespace(to=None, cc=None, bto=None, bcc=None)
    recipients = oh._extract_recipients(activity)
    assert recipients == []


# ---------------------------------------------------------------------------
# handle_outbox_item — improved delivery log content (D5-6-LOGCTX)
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


# ---------------------------------------------------------------------------
# _format_object helper (D5-7-LOGCLEAN-1)
# ---------------------------------------------------------------------------


def test_format_object_returns_type_and_id_for_domain_object():
    """_format_object produces '<TypeName> <id>' for objects with id_."""
    obj = SimpleNamespace(id_="urn:uuid:abc-123")
    result = oh._format_object(obj)
    assert result == "SimpleNamespace urn:uuid:abc-123"


def test_format_object_passes_through_strings():
    """_format_object returns strings unchanged."""
    uri = "urn:uuid:def-456"
    assert oh._format_object(uri) == uri


def test_format_object_handles_none():
    """_format_object returns 'None' for None."""
    assert oh._format_object(None) == "None"


def test_format_object_handles_object_without_id():
    """_format_object returns just the class name when id_ is absent."""
    obj = SimpleNamespace()  # no id_ attribute
    result = oh._format_object(obj)
    assert result == "SimpleNamespace"


def test_handle_outbox_item_delivery_log_no_pydantic_repr(caplog):
    """Delivery log must not contain Pydantic field-repr noise (D5-7-LOGCLEAN-1).

    The log should never include fragments like ``type_=<``, ``context_=``, or
    ``id_='`` that indicate a raw Pydantic repr was used.
    """
    recipient = "https://example.org/actors/alice"
    obj_id = "urn:uuid:case-001"
    # Simulate a domain object (Pydantic-like) as the activity's object_
    domain_obj = SimpleNamespace(id_=obj_id)
    activity = VultronActivity(
        id_="urn:test:act-logclean",
        type_="Create",
        actor="https://example.org/actors/bob",
        to=[recipient],
    )
    # Attach domain obj so _format_object is exercised via activity_object
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
    # Must contain the concise object summary
    assert "SimpleNamespace" in delivery_log
    assert obj_id in delivery_log
    # Must NOT contain Pydantic field-repr fragments
    assert "type_=<" not in delivery_log
    assert "context_=" not in delivery_log


# ---------------------------------------------------------------------------
# handle_outbox_item — expansion bridge for Add, Invite, Accept (P347-BRIDGE)
# ---------------------------------------------------------------------------


def _make_activity_with_bare_object(
    activity_type: str, activity_id: str, recipient: str
) -> VultronActivity:
    """Return a VultronActivity of *activity_type* with a bare-string object_."""
    act = VultronActivity(
        id_=activity_id,
        type_=activity_type,
        actor="https://example.org/actors/bob",
        to=[recipient],
    )
    act.object_ = "urn:uuid:inner-obj-001"  # type: ignore[assignment]
    return act


@pytest.mark.parametrize("activity_type", ["Add", "Invite", "Accept"])
def test_handle_outbox_item_expands_bare_object_for_new_types(
    activity_type, caplog
):
    """handle_outbox_item expands bare-string object_ for Add/Invite/Accept."""
    recipient = "https://example.org/actors/alice"
    activity = _make_activity_with_bare_object(
        activity_type, f"urn:test:act-{activity_type.lower()}", recipient
    )
    inner_id = "urn:uuid:inner-obj-001"
    inner_obj = SimpleNamespace(id_=inner_id)

    def _read(id_):
        if id_ == activity.id_:
            return activity
        if id_ == inner_id:
            return inner_obj
        return None

    mock_dl = MagicMock()
    mock_dl.read.side_effect = _read
    mock_emitter = AsyncMock()

    with caplog.at_level("DEBUG"):
        asyncio.run(
            oh.handle_outbox_item(
                "actor-bob", activity.id_, mock_dl, mock_emitter
            )
        )

    # object_ should have been expanded to the full inner object
    mock_emitter.emit.assert_called_once()
    emitted_activity, _ = mock_emitter.emit.call_args[0]
    assert emitted_activity.object_ is inner_obj
    assert "Expanded" in caplog.text


@pytest.mark.parametrize("activity_type", ["Add", "Invite", "Accept"])
def test_handle_outbox_item_raises_integrity_error_when_expansion_fails(
    activity_type,
):
    """handle_outbox_item raises VultronOutboxObjectIntegrityError when the
    inner object is not found for Add/Invite/Accept activities."""
    recipient = "https://example.org/actors/alice"
    activity = _make_activity_with_bare_object(
        activity_type, f"urn:test:act-{activity_type.lower()}-fail", recipient
    )

    def _read(id_):
        if id_ == activity.id_:
            return activity
        return None  # inner object not found → expansion fails

    mock_dl = MagicMock()
    mock_dl.read.side_effect = _read
    mock_emitter = AsyncMock()

    with pytest.raises(VultronOutboxObjectIntegrityError):
        asyncio.run(
            oh.handle_outbox_item(
                "actor-bob", activity.id_, mock_dl, mock_emitter
            )
        )


# ---------------------------------------------------------------------------
# _dehydrate_references (DR-01)
# ---------------------------------------------------------------------------


def test_dehydrate_references_preserves_vulnerability_case_stub():
    """_dehydrate_references preserves VulnerabilityCase stub dicts (MV-10-001).

    A minimal {id, type} dict with type=VulnerabilityCase must survive
    dehydration intact so that selective disclosure (stub-based invite.target)
    is not erased before the activity reaches the outbox.
    """
    raw = {
        "type": "Invite",
        "actor": "https://example.org/actors/alice",
        "target": {
            "id": "https://example.org/cases/case-001",
            "type": "VulnerabilityCase",
        },
    }
    result = oh._dehydrate_references(raw)
    assert result["target"] == {
        "id": "https://example.org/cases/case-001",
        "type": "VulnerabilityCase",
    }


def test_dehydrate_references_prefers_href_over_id():
    """_dehydrate_references uses 'href' rather than 'id' for AS2 Link dicts."""
    raw = {
        "actor": "https://example.org/actors/alice",
        "target": {
            "id": "urn:uuid:link-object-id",
            "href": "https://example.org/cases/case-002",
        },
    }
    result = oh._dehydrate_references(raw)
    assert result["target"] == "https://example.org/cases/case-002"


def test_dehydrate_references_handles_list_field():
    """_dehydrate_references collapses actor dicts in list fields element-wise."""
    raw = {
        "to": [
            {"id": "https://example.org/actors/bob", "type": "Person"},
            "https://example.org/actors/charlie",  # already a string
        ]
    }
    result = oh._dehydrate_references(raw)
    assert result["to"] == [
        "https://example.org/actors/bob",
        "https://example.org/actors/charlie",
    ]


def test_dehydrate_references_leaves_object_field_intact():
    """_dehydrate_references does NOT touch the 'object' field (exempt)."""
    inline_obj = {
        "id": "urn:uuid:report-001",
        "type": "VulnerabilityReport",
        "name": "TEST",
    }
    raw = {
        "actor": "https://example.org/actors/alice",
        "object": inline_obj,
    }
    result = oh._dehydrate_references(raw)
    assert result["object"] is inline_obj


def test_dehydrate_references_leaves_string_fields_unchanged():
    """_dehydrate_references does not alter fields that are already strings."""
    raw = {
        "actor": "https://example.org/actors/alice",
        "target": "https://example.org/cases/case-already-string",
    }
    result = oh._dehydrate_references(raw)
    assert result["actor"] == "https://example.org/actors/alice"
    assert result["target"] == "https://example.org/cases/case-already-string"


def test_dehydrate_references_leaves_none_fields_unchanged():
    """_dehydrate_references skips fields that are None."""
    raw = {"actor": "https://example.org/actors/alice", "target": None}
    result = oh._dehydrate_references(raw)
    assert result["target"] is None


def test_handle_outbox_item_converts_typed_activity_with_full_target():
    """handle_outbox_item delivers when activity.target is a full domain object.

    Regression test for DR-01: typed AS2 activities (e.g. RmInviteToCaseActivity)
    may store a full VulnerabilityCase as target.  The outbox handler must
    dehydrate it to an ID string before VultronActivity.model_validate().
    """
    recipient = "https://example.org/actors/alice"
    case_id = "https://example.org/cases/case-123"

    # Simulate a typed activity whose model_dump produces a full case dict as target
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

        def model_dump(self, *, by_alias=False):
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
    # target must be the case ID string, not the full dict
    assert emitted_activity.target == case_id
    assert recipient in emitted_recipients
