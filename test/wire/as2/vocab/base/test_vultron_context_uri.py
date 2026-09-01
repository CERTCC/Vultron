#!/usr/bin/env python
"""Tests for VM-10-001 and VM-10-002: VultronAS2Object context_ defaults to the
Vultron namespace URI, and every wire type whose type_ value is not an AS2
vocabulary term carries VocabNamespace.VULTRON.

AC-1: VultronAS2Object.context_ defaults to VULTRON_CONTEXT_URI.
AC-2: as_Base.context_ retains ACTIVITY_STREAMS_NS (tested in test_wire_base_hierarchy.py).
AC-3: Serialization emits the Vultron URI in @context for VultronAS2Object subclasses.
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
from vultron.wire.as2.vocab.objects.base import VultronAS2Object
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


# --- AC-1: VultronAS2Object default context_ -----------------------------------


@pytest.mark.spec("VM-10-002")
def test_vultron_as2_object_context_defaults_to_vultron_uri():
    """AC-1: VultronAS2Object.context_ defaults to the Vultron context URI."""
    obj = VultronAS2Object()
    assert obj.context_ == VULTRON_CONTEXT_URI


@pytest.mark.spec("VM-10-002")
def test_vultron_as2_object_context_is_not_as2_namespace():
    """AC-1: VultronAS2Object.context_ does NOT default to the AS2 namespace."""
    obj = VultronAS2Object()
    assert obj.context_ != ACTIVITY_STREAMS_NS


# --- AC-3: Serialization emits correct @context --------------------------------


@pytest.mark.spec("VM-10-001")
@pytest.mark.spec("VM-10-002")
def test_vultron_subclass_serializes_vultron_context():
    """AC-3: A VultronAS2Object subclass serializes @context as the Vultron URI."""
    obj = VultronAS2Object()
    data = json.loads(obj.to_json())
    assert data["@context"] == VULTRON_CONTEXT_URI


@pytest.mark.spec("VM-10-001")
def test_embargo_event_serializes_vultron_context():
    """AC-3: as_EmbargoEvent (Vultron type extending as_Event) serializes Vultron @context."""
    obj = as_EmbargoEvent()
    data = json.loads(obj.to_json())
    assert data["@context"] == VULTRON_CONTEXT_URI


@pytest.mark.spec("VM-10-002")
def test_as_base_subclass_without_override_retains_as2_context():
    """AC-3: A plain as_Base subclass (not VultronAS2Object) still uses the AS2 namespace."""
    from vultron.wire.as2.vocab.base.base import as_Base

    obj = as_Base()
    data = json.loads(obj.to_json())
    assert data["@context"] == ACTIVITY_STREAMS_NS


# --- AC-4: Round-trip preserves Vultron @context -------------------------------


@pytest.mark.spec("VM-10-001")
@pytest.mark.spec("VM-10-002")
def test_vultron_as2_object_roundtrip_preserves_context():
    """AC-4: from_json(obj.to_json()) preserves the Vultron @context."""
    obj = VultronAS2Object()
    restored = VultronAS2Object.from_json(obj.to_json())
    assert restored.context_ == VULTRON_CONTEXT_URI


@pytest.mark.spec("VM-10-001")
def test_embargo_event_roundtrip_preserves_context():
    """AC-4: as_EmbargoEvent round-trip preserves the Vultron @context."""
    obj = as_EmbargoEvent()
    restored = as_EmbargoEvent.from_json(obj.to_json())
    assert restored.context_ == VULTRON_CONTEXT_URI


# --- as_EmbargoEvent namespace annotation -------------------------------------


@pytest.mark.spec("VM-10-002")
def test_embargo_event_vocab_namespace_is_vultron():
    """as_EmbargoEvent._vocab_ns must be VULTRON (EmbargoEvent is a Vultron term)."""
    assert as_EmbargoEvent._vocab_ns == VocabNamespace.VULTRON


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
