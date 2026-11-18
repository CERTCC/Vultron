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

"""Core's AS2 base classes are AS2 as the Activity Vocabulary defines it.

Core owns the AS2 base vocabulary (ADR-0208, ARCH-25-010), so core and the
wire build on one set of AS2 classes.  These checks hold each registered base
class to the pinned AS2 ontology, read with its recorded departures
(:mod:`test.support.as2_ontology`), so that the classes stay AS2 models:

- its ``type`` is an AS2 type, and the wire registers that class under it;
- every serialized property is one the ontology allows on that type, which
  also keeps every Vultron property off it;
- it requires nothing on receipt beyond the recorded Vultron departures, so a
  valid AS2 object from a peer still validates.

The checks read the registry, so a base class added later is checked too.
"""

from typing import Any

import pytest
from pydantic import BaseModel

import vultron.core.models  # noqa: F401 - every base class registers
from test.support.as2_ontology import (
    pinned_ontology_supertypes,
    properties_allowed_on,
)
from vultron.core.models._helpers import (
    INBOUND_CONTEXT_KEY,
    own_type,
    received_without_published,
)
from vultron.core.models.as2_base import AS2_BASE_CLASSES
from vultron.wire.as2.vocab.base.base import VULTRON_PROPERTY_KEY
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

#: JSON-LD keywords AS2 serializes as such, not as ontology properties.
_JSON_LD_KEYWORDS = frozenset({"@context", "id", "type"})

#: AS2's JSON-LD context spells a language map of a property ``<name>Map``.
_LANGUAGE_MAP_SUFFIX = "Map"

#: The keys a received object must carry beyond what AS2 requires: Vultron's
#: receive rules, each with its spec.  ``published`` binds only a kind the
#: rule does not exempt (``received_without_published``).
_RECEIVE_DEPARTURES: dict[str, str] = {
    "id": "OID-01-013",
    "published": "CLP-15-011",
}

_DEPARTURE_VALUES: dict[str, str] = {
    "id": "https://example.org/objects/1",
    "published": "2026-01-01T00:00:00+00:00",
}


def _as2_type(cls: type[BaseModel]) -> str:
    """The AS2 type *cls* models: its own ``type``, or ``Object`` for the
    generic root, which declares none."""
    declared = own_type(cls)
    return declared if isinstance(declared, str) else "Object"


def _serialized_names(cls: type[BaseModel]) -> dict[str, str]:
    """Each field of *cls* by the name it serializes as."""
    return {
        str(field.serialization_alias or field.alias or name): name
        for name, field in cls.model_fields.items()
        if not field.exclude or name == "context_"
    }


def _departures(cls: type[BaseModel]) -> dict[str, str]:
    return {
        key: spec
        for key, spec in _RECEIVE_DEPARTURES.items()
        if key != "published" or not received_without_published(cls)
    }


def _minimal(cls: type[BaseModel], omit: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"type": _as2_type(cls)}
    body.update(
        {
            key: _DEPARTURE_VALUES[key]
            for key in _departures(cls)
            if key != omit
        }
    )
    return body


_BASES = pytest.mark.parametrize(
    "cls", AS2_BASE_CLASSES, ids=[c.__name__ for c in AS2_BASE_CLASSES]
)


def test_the_registry_holds_the_object_root_and_the_collections():
    """The registry is populated, so the checks below are not vacuous."""
    names = {cls.__name__ for cls in AS2_BASE_CLASSES}

    assert {"CoreObject", "Collection", "OrderedCollection"} <= names


@pytest.mark.spec("ARCH-25-010")
@_BASES
def test_a_base_class_type_is_an_as2_type(cls: type[BaseModel]):
    """Its ``type`` is a class of the AS2 ontology, unchanged."""
    assert _as2_type(cls) in pinned_ontology_supertypes()


@pytest.mark.spec("ARCH-25-010")
@_BASES
def test_the_wire_registers_a_base_class_under_its_type(cls: type[BaseModel]):
    """The wire builds on the core class: its ``type`` resolves to it."""
    declared = own_type(cls)
    if not isinstance(declared, str):
        pytest.skip("the generic root declares no type to register")
    assert WIRE_TYPE_MAP[declared] is cls


@pytest.mark.spec("ARCH-25-010")
@_BASES
def test_every_property_of_a_base_class_is_an_as2_property_of_its_type(
    cls: type[BaseModel],
):
    """Each serialized name is a JSON-LD keyword or an AS2 property the
    ontology's domains allow on the class's type, so no Vultron property
    sits on a base class."""
    allowed = properties_allowed_on(_as2_type(cls))
    stray = sorted(
        name
        for name in _serialized_names(cls)
        if name not in _JSON_LD_KEYWORDS
        and name not in allowed
        and name.removesuffix(_LANGUAGE_MAP_SUFFIX) not in allowed
    )

    assert not stray, f"{cls.__name__} serializes non-AS2 keys: {stray}"


@pytest.mark.spec("ARCH-25-010")
@_BASES
def test_no_base_class_field_is_marked_a_vultron_property(
    cls: type[BaseModel],
):
    """No field carries the Vultron-namespace marker."""
    marked = sorted(
        name
        for name, field in cls.model_fields.items()
        if isinstance(field.json_schema_extra, dict)
        and VULTRON_PROPERTY_KEY in field.json_schema_extra
    )

    assert not marked


@pytest.mark.spec("ARCH-25-010")
@_BASES
def test_a_valid_as2_object_from_a_peer_validates(cls: type[BaseModel]):
    """A received object with its ``type`` and only the recorded departures
    validates: the class requires nothing else AS2 does not."""
    cls.model_validate(_minimal(cls), context={INBOUND_CONTEXT_KEY: True})


@pytest.mark.spec("ARCH-25-010")
@pytest.mark.parametrize(
    ("cls", "key"),
    [
        pytest.param(cls, key, id=f"{cls.__name__}-{key}")
        for cls in AS2_BASE_CLASSES
        for key in _departures(cls)
    ],
)
def test_each_recorded_departure_still_departs(cls: type[BaseModel], key: str):
    """A departure stays recorded only while the class still refuses the
    object without it."""
    with pytest.raises(ValueError, match=_RECEIVE_DEPARTURES[key]):
        cls.model_validate(
            _minimal(cls, omit=key), context={INBOUND_CONTEXT_KEY: True}
        )
