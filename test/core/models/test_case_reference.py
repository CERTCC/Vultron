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

from vultron.core.models.base import CoreObject
from vultron.core.models.case_reference import (
    CASE_REFERENCE_TAG_VOCABULARY,
    CaseReference,
)
from vultron.core.models.registry import CORE_VOCABULARY

_URL = "https://example.org/advisory"


class TestCaseReferenceBasics:
    """CaseReference is a CoreObject with required url field."""

    def test_inherits_core_object(self):
        assert issubclass(CaseReference, CoreObject)

    def test_type_literal(self):
        ref = CaseReference(url=_URL)
        assert ref.type_ == "CaseReference"

    def test_url_required(self):
        with pytest.raises(ValidationError):
            CaseReference()

    def test_url_must_be_non_empty(self):
        with pytest.raises(ValidationError):
            CaseReference(url="")

    def test_name_optional(self):
        ref = CaseReference(url=_URL, name="Advisory Title")
        assert ref.name == "Advisory Title"

    def test_name_none_by_default(self):
        ref = CaseReference(url=_URL)
        assert ref.name is None

    def test_tags_optional(self):
        ref = CaseReference(url=_URL, tags=["patch"])
        assert ref.tags == ["patch"]

    def test_tags_none_by_default(self):
        ref = CaseReference(url=_URL)
        assert ref.tags is None

    def test_id_auto_generated_as_urn(self):
        ref = CaseReference(url=_URL)
        assert ref.id_.startswith("urn:uuid:")


class TestCaseReferenceTagValidation:
    """tags field validates against CASE_REFERENCE_TAG_VOCABULARY."""

    def test_valid_single_tag(self):
        ref = CaseReference(url=_URL, tags=["patch"])
        assert ref.tags == ["patch"]

    def test_valid_multiple_tags(self):
        ref = CaseReference(url=_URL, tags=["patch", "vendor-advisory"])
        assert ref.tags is not None
        assert len(ref.tags) == 2

    def test_invalid_tag_raises(self):
        with pytest.raises(ValidationError):
            CaseReference(url=_URL, tags=["invalid-tag-xyz"])

    def test_empty_tags_list_raises(self):
        with pytest.raises(ValidationError):
            CaseReference(url=_URL, tags=[])

    def test_empty_string_tag_raises(self):
        with pytest.raises(ValidationError):
            CaseReference(url=_URL, tags=[""])

    def test_all_vocabulary_tags_are_valid(self):
        for tag in CASE_REFERENCE_TAG_VOCABULARY:
            ref = CaseReference(url=_URL, tags=[tag])
            assert ref.tags == [tag]


class TestCaseReferenceRegistration:
    """CaseReference registers in CORE_VOCABULARY — ADR-0017."""

    def test_registered_in_core_vocabulary(self):
        assert "CaseReference" in CORE_VOCABULARY
        assert CORE_VOCABULARY["CaseReference"] is CaseReference


class TestCaseReferenceWireRoundTrip:
    """Wire CaseReference.from_core / .to_core must preserve identity."""

    def test_from_core_preserves_url(self):
        from vultron.wire.as2.vocab.objects.case_reference import (
            as_CaseReference as WireCaseReference,
        )

        core_ref = CaseReference(
            id_="urn:uuid:ref-test",
            url=_URL,
            name="Example Advisory",
            tags=["patch"],
        )
        wire_ref = WireCaseReference.from_core(core_ref)
        assert wire_ref.url == _URL
        assert wire_ref.name == "Example Advisory"

    def test_to_core_produces_core_reference(self):
        from vultron.wire.as2.vocab.objects.case_reference import (
            as_CaseReference as WireCaseReference,
        )

        wire_ref = WireCaseReference(url=_URL, tags=["vendor-advisory"])
        core_ref = wire_ref.to_core()
        assert isinstance(core_ref, CaseReference)
        assert core_ref.url == _URL
        assert core_ref.tags == ["vendor-advisory"]

    def test_round_trip_preserves_id(self):
        from vultron.wire.as2.vocab.objects.case_reference import (
            as_CaseReference as WireCaseReference,
        )

        core_ref = CaseReference(
            id_="urn:uuid:ref-roundtrip",
            url=_URL,
        )
        wire_ref = WireCaseReference.from_core(core_ref)
        restored = wire_ref.to_core()
        assert restored.id_ == "urn:uuid:ref-roundtrip"
        assert isinstance(restored, CaseReference)
