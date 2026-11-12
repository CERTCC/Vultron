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

"""Tests for the core CaseReference domain model (step 6 of issue #699)."""

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from test.support.objects import make, with_times
from vultron.core.models.base import CoreObject
from vultron.core.models.case_reference import (
    CASE_REFERENCE_REL_NAMESPACE,
    CASE_REFERENCE_REL_VOCABULARY,
    CVE_REFERENCE_TAG_RELS,
    CVE_REFERENCE_TAGS,
    CaseReference,
    CaseReferenceLink,
)
from vultron.core.models.registry import CORE_VOCABULARY

_HREF = "https://example.org/advisory"
_PATCH = f"{CASE_REFERENCE_REL_NAMESPACE}patch"
_VENDOR_ADVISORY = f"{CASE_REFERENCE_REL_NAMESPACE}vendor-advisory"


def _ref(**link: object) -> CaseReference:
    return make(CaseReference, url={"href": _HREF, **link})


def _errors(exc: ValidationError) -> list[tuple[tuple[int | str, ...], str]]:
    """Each refusal's location and error type, so a test pins its cause."""
    return [(error["loc"], error["type"]) for error in exc.errors()]


class TestCaseReferenceIsAnObject:
    """A reference keeps its own id and lifecycle (#6249, CM-34)."""

    def test_inherits_core_object(self):
        assert issubclass(CaseReference, CoreObject)

    def test_type_literal(self):
        assert _ref().type_ == "CaseReference"

    @pytest.mark.spec("CM-05-004")
    def test_id_auto_generated_as_urn(self):
        assert _ref().id_.startswith("urn:uuid:")

    def test_registered_in_core_vocabulary(self):
        assert CORE_VOCABULARY["CaseReference"] is CaseReference

    def test_name_optional(self):
        assert _ref().name is None
        named = make(CaseReference, url={"href": _HREF}, name="Advisory")
        assert named.name == "Advisory"


class TestUrlIsALink:
    """``url`` holds an ``as:Link`` with href, name, mediaType and rel."""

    @pytest.mark.spec("CM-05-005")
    def test_url_required(self):
        with pytest.raises(ValidationError) as exc_info:
            make(CaseReference)  # pyright: ignore[reportCallIssue]
        assert _errors(exc_info.value) == [(("url",), "missing")]

    @pytest.mark.spec("CM-05-005")
    def test_href_required(self):
        with pytest.raises(ValidationError) as exc_info:
            make(CaseReference, url={"name": "No target"})
        assert _errors(exc_info.value) == [(("url", "href"), "missing")]

    def test_href_must_be_non_empty(self):
        with pytest.raises(ValidationError) as exc_info:
            make(CaseReference, url={"href": ""})
        assert _errors(exc_info.value) == [(("url", "href"), "value_error")]

    def test_bare_string_url_refused(self):
        with pytest.raises(ValidationError) as exc_info:
            make(CaseReference, url=_HREF)
        assert _errors(exc_info.value) == [(("url",), "model_type")]

    @pytest.mark.spec("CM-05-004")
    def test_link_holds_its_fields(self):
        ref = _ref(
            name="Vendor bulletin", media_type="text/html", rel=[_PATCH]
        )
        assert isinstance(ref.url, CaseReferenceLink)
        assert ref.url.type_ == "Link"
        assert ref.url.href == _HREF
        assert ref.url.name == "Vendor bulletin"
        assert ref.url.media_type == "text/html"
        assert ref.url.rel == [_PATCH]

    @pytest.mark.spec("CM-05-004")
    def test_link_has_no_id(self):
        with pytest.raises(ValidationError) as exc_info:
            CaseReferenceLink.model_validate(
                {"href": _HREF, "id": "urn:test:link:1"}
            )
        assert _errors(exc_info.value) == [(("id",), "extra_forbidden")]

    def test_link_serializes_in_wire_spelling(self):
        dumped = _ref(media_type="text/html", rel=[_PATCH]).model_dump(
            by_alias=True, mode="json"
        )
        assert dumped["url"] == {
            "type": "Link",
            "href": _HREF,
            "name": None,
            "mediaType": "text/html",
            "rel": [_PATCH],
        }

    def test_link_refuses_other_keys(self):
        with pytest.raises(ValidationError) as exc_info:
            make(CaseReference, url={"href": _HREF, "width": 3})
        assert _errors(exc_info.value) == [
            (("url", "width"), "extra_forbidden")
        ]

    def test_round_trip_through_json(self):
        ref = _ref(name="Advisory", rel=[_PATCH, "related"])
        again = CaseReference.model_validate_json(
            ref.model_dump_json(by_alias=True)
        )
        assert again == ref


class _ParsedModel(BaseModel):
    """Stands in for a model the parse edge built (the wire ``as_Link``)."""

    model_config = ConfigDict(populate_by_name=True)

    type_: str = Field(validation_alias="type", serialization_alias="type")
    href: str
    media_type: str | None = Field(default=None, alias="mediaType")
    width: int | None = None


class TestReadingAParsedModel:
    """A Link the parser already built is read through its given fields."""

    def test_given_fields_are_read(self):
        parsed = _ParsedModel(type_="Link", href=_HREF, mediaType="text/html")
        link = CaseReferenceLink.model_validate(parsed)
        assert link.href == _HREF
        assert link.media_type == "text/html"

    def test_a_refusal_names_the_wire_field(self):
        parsed = _ParsedModel(type_="Note", href=_HREF)
        with pytest.raises(ValidationError) as exc_info:
            CaseReferenceLink.model_validate(parsed)
        assert [error["loc"] for error in exc_info.value.errors()] == [
            ("type",)
        ]

    def test_a_field_the_link_does_not_hold_is_refused(self):
        parsed = _ParsedModel(type_="Link", href=_HREF, width=3)
        with pytest.raises(ValidationError, match=r"given \['width'\]"):
            CaseReferenceLink.model_validate(parsed)

    def test_an_extra_key_on_a_parsed_model_is_refused(self):
        class _OpenModel(_ParsedModel):
            model_config = ConfigDict(populate_by_name=True, extra="allow")

        parsed = _OpenModel(type_="Link", href=_HREF, foo="bar")  # pyright: ignore[reportCallIssue]
        with pytest.raises(ValidationError, match=r"given \['foo'\]"):
            CaseReferenceLink.model_validate(parsed)


class TestRelVocabulary:
    """CVE reference tags are ``rel`` values written per RFC 8288."""

    @pytest.mark.spec("CM-05-012")
    def test_rel_empty_by_default(self):
        assert _ref().url.rel == []

    @pytest.mark.spec("CM-05-012")
    def test_every_cve_tag_has_a_rel(self):
        assert set(CVE_REFERENCE_TAG_RELS) == CVE_REFERENCE_TAGS
        assert (
            set(CVE_REFERENCE_TAG_RELS.values())
            == CASE_REFERENCE_REL_VOCABULARY
        )

    @pytest.mark.spec("CM-05-012")
    def test_unregistered_tags_are_uris_in_the_vultron_namespace(self):
        for tag, rel in CVE_REFERENCE_TAG_RELS.items():
            if tag == "related":
                continue
            assert rel == f"{CASE_REFERENCE_REL_NAMESPACE}{tag}"

    @pytest.mark.spec("CM-05-012")
    def test_iana_registered_related_stays_a_bare_name(self):
        assert CVE_REFERENCE_TAG_RELS["related"] == "related"

    @pytest.mark.spec("CM-05-012")
    def test_every_vocabulary_rel_is_accepted(self):
        for rel in CASE_REFERENCE_REL_VOCABULARY:
            assert _ref(rel=[rel]).url.rel == [rel]

    @pytest.mark.spec("CM-05-012")
    def test_several_rels_keep_their_order(self):
        assert _ref(rel=[_VENDOR_ADVISORY, _PATCH]).url.rel == [
            _VENDOR_ADVISORY,
            _PATCH,
        ]

    @pytest.mark.spec("CM-05-012")
    def test_a_single_rel_string_reads_as_a_list(self):
        assert _ref(rel=_PATCH).url.rel == [_PATCH]

    @pytest.mark.spec("CM-05-012")
    def test_a_bare_cve_tag_is_refused(self):
        with pytest.raises(ValidationError, match="Invalid rel"):
            _ref(rel=["patch"])

    @pytest.mark.spec("CM-05-012")
    def test_every_invalid_rel_is_named(self):
        with pytest.raises(ValidationError) as exc_info:
            _ref(rel=[_PATCH, "bogus-1", "bogus-2"])
        message = str(exc_info.value)
        assert "bogus-1" in message and "bogus-2" in message

    @pytest.mark.spec("CM-05-012")
    def test_empty_rel_string_refused(self):
        with pytest.raises(ValidationError) as exc_info:
            _ref(rel=[""])
        assert _errors(exc_info.value) == [(("url", "rel", 0), "value_error")]

    @pytest.mark.spec("CM-05-012")
    def test_rel_checked_on_assignment(self):
        ref = _ref()
        with pytest.raises(ValidationError, match="Invalid rel"):
            ref.url.rel = ["bogus"]


class TestTagsFieldIsGone:
    """The Vultron ``tags`` field is removed with no alias (ADR-0175)."""

    def test_tags_key_refused(self):
        with pytest.raises(ValidationError) as exc_info:
            CaseReference.model_validate(
                with_times(
                    CaseReference, {"url": {"href": _HREF}, "tags": ["patch"]}
                )
            )
        assert _errors(exc_info.value) == [(("tags",), "extra_forbidden")]


class TestWireAlias:
    """as_CaseReference IS CaseReference (ARCH-25-003, ADR-0099)."""

    def test_wire_alias_is_core_class(self):
        from vultron.wire.as2.vocab.objects.case_reference import (
            as_CaseReference,
        )

        assert as_CaseReference is CaseReference
