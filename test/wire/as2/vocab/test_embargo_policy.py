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

"""
Tests for EmbargoPolicy Pydantic model (EP-01-001 to EP-01-004,
DUR-01-001, DUR-04-001, DUR-04-002, DUR-05-001, DUR-05-002).
"""

import json
import unittest
from datetime import timedelta
from typing import Any, cast

import pytest
from pydantic import ValidationError

import vultron.wire.as2.vocab.objects.embargo_policy as ep_module
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.enums import VultronObjectType as VO_type

ACTOR_ID = "https://example.org/actors/vendor"
INBOX = "https://example.org/actors/vendor/inbox"

# Canonical ISO 8601 durations used across tests
_P90D = timedelta(days=90)
_P45D = timedelta(days=45)
_P180D = timedelta(days=180)
_P60D = timedelta(days=60)


class TestEmbargoPolicyCreation(unittest.TestCase):
    """Test EmbargoPolicy model creation — EP-01-001 through EP-01-003."""

    def setUp(self):
        self.policy = cast(Any, ep_module.EmbargoPolicy)(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration="P90D",
            minimum_duration="P45D",
            maximum_duration="P180D",
            notes="Prefer 90 days; shorter for critical.",
        )

    def test_creation_with_all_fields(self):
        p = self.policy
        self.assertEqual(ACTOR_ID, p.actor_id)
        self.assertEqual(INBOX, p.inbox)
        self.assertEqual(_P90D, p.preferred_duration)
        self.assertEqual(_P45D, p.minimum_duration)
        self.assertEqual(_P180D, p.maximum_duration)
        self.assertEqual("Prefer 90 days; shorter for critical.", p.notes)
        self.assertEqual(VO_type.EMBARGO_POLICY, p.type_)

    def test_creation_accepts_timedelta_directly(self):
        p = ep_module.EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration=_P60D,
        )
        self.assertEqual(_P60D, p.preferred_duration)

    def test_creation_with_required_fields_only(self):
        p = cast(Any, ep_module.EmbargoPolicy)(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration="P60D",
        )
        self.assertEqual(_P60D, p.preferred_duration)
        self.assertIsNone(p.minimum_duration)
        self.assertIsNone(p.maximum_duration)
        self.assertIsNone(p.notes)

    def test_actor_id_required(self):
        with pytest.raises(ValidationError):
            cast(Any, ep_module.EmbargoPolicy)(
                inbox=INBOX, preferred_duration="P90D"
            )

    def test_inbox_required(self):
        with pytest.raises(ValidationError):
            cast(Any, ep_module.EmbargoPolicy)(
                actor_id=ACTOR_ID, preferred_duration="P90D"
            )

    def test_preferred_duration_required(self):
        with pytest.raises(ValidationError):
            cast(Any, ep_module.EmbargoPolicy)(actor_id=ACTOR_ID, inbox=INBOX)

    def test_as_type_is_embargo_policy(self):
        self.assertEqual(VO_type.EMBARGO_POLICY, self.policy.type_)

    def test_has_auto_generated_id(self):
        self.assertIsNotNone(self.policy.id_)
        self.assertNotEqual("", self.policy.id_)


class TestEmbargoPolicyValidation(unittest.TestCase):
    """Test EmbargoPolicy field validators — DUR-04-001, DUR-04-002."""

    def _make(
        self,
        *,
        actor_id: str = ACTOR_ID,
        inbox: str = INBOX,
        preferred_duration: str | timedelta = "P90D",
        minimum_duration: str | timedelta | None = None,
        maximum_duration: str | timedelta | None = None,
        notes: str | None = None,
    ) -> ep_module.EmbargoPolicy:
        # cast(Any, ...) allows passing str inputs that Pydantic's field_validator
        # converts to timedelta at runtime (mypy sees the declared timedelta type).
        return cast(
            ep_module.EmbargoPolicy,
            cast(Any, ep_module.EmbargoPolicy)(
                actor_id=actor_id,
                inbox=inbox,
                preferred_duration=preferred_duration,
                minimum_duration=minimum_duration,
                maximum_duration=maximum_duration,
                notes=notes,
            ),
        )

    def test_actor_id_empty_string_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            self._make(actor_id="")
        assert "must be a non-empty string" in str(exc_info.value)

    def test_actor_id_whitespace_only_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            self._make(actor_id="   ")
        assert "must be a non-empty string" in str(exc_info.value)

    def test_inbox_empty_string_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            self._make(inbox="")
        assert "must be a non-empty string" in str(exc_info.value)

    def test_inbox_whitespace_only_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            self._make(inbox="   ")
        assert "must be a non-empty string" in str(exc_info.value)

    def test_malformed_duration_rejected(self):
        """DUR-04-002: Malformed ISO 8601 duration strings must be rejected."""
        with pytest.raises(ValidationError):
            self._make(preferred_duration="not-a-duration")

    def test_empty_duration_rejected(self):
        """DUR-04-003: Empty duration strings must be rejected."""
        with pytest.raises(ValidationError):
            self._make(preferred_duration="P")

    def test_year_unit_rejected(self):
        """DUR-04-001: Durations containing Y must be rejected."""
        with pytest.raises(ValidationError):
            self._make(preferred_duration="P1Y")

    def test_month_unit_rejected(self):
        """DUR-04-001: Durations containing date-part M must be rejected."""
        with pytest.raises(ValidationError):
            self._make(preferred_duration="P3M")

    def test_week_unit_rejected(self):
        """DUR-04-001: Durations containing W must be rejected."""
        with pytest.raises(ValidationError):
            self._make(preferred_duration="P2W")

    def test_valid_hour_duration_accepted(self):
        """Hours are an allowed unit per DUR-02-001."""
        p = self._make(preferred_duration="PT24H")
        self.assertEqual(timedelta(hours=24), p.preferred_duration)

    def test_valid_mixed_duration_accepted(self):
        """Mixed day+hour durations are allowed per DUR-02-001."""
        p = self._make(preferred_duration="P1DT12H")
        self.assertEqual(timedelta(days=1, hours=12), p.preferred_duration)

    def test_minimum_duration_none_accepted(self):
        p = self._make(minimum_duration=None)
        self.assertIsNone(p.minimum_duration)

    def test_maximum_duration_none_accepted(self):
        p = self._make(maximum_duration=None)
        self.assertIsNone(p.maximum_duration)

    def test_minimum_duration_invalid_rejected(self):
        with pytest.raises(ValidationError):
            self._make(minimum_duration="P1Y")

    def test_maximum_duration_invalid_rejected(self):
        with pytest.raises(ValidationError):
            self._make(maximum_duration="not-valid")

    def test_notes_none_accepted(self):
        p = self._make(notes=None)
        self.assertIsNone(p.notes)

    def test_notes_empty_string_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            self._make(notes="")
        assert "must be a non-empty string" in str(exc_info.value)

    def test_notes_whitespace_only_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            self._make(notes="   ")
        assert "must be a non-empty string" in str(exc_info.value)


class TestEmbargoPolicySerialization(unittest.TestCase):
    """Test EmbargoPolicy serialization — EP-01-004, DUR-05-001, DUR-05-002."""

    def setUp(self):
        self.policy = cast(Any, ep_module.EmbargoPolicy)(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration="P90D",
            minimum_duration="P45D",
            maximum_duration="P180D",
            notes="Prefer 90 days.",
        )

    def test_internal_representation_is_timedelta(self):
        """DUR-05-001: Duration fields use timedelta internally."""
        self.assertIsInstance(self.policy.preferred_duration, timedelta)
        self.assertIsInstance(self.policy.minimum_duration, timedelta)
        self.assertIsInstance(self.policy.maximum_duration, timedelta)

    def test_json_serialization_uses_iso8601_strings(self):
        """DUR-05-002: JSON wire layer serializes durations as ISO 8601 strings."""
        data = json.loads(self.policy.to_json())
        # JSON uses camelCase (alias_generator=to_camel)
        self.assertIsInstance(data["preferredDuration"], str)
        self.assertIsInstance(data["minimumDuration"], str)
        self.assertIsInstance(data["maximumDuration"], str)
        # Verify values are correct ISO 8601 strings
        self.assertEqual("P90D", data["preferredDuration"])
        self.assertEqual("P45D", data["minimumDuration"])
        self.assertEqual("P180D", data["maximumDuration"])

    def test_json_does_not_serialize_as_number(self):
        """DUR-05-002: Duration MUST NOT be serialized as a plain number."""
        data = json.loads(self.policy.to_json())
        # JSON uses camelCase (alias_generator=to_camel)
        self.assertNotIsInstance(data["preferredDuration"], (int, float))

    def test_round_trip_via_object_to_record(self):
        record = object_to_record(self.policy)
        data = record.data_
        self.assertIn("actor_id", data)
        self.assertEqual(ACTOR_ID, data["actor_id"])
        self.assertIn("inbox", data)
        self.assertEqual(INBOX, data["inbox"])
        self.assertIn("preferred_duration", data)
        self.assertEqual("P90D", data["preferred_duration"])
        self.assertIn("minimum_duration", data)
        self.assertEqual("P45D", data["minimum_duration"])
        self.assertIn("maximum_duration", data)
        self.assertEqual("P180D", data["maximum_duration"])
        self.assertIn("notes", data)

    def test_datalayer_round_trip(self):
        """DUR-05-001, DUR-05-002: Round-trip through DataLayer preserves durations."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        dl.create(self.policy)
        stored = dl.read(self.policy.id_)
        self.assertIsNotNone(stored)
        stored = cast(ep_module.EmbargoPolicy, stored)
        self.assertEqual(self.policy.id_, stored.id_)
        self.assertEqual(ACTOR_ID, stored.actor_id)
        self.assertEqual(INBOX, stored.inbox)
        self.assertEqual(_P90D, stored.preferred_duration)
        self.assertEqual(_P45D, stored.minimum_duration)
        self.assertEqual(_P180D, stored.maximum_duration)

    def test_roundtrip_timedelta_to_iso8601_and_back(self):
        """DUR-05-001, DUR-05-002: timedelta → 'P90D' → timedelta round-trips correctly."""
        p = ep_module.EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration=timedelta(days=90),
        )
        json_str = p.to_json()
        data = json.loads(json_str)
        # JSON uses camelCase (alias_generator=to_camel)
        self.assertEqual("P90D", data["preferredDuration"])
        # Reconstruct from JSON
        p2 = ep_module.EmbargoPolicy.model_validate_json(json_str)
        self.assertEqual(timedelta(days=90), p2.preferred_duration)

    def test_json_serialization(self):
        j = self.policy.to_json()
        self.assertIn("EmbargoPolicy", j)
        self.assertIn(ACTOR_ID, j)
        self.assertIn(INBOX, j)

    def test_type_distinctness(self):
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        case = VulnerabilityCase()
        self.assertNotEqual(self.policy.type_, case.type_)


if __name__ == "__main__":
    unittest.main()
