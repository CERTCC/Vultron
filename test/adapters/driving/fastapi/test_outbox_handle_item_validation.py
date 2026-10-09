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
Unit tests for handle_outbox_item — the last-resort guards.

The handler is a dumb relay (VM-08-003): it never expands a bare ``object``
from the DataLayer.  A body whose ``object`` is a reference is refused, not
repaired (AKM-03-002, MV-09-002).

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``

Spec coverage:
- OX-08-001/002/003: ``to:`` field MUST be non-empty; raises
  VultronOutboxToFieldMissingError.
- OX-08-004: ``cc``/``bto``/``bcc`` presence logs a WARNING.
- AKM-03-002 / MV-09-002: a bare-string or Link ``object`` on an initiating
  activity raises VultronOutboxObjectIntegrityError before any delivery.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.adapters.driving.fastapi.outbox_delivery import (
    _INLINE_OBJECT_ACTIVITY_TYPES,
)
from vultron.adapters.outbox_sealed_body import (
    SealedOutboundBody,
    sealed_body_id,
)
from vultron.errors import (
    VultronOutboxObjectIntegrityError,
    VultronOutboxToFieldMissingError,
)

RECIPIENT = "https://example.org/actors/alice"
SENDER = "https://example.org/actors/sender"


def _sealed(activity_id: str, body: dict) -> SealedOutboundBody:
    return SealedOutboundBody(
        id_=sealed_body_id(activity_id),
        activity_id=activity_id,
        body=json.dumps({"id": activity_id, **body}),
    )


def _dl_with(sealed: SealedOutboundBody) -> MagicMock:
    mock_dl = MagicMock()
    mock_dl.read.side_effect = lambda id_: (
        sealed if id_ == sealed.id_ else None
    )
    return mock_dl


def _deliver(sealed: SealedOutboundBody, emitter) -> None:
    asyncio.run(
        oh.handle_outbox_item(
            "actor-abc", sealed.activity_id, _dl_with(sealed), emitter
        )
    )


# ---------------------------------------------------------------------------
# Inline-object guard (AKM-03-002, MV-09-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AKM-03-002")
@pytest.mark.spec("MV-09-002")
@pytest.mark.parametrize(
    "activity_type", sorted(_INLINE_OBJECT_ACTIVITY_TYPES)
)
def test_handle_outbox_item_refuses_a_bare_object_for_inline_types(
    activity_type,
):
    """A bare-string ``object`` on an initiating activity is refused, not expanded.

    The DataLayer double records every read: the handler must not go looking
    for the object it was not given.
    """
    sealed = _sealed(
        f"urn:test:act-{activity_type.lower()}",
        {
            "type": activity_type,
            "actor": SENDER,
            "to": [RECIPIENT],
            "object": "urn:uuid:inner-obj-001",
        },
    )
    mock_dl = _dl_with(sealed)
    mock_emitter = AsyncMock()

    with pytest.raises(VultronOutboxObjectIntegrityError) as exc_info:
        asyncio.run(
            oh.handle_outbox_item(
                "actor-abc", sealed.activity_id, mock_dl, mock_emitter
            )
        )

    assert exc_info.value.activity_type == activity_type
    mock_emitter.emit.assert_not_called()
    read_ids = [call.args[0] for call in mock_dl.read.call_args_list]
    assert read_ids == [sealed.id_], (
        "the handler must not expand from the store"
    )


@pytest.mark.spec("MV-09-002")
def test_handle_outbox_item_refuses_a_link_object():
    """An AS2 ``Link`` in ``object`` is a reference too, and is refused."""
    sealed = _sealed(
        "urn:test:act-link",
        {
            "type": "Create",
            "actor": SENDER,
            "to": [RECIPIENT],
            "object": {"type": "Link", "href": "https://example.org/o/1"},
        },
    )
    mock_emitter = AsyncMock()
    with pytest.raises(VultronOutboxObjectIntegrityError):
        _deliver(sealed, mock_emitter)
    mock_emitter.emit.assert_not_called()


def test_handle_outbox_item_allows_a_bare_object_for_non_initiating_types():
    """The guard is scoped to AKM-03-001's initiating types."""
    sealed = _sealed(
        "urn:test:act-read",
        {
            "type": "Read",
            "actor": SENDER,
            "to": [RECIPIENT],
            "object": "urn:uuid:offer-1",
        },
    )
    mock_emitter = AsyncMock()
    _deliver(sealed, mock_emitter)
    mock_emitter.emit.assert_called_once()


# ---------------------------------------------------------------------------
# to: enforcement (OX-08)
# ---------------------------------------------------------------------------


@pytest.mark.spec("OX-08-003")
def test_handle_outbox_item_raises_when_to_is_absent():
    """handle_outbox_item raises VultronOutboxToFieldMissingError when to is None (OX-08-003)."""
    sealed = _sealed(
        "urn:test:act-to-check",
        {"type": "Offer", "actor": SENDER, "object": {}},
    )
    mock_emitter = AsyncMock()
    with pytest.raises(VultronOutboxToFieldMissingError) as exc_info:
        _deliver(sealed, mock_emitter)
    assert exc_info.value.activity_id == sealed.activity_id
    assert exc_info.value.activity_type == "Offer"
    mock_emitter.emit.assert_not_called()


@pytest.mark.spec("OX-08-002")
def test_handle_outbox_item_raises_when_to_is_empty_list():
    """handle_outbox_item raises VultronOutboxToFieldMissingError when to is [] (OX-08-002)."""
    sealed = _sealed(
        "urn:test:act-to-check",
        {"type": "Offer", "actor": SENDER, "to": [], "object": {}},
    )
    mock_emitter = AsyncMock()
    with pytest.raises(VultronOutboxToFieldMissingError):
        _deliver(sealed, mock_emitter)
    mock_emitter.emit.assert_not_called()


# ---------------------------------------------------------------------------
# cc/bto/bcc warnings (OX-08-004)
# ---------------------------------------------------------------------------


@pytest.mark.spec("OX-08-004")
@pytest.mark.parametrize("addr_field", ["cc", "bto", "bcc"])
def test_handle_outbox_item_warns_when_non_standard_addr_field_present(
    addr_field, caplog
):
    """handle_outbox_item logs WARNING when cc/bto/bcc set, but still delivers (OX-08-004)."""
    other = "https://example.org/actors/charlie"
    sealed = _sealed(
        "urn:test:act-warn",
        {
            "type": "Create",
            "actor": SENDER,
            "to": [RECIPIENT],
            addr_field: [other],
            "object": {},
        },
    )
    mock_emitter = AsyncMock()

    with caplog.at_level("WARNING"):
        _deliver(sealed, mock_emitter)

    assert any(addr_field in r.message for r in caplog.records), (
        f"Expected WARNING mentioning '{addr_field}'"
    )
    mock_emitter.emit.assert_called_once()
    _, _, recipients = mock_emitter.emit.call_args[0]
    assert recipients == [RECIPIENT, other]


def test_handle_outbox_item_no_warning_when_only_to_set(caplog):
    """handle_outbox_item logs no cc/bto/bcc WARNING when only to: is set."""
    sealed = _sealed(
        "urn:test:act-no-warn",
        {"type": "Create", "actor": SENDER, "to": [RECIPIENT], "object": {}},
    )
    with caplog.at_level("WARNING"):
        _deliver(sealed, AsyncMock())
    assert not any(
        f in r.message for r in caplog.records for f in ("cc", "bto", "bcc")
    )


@pytest.mark.spec("OX-08-004")
def test_handle_outbox_item_warns_for_the_senders_own_cc_copy(caplog):
    """OX-08-004 has no exemption: a sender copying itself in ``cc:`` warns.

    The CLP-10-001 self-copy this used to exempt was retired by ADR-0109, so
    the copy is exactly what the warning exists to surface.
    """
    sealed = _sealed(
        "urn:test:act-self-cc",
        {
            "type": "Create",
            "actor": SENDER,
            "to": [RECIPIENT],
            "cc": [SENDER],
            "object": {},
        },
    )
    mock_emitter = AsyncMock()
    with caplog.at_level("WARNING"):
        _deliver(sealed, mock_emitter)
    assert any(
        "cc" in r.message and r.levelname == "WARNING" for r in caplog.records
    )
    mock_emitter.emit.assert_called_once()
