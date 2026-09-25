#!/usr/bin/env python
"""
Unit tests for vultron.adapters.driving.fastapi.inbox_storage.

Tests the ingress storage helpers in isolation from the HTTP layer. They were
tested under ``routers/actors/test_inbox.py`` until #3705 moved them out of
the router package.
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

from vultron.adapters.driving.fastapi.inbox_storage import (
    _reparse_as_specific_type,
    _store_inbox_activity,
    _store_nested_inbox_object,
)
from vultron.core.models.actor import CoreActor
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_ACTOR_URI = "https://example.org/actors/alice"


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
    result = _reparse_as_specific_type(case, raw_obj)  # type: ignore[arg-type]
    assert result is case


@pytest.mark.spec("VM-06-008")
def test_reparse_as_specific_type_never_returns_a_core_class():
    """A core-only ``type`` name must not re-parse as a core class (ISSUE-3565).

    ``CoreActor`` is registered only in the core map, and a minimal dict
    validates as it, so before the lookup went wire-only the inbox handed a core
    object to the DataLayer for an inbound ``{"type": "CoreActor"}``.
    """
    from vultron.wire.as2.vocab.base.objects.base import as_Object

    raw_obj = {"id": "urn:uuid:core-only-reparse", "type": "CoreActor"}
    nested = as_Object.model_validate(raw_obj)

    result = _reparse_as_specific_type(nested, raw_obj)

    assert result is nested  # type: ignore[comparison-overlap]
    assert not isinstance(result, CoreActor)


@pytest.mark.spec("VM-06-008")
def test_store_nested_inbox_object_persists_no_core_class_for_core_only_name(
    datalayer, monkeypatch
):
    """The object the inbox persists for a core-only name is not core."""
    from vultron.adapters.driving.fastapi import inbox_storage
    from vultron.core.models.base import CoreObject
    from vultron.wire.as2.vocab.base.objects.base import as_Object

    persisted: list[object] = []
    real_object_to_record = inbox_storage.object_to_record

    def _spy(obj):
        persisted.append(obj)
        return real_object_to_record(obj)

    monkeypatch.setattr(inbox_storage, "object_to_record", _spy)

    raw_obj = {"id": "urn:uuid:core-only-store", "type": "CoreActor"}
    activity = as_Announce(
        actor=_ACTOR_URI, object_=as_Object.model_validate(raw_obj)
    )
    _store_nested_inbox_object(datalayer, activity, {"object": raw_obj})

    assert len(persisted) == 1
    assert not isinstance(persisted[0], CoreObject)


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


def test_store_nested_inbox_object_projection_failure_surfaces_on_read(
    datalayer, caplog
):
    """An unreadable inline object surfaces its failure on read (#2232, #2940).

    Since #2940 removed write-side wire→core normalisation (``extra="forbid"``
    is the boundary contract now), ingress stores the inline object verbatim
    rather than rejecting it at write.  The failure is not silently swallowed
    on the way back out: reading the row logs a WARNING naming #2232 rather
    than reporting a misleading "not found" with no trace.
    """
    import logging

    from pydantic import BaseModel

    # The fixture changed with ADR-0099 detail 3, and the reason is worth keeping.
    # It used to build an ``as_CaseParticipant`` with ``accepted_embargo_ids=[""]``
    # — legal on the lenient wire class, rejected by the core class's
    # ``NonEmptyString``, so "constructible yet unprojectable". Collapsing the pair
    # removes that state: one class means such an object fails *construction*
    # instead of projection, and there is no wire object left to hand back on
    # read. What still reaches the store is a shape the core class refuses — here
    # a key no ``CaseParticipant`` field accepts, which ``extra="forbid"`` rejects.
    #
    # Deliberately a plain ``BaseModel`` and not a ``CoreObject`` subclass: the
    # latter self-registers in ``CORE_TYPE_MAP`` via ``__init_subclass__``, and with
    # ``type_ = "CaseParticipant"`` it would clobber the real entry for every test
    # that ran afterwards. ``model_construct`` puts it in the slot without the
    # union validation a non-core model would fail.
    class _ShadowingParticipant(BaseModel):
        id_: str = "urn:uuid:participant-2232-unprojectable"
        type_: str = "CaseParticipant"
        not_a_participant_field: str = "x"

    _ShadowingParticipant.__module__ = "vultron.wire.as2.vocab.objects.fake"

    unprojectable = _ShadowingParticipant()
    activity = as_Announce.model_construct(
        actor=_ACTOR_URI, object_=unprojectable
    )

    _store_nested_inbox_object(datalayer, activity, None)

    with caplog.at_level(logging.WARNING):
        result = datalayer.read(unprojectable.id_)

    # No class can read the row, so it reads as absent — but loudly.
    assert result is None
    assert "issue #2232" in caplog.text


def test_store_nested_inbox_object_duplicate_stays_at_debug(datalayer, caplog):
    """A genuine duplicate is not an error — it must not be logged as one."""
    import logging

    case = as_VulnerabilityCase(
        id_="urn:uuid:case-dup-2232",
        name="Duplicate Case",
    )
    activity = as_Announce(actor=_ACTOR_URI, object_=case)
    _store_nested_inbox_object(datalayer, activity, None)

    with caplog.at_level(logging.DEBUG):
        _store_nested_inbox_object(datalayer, activity, None)

    assert "already exists" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
