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
Unit tests for the outbox handler object-preparation pipeline.

Covers: ``_recover_typed_inline_object_from_dict``,
``_hydrate_inline_object_if_persistable``,
``_prepare_activity_object_for_delivery``, and the
``handle_outbox_item`` DataLayer hydration integration path
(CBT-05-005, #572 regression).

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.core.models.activity import VultronActivity

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


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
# _recover_typed_inline_object_from_dict
# ---------------------------------------------------------------------------


def test_recover_typed_inline_object_from_dict_rehydrates_model():
    """_recover_typed_inline_object_from_dict rebuilds configured model types."""
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )

    activity = _make_vultron_activity(
        to=["https://example.org/actors/alice"],
        activity_type="Create",
    )
    object_dict = {
        "id": "https://example.org/cases/case-123",
        "type": "VulnerabilityCase",
        "name": "Case 123",
    }

    recovered = oh._recover_typed_inline_object_from_dict(
        object_dict,
        "Create",
        activity.id_,
        activity,
    )

    assert isinstance(recovered, VulnerabilityCase)
    assert activity.object_ is recovered


def test_recover_typed_inline_object_from_dict_returns_input_on_validation_error(
    monkeypatch,
):
    """_recover_typed_inline_object_from_dict leaves dict unchanged on failure."""

    class BrokenModel:
        @classmethod
        def model_validate(cls, payload):
            raise ValueError("broken")

    monkeypatch.setitem(oh._STUB_OBJECT_MODEL_MAP, "BrokenType", BrokenModel)
    activity = _make_vultron_activity(
        to=["https://example.org/actors/alice"],
        activity_type="Create",
    )
    object_dict = {
        "id": "urn:uuid:broken-1",
        "type": "BrokenType",
        "name": "Broken",
    }

    recovered = oh._recover_typed_inline_object_from_dict(
        object_dict,
        "Create",
        activity.id_,
        activity,
    )

    assert recovered == object_dict
    assert activity.object_ is None


# ---------------------------------------------------------------------------
# _hydrate_inline_object_if_persistable
# ---------------------------------------------------------------------------


def test_hydrate_inline_object_if_persistable_hydrates_basemodel():
    """_hydrate_inline_object_if_persistable calls dl.hydrate for BaseModel."""
    from pydantic import BaseModel

    class DummyModel(BaseModel):
        id_: str

    activity = _make_vultron_activity(
        to=["https://example.org/actors/alice"],
        activity_type="Create",
    )
    model = DummyModel(id_="urn:uuid:dummy-1")
    hydrated_model = DummyModel(id_="urn:uuid:dummy-2")
    mock_dl = MagicMock()
    mock_dl.hydrate.return_value = hydrated_model

    result = oh._hydrate_inline_object_if_persistable(model, activity, mock_dl)

    mock_dl.hydrate.assert_called_once_with(model)
    assert result is hydrated_model
    assert activity.object_ is hydrated_model


# ---------------------------------------------------------------------------
# _prepare_activity_object_for_delivery
# ---------------------------------------------------------------------------


def test_prepare_activity_object_for_delivery_calls_helper_pipeline(
    monkeypatch,
):
    """_prepare_activity_object_for_delivery uses expansion/validate/recovery/hydration."""
    activity = _make_vultron_activity(
        to=["https://example.org/actors/alice"],
        activity_type="Create",
    )
    activity.object_ = {"id": "urn:uuid:obj", "type": "VulnerabilityCase"}
    mock_dl = MagicMock()

    expanded_obj = {"id": "urn:uuid:expanded", "type": "VulnerabilityCase"}
    recovered_obj = SimpleNamespace(id_="urn:uuid:recovered")
    hydrated_obj = SimpleNamespace(id_="urn:uuid:hydrated")

    expand = MagicMock(return_value=expanded_obj)
    validate = MagicMock()
    recover = MagicMock(return_value=recovered_obj)
    hydrate = MagicMock(return_value=hydrated_obj)

    monkeypatch.setattr(oh, "_expand_inline_object", expand)
    monkeypatch.setattr(oh, "_validate_inline_object", validate)
    monkeypatch.setattr(oh, "_recover_typed_inline_object_from_dict", recover)
    monkeypatch.setattr(oh, "_hydrate_inline_object_if_persistable", hydrate)

    result = oh._prepare_activity_object_for_delivery(
        activity, activity.id_, "Create", mock_dl
    )

    expand.assert_called_once()
    validate.assert_called_once_with(activity.id_, "Create", expanded_obj)
    recover.assert_called_once_with(
        expanded_obj, "Create", activity.id_, activity
    )
    hydrate.assert_called_once_with(recovered_obj, activity, mock_dl)
    assert result is hydrated_obj


# ---------------------------------------------------------------------------
# handle_outbox_item — DataLayer hydration integration (CBT-05-005)
# ---------------------------------------------------------------------------


def test_handle_outbox_item_calls_hydrate_on_inline_object():
    """handle_outbox_item calls dl.hydrate() on the inline object_ and uses
    the returned (fully-hydrated) object for delivery."""
    from unittest.mock import AsyncMock as _AM, MagicMock as _MM

    from vultron.core.models.activity import VultronActivity as _VA

    recipient = "https://example.org/actors/alice"
    case_obj = _VA.__new__(_VA)  # a PersistableModel subclass
    hydrated_case = _VA.__new__(_VA)

    activity = VultronActivity(
        id_="urn:test:act-hydrate-call",
        type_="Create",
        actor="https://example.org/actors/vendor",
        to=[recipient],
    )
    activity.object_ = case_obj

    mock_dl = _MM()
    mock_dl.read.side_effect = lambda id_: (
        activity if id_ == activity.id_ else None
    )
    mock_dl.hydrate.return_value = hydrated_case
    mock_emitter = _AM()

    asyncio.run(
        oh.handle_outbox_item(
            "actor-vendor", activity.id_, mock_dl, mock_emitter
        )
    )

    mock_dl.hydrate.assert_called_once_with(case_obj)
    mock_emitter.emit.assert_called_once()
    emitted_activity, _ = mock_emitter.emit.call_args[0]
    assert emitted_activity.object_ is hydrated_case


def test_handle_outbox_item_delivers_hydrated_participants():
    """dl.hydrate() is responsible for expanding case_participants.

    Regression test for #572: participant expansion is a DataLayer concern
    (CBT-01-007, CBT-05-005).  handle_outbox_item must use the object
    returned by dl.hydrate() — which carries the expanded participants — as
    the outbound object_, not the pre-hydration object.
    """
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )

    participant_id = "urn:uuid:participant-572-001"
    case_obj = VulnerabilityCase(
        id_="urn:uuid:case-572-001",
        case_participants=[participant_id],  # bare string before hydration
    )
    # dl.hydrate() is responsible for replacing bare strings with objects;
    # simulate it returning a case with participants already expanded.
    hydrated_case = VulnerabilityCase(
        id_="urn:uuid:case-572-001",
        case_participants=[],  # hydrate() would fill this with full objects
    )
    activity = VultronActivity(
        id_="urn:test:join-572-001",
        type_="Join",
        actor="https://vendor.example.org/actors/vendor",
        to=["https://finder.example.org/actors/finder"],
    )
    activity.object_ = case_obj  # type: ignore[assignment]

    mock_dl = MagicMock()
    mock_dl.read.side_effect = lambda id_: (
        activity if id_ == activity.id_ else None
    )
    mock_dl.hydrate.return_value = hydrated_case
    mock_emitter = AsyncMock()

    asyncio.run(
        oh.handle_outbox_item(
            "actor-vendor", activity.id_, mock_dl, mock_emitter
        )
    )

    mock_dl.hydrate.assert_called_once_with(case_obj)
    emitted_activity, _ = mock_emitter.emit.call_args[0]
    assert emitted_activity.object_ is hydrated_case, (
        "handle_outbox_item must use the dl.hydrate() result as object_ "
        "so recipients receive expanded participant objects (#572)"
    )
