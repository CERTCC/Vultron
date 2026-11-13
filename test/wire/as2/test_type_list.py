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
"""A ``type`` list at the wire edge: sent for an extension type, resolved on receipt.

ADR-0196: an extension class that declares an AS2 core supertype serializes its
``type`` as ``[own type, core type]`` (VM-03-005), and one shared resolver
narrows a received list to the most specific class the vocabulary knows
(VM-03-006).  The extension classes here are test-only, registered for this
module and removed after it, so the tests do not depend on ``Refuse``.
"""

import copy
import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, ClassVar, Literal
from unittest.mock import patch

import pytest
from pydantic import Field, ValidationError

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.http_object_fetch import parse_fetched_object
from vultron.adapters.driving.fastapi.helpers import obj_from_item
from vultron.adapters.driving.fastapi.outbox_addressing import _format_object
from vultron.adapters.driving.fastapi.outbox_delivery import _activity_type
from vultron.core.models.base import CoreObject
from vultron.core.models.registry import CORE_TYPE_MAP
from vultron.wire.as2.errors import VultronParseUnknownTypeError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab import (
    activities as _activities,  # noqa: F401
    objects as _objects,  # noqa: F401
)
from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.base.registry import (
    VOCABULARY,
    WIRE_TYPE_MAP,
    AmbiguousWireTypeError,
    narrow_type_list,
    resolve_wire_type,
    resolved_wire_type_name,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    is_case_reference_shape,
)

PUBLISHED = "2026-03-04T05:06:07+00:00"
ACTOR = "https://example.org/actors/alice"


@pytest.fixture(scope="module")
def ext() -> Iterator[SimpleNamespace]:
    """Two test-only extension classes, registered only for this module.

    ``TestDecline`` refines ``Reject`` (an activity) and ``TestMemo`` refines
    ``Note`` (an object), the shape ``Refuse`` will take (ADR-0196).  The
    registries are restored afterwards, so no other test sees them.
    """
    with patch.dict(WIRE_TYPE_MAP), patch.dict(VOCABULARY):

        class as_TestDecline(as_Reject):
            _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.VULTRON
            _as2_core_supertype = as_Reject
            type_: Literal["TestDecline"] = Field(  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]
                default="TestDecline",
                validation_alias="type",
                serialization_alias="type",
            )

        class as_TestMemo(as_Note):
            _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.VULTRON
            _as2_core_supertype = as_Note
            type_: Literal["TestMemo"] = Field(  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]
                default="TestMemo",
                validation_alias="type",
                serialization_alias="type",
            )

        yield SimpleNamespace(Decline=as_TestDecline, Memo=as_TestMemo)


def _decline(ext: SimpleNamespace) -> Any:
    return ext.Decline(
        actor=ACTOR,
        object_="https://example.org/notes/1",
        published=PUBLISHED,
        updated=PUBLISHED,
    )


def _wire(obj: Any) -> dict[str, Any]:
    """The JSON a sender writes for *obj*."""
    wire: dict[str, Any] = json.loads(obj.to_json())
    return wire


def _activity_body(type_value: object, **extra: Any) -> dict[str, Any]:
    return {
        "type": type_value,
        "id": "https://example.org/activities/1",
        "actor": ACTOR,
        "published": PUBLISHED,
        "object": "https://example.org/notes/1",
        **extra,
    }


@pytest.mark.spec("VM-03-005")
class TestOutboundTypeList:
    """An extension type is sent with its core type (VM-03-005)."""

    def test_the_wire_type_is_the_list_of_own_type_then_core_type(self, ext):
        decline = _decline(ext)

        assert _wire(decline)["type"] == ["TestDecline", "Reject"]
        assert decline.to_dict()["type"] == ["TestDecline", "Reject"]

    def test_type_inside_stays_the_extension_type(self, ext):
        decline = _decline(ext)

        assert decline.type_ == "TestDecline"
        # The persistence dump keeps one string: only the wire form lists.
        assert decline.model_dump()["type_"] == "TestDecline"
        assert decline.model_dump(mode="json")["type_"] == "TestDecline"

    def test_a_class_with_no_core_supertype_keeps_a_string(self):
        reject = as_Reject(
            actor=ACTOR,
            object_="https://example.org/notes/1",
            published=PUBLISHED,
            updated=PUBLISHED,
        )

        assert _wire(reject)["type"] == "Reject"

    def test_an_inline_extension_object_is_sent_with_the_list(self, ext):
        memo = ext.Memo(content="x", published=PUBLISHED, updated=PUBLISHED)
        create = as_Create(
            actor=ACTOR, object_=memo, published=PUBLISHED, updated=PUBLISHED
        )

        assert _wire(create)["object"]["type"] == ["TestMemo", "Note"]

    def test_the_list_validates_back_to_the_same_class(self, ext):
        wire = _wire(_decline(ext))

        rebuilt = ext.Decline.model_validate(wire)

        assert type(rebuilt) is ext.Decline
        assert rebuilt.type_ == "TestDecline"

    def test_the_parser_reads_the_list_back_to_the_same_class(self, ext):
        parsed = parse_activity(_wire(_decline(ext)))

        assert type(parsed) is ext.Decline
        assert parsed.type_ == "TestDecline"

    def test_an_inline_extension_object_parses_back_to_its_class(self, ext):
        memo = ext.Memo(content="x", published=PUBLISHED, updated=PUBLISHED)
        create = as_Create(
            actor=ACTOR, object_=memo, published=PUBLISHED, updated=PUBLISHED
        )

        parsed = parse_activity(_wire(create))

        assert type(parsed.object_) is ext.Memo

    def test_a_stored_copy_reads_back_as_the_same_class(self, ext):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        try:
            decline = _decline(ext)
            dl.save(decline)

            stored = dl.read(decline.id_)
        finally:
            dl.clear_all()
            dl.close()

        assert type(stored) is ext.Decline
        assert stored.type_ == "TestDecline"

    @pytest.mark.spec("VM-08-002")
    def test_the_received_evidence_keeps_the_list(self, ext):
        parsed = parse_activity(_wire(_decline(ext)))

        assert parsed.received_evidence is not None
        assert parsed.received_evidence["type"] == ["TestDecline", "Reject"]


class TestCoreSupertypeDeclaration:
    """A malformed declaration fails when the class is defined."""

    @pytest.fixture(autouse=True)
    def _scratch_registries(self) -> Iterator[None]:
        with patch.dict(WIRE_TYPE_MAP), patch.dict(VOCABULARY):
            yield

    def test_the_supertype_must_be_an_ancestor(self):
        with pytest.raises(TypeError, match="must be a superclass"):

            class as_TestStray(as_Reject):
                _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.VULTRON
                _as2_core_supertype = as_Note
                type_: Literal["TestStray"] = "TestStray"  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]

    def test_the_supertype_must_be_an_as2_class(self, ext):
        with pytest.raises(TypeError, match="AS2 core class"):

            class as_TestDeeper(ext.Decline):
                _as2_core_supertype = ext.Decline
                type_: Literal["TestDeeper"] = "TestDeeper"  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]

    def test_the_class_must_be_a_vultron_extension(self):
        with pytest.raises(TypeError, match="Vultron extension class"):

            class as_TestPlain(as_Reject):
                _as2_core_supertype = as_Reject
                type_: Literal["TestPlain"] = "TestPlain"  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]

    def test_the_class_must_name_its_own_type(self):
        with pytest.raises(TypeError, match="shares the wire type"):

            class as_TestSame(as_Reject):
                _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.VULTRON
                _as2_core_supertype = as_Reject
                type_: Literal["Reject"] = "Reject"  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]

    def test_the_supertype_must_be_a_wire_class(self):
        with pytest.raises(TypeError, match="must be a wire class"):

            class as_TestOdd(as_Reject):
                _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.VULTRON
                _as2_core_supertype = "Reject"  # type: ignore[assignment]
                type_: Literal["TestOdd"] = "TestOdd"  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]


@pytest.mark.spec("VM-03-006")
class TestInboundTypeList:
    """A received ``type`` list resolves to its most specific known class."""

    @pytest.mark.parametrize(
        "type_value",
        [["TestDecline", "Reject"], ["Reject", "TestDecline"], "TestDecline"],
    )
    def test_any_order_resolves_to_the_most_specific_class(
        self, ext, type_value
    ):
        assert resolve_wire_type(type_value) is ext.Decline
        assert type(parse_activity(_activity_body(type_value))) is ext.Decline

    def test_a_term_the_vocabulary_does_not_know_is_ignored(self):
        assert resolve_wire_type(["Foo", "Reject"]) is as_Reject
        assert type(parse_activity(_activity_body(["Foo", "Reject"]))) is (
            as_Reject
        )

    def test_a_non_string_term_is_ignored(self):
        assert resolve_wire_type([7, None, "Reject"]) is as_Reject

    def test_two_unrelated_known_types_are_refused(self):
        with pytest.raises(AmbiguousWireTypeError):
            resolve_wire_type(["Reject", "Accept"])
        with pytest.raises(VultronParseUnknownTypeError, match="subtype"):
            parse_activity(_activity_body(["Reject", "Accept"]))

    def test_two_unrelated_known_types_are_refused_inline(self):
        body = _activity_body(
            "Create",
            object={
                "type": ["Note", "VulnerabilityReport"],
                "id": "https://example.org/reports/1",
                "name": "r",
            },
        )

        with pytest.raises(VultronParseUnknownTypeError, match="'object'"):
            parse_activity(body)

    @pytest.mark.parametrize("type_value", [[], ["Foo"], ["Foo", "Bar"]])
    def test_a_list_with_no_known_type_is_unknown(self, type_value):
        with pytest.raises(KeyError):
            resolve_wire_type(type_value)
        with pytest.raises(VultronParseUnknownTypeError):
            parse_activity(_activity_body(type_value))

    @pytest.mark.parametrize("type_value", [0, {}, None, ("Reject",)])
    def test_a_value_that_is_neither_string_nor_list_is_unknown(
        self, type_value
    ):
        with pytest.raises(KeyError):
            resolve_wire_type(type_value)

    def test_an_inline_list_resolves_to_a_core_class(self):
        body = _activity_body(
            "Create",
            object={
                "type": ["Foo", "VulnerabilityReport"],
                "id": "https://example.org/reports/1",
                "name": "r",
            },
        )

        parsed = parse_activity(copy.deepcopy(body))

        assert isinstance(parsed.object_, CoreObject)
        assert parsed.object_.type_ == "VulnerabilityReport"
        assert parsed.received_evidence == body

    def test_the_core_fallback_follows_include_core(self):
        core_only = next(
            name for name in CORE_TYPE_MAP if name not in WIRE_TYPE_MAP
        )

        with pytest.raises(KeyError):
            resolve_wire_type(["Foo", core_only])
        assert (
            resolve_wire_type(["Foo", core_only], include_core=True)
            is CORE_TYPE_MAP[core_only]
        )

    def test_a_fetched_body_with_a_type_list_parses(self):
        document = {
            "type": ["Foo", "Note"],
            "id": "https://example.org/objects/fetched-1",
            "content": "held",
        }

        parsed = parse_fetched_object(
            document, document["id"], "https://example.org/actors/holder"
        )

        assert type(parsed) is as_Note

    def test_a_client_item_with_a_type_list_builds_its_class(self):
        item = {
            "type": ["Foo", "Note"],
            "content": "x",
            "published": PUBLISHED,
            "updated": PUBLISHED,
        }

        assert type(obj_from_item(item)) is as_Note

    def test_a_case_reference_list_is_a_case_reference(self):
        assert is_case_reference_shape(
            {"type": ["Foo", "VulnerabilityCase"], "id": "https://e.org/c/1"}
        )


class TestResolverHelpers:
    """The name and narrowing helpers answer what the resolver answers."""

    def test_the_name_is_the_term_of_the_most_specific_class(self, ext):
        assert resolved_wire_type_name(["Reject", "TestDecline"]) == (
            "TestDecline"
        )
        assert resolved_wire_type_name("Reject") == "Reject"
        assert resolved_wire_type_name(["Foo"]) is None
        assert resolved_wire_type_name(["Reject", "Accept"]) is None

    def test_narrowing_replaces_only_a_list(self, ext):
        listed = {"type": ["Reject", "TestDecline"], "id": "x"}
        named = {"type_": "Reject"}

        assert narrow_type_list(listed) == {"type": "TestDecline", "id": "x"}
        assert listed["type"] == ["Reject", "TestDecline"]
        assert narrow_type_list(named) is named

    def test_narrowing_refuses_an_unresolvable_list(self):
        with pytest.raises(KeyError):
            narrow_type_list({"type": ["Foo"]})

    def test_a_class_refuses_a_list_that_resolves_to_nothing(self):
        with pytest.raises(ValidationError, match="Unknown vocabulary type"):
            as_Note.model_validate({"type": ["Foo"], "content": "x"})

    def test_outbox_logs_name_the_resolved_type(self):
        assert _activity_type({"type": ["Foo", "Reject"]}) == "Reject"
        assert _activity_type({}) == "Activity"
        assert (
            _format_object({"type": ["Foo", "Note"], "id": "https://e.org/n"})
            == "Note https://e.org/n"
        )
