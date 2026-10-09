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

import logging
from typing import Any

import pytest

from vultron.adapters.driving.fastapi.inbox_storage import (
    _store_inbox_activity,
    _store_nested_inbox_object,
)
from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseStub,
)

_ACTOR_URI = "https://example.org/actors/alice"


# ---------------------------------------------------------------------------
# _store_nested_inbox_object stores what the parser produced (MV-11-005)
# ---------------------------------------------------------------------------
#
# These replace the tests of ``_reparse_as_specific_type``, which re-validated
# an inline object from the raw request body and was deleted by #3922.  Each
# drives a raw body through ``parse_activity`` — the only door inbound data
# enters by — and asserts that the object handed to storage is the parsed one.

_PUBLISHED = "2026-03-04T05:06:07+00:00"


def _parsed_announce(inline: dict[str, Any]) -> as_Announce:
    activity = parse_activity(_announce_body(inline))
    assert isinstance(activity, as_Announce)
    return activity


def _announce_body(inline: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Announce",
        "id": "https://example.org/activities/announce-1",
        "actor": _ACTOR_URI,
        "published": _PUBLISHED,
        "object": inline,
    }


@pytest.fixture
def persisted(monkeypatch) -> list[object]:
    """Capture every object ``_store_nested_inbox_object`` hands to storage."""
    from vultron.adapters.driving.fastapi import inbox_storage

    captured: list[object] = []
    real_object_to_record = inbox_storage.object_to_record

    def _spy(obj):
        captured.append(obj)
        return real_object_to_record(obj)

    monkeypatch.setattr(inbox_storage, "object_to_record", _spy)
    return captured


@pytest.mark.spec("MV-11-005")
def test_store_nested_inbox_object_stores_the_parsed_inline_case(
    datalayer, persisted
):
    """A full inline case is stored as the ``VulnerabilityCase`` parsed."""
    activity = _parsed_announce(
        {
            "type": "VulnerabilityCase",
            "id": "urn:uuid:case-parsed-001",
            "name": "Parsed Case",
        }
    )

    _store_nested_inbox_object(datalayer, activity)

    assert persisted == [activity.object_]
    assert type(persisted[0]) is as_VulnerabilityCase
    stored = datalayer.read("urn:uuid:case-parsed-001")
    assert isinstance(stored, VulnerabilityCase)


@pytest.mark.spec("EMB-18-003")
def test_store_nested_inbox_object_stores_the_inline_embargo_a_case_names(
    datalayer,
):
    """An inline active embargo is held as a record beside the case."""
    case_id = "urn:uuid:case-embargo-001"
    embargo_id = f"{case_id}/embargo_events/e1"
    activity = _parsed_announce(
        {
            "type": "VulnerabilityCase",
            "id": case_id,
            "name": "Embargoed Case",
            "embargoRegister": [
                {
                    "embargo": {
                        "type": "EmbargoEvent",
                        "id": embargo_id,
                        "context": case_id,
                        "startTime": _PUBLISHED,
                        "endTime": "2099-01-01T00:00:00+00:00",
                    },
                    "status": "ACTIVE",
                }
            ],
        }
    )

    _store_nested_inbox_object(datalayer, activity)

    assert isinstance(datalayer.read(embargo_id), EmbargoEvent)
    assert isinstance(datalayer.read(case_id), VulnerabilityCase)


@pytest.mark.spec("EMB-18-003")
def test_store_nested_inbox_object_skips_a_case_naming_an_unheld_embargo(
    datalayer, caplog
):
    """A bare embargo id this store cannot read keeps the case out of it."""
    case_id = "urn:uuid:case-embargo-002"
    activity = _parsed_announce(
        {
            "type": "VulnerabilityCase",
            "id": case_id,
            "name": "Unheld Embargo Case",
            "embargoRegister": [
                {
                    "embargo": f"{case_id}/embargo_events/unheld",
                    "status": "ACTIVE",
                }
            ],
        }
    )

    with caplog.at_level(logging.WARNING):
        _store_nested_inbox_object(datalayer, activity)

    assert datalayer.read(case_id) is None
    assert any("EMB-18-003" in r.getMessage() for r in caplog.records)


@pytest.mark.spec("MV-11-005")
def test_store_nested_inbox_object_stores_the_parsed_case_stub(
    datalayer, persisted
):
    """A case stub is stored as the ``as_VulnerabilityCaseStub`` parsed."""
    activity = _parsed_announce(
        {
            "type": "VulnerabilityCaseStub",
            "caseId": "urn:uuid:case-stub-001",
            "summary": "Security issue — details shared after acceptance",
        }
    )
    assert type(activity.object_) is as_VulnerabilityCaseStub

    _store_nested_inbox_object(datalayer, activity)

    assert persisted == [activity.object_]


@pytest.mark.spec("MV-11-005")
@pytest.mark.spec("MV-11-003")
def test_store_nested_inbox_object_stores_parsed_class_after_a_set_aside_key(
    datalayer, persisted, caplog
):
    """A set-aside foreign key does not demote the stored class (#3922).

    The retired re-parse validated the raw body again, met the key the parse
    edge had set aside, failed the case's ``extra="forbid"``, and stored the
    base ``as_Object`` instead.  Storage now sees only the parsed case, and the
    stored record carries no trace of the key.
    """
    import logging

    activity = _parsed_announce(
        {
            "type": "VulnerabilityCase",
            "id": "urn:uuid:case-foreign-001",
            "name": "Case With A Foreign Key",
            "fooBar": 1,
        }
    )

    with caplog.at_level(logging.DEBUG):
        _store_nested_inbox_object(datalayer, activity)

    assert persisted == [activity.object_]
    assert type(persisted[0]) is as_VulnerabilityCase
    stored = datalayer.read("urn:uuid:case-foreign-001")
    assert isinstance(stored, VulnerabilityCase)
    assert "fooBar" not in stored.model_dump(by_alias=True)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    # The key survives only in the received evidence (VM-08-002).
    evidence = activity.received_evidence
    assert evidence is not None and evidence["object"]["fooBar"] == 1


@pytest.mark.spec("VM-06-008")
def test_store_nested_inbox_object_persists_no_core_class_for_core_only_name(
    datalayer, persisted
):
    """The object the inbox persists for a core-only name is not core.

    ``CoreActor`` is registered only in the core map.  Before the lookups went
    wire-only the inbox handed a core object to the DataLayer for an inbound
    ``{"type": "CoreActor"}`` (ISSUE-3565); the parser leaves an unresolved
    type to its parent field, and storage keeps what the parser produced.
    """
    from vultron.core.models.base import CoreObject

    activity = _parsed_announce(
        {"id": "urn:uuid:core-only-store", "type": "CoreActor"}
    )

    _store_nested_inbox_object(datalayer, activity)

    assert len(persisted) == 1
    assert not isinstance(persisted[0], (CoreObject, CoreActor))


# ---------------------------------------------------------------------------
# _store_inbox_activity
# ---------------------------------------------------------------------------


def test_store_inbox_activity_persists_activity(datalayer):
    note = as_Note(content="test")
    activity = as_Create(actor=_ACTOR_URI, object_=note)
    _store_inbox_activity(datalayer, activity)
    stored = datalayer.read(activity.id_)
    assert stored is not None


@pytest.mark.spec("IE-10-001")
def test_store_inbox_activity_is_idempotent(datalayer):
    """Ingress storage is where a redelivery is detected (IE-10-001).

    The second call must not raise, must report that it wrote nothing, and must
    leave the first delivery in place rather than overwriting it.
    """
    note = as_Note(content="test")
    activity = as_Create(actor=_ACTOR_URI, object_=note, summary="first")
    assert _store_inbox_activity(datalayer, activity) is True

    redelivered = activity.model_copy(update={"summary": "second"})
    assert _store_inbox_activity(datalayer, redelivered) is False
    stored = datalayer.read(activity.id_)
    assert getattr(stored, "summary", None) == "first"


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
    _store_nested_inbox_object(datalayer, activity)
    stored = datalayer.read(case.id_)
    assert stored is not None


def test_store_nested_inbox_object_skips_string_object(datalayer):
    """When object_ is a URI string, no persistence should happen."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Announce,
    )

    activity = as_Announce(actor=_ACTOR_URI, object_="urn:uuid:some-id")
    # Should not raise; DL should remain empty
    _store_nested_inbox_object(datalayer, activity)


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

    _store_nested_inbox_object(datalayer, activity)

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
    _store_nested_inbox_object(datalayer, activity)

    with caplog.at_level(logging.DEBUG):
        _store_nested_inbox_object(datalayer, activity)

    assert "already exists" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
