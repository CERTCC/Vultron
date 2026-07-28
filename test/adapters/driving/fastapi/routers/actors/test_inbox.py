#!/usr/bin/env python
"""
Unit tests for vultron.adapters.driving.fastapi.routers.actors._inbox.

Tests inbox processing helpers in isolation from the HTTP layer.
"""

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

import pytest
from fastapi import HTTPException

from typing import cast

from vultron.adapters.driving.fastapi.routers.actors._inbox import (
    _activity_already_received,
    _get_body,
    _record_inbox_receipt,
    _reparse_as_specific_type,
    _store_inbox_activity,
    _store_nested_inbox_object,
    parse_activity,
)
from vultron.core.models.actor import CoreActor
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_ACTOR_URI = "https://example.org/actors/alice"
_ACTIVITY_URI = "https://example.org/activities/create-001"


# ---------------------------------------------------------------------------
# parse_activity
# ---------------------------------------------------------------------------


def test_parse_activity_returns_typed_activity_for_valid_body():
    note = as_Note(content="hello")
    create = as_Create(
        actor=_ACTOR_URI,
        object_=note,
    )
    body = create.model_dump(mode="json", by_alias=True, exclude_none=True)
    result = parse_activity(body)
    assert isinstance(result, as_Create)


def test_parse_activity_raises_400_when_type_missing():
    with pytest.raises(HTTPException) as exc_info:
        parse_activity({"actor": _ACTOR_URI, "object": {}})
    assert exc_info.value.status_code == 400


def test_parse_activity_raises_422_for_unknown_type():
    with pytest.raises(HTTPException) as exc_info:
        parse_activity(
            {"type": "NonExistentActivityType", "actor": _ACTOR_URI}
        )
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# _get_body
# ---------------------------------------------------------------------------


def test_get_body_returns_dict_unchanged():
    body = {"type": "Create", "actor": _ACTOR_URI}
    assert _get_body(body) is body


# ---------------------------------------------------------------------------
# _activity_already_received
# ---------------------------------------------------------------------------


def test_activity_already_received_returns_true_when_in_inbox():
    actor = as_Organization(id_=_ACTOR_URI, name="Alice")
    actor.inbox.items.append(_ACTIVITY_URI)
    assert (
        _activity_already_received(cast(CoreActor, actor), _ACTIVITY_URI)
        is True
    )


def test_activity_already_received_returns_false_when_not_in_inbox():
    actor = as_Organization(id_=_ACTOR_URI, name="Alice")
    assert (
        _activity_already_received(cast(CoreActor, actor), _ACTIVITY_URI)
        is False
    )


def test_activity_already_received_returns_false_when_inbox_is_none():
    actor = CoreActor(id_=_ACTOR_URI, name="Alice")
    assert _activity_already_received(actor, _ACTIVITY_URI) is False


# ---------------------------------------------------------------------------
# _reparse_as_specific_type
# ---------------------------------------------------------------------------


def test_reparse_as_specific_type_returns_specific_class_for_known_type():
    from vultron.wire.as2.vocab.base.objects.base import as_Object

    case = as_VulnerabilityCase(
        id_="urn:uuid:test-case-001",
        name="Test CVD Case",
    )
    raw_obj = case.model_dump(mode="json", by_alias=True, exclude_none=True)
    # Pass as base as_Object to simulate what the wire parser produces
    nested = as_Object.model_validate(raw_obj)
    result = _reparse_as_specific_type(nested, raw_obj)
    assert isinstance(result, as_VulnerabilityCase)


def test_reparse_as_specific_type_returns_base_when_type_is_none():
    from vultron.wire.as2.vocab.base.objects.base import as_Object

    nested = as_Object()
    result = _reparse_as_specific_type(nested, {})
    assert result is nested  # type: ignore[comparison-overlap]


def test_reparse_as_specific_type_returns_same_object_when_already_specific_class():
    """Guard branch: nested is already the specific class → return unchanged."""
    case = as_VulnerabilityCase(
        id_="urn:uuid:test-case-already-specific",
        name="Already Specific",
    )
    raw_obj = case.model_dump(mode="json", by_alias=True, exclude_none=True)
    result = _reparse_as_specific_type(case, raw_obj)
    assert result is case


# ---------------------------------------------------------------------------
# _store_inbox_activity
# ---------------------------------------------------------------------------


def test_store_inbox_activity_persists_activity(datalayer):
    note = as_Note(content="test")
    activity = as_Create(actor=_ACTOR_URI, object_=note)
    _store_inbox_activity(datalayer, activity)
    stored = datalayer.read(activity.id_)
    assert stored is not None


def test_store_inbox_activity_is_idempotent(datalayer):
    note = as_Note(content="test")
    activity = as_Create(actor=_ACTOR_URI, object_=note)
    # Second call must not raise
    _store_inbox_activity(datalayer, activity)
    _store_inbox_activity(datalayer, activity)


# ---------------------------------------------------------------------------
# _store_nested_inbox_object
# ---------------------------------------------------------------------------


def test_store_nested_inbox_object_stores_inline_case(datalayer):
    case = as_VulnerabilityCase(
        id_="urn:uuid:case-nest-001",
        name="Nested Case",
    )
    activity = as_Announce(
        actor=_ACTOR_URI,
        object_=case,
    )
    raw_body = {
        "object": case.model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
    }
    _store_nested_inbox_object(datalayer, activity, raw_body)
    stored = datalayer.read(case.id_)
    assert stored is not None


def test_store_nested_inbox_object_skips_string_object(datalayer):
    """When object_ is a URI string, no persistence should happen."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Announce,
    )

    activity = as_Announce(actor=_ACTOR_URI, object_="urn:uuid:some-id")
    # Should not raise; DL should remain empty
    _store_nested_inbox_object(datalayer, activity, None)


def test_store_nested_inbox_object_skips_when_no_body(datalayer):
    case = as_VulnerabilityCase(
        id_="urn:uuid:case-nobody-001",
        name="No Body Case",
    )
    activity = as_Announce(actor=_ACTOR_URI, object_=case)
    # body=None: should fall back to base as_Object storage without crashing
    _store_nested_inbox_object(datalayer, activity, None)


# ---------------------------------------------------------------------------
# _record_inbox_receipt
# ---------------------------------------------------------------------------


def test_record_inbox_receipt_appends_to_inbox_items(datalayer):
    from vultron.adapters.driven.db_record import object_to_record

    actor = as_Organization(id_=_ACTOR_URI, name="Alice")
    datalayer.create(object_to_record(actor))

    _record_inbox_receipt(
        datalayer, cast(CoreActor, actor), _ACTIVITY_URI, _ACTOR_URI
    )
    assert _ACTIVITY_URI in actor.inbox.items


def test_record_inbox_receipt_is_noop_when_inbox_has_no_items_attr(datalayer):
    """Actor with string inbox URI should not raise."""
    actor = CoreActor(id_=_ACTOR_URI, name="Alice", inbox="https://inbox.url")
    # Should not raise
    _record_inbox_receipt(datalayer, actor, _ACTIVITY_URI, _ACTOR_URI)
