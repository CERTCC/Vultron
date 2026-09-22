#!/usr/bin/env python
"""Tests for VM-10-001 and VM-10-002: as_VultronObject context_ defaults to the
Vultron namespace URI, and every wire type whose type_ value is not an AS2
vocabulary term carries VocabNamespace.VULTRON.

AC-1: as_VultronObject.context_ defaults to VULTRON_CONTEXT_URI.
AC-2: as_Base.context_ retains ACTIVITY_STREAMS_NS (tested in test_wire_base_hierarchy.py).
AC-3: Serialization emits the Vultron URI in @context for as_VultronObject subclasses.
AC-4: Round-trip from_json(obj.to_json()) preserves the Vultron @context.
AC-5: test_as_base_context_is_as2_namespace passes unmodified (in test_wire_base_hierarchy.py).
AC-6: Every wire type with a non-AS2 type_ value annotates _vocab_ns=VULTRON.
AC-7: Tests carry @pytest.mark.spec("VM-10-001") / @pytest.mark.spec("VM-10-002").
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

import importlib
import json
import pkgutil

import pytest

import vultron.wire.as2.vocab.activities as _act_pkg
import vultron.wire.as2.vocab.objects as _obj_pkg
from vultron.wire.as2.enums import as_AllObjectTypes
from vultron.wire.as2.vocab.base.base import (
    ACTIVITY_STREAMS_NS,
    VULTRON_CONTEXT_URI,
)
from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.registry import VOCABULARY
from vultron.wire.as2.vocab.objects.base import as_VultronObject
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

# Ensure all registered vocab types are loaded for AC-6.
for _mi in list(pkgutil.iter_modules(_obj_pkg.__path__)):
    importlib.import_module(f"vultron.wire.as2.vocab.objects.{_mi.name}")
for _mi in list(pkgutil.iter_modules(_act_pkg.__path__)):
    importlib.import_module(f"vultron.wire.as2.vocab.activities.{_mi.name}")

# Complete set of standard ActivityStreams 2.0 type_ values.
_AS2_VOCAB_TERMS = frozenset({m.value for m in as_AllObjectTypes}) | {
    "Object",
    "Collection",
    "OrderedCollection",
    "CollectionPage",
    "OrderedCollectionPage",
    "Link",
    "Mention",
    "Base",
}


# --- AC-1: as_VultronObject default context_ -----------------------------------


@pytest.mark.spec("VM-10-002")
def test_as_vultron_object_context_defaults_to_vultron_uri():
    """AC-1: as_VultronObject.context_ defaults to the Vultron context URI."""
    obj = as_VultronObject()
    assert obj.context_ == VULTRON_CONTEXT_URI


@pytest.mark.spec("VM-10-002")
def test_as_vultron_object_context_is_not_as2_namespace():
    """AC-1: as_VultronObject.context_ does NOT default to the AS2 namespace."""
    obj = as_VultronObject()
    assert obj.context_ != ACTIVITY_STREAMS_NS


# --- AC-3: Serialization emits correct @context --------------------------------


@pytest.mark.spec("VM-10-001")
@pytest.mark.spec("VM-10-002")
def test_vultron_subclass_serializes_vultron_context():
    """AC-3: A as_VultronObject subclass serializes @context as the Vultron URI."""
    obj = as_VultronObject()
    data = json.loads(obj.to_json())
    assert data["@context"] == VULTRON_CONTEXT_URI


@pytest.mark.spec("VM-10-001")
def test_embargo_event_serializes_vultron_context():
    """AC-3: as_EmbargoEvent is now a core class (ADR-0099 detail 3, issue #3487).

    The paired wire class was deleted; as_EmbargoEvent IS EmbargoEvent (core).
    Core objects do not carry @context — that is a wire-layer serialization concern.
    Verify the identity and that model_dump_json produces the expected type_ field.
    """
    from vultron.core.models.embargo_event import EmbargoEvent

    assert as_EmbargoEvent is EmbargoEvent
    obj = as_EmbargoEvent(context="urn:uuid:case-123")
    data = json.loads(obj.model_dump_json(exclude_none=True, by_alias=True))
    assert data["type"] == "EmbargoEvent"


@pytest.mark.spec("VM-10-002")
def test_as_base_subclass_without_override_retains_as2_context():
    """AC-3: A plain as_Base subclass (not as_VultronObject) still uses the AS2 namespace."""
    from vultron.wire.as2.vocab.base.base import as_Base

    obj = as_Base()
    data = json.loads(obj.to_json())
    assert data["@context"] == ACTIVITY_STREAMS_NS


# --- AC-4: Round-trip preserves Vultron @context -------------------------------


@pytest.mark.spec("VM-10-001")
@pytest.mark.spec("VM-10-002")
def test_as_vultron_object_roundtrip_preserves_context():
    """AC-4: from_json(obj.to_json()) preserves the Vultron @context."""
    obj = as_VultronObject()
    restored = as_VultronObject.from_json(obj.to_json())
    assert restored.context_ == VULTRON_CONTEXT_URI


@pytest.mark.spec("VM-10-001")
def test_embargo_event_roundtrip_preserves_context():
    """AC-4: as_EmbargoEvent is now a core class (ADR-0099 detail 3, issue #3487).

    Round-trip via model_dump/model_validate preserves the context field.
    (Core ``context`` stores the case URI, not a @context namespace URI.)
    """
    obj = as_EmbargoEvent(context="urn:uuid:case-123")
    data = obj.model_dump(mode="json", by_alias=True, exclude_none=True)
    restored = as_EmbargoEvent.model_validate(data)
    assert restored.context == obj.context


# --- as_EmbargoEvent namespace annotation -------------------------------------


@pytest.mark.spec("VM-10-002")
def test_embargo_event_vocab_namespace_is_vultron():
    """as_EmbargoEvent is now a core class (ADR-0099 detail 3, issue #3487).

    The paired wire class was deleted; _vocab_ns is a wire-layer concept and
    does not exist on the core EmbargoEvent.  Verify the class identity instead.
    """
    from vultron.core.models.embargo_event import EmbargoEvent

    assert as_EmbargoEvent is EmbargoEvent
    assert not hasattr(as_EmbargoEvent, "_vocab_ns")


# --- AC-6: Structural check — every non-AS2 type must be annotated VULTRON ----


@pytest.mark.spec("VM-10-002")
def test_all_non_as2_registered_types_are_vultron_namespaced():
    """AC-6: Every concrete wire type whose type_ value is not an AS2 vocab term
    must have _vocab_ns == VocabNamespace.VULTRON.

    This catches classes like as_EmbargoEvent that inherit _vocab_ns from an
    AS2 base (e.g. as_Event) but carry a Vultron-specific type_ value that AS2
    receivers cannot resolve without the Vultron context URI.
    """
    violations = []
    for class_name, cls in VOCABULARY.items():
        type_field = cls.model_fields.get("type_")
        if type_field is None:
            continue
        type_default = type_field.default
        if not isinstance(type_default, str):
            continue
        if type_default in _AS2_VOCAB_TERMS:
            continue
        ns = getattr(cls, "_vocab_ns", None)
        if ns != VocabNamespace.VULTRON:
            violations.append((class_name, type_default, ns))

    assert not violations, (
        "Wire types with non-AS2 type_ values that are NOT annotated "
        "VocabNamespace.VULTRON:\n"
        + "\n".join(
            f"  {name!r} (type_={t!r}): {ns}" for name, t, ns in violations
        )
    )
