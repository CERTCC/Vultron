#!/usr/bin/env python
"""Boundary tests verifying the wire base hierarchy has its own root.

ADR-0099 detail 4 retired the shared root that issue #799 introduced:
``as_Base`` now stands on ``BaseModel`` directly, so no wire class inherits
core fields, configuration or registration hooks (ARCH-12-001, ARCH-12-002).
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

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from vultron.core.models.base import CoreObject, CoreRecord
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.registry import VOCABULARY, WIRE_TYPE_MAP
from vultron.wire.as2.vocab.base.utils import URN_UUID_PREFIX

# --- Own root (ADR-0099 detail 4, ARCH-12-001) -----------------------------


def test_as_base_stands_directly_on_base_model():
    """``as_Base`` has its own root; nothing core sits between it and Pydantic."""
    assert as_Base.__bases__ == (BaseModel,)


def test_wire_base_inherits_no_core_root():
    """Neither wire base inherits either core root."""
    for wire_cls in (as_Base, as_Object):
        assert not issubclass(wire_cls, CoreRecord)
        assert not issubclass(wire_cls, CoreObject)


def test_as_object_still_inherits_as_base():
    """Wire-branch shape preserved: as_Object -> as_Base."""
    assert issubclass(as_Object, as_Base)


def test_as_object_mro_is_wire_only():
    """No ``vultron.core`` class appears in ``as_Object``'s MRO."""
    core_bases = [
        cls.__qualname__
        for cls in as_Object.__mro__
        if cls.__module__.startswith("vultron.core")
    ]
    assert core_bases == []


# --- Field-precedence / wire-semantics preserved ---------------------------


def test_as_base_id_uses_wire_default():
    """as_Base.id_ still uses generate_new_id (urn:uuid: prefix)."""
    obj = as_Base()
    assert obj.id_.startswith(URN_UUID_PREFIX)


def test_as_base_context_is_as2_namespace():
    """Wire branch: context_ defaults to the AS2 namespace, not None."""
    obj = as_Base()
    assert obj.context_ == "https://www.w3.org/ns/activitystreams"


def test_as_base_type_set_from_class_name():
    """Wire model_validator sets type_ from stripped class name."""
    obj = as_Base()
    assert obj.type_ == "Base"


def test_as_base_context_alias_accepted():
    """@context validation alias still accepted on as_Base."""
    obj = as_Base.model_validate(
        {"@context": "https://www.w3.org/ns/activitystreams"}
    )
    assert obj.context_ == "https://www.w3.org/ns/activitystreams"


def test_as_object_type_set_from_class_name():
    """Wire model_validator sets type_ from stripped class name on as_Object."""
    obj = as_Object()
    assert obj.type_ == "Object"


def test_as_object_published_defaults_to_now():
    """as_Object.published default still provided (from as_Object field def)."""
    obj = as_Object()
    assert obj.published is not None


def test_as_object_datetime_roundtrip():
    """as_Object wire datetime validators still accept ISO strings."""
    iso = "2026-01-15T12:00:00+00:00"
    obj = as_Object.model_validate({"published": iso})
    assert isinstance(obj.published, datetime)
    assert obj.published.tzinfo is not None


def test_as_object_naive_datetime_string_normalized_to_utc():
    """validate_datetime normalizes offset-less ISO strings to UTC (CS-13-001, ADR-0032)."""
    from datetime import timezone

    naive_iso = "2026-01-15T12:00:00"
    obj = as_Object.model_validate({"published": naive_iso})
    assert isinstance(obj.published, datetime)
    assert obj.published.tzinfo is not None
    assert obj.published.tzinfo == timezone.utc
    assert obj.published.year == 2026
    assert obj.published.hour == 12


def test_as_object_naive_datetime_object_normalized_to_utc():
    """validate_datetime normalizes naive datetime objects to UTC (CS-13-001, ADR-0032)."""
    from datetime import timezone

    naive_dt = datetime(2026, 1, 15, 12, 0, 0)
    assert naive_dt.tzinfo is None
    obj = as_Object.model_validate({"start_time": naive_dt})
    assert isinstance(obj.start_time, datetime)
    assert obj.start_time.tzinfo is not None
    assert obj.start_time.tzinfo == timezone.utc


def test_as_object_attributed_to_accepts_non_string():
    """Wire field attributed_to remains Any|None — non-string values must be accepted.

    ``CoreObject`` narrows attributed_to to NonEmptyString | None; the wire
    branch declares it as Any | None so that AS2 payloads carrying nested
    objects or dicts are accepted without validation errors.  A plain annotation check (looking for NoneType in __args__) would
    pass even if NonEmptyString | None took over, so we use a runtime round-trip.
    """
    # dict (inline AS2 object) must not raise
    obj = as_Object.model_validate(
        {"attributed_to": {"id": "https://example.org/alice"}}
    )
    assert obj.attributed_to == {"id": "https://example.org/alice"}

    # integer must not raise (fully lenient Any)
    obj2 = as_Object.model_validate({"attributed_to": 42})
    assert obj2.attributed_to == 42


def test_as_object_id_uses_wire_default():
    """as_Object.id_ still uses wire generate_new_id."""
    obj = as_Object()
    assert obj.id_.startswith(URN_UUID_PREFIX)


# --- Registry: __init_subclass__ still fires for wire concrete types --------


def test_concrete_wire_subclass_still_registers():
    """A concrete as_Object subclass with Literal type_ is still auto-registered.

    Regression: the inheritance change must not break VOCABULARY/WIRE_TYPE_MAP
    registration via as_Base.__init_subclass__.
    """

    class as_HierarchyTestProbe(as_Object):
        type_: Literal["HierarchyTestProbe"] = Field(
            default="HierarchyTestProbe",
            validation_alias="type",
            serialization_alias="type",
        )

    # VOCABULARY keyed by full class name (ARCH-23-002)
    assert "as_HierarchyTestProbe" in VOCABULARY
    assert VOCABULARY["as_HierarchyTestProbe"] is as_HierarchyTestProbe

    # WIRE_TYPE_MAP keyed by type_ value (for parser lookups)
    assert "HierarchyTestProbe" in WIRE_TYPE_MAP
    assert WIRE_TYPE_MAP["HierarchyTestProbe"] is as_HierarchyTestProbe

    # Cleanup to avoid polluting registries across tests
    del VOCABULARY["as_HierarchyTestProbe"]
    del WIRE_TYPE_MAP["HierarchyTestProbe"]
