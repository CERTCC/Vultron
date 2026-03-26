"""
Tests for CaseEvent model and VulnerabilityCase.events field (SC-PRE-1).

References: specs/case-management.md CM-02-009, CM-10-002.
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

import unittest
from datetime import datetime, timezone
from typing import cast

import pytest
from pydantic import ValidationError

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.wire.as2.vocab.objects.case_event import CaseEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

OBJ_ID = "https://example.org/reports/abc123"
EVENT_TYPE = "embargo_accepted"


class TestCaseEventCreation(unittest.TestCase):
    """Test CaseEvent model creation."""

    def test_creation_with_all_fields(self):
        ts = datetime.now(tz=timezone.utc)
        evt = CaseEvent(
            object_id=OBJ_ID, event_type=EVENT_TYPE, received_at=ts
        )
        self.assertEqual(OBJ_ID, evt.object_id)
        self.assertEqual(EVENT_TYPE, evt.event_type)
        self.assertEqual(ts, evt.received_at)

    def test_received_at_defaults_to_utc_now(self):
        before = datetime.now(tz=timezone.utc).replace(microsecond=0)
        evt = CaseEvent(object_id=OBJ_ID, event_type=EVENT_TYPE)
        after = datetime.now(tz=timezone.utc)
        self.assertIsNotNone(evt.received_at)
        self.assertGreaterEqual(evt.received_at, before)
        self.assertLessEqual(evt.received_at, after)

    def test_received_at_is_timezone_aware(self):
        evt = CaseEvent(object_id=OBJ_ID, event_type=EVENT_TYPE)
        self.assertIsNotNone(evt.received_at.tzinfo)

    def test_object_id_required(self):
        with pytest.raises(ValidationError):
            CaseEvent(object_id="", event_type=EVENT_TYPE)

    def test_event_type_required(self):
        with pytest.raises(ValidationError):
            CaseEvent(object_id=OBJ_ID, event_type="")

    def test_object_id_empty_string_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            CaseEvent(object_id="", event_type=EVENT_TYPE)
        assert "must be a non-empty string" in str(exc_info.value)

    def test_object_id_whitespace_only_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            CaseEvent(object_id="   ", event_type=EVENT_TYPE)
        assert "must be a non-empty string" in str(exc_info.value)

    def test_event_type_empty_string_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            CaseEvent(object_id=OBJ_ID, event_type="")
        assert "must be a non-empty string" in str(exc_info.value)

    def test_event_type_whitespace_only_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            CaseEvent(object_id=OBJ_ID, event_type="   ")
        assert "must be a non-empty string" in str(exc_info.value)


class TestCaseEventSerialization(unittest.TestCase):
    """Test CaseEvent JSON serialization round-trips."""

    def setUp(self):
        self.ts = datetime(2026, 3, 6, 20, 0, 0, tzinfo=timezone.utc)
        self.evt = CaseEvent(
            object_id=OBJ_ID, event_type=EVENT_TYPE, received_at=self.ts
        )

    def test_received_at_serializes_to_iso8601_utc(self):
        data = self.evt.model_dump(mode="json")
        self.assertIn("received_at", data)
        ts_str = data["received_at"]
        self.assertIsInstance(ts_str, str)
        parsed = datetime.fromisoformat(ts_str)
        self.assertIsNotNone(parsed.tzinfo)

    def test_round_trip_via_model_dump_and_validate(self):
        data = self.evt.model_dump(mode="json")
        restored = CaseEvent.model_validate(data)
        self.assertEqual(self.evt.object_id, restored.object_id)
        self.assertEqual(self.evt.event_type, restored.event_type)
        self.assertEqual(self.evt.received_at, restored.received_at)

    def test_received_at_iso8601_string_parses_correctly(self):
        ts_str = "2026-03-06T20:00:00+00:00"
        evt = CaseEvent(
            object_id=OBJ_ID,
            event_type=EVENT_TYPE,
            received_at=ts_str,  # type: ignore[arg-type]
        )
        self.assertEqual(
            datetime(2026, 3, 6, 20, 0, 0, tzinfo=timezone.utc),
            evt.received_at,
        )

    def test_received_at_z_suffix_parses_correctly(self):
        ts_str = "2026-03-06T20:00:00Z"
        evt = CaseEvent(
            object_id=OBJ_ID,
            event_type=EVENT_TYPE,
            received_at=ts_str,  # type: ignore[arg-type]
        )
        self.assertEqual(
            datetime(2026, 3, 6, 20, 0, 0, tzinfo=timezone.utc),
            evt.received_at,
        )


class TestVulnerabilityCaseEventsField(unittest.TestCase):
    """Test VulnerabilityCase.events field (SC-PRE-1)."""

    def test_events_defaults_to_empty_list(self):
        case = VulnerabilityCase()
        self.assertEqual([], case.events)

    def test_record_event_appends_to_events(self):
        case = VulnerabilityCase()
        evt = case.record_event(OBJ_ID, EVENT_TYPE)
        self.assertEqual(1, len(case.events))
        self.assertIs(evt, case.events[0])

    def test_record_event_returns_case_event_with_correct_fields(self):
        case = VulnerabilityCase()
        evt = case.record_event(OBJ_ID, EVENT_TYPE)
        self.assertEqual(OBJ_ID, evt.object_id)
        self.assertEqual(EVENT_TYPE, evt.event_type)
        self.assertIsNotNone(evt.received_at)
        self.assertIsNotNone(evt.received_at.tzinfo)

    def test_record_event_is_append_only(self):
        case = VulnerabilityCase()
        case.record_event(OBJ_ID, "participant_joined")
        case.record_event(OBJ_ID, "embargo_accepted")
        self.assertEqual(2, len(case.events))
        self.assertEqual("participant_joined", case.events[0].event_type)
        self.assertEqual("embargo_accepted", case.events[1].event_type)

    def test_events_round_trip_via_object_to_record(self):
        case = VulnerabilityCase()
        case.record_event(OBJ_ID, EVENT_TYPE)
        record = object_to_record(case)
        data = record.data_
        self.assertIn("events", data)
        self.assertEqual(1, len(data["events"]))
        evt_data = data["events"][0]
        self.assertEqual(OBJ_ID, evt_data["object_id"])
        self.assertEqual(EVENT_TYPE, evt_data["event_type"])
        self.assertIn("received_at", evt_data)

    def test_events_round_trip_via_datalayer(self):
        dl = TinyDbDataLayer(db_path=None)
        case = VulnerabilityCase()
        ts = datetime(2026, 3, 6, 20, 0, 0, tzinfo=timezone.utc)
        case.events.append(
            CaseEvent(object_id=OBJ_ID, event_type=EVENT_TYPE, received_at=ts)
        )
        dl.create(case)
        stored = cast(VulnerabilityCase, dl.read(case.as_id))
        self.assertIsNotNone(stored)
        self.assertIsInstance(stored, VulnerabilityCase)
        self.assertEqual(1, len(stored.events))
        evt = stored.events[0]
        self.assertEqual(OBJ_ID, evt.object_id)
        self.assertEqual(EVENT_TYPE, evt.event_type)
        self.assertEqual(ts, evt.received_at)

    def test_events_preserved_on_model_validate(self):
        ts = datetime(2026, 3, 6, 20, 0, 0, tzinfo=timezone.utc)
        original = VulnerabilityCase()
        original.events.append(
            CaseEvent(object_id=OBJ_ID, event_type=EVENT_TYPE, received_at=ts)
        )
        data = original.model_dump(mode="json")
        restored = VulnerabilityCase.model_validate(data)
        self.assertEqual(1, len(restored.events))
        evt = restored.events[0]
        self.assertIsInstance(evt, CaseEvent)
        self.assertEqual(OBJ_ID, evt.object_id)
        self.assertEqual(EVENT_TYPE, evt.event_type)
        self.assertEqual(ts, evt.received_at)


if __name__ == "__main__":
    unittest.main()
