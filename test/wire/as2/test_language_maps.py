"""AS2 natural-language maps are declared fields on both object roots (#4471).

AS2 Core section 4.7 lets ``content``, ``name`` and ``summary`` arrive as
``contentMap``, ``nameMap`` and ``summaryMap``: a language tag mapped to the
text in that language.  ARCH-25-008 declares every legitimate AS2 object field
on ``CoreObject`` and ``as_Object``, so a received map is read, not set aside
at the parse edge (MV-11-001, MV-11-003), and it survives the DataLayer.  Its
tags and values are "if present, then non-empty" (CS-08-001).  An empty map is
a key the sender never sent, so no dump carries one.
"""

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

import logging
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.base import CoreObject
from vultron.core.models.report import VulnerabilityReport
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object

PUBLISHED = "2026-03-04T05:06:07+00:00"
ACTIVITY_ID = "https://example.org/activities/maps-1"
SENDER = "https://example.org/actors/finder"
OBJECT_ID = "https://example.org/objects/maps-1"

#: One map per AS2 natural-language property, under its wire spelling.
MAPS: dict[str, dict[str, str]] = {
    "contentMap": {"en": "A buffer overflow", "fr": "Un débordement"},
    "nameMap": {"en": "Report", "de": "Bericht"},
    "summaryMap": {"en": "Short", "es": "Corto"},
}

#: The field name each wire spelling fills.
FIELDS = {
    "contentMap": "content_map",
    "nameMap": "name_map",
    "summaryMap": "summary_map",
}

ROOTS = [
    pytest.param(CoreObject, id="CoreObject"),
    pytest.param(as_Object, id="as_Object"),
]

#: An inline object of each branch: a core class and a wire class.
INLINE_TYPES = [
    pytest.param("VulnerabilityReport", VulnerabilityReport, id="core-class"),
    pytest.param("Note", as_Object, id="wire-class"),
]


def _create(inline: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Create",
        "id": ACTIVITY_ID,
        "actor": SENDER,
        "published": PUBLISHED,
        "object": inline,
    }


def _inline(obj_type: str, **extra: Any) -> dict[str, Any]:
    return {
        "type": obj_type,
        "id": OBJECT_ID,
        "name": "a report",
        "content": "body",
        "published": PUBLISHED,
        **extra,
    }


@pytest.mark.spec("ARCH-25-008")
@pytest.mark.parametrize("root", ROOTS)
def test_both_roots_declare_the_language_maps_empty_by_default(
    root: type[BaseModel],
) -> None:
    obj = make(root, id_=OBJECT_ID)
    for field in FIELDS.values():
        assert getattr(obj, field) == {}


@pytest.mark.spec("ARCH-25-008", "MV-11-001", "MV-11-003")
@pytest.mark.parametrize("obj_type, branch", INLINE_TYPES)
def test_a_received_language_map_is_read_not_set_aside(
    obj_type: str, branch: type, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    activity = parse_activity(_create(_inline(obj_type, **MAPS)))

    assert isinstance(activity, as_TransitiveActivity)
    inline = activity.object_
    assert isinstance(inline, branch)
    assert isinstance(inline, BaseModel)
    for key, field in FIELDS.items():
        assert getattr(inline, field) == MAPS[key]
    set_aside = [
        r.getMessage()
        for r in caplog.records
        if "Set aside unknown key" in r.getMessage()
    ]
    assert set_aside == []
    dumped = inline.model_dump(mode="json", by_alias=True, exclude_none=True)
    for key, value in MAPS.items():
        assert dumped[key] == value


@pytest.mark.spec("ARCH-25-008")
def test_a_received_language_map_round_trips_through_the_datalayer() -> None:
    activity = parse_activity(_create(_inline("VulnerabilityReport", **MAPS)))
    assert isinstance(activity, as_TransitiveActivity)
    report = activity.object_
    assert isinstance(report, VulnerabilityReport)
    dl = SqliteDataLayer(db_url="sqlite:///:memory:", actor_id=SENDER)

    dl.save(report)
    stored = dl.read(OBJECT_ID)

    assert isinstance(stored, VulnerabilityReport)
    for key, field in FIELDS.items():
        assert getattr(stored, field) == MAPS[key]


@pytest.mark.spec("CS-08-001", "CS-08-002")
@pytest.mark.parametrize("root", ROOTS)
@pytest.mark.parametrize("field", list(FIELDS.values()))
@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"": "text"}, id="empty-tag"),
        pytest.param({"  ": "text"}, id="blank-tag"),
        pytest.param({"en": ""}, id="empty-value"),
        pytest.param({"en": " \t"}, id="blank-value"),
    ],
)
def test_a_blank_tag_or_value_is_refused_when_built(
    root: type[BaseModel], field: str, bad: dict[str, str]
) -> None:
    with pytest.raises(ValidationError):
        make(root, id_=OBJECT_ID, **{field: bad})


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("obj_type", ["VulnerabilityReport", "Note"])
@pytest.mark.parametrize("key", list(MAPS))
def test_a_received_blank_value_is_refused_at_the_parse_edge(
    obj_type: str, key: str
) -> None:
    with pytest.raises(VultronParseValidationError):
        parse_activity(_create(_inline(obj_type, **{key: {"en": " "}})))


@pytest.mark.spec("ARCH-21-002")
@pytest.mark.parametrize("obj_type, branch", INLINE_TYPES)
def test_a_received_null_map_is_read_as_empty(
    obj_type: str, branch: type
) -> None:
    """JSON-LD reads ``null`` as no value, as every other AS2 property on
    the roots admits it."""
    nulls = dict.fromkeys(MAPS)

    activity = parse_activity(_create(_inline(obj_type, **nulls)))

    assert isinstance(activity, as_TransitiveActivity)
    inline = activity.object_
    assert isinstance(inline, branch)
    for field in FIELDS.values():
        assert getattr(inline, field) == {}


@pytest.mark.spec("ARCH-25-008")
@pytest.mark.parametrize("root", ROOTS)
def test_an_empty_map_is_left_out_of_every_dump(root: type[BaseModel]) -> None:
    obj = make(root, id_=OBJECT_ID)

    wire = obj.model_dump(mode="json", by_alias=True, exclude_none=True)
    stored = obj.model_dump(mode="json")

    for key, field in FIELDS.items():
        assert key not in wire
        assert field not in stored


@pytest.mark.spec("ARCH-25-008")
def test_a_stored_object_without_maps_reads_back_with_empty_maps() -> None:
    report = make(VulnerabilityReport, id_=OBJECT_ID, name="r", content="c")
    dl = SqliteDataLayer(db_url="sqlite:///:memory:", actor_id=SENDER)

    dl.save(report)
    stored = dl.read(OBJECT_ID)

    assert isinstance(stored, VulnerabilityReport)
    for field in FIELDS.values():
        assert getattr(stored, field) == {}
