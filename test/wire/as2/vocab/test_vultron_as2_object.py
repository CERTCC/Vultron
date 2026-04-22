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

"""Tests for VultronAS2Object.from_core / to_core / _field_map — WIRE-TRANS-02."""

import pytest
from pydantic import BaseModel

from vultron.wire.as2.vocab.objects.base import VultronAS2Object


class _SimpleCoreObj(BaseModel):
    """Minimal core domain object for testing."""

    id_: str = "urn:uuid:test-1234"
    type_: str | None = None
    name: str | None = None
    content: str | None = None


class _RenamedCoreObj(BaseModel):
    """Core domain object with a field whose name differs from the wire field."""

    id_: str = "urn:uuid:test-5678"
    type_: str | None = None
    domain_label: str | None = "hello"


class _MappedWireObj(VultronAS2Object):
    """Wire type with a _field_map translating domain_label → wire_label."""

    _field_map = {"domain_label": "name"}


class TestVultronAS2ObjectFieldMap:
    def test_default_field_map_is_empty(self):
        assert VultronAS2Object._field_map == {}

    def test_subclass_can_override_field_map(self):
        assert _MappedWireObj._field_map == {"domain_label": "name"}


class TestVultronAS2ObjectFromCore:
    def test_from_core_returns_wire_instance(self):
        core = _SimpleCoreObj()
        wire = VultronAS2Object.from_core(core)
        assert isinstance(wire, VultronAS2Object)

    def test_from_core_preserves_id(self):
        core = _SimpleCoreObj(id_="urn:uuid:abc-123")
        wire = VultronAS2Object.from_core(core)
        assert wire.id_ == "urn:uuid:abc-123"

    def test_from_core_preserves_name(self):
        core = _SimpleCoreObj(name="Test Object")
        wire = VultronAS2Object.from_core(core)
        assert wire.name == "Test Object"

    def test_from_core_preserves_content(self):
        core = _SimpleCoreObj(content="some content")
        wire = VultronAS2Object.from_core(core)
        assert wire.content == "some content"

    def test_from_core_with_field_map_renames_field(self):
        core = _RenamedCoreObj(domain_label="my-label")
        wire = _MappedWireObj.from_core(core)
        assert isinstance(wire, _MappedWireObj)
        assert wire.name == "my-label"

    def test_from_core_with_field_map_absent_key_is_ignored(self):
        """_field_map entry for a missing domain field is silently skipped."""
        core = _RenamedCoreObj(domain_label=None)
        wire = _MappedWireObj.from_core(core)
        # domain_label=None → name=None (not present → not renamed)
        assert wire.name is None

    def test_from_core_subclass_returns_subclass_instance(self):
        core = _SimpleCoreObj()
        wire = _MappedWireObj.from_core(core)
        assert type(wire) is _MappedWireObj

    def test_from_core_does_not_mutate_original_object(self):
        core = _RenamedCoreObj(domain_label="original")
        _MappedWireObj.from_core(core)
        assert core.domain_label == "original"


class TestVultronAS2ObjectToCore:
    def test_to_core_raises_not_implemented(self):
        wire = VultronAS2Object()
        with pytest.raises(NotImplementedError):
            wire.to_core()

    def test_to_core_raises_on_subclass_without_override(self):
        wire = _MappedWireObj()
        with pytest.raises(NotImplementedError):
            wire.to_core()

    def test_to_core_error_mentions_class_name(self):
        wire = _MappedWireObj()
        with pytest.raises(NotImplementedError, match="_MappedWireObj"):
            wire.to_core()


class TestVultronAS2ObjectNoShim:
    """Ensure the backward-compatibility alias was removed (WIRE-TRANS-01)."""

    def test_VultronObject_not_exported_from_wire_base(self):
        import vultron.wire.as2.vocab.objects.base as wire_base

        assert not hasattr(
            wire_base, "VultronObject"
        ), "VultronObject alias must not exist in wire objects base module"
