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
Tests for EmbargoPolicy Pydantic model (EP-01-001 to EP-01-004).
"""

import unittest
from typing import Any, cast

import pytest
from pydantic import ValidationError

import vultron.wire.as2.vocab.objects.embargo_policy as ep_module
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.models.enums import VultronObjectType as VO_type

ACTOR_ID = "https://example.org/actors/vendor"
INBOX = "https://example.org/actors/vendor/inbox"


class TestEmbargoPolicyCreation(unittest.TestCase):
    """Test EmbargoPolicy model creation — EP-01-001 through EP-01-003."""

    def setUp(self):
        self.policy = ep_module.EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration_days=90,
            minimum_duration_days=45,
            maximum_duration_days=180,
            notes="Prefer 90 days; shorter for critical.",
        )

    def test_creation_with_all_fields(self):
        p = self.policy
        self.assertEqual(ACTOR_ID, p.actor_id)
        self.assertEqual(INBOX, p.inbox)
        self.assertEqual(90, p.preferred_duration_days)
        self.assertEqual(45, p.minimum_duration_days)
        self.assertEqual(180, p.maximum_duration_days)
        self.assertEqual("Prefer 90 days; shorter for critical.", p.notes)
        self.assertEqual(VO_type.EMBARGO_POLICY, p.type_)

    def test_creation_with_required_fields_only(self):
        p = ep_module.EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration_days=60,
        )
        self.assertEqual(60, p.preferred_duration_days)
        self.assertIsNone(p.minimum_duration_days)
        self.assertIsNone(p.maximum_duration_days)
        self.assertIsNone(p.notes)

    def test_actor_id_required(self):
        with pytest.raises(ValidationError):
            cast(Any, ep_module.EmbargoPolicy)(
                inbox=INBOX, preferred_duration_days=90
            )

    def test_inbox_required(self):
        with pytest.raises(ValidationError):
            cast(Any, ep_module.EmbargoPolicy)(
                actor_id=ACTOR_ID, preferred_duration_days=90
            )

    def test_preferred_duration_days_required(self):
        with pytest.raises(ValidationError):
            cast(Any, ep_module.EmbargoPolicy)(actor_id=ACTOR_ID, inbox=INBOX)

    def test_as_type_is_embargo_policy(self):
        self.assertEqual(VO_type.EMBARGO_POLICY, self.policy.type_)

    def test_has_auto_generated_id(self):
        self.assertIsNotNone(self.policy.id_)
        self.assertNotEqual("", self.policy.id_)


class TestEmbargoPolicyValidation(unittest.TestCase):
    """Test EmbargoPolicy field validators."""

    def _make(
        self,
        *,
        actor_id: str = ACTOR_ID,
        inbox: str = INBOX,
        preferred_duration_days: int = 90,
        minimum_duration_days: int | None = None,
        maximum_duration_days: int | None = None,
        notes: str | None = None,
    ) -> ep_module.EmbargoPolicy:
        return ep_module.EmbargoPolicy(
            actor_id=actor_id,
            inbox=inbox,
            preferred_duration_days=preferred_duration_days,
            minimum_duration_days=minimum_duration_days,
            maximum_duration_days=maximum_duration_days,
            notes=notes,
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

    def test_preferred_duration_days_negative_rejected(self):
        with pytest.raises(ValidationError):
            self._make(preferred_duration_days=-1)

    def test_preferred_duration_days_zero_accepted(self):
        p = self._make(preferred_duration_days=0)
        self.assertEqual(0, p.preferred_duration_days)

    def test_minimum_duration_days_negative_rejected(self):
        with pytest.raises(ValidationError):
            self._make(minimum_duration_days=-1)

    def test_maximum_duration_days_negative_rejected(self):
        with pytest.raises(ValidationError):
            self._make(maximum_duration_days=-1)

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

    def test_minimum_duration_days_none_accepted(self):
        p = self._make(minimum_duration_days=None)
        self.assertIsNone(p.minimum_duration_days)

    def test_maximum_duration_days_none_accepted(self):
        p = self._make(maximum_duration_days=None)
        self.assertIsNone(p.maximum_duration_days)


class TestEmbargoPolicySerialization(unittest.TestCase):
    """Test EmbargoPolicy serialization — EP-01-004."""

    def setUp(self):
        self.policy = ep_module.EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration_days=90,
            minimum_duration_days=45,
            maximum_duration_days=180,
            notes="Prefer 90 days.",
        )

    def test_round_trip_via_object_to_record(self):
        record = object_to_record(self.policy)
        data = record.data_
        self.assertIn("actor_id", data)
        self.assertEqual(ACTOR_ID, data["actor_id"])
        self.assertIn("inbox", data)
        self.assertEqual(INBOX, data["inbox"])
        self.assertIn("preferred_duration_days", data)
        self.assertEqual(90, data["preferred_duration_days"])
        self.assertIn("minimum_duration_days", data)
        self.assertEqual(45, data["minimum_duration_days"])
        self.assertIn("maximum_duration_days", data)
        self.assertEqual(180, data["maximum_duration_days"])
        self.assertIn("notes", data)

    def test_datalayer_round_trip(self):
        dl = TinyDbDataLayer(db_path=None)
        dl.create(self.policy)
        stored = dl.read(self.policy.id_)
        self.assertIsNotNone(stored)
        stored = cast(ep_module.EmbargoPolicy, stored)
        self.assertEqual(self.policy.id_, stored.id_)
        self.assertEqual(ACTOR_ID, stored.actor_id)
        self.assertEqual(INBOX, stored.inbox)
        self.assertEqual(90, stored.preferred_duration_days)
        self.assertEqual(45, stored.minimum_duration_days)
        self.assertEqual(180, stored.maximum_duration_days)

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
