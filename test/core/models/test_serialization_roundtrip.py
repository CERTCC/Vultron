"""Tests for VultronBase/VultronActivity serialization round-trip fidelity.

BUG-2026040902: VultronBase.id_ has no validation/serialization aliases,
so ``model_dump(by_alias=True)`` emits ``"id_"`` instead of ``"id"``,
and ``model_validate({"id": "..."})`` generates a NEW UUID.

Subclass type_ fields (VultronOffer, VultronAccept,
VultronCreateCaseActivity) similarly lose their aliases when they
override ``type_`` without reattaching the ``Field(...)`` metadata.

These bugs break the outbox → HTTP → inbox delivery path because the
serialised payload uses the wrong key names and loses the original
activity ID.
"""

import pytest

from vultron.core.models.activity import (
    VultronAccept,
    VultronActivity,
    VultronCreateCaseActivity,
    VultronOffer,
)
from vultron.core.models.base import VultronBase, VultronObject

# ---------------------------------------------------------------------------
# VultronBase.id_ alias tests
# ---------------------------------------------------------------------------


class TestVultronBaseIdAlias:
    """VultronBase.id_ must serialise as ``"id"`` and deserialise from ``"id"``."""

    def test_model_dump_by_alias_uses_id_key(self):
        """model_dump(by_alias=True) must emit ``"id"``, not ``"id_"``."""
        obj = VultronBase(id_="urn:uuid:keep-me")
        dumped = obj.model_dump(by_alias=True)
        assert (
            "id" in dumped
        ), f"Expected 'id' key, got keys: {list(dumped.keys())}"
        assert (
            "id_" not in dumped
        ), "'id_' key should not appear in aliased dump"
        assert dumped["id"] == "urn:uuid:keep-me"

    def test_model_validate_from_id_key(self):
        """model_validate({'id': ...}) must populate id_ from the ``"id"`` key."""
        obj = VultronBase.model_validate({"id": "urn:uuid:from-json"})
        assert obj.id_ == "urn:uuid:from-json"

    def test_model_validate_from_id_underscore_key(self):
        """model_validate({'id_': ...}) must still work (populate_by_name)."""
        obj = VultronBase.model_validate({"id_": "urn:uuid:from-field-name"})
        assert obj.id_ == "urn:uuid:from-field-name"

    def test_id_survives_dump_validate_roundtrip(self):
        """id_ must survive a dump → validate round-trip unchanged."""
        original = VultronBase(id_="urn:uuid:roundtrip")
        dumped = original.model_dump(by_alias=True)
        restored = VultronBase.model_validate(dumped)
        assert restored.id_ == "urn:uuid:roundtrip"


class TestVultronObjectIdAlias:
    """VultronObject inherits from VultronBase; id_ aliases must propagate."""

    def test_model_dump_by_alias_uses_id_key(self):
        obj = VultronObject(id_="urn:uuid:obj-test")
        dumped = obj.model_dump(by_alias=True)
        assert "id" in dumped
        assert dumped["id"] == "urn:uuid:obj-test"


# ---------------------------------------------------------------------------
# VultronActivity id_ round-trip
# ---------------------------------------------------------------------------


class TestVultronActivityIdRoundTrip:
    """VultronActivity must preserve id_ through dump → validate cycles."""

    def test_id_preserved_in_roundtrip(self):
        act = VultronActivity(
            id_="urn:uuid:act-original",
            type_="Announce",
            actor="https://example.org/actors/test",
        )
        dumped = act.model_dump(by_alias=True)
        assert dumped.get("id") == "urn:uuid:act-original"

        restored = VultronActivity.model_validate(dumped)
        assert restored.id_ == "urn:uuid:act-original"


# ---------------------------------------------------------------------------
# Subclass type_ alias tests
# ---------------------------------------------------------------------------


SUBCLASS_TEST_CASES = [
    (VultronOffer, "Offer"),
    (VultronAccept, "Accept"),
    (VultronCreateCaseActivity, "Create"),
]


@pytest.mark.parametrize("cls, expected_type", SUBCLASS_TEST_CASES)
class TestSubclassTypeAlias:
    """Subclasses that override type_ must retain serialization aliases."""

    def test_dump_by_alias_uses_type_key(self, cls, expected_type):
        """model_dump(by_alias=True) must emit ``"type"``, not ``"type_"``."""
        obj = cls(actor="https://example.org/actors/test")
        dumped = obj.model_dump(by_alias=True)
        assert (
            "type" in dumped
        ), f"{cls.__name__}: expected 'type' key, got {list(dumped.keys())}"
        assert (
            "type_" not in dumped
        ), f"{cls.__name__}: 'type_' key should not appear"
        assert dumped["type"] == expected_type

    def test_validate_from_type_key(self, cls, expected_type):
        """model_validate({'type': ...}) must populate type_ correctly."""
        data = {
            "type": expected_type,
            "actor": "https://example.org/actors/test",
        }
        obj = cls.model_validate(data)
        assert obj.type_ == expected_type


# ---------------------------------------------------------------------------
# Cross-model round-trip (as_Create → VultronActivity, as in outbox_handler)
# ---------------------------------------------------------------------------


class TestCrossModelRoundTrip:
    """Simulate the outbox_handler conversion: as_Activity.model_dump → VultronActivity.model_validate."""

    def test_as_create_to_vultron_activity_preserves_id(self):
        """When outbox_handler converts as_Create → VultronActivity, the id must survive."""
        # Simulate what as_Create.model_dump(by_alias=True) produces
        as_create_dump = {
            "id": "urn:uuid:original-activity-id",
            "type": "Create",
            "actor": "https://vendor.example.org/actors/vendor",
            "object": "urn:uuid:case-123",
            "to": ["https://finder.example.org/actors/finder"],
        }
        vultron_act = VultronActivity.model_validate(as_create_dump)
        assert vultron_act.id_ == "urn:uuid:original-activity-id"
        assert vultron_act.type_ == "Create"

    def test_vultron_activity_dump_for_http_delivery(self):
        """VultronActivity.model_dump(by_alias=True) must produce valid HTTP payload."""
        act = VultronActivity(
            id_="urn:uuid:delivery-test",
            type_="Create",
            actor="https://vendor.example.org/actors/vendor",
            object_="urn:uuid:case-obj",
            to=["https://finder.example.org/actors/finder"],
        )
        payload = act.model_dump(by_alias=True, exclude_none=True)
        # Must use "id" not "id_" and "type" not "type_"
        assert "id" in payload
        assert "id_" not in payload
        assert "type" in payload
        assert "type_" not in payload
        assert payload["id"] == "urn:uuid:delivery-test"
        assert payload["type"] == "Create"
        assert payload["object"] == "urn:uuid:case-obj"
