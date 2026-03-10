#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

import unittest

import pytest
from pydantic import ValidationError

import vultron.as_vocab.objects.case_reference as cr
from vultron.enums import VultronObjectType as VO_type


class TestCaseReference(unittest.TestCase):
    """Test CaseReference Pydantic model."""

    def setUp(self):
        """Set up test fixtures."""
        self.reference = cr.CaseReference(
            url="https://example.org/advisory/",
            name="Example Security Advisory",
            tags=["vendor-advisory", "patch"],
            attributed_to=["https://example.org/actor/alice"],
        )

    def test_case_reference_creation_with_all_fields(self):
        """Test CaseReference creation with all fields."""
        ref = self.reference
        self.assertEqual("https://example.org/advisory/", ref.url)
        self.assertEqual("Example Security Advisory", ref.name)
        self.assertIn("vendor-advisory", ref.tags)
        self.assertIn("patch", ref.tags)
        self.assertEqual(VO_type.CASE_REFERENCE, ref.as_type)

    def test_case_reference_url_required(self):
        """Test that url field is required."""
        with pytest.raises(ValidationError):
            cr.CaseReference()

    def test_case_reference_url_not_empty(self):
        """Test that url must be non-empty string."""
        with pytest.raises(ValidationError) as exc_info:
            cr.CaseReference(url="")

        assert "url must be a non-empty string" in str(exc_info.value)

    def test_case_reference_url_only(self):
        """Test CaseReference with only url field."""
        ref = cr.CaseReference(url="https://example.org/")
        self.assertEqual("https://example.org/", ref.url)
        self.assertIsNone(ref.name)
        self.assertIsNone(ref.tags)

    def test_case_reference_name_optional(self):
        """Test that name field is optional."""
        ref = cr.CaseReference(url="https://example.org/")
        self.assertIsNone(ref.name)

    def test_case_reference_name_not_empty(self):
        """Test that name must be non-empty string if provided."""
        with pytest.raises(ValidationError) as exc_info:
            cr.CaseReference(url="https://example.org/", name="")

        assert "name must be either None or a non-empty string" in str(
            exc_info.value
        )

    def test_case_reference_name_with_url(self):
        """Test CaseReference with name."""
        ref = cr.CaseReference(
            url="https://example.org/", name="Advisory Title"
        )
        self.assertEqual("Advisory Title", ref.name)

    def test_case_reference_tags_optional(self):
        """Test that tags field is optional."""
        ref = cr.CaseReference(url="https://example.org/")
        self.assertIsNone(ref.tags)

    def test_case_reference_tags_single_tag(self):
        """Test CaseReference with single tag."""
        ref = cr.CaseReference(url="https://example.org/", tags=["patch"])
        self.assertEqual(["patch"], ref.tags)

    def test_case_reference_tags_multiple_tags(self):
        """Test CaseReference with multiple tags."""
        tags = ["vendor-advisory", "patch", "exploit"]
        ref = cr.CaseReference(url="https://example.org/", tags=tags)
        self.assertEqual(tags, ref.tags)

    def test_case_reference_tags_empty_list_rejected(self):
        """Test that empty tags list is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            cr.CaseReference(url="https://example.org/", tags=[])

        assert "tags must have at least one element" in str(exc_info.value)

    def test_case_reference_tags_not_empty_strings(self):
        """Test that tags cannot contain empty strings."""
        with pytest.raises(ValidationError) as exc_info:
            cr.CaseReference(url="https://example.org/", tags=["patch", ""])

        assert "All tags must be non-empty strings" in str(exc_info.value)

    def test_case_reference_invalid_tag_rejected(self):
        """Test that tags not in CASE_REFERENCE_TAG_VOCABULARY are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            cr.CaseReference(
                url="https://example.org/", tags=["not-a-real-tag"]
            )

        assert "Invalid tag" in str(exc_info.value)

    def test_case_reference_valid_cve_tags(self):
        """Test CaseReference with valid CVE JSON schema tags."""
        valid_tags = [
            "broken-link",
            "exploit",
            "government-resource",
            "patch",
            "vendor-advisory",
        ]
        for tag in valid_tags:
            ref = cr.CaseReference(url="https://example.org/", tags=[tag])
            self.assertEqual([tag], ref.tags)

    def test_case_reference_all_valid_cve_tags(self):
        """Test that all CVE schema tags are accepted."""
        all_tags = list(cr.CASE_REFERENCE_TAG_VOCABULARY)
        # Test each tag individually
        for tag in all_tags:
            ref = cr.CaseReference(url="https://example.org/", tags=[tag])
            self.assertIn(tag, ref.tags)

    def test_case_reference_round_trip(self):
        """Test serialization and deserialization round-trip."""
        ref = self.reference
        json_str = ref.to_json()
        deserialized = cr.CaseReference.model_validate_json(json_str)

        self.assertEqual(ref.url, deserialized.url)
        self.assertEqual(ref.name, deserialized.name)
        self.assertEqual(ref.tags, deserialized.tags)

    def test_case_reference_round_trip_minimal(self):
        """Test round-trip with minimal fields."""
        ref = cr.CaseReference(url="https://example.org/")
        json_str = ref.to_json()
        deserialized = cr.CaseReference.model_validate_json(json_str)

        self.assertEqual(ref.url, deserialized.url)
        self.assertIsNone(deserialized.name)
        self.assertIsNone(deserialized.tags)

    def test_case_reference_is_vultron_object_type(self):
        """Test that CaseReference has correct as_type."""
        ref = cr.CaseReference(url="https://example.org/")
        self.assertEqual(ref.as_type, VO_type.CASE_REFERENCE)

    def test_case_reference_separate_from_report(self):
        """Test that CaseReference is a distinct type."""
        from vultron.as_vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        ref = cr.CaseReference(url="https://example.org/")
        report = VulnerabilityReport(content="Test report")

        self.assertNotEqual(type(ref), type(report))
        self.assertNotEqual(ref.as_type, report.as_type)

    def test_case_reference_separate_from_vulnerability_record(self):
        """Test that CaseReference is distinct from VulnerabilityRecord."""
        from vultron.as_vocab.objects.vulnerability_record import (
            VulnerabilityRecord,
        )

        ref = cr.CaseReference(url="https://example.org/")
        record = VulnerabilityRecord(name="CVE-2024-1234")

        self.assertNotEqual(type(ref), type(record))
        self.assertNotEqual(ref.as_type, record.as_type)

    def test_case_reference_multiple_tags_preserved(self):
        """Test that multiple tags are preserved in order."""
        tags = ["vendor-advisory", "patch", "release-notes"]
        ref = cr.CaseReference(url="https://example.org/", tags=tags)
        self.assertEqual(tags, ref.tags)


if __name__ == "__main__":
    unittest.main()
