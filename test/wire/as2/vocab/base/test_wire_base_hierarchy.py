#!/usr/bin/env python
"""Boundary tests verifying the wire base hierarchy inherits from the shared
root (ARCH-12-001, ARCH-12-002, issue #799).

AC-1: issubclass(as_Base, VultronBase) is True.
AC-2: issubclass(as_Object, VultronObject) is True.
AC-3: No new mypy or pyright errors (validated via linters, not here).
AC-4: All existing tests pass; inheritance chain confirmed here.
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
from typing import Any, Literal

from pydantic import BaseModel, Field

from vultron.core.models.base import VultronBase, VultronObject
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.registry import VOCABULARY
from vultron.wire.as2.vocab.base.utils import URN_UUID_PREFIX

# --- AC-1/AC-2: Inheritance chain (ARCH-12-001) ----------------------------


def test_as_base_inherits_vultron_base():
    """AC-1: issubclass(as_Base, VultronBase) is True."""
    assert issubclass(as_Base, VultronBase)


def test_as_object_inherits_vultron_object():
    """AC-2: issubclass(as_Object, VultronObject) is True."""
    assert issubclass(as_Object, VultronObject)


def test_as_base_still_inherits_base_model():
    """Transitive: as_Base -> VultronBase -> BaseModel."""
    assert issubclass(as_Base, BaseModel)


def test_as_object_still_inherits_as_base():
    """Wire-branch shape preserved: as_Object -> as_Base."""
    assert issubclass(as_Object, as_Base)


def test_as_object_inherits_vultron_base():
    """as_Object transitively inherits VultronBase via both branches."""
    assert issubclass(as_Object, VultronBase)


def test_as_object_mro():
    """MRO confirms diamond linearisation: as_Object -> as_Base -> VultronObject -> VultronBase."""
    mro_names = [cls.__name__ for cls in as_Object.__mro__]
    assert mro_names.index("as_Object") < mro_names.index("as_Base")
    assert mro_names.index("as_Base") < mro_names.index("VultronObject")
    assert mro_names.index("VultronObject") < mro_names.index("VultronBase")


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


def test_as_object_attributed_to_is_any():
    """Wire field attributed_to remains Any|None (not narrowed by VultronObject)."""
    field = as_Object.model_fields["attributed_to"]
    annotation = field.annotation
    # as_Object re-declares attributed_to as Any | None; VultronObject has
    # NonEmptyString | None.  The wire declaration must win.
    args = getattr(annotation, "__args__", None)
    assert annotation is Any or (args is not None and type(None) in args)


def test_as_object_id_uses_wire_default():
    """as_Object.id_ still uses wire generate_new_id."""
    obj = as_Object()
    assert obj.id_.startswith(URN_UUID_PREFIX)


# --- Registry: __init_subclass__ still fires for wire concrete types --------


def test_concrete_wire_subclass_still_registers():
    """A concrete as_Object subclass with Literal type_ is still auto-registered.

    Regression: the inheritance change must not break VOCABULARY registration
    via as_Base.__init_subclass__.
    """

    class as_HierarchyTestProbe(as_Object):
        type_: Literal["HierarchyTestProbe"] = Field(
            default="HierarchyTestProbe",
            validation_alias="type",
            serialization_alias="type",
        )

    assert "HierarchyTestProbe" in VOCABULARY
    assert VOCABULARY["HierarchyTestProbe"] is as_HierarchyTestProbe

    # Cleanup to avoid polluting VOCABULARY across tests
    del VOCABULARY["HierarchyTestProbe"]
