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
Unit tests for handle_outbox_item — expansion bridge, to: enforcement,
and object integrity error cases.

Covers: bare-string object_ expansion for inline-object activity types
(P347-BRIDGE), OX-08 to: field validation, and OX-09 integrity errors.

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``

Spec coverage:
- OX-08-001/002/003: ``to:`` field MUST be non-empty; raises
  VultronOutboxToFieldMissingError.
- OX-08-004: ``cc``/``bto``/``bcc`` presence logs a WARNING.
- OX-09: bare-string object_ for non-expandable types raises integrity error.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.core.models.activity import VultronActivity
from vultron.errors import (
    VultronOutboxObjectIntegrityError,
    VultronOutboxToFieldMissingError,
)

# ---------------------------------------------------------------------------
# Helpers
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


def _make_vultron_activity(
    to=None, cc=None, bto=None, bcc=None, activity_type="Offer"
) -> VultronActivity:
    """Build a VultronActivity with the given addressing fields."""
    return VultronActivity(
        id_="urn:test:act-to-check",
        type_=activity_type,
        actor="https://example.org/actors/sender",
        to=to,
        cc=cc,
        bto=bto,
        bcc=bcc,
    )


# ---------------------------------------------------------------------------
# handle_outbox_item — expansion bridge (P347-BRIDGE)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "activity_type", ["Add", "Invite", "Accept", "Offer", "Join"]
)
def test_handle_outbox_item_expands_bare_object_for_new_types(
    activity_type, caplog
):
    """handle_outbox_item expands bare-string object_ for inline-object types."""
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

    mock_emitter.emit.assert_called_once()
    emitted_activity, _ = mock_emitter.emit.call_args[0]
    assert emitted_activity.object_ is inner_obj
    assert "Expanded" in caplog.text


@pytest.mark.parametrize(
    "activity_type", ["Add", "Invite", "Accept", "Offer", "Join"]
)
def test_handle_outbox_item_raises_integrity_error_when_expansion_fails(
    activity_type,
):
    """handle_outbox_item raises VultronOutboxObjectIntegrityError when the
    inner object is not found for inline-object activity types."""
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
# handle_outbox_item — to: field enforcement (OX-08)
# ---------------------------------------------------------------------------


def test_handle_outbox_item_raises_when_to_is_none():
    """handle_outbox_item raises VultronOutboxToFieldMissingError when to is None (OX-08-003)."""
    activity = _make_vultron_activity(to=None)
    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    mock_emitter = AsyncMock()

    with pytest.raises(VultronOutboxToFieldMissingError) as exc_info:
        asyncio.run(
            oh.handle_outbox_item(
                "actor-abc", activity.id_, mock_dl, mock_emitter
            )
        )

    assert exc_info.value.activity_id == activity.id_
    assert exc_info.value.activity_type == "Offer"
    mock_emitter.emit.assert_not_called()


def test_handle_outbox_item_raises_when_to_is_empty_list():
    """handle_outbox_item raises VultronOutboxToFieldMissingError when to is [] (OX-08-002)."""
    activity = _make_vultron_activity(to=[])
    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    mock_emitter = AsyncMock()

    with pytest.raises(VultronOutboxToFieldMissingError) as exc_info:
        asyncio.run(
            oh.handle_outbox_item(
                "actor-abc", activity.id_, mock_dl, mock_emitter
            )
        )

    assert exc_info.value.activity_id == activity.id_
    assert exc_info.value.activity_type == "Offer"
    mock_emitter.emit.assert_not_called()


@pytest.mark.parametrize("addr_field", ["cc", "bto", "bcc"])
def test_handle_outbox_item_warns_when_non_standard_addr_field_present(
    addr_field, caplog
):
    """handle_outbox_item logs WARNING when cc/bto/bcc set, but still delivers (OX-08-004)."""
    recipient = "https://example.org/actors/alice"
    other = "https://example.org/actors/charlie"
    if addr_field == "cc":
        activity = VultronActivity(
            id_="urn:test:act-warn",
            type_="Create",
            actor="https://example.org/actors/sender",
            to=[recipient],
            cc=[other],
        )
    elif addr_field == "bto":
        activity = VultronActivity(
            id_="urn:test:act-warn",
            type_="Create",
            actor="https://example.org/actors/sender",
            to=[recipient],
            bto=[other],
        )
    else:
        activity = VultronActivity(
            id_="urn:test:act-warn",
            type_="Create",
            actor="https://example.org/actors/sender",
            to=[recipient],
            bcc=[other],
        )
    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    mock_emitter = AsyncMock()

    with caplog.at_level("WARNING"):
        asyncio.run(
            oh.handle_outbox_item(
                "actor-abc", activity.id_, mock_dl, mock_emitter
            )
        )

    assert any(
        addr_field in r.message for r in caplog.records
    ), f"Expected WARNING mentioning '{addr_field}'"
    mock_emitter.emit.assert_called_once()


def test_handle_outbox_item_no_warning_when_only_to_set(caplog):
    """handle_outbox_item logs no cc/bto/bcc WARNING when only to: is set."""
    recipient = "https://example.org/actors/alice"
    activity = VultronActivity(
        id_="urn:test:act-no-warn",
        type_="Create",
        actor="https://example.org/actors/sender",
        to=[recipient],
    )
    mock_dl = MagicMock()
    mock_dl.read.return_value = activity
    mock_emitter = AsyncMock()

    with caplog.at_level("WARNING"):
        asyncio.run(
            oh.handle_outbox_item(
                "actor-abc", activity.id_, mock_dl, mock_emitter
            )
        )

    warning_texts = [
        r.message for r in caplog.records if r.levelname == "WARNING"
    ]
    assert not any(
        any(f in msg for f in ("cc", "bto", "bcc")) for msg in warning_texts
    )


def test_handle_outbox_item_raises_integrity_error_for_bare_object():
    """Malformed bare-string object_ must raise integrity error (OX-09/MV-09)."""
    activity = _make_vultron_activity(
        to=["https://example.org/actors/alice"],
        activity_type="Create",
    )
    activity.object_ = "urn:uuid:bare-object"  # type: ignore[assignment]
    mock_dl = MagicMock()
    mock_dl.read.side_effect = lambda id_: (
        activity if id_ == activity.id_ else None
    )
    mock_emitter = AsyncMock()

    with pytest.raises(VultronOutboxObjectIntegrityError) as exc_info:
        asyncio.run(
            oh.handle_outbox_item(
                "actor-abc",
                activity.id_,
                mock_dl,
                mock_emitter,
            )
        )

    assert exc_info.value.activity_id == activity.id_
    assert exc_info.value.activity_type == "Create"
    mock_emitter.emit.assert_not_called()
