#!/usr/bin/env python
"""
Unit tests for vultron.adapters.driving.fastapi.routers.actors._lookup.

Tests actor-record lookup helpers in isolation from the HTTP layer.
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

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.routers.actors._lookup import (
    _ACTOR_RECORD_TYPES,
    _ACTOR_TYPE_MAP,
    _actor_class_for_record,
    _find_actor_record,
    _find_actor_record_by_id,
    _resolve_actor_or_404,
)
from vultron.core.models.actor import (
    CoreActor,
    VultronApplication,
    VultronGroup,
    VultronOrganization,
    VultronPerson,
    VultronService,
)
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Organization,
    as_Person,
)

_ACTOR_URI = "https://example.org/actors/alice"


# ---------------------------------------------------------------------------
# _ACTOR_RECORD_TYPES
# ---------------------------------------------------------------------------


def test_actor_record_types_contains_expected_entries():
    assert "Actor" in _ACTOR_RECORD_TYPES
    assert "Person" in _ACTOR_RECORD_TYPES
    assert "Organization" in _ACTOR_RECORD_TYPES
    assert "Service" in _ACTOR_RECORD_TYPES
    assert "Application" in _ACTOR_RECORD_TYPES
    assert "Group" in _ACTOR_RECORD_TYPES


# ---------------------------------------------------------------------------
# _ACTOR_TYPE_MAP
# ---------------------------------------------------------------------------


def test_actor_type_map_covers_all_concrete_types():
    assert _ACTOR_TYPE_MAP["Person"] is VultronPerson
    assert _ACTOR_TYPE_MAP["Organization"] is VultronOrganization
    assert _ACTOR_TYPE_MAP["Service"] is VultronService
    assert _ACTOR_TYPE_MAP["Application"] is VultronApplication
    assert _ACTOR_TYPE_MAP["Group"] is VultronGroup


# ---------------------------------------------------------------------------
# _actor_class_for_record
# ---------------------------------------------------------------------------


def test_actor_class_for_record_returns_mapped_class_from_payload_type():
    rec = {"data_": {"type_": "Person"}}
    assert _actor_class_for_record(rec) is VultronPerson


def test_actor_class_for_record_falls_back_to_record_type():
    rec = {"type_": "Organization", "data_": {}}
    assert _actor_class_for_record(rec) is VultronOrganization


def test_actor_class_for_record_returns_core_actor_for_unknown_type():
    rec = {"type_": "Unknown", "data_": {}}
    assert _actor_class_for_record(rec) is CoreActor


def test_actor_class_for_record_prefers_payload_type_json_key():
    """``data_.type`` (JSON alias) should also be recognised."""
    rec = {"data_": {"type": "Service"}}
    assert _actor_class_for_record(rec) is VultronService


# ---------------------------------------------------------------------------
# _find_actor_record_by_id
# ---------------------------------------------------------------------------


def test_find_actor_record_by_id_returns_record_when_found(datalayer):
    actor = as_Organization(id_=_ACTOR_URI, name="Alice Org")
    datalayer.create(object_to_record(actor))
    result = _find_actor_record_by_id(datalayer, _ACTOR_URI)
    assert result is not None
    assert result.get("id_") == _ACTOR_URI


def test_find_actor_record_by_id_returns_none_for_missing_actor(datalayer):
    result = _find_actor_record_by_id(datalayer, "https://example.org/nobody")
    assert result is None


# ---------------------------------------------------------------------------
# _find_actor_record
# ---------------------------------------------------------------------------


def test_find_actor_record_returns_by_full_id(datalayer):
    actor = as_Person(id_=_ACTOR_URI, name="Alice")
    datalayer.create(object_to_record(actor))
    result = _find_actor_record(datalayer, _ACTOR_URI)
    assert result is not None
    assert result.get("id_") == _ACTOR_URI


def test_find_actor_record_returns_by_path_suffix(datalayer):
    """Short-ID lookup: actor whose id_ ends with '/{actor_id}'."""
    actor = as_Organization(id_=_ACTOR_URI, name="Alice Org")
    datalayer.create(object_to_record(actor))
    # 'alice' is the last path segment of _ACTOR_URI
    result = _find_actor_record(datalayer, "alice")
    assert result is not None
    assert result.get("id_") == _ACTOR_URI


def test_find_actor_record_returns_none_when_absent(datalayer):
    result = _find_actor_record(datalayer, "nonexistent-id")
    assert result is None


# ---------------------------------------------------------------------------
# _resolve_actor_or_404
# ---------------------------------------------------------------------------


def test_resolve_actor_or_404_returns_actor_when_found(datalayer):
    actor = as_Organization(id_=_ACTOR_URI, name="Alice Org")
    datalayer.create(actor)
    resolved = _resolve_actor_or_404(_ACTOR_URI, datalayer)
    assert resolved is not None
    assert resolved.id_ == _ACTOR_URI


def test_resolve_actor_or_404_raises_http_404_when_missing(datalayer):
    with pytest.raises(HTTPException) as exc_info:
        _resolve_actor_or_404("https://example.org/nobody", datalayer)
    assert exc_info.value.status_code == 404
