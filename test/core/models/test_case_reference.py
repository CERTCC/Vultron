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
from pydantic import ValidationError

from test.support.objects import make
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
        with pytest.raises(ValidationError):
            make(CaseReference)  # pyright: ignore[reportCallIssue]

    @pytest.mark.spec("CM-05-005")
    def test_href_required(self):
        with pytest.raises(ValidationError):
            make(CaseReference, url={"name": "No target"})

    def test_href_must_be_non_empty(self):
        with pytest.raises(ValidationError):
            make(CaseReference, url={"href": ""})

    def test_bare_string_url_refused(self):
        with pytest.raises(ValidationError):
            make(CaseReference, url=_HREF)

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
        assert "id_" not in CaseReferenceLink.model_fields

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
        with pytest.raises(ValidationError):
            make(CaseReference, url={"href": _HREF, "width": 3})

    def test_round_trip_through_json(self):
        ref = _ref(name="Advisory", rel=[_PATCH, "related"])
        again = CaseReference.model_validate_json(
            ref.model_dump_json(by_alias=True)
        )
        assert again == ref


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
        with pytest.raises(ValidationError):
            _ref(rel=[""])

    @pytest.mark.spec("CM-05-012")
    def test_rel_checked_on_assignment(self):
        ref = _ref()
        with pytest.raises(ValidationError):
            ref.url.rel = ["bogus"]


class TestTagsFieldIsGone:
    """The Vultron ``tags`` field is removed with no alias (ADR-0175)."""

    def test_no_tags_field(self):
        assert "tags" not in CaseReference.model_fields

    def test_tags_key_refused(self):
        with pytest.raises(ValidationError):
            CaseReference.model_validate(
                {"url": {"href": _HREF}, "tags": ["patch"]}
            )


class TestWireAlias:
    """as_CaseReference IS CaseReference (ARCH-25-003, ADR-0099)."""

    def test_wire_alias_is_core_class(self):
        from vultron.wire.as2.vocab.objects.case_reference import (
            as_CaseReference,
        )

        assert as_CaseReference is CaseReference
