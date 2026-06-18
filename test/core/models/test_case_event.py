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

"""Tests for the core CaseEvent domain model (step 6 of issue #699)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from vultron.core.models.case_event import CaseEvent, VultronCaseEvent


class TestCaseEventBasics:
    """CaseEvent is a BaseModel with required fields."""

    def test_object_id_required(self):
        with pytest.raises(ValidationError):
            CaseEvent.model_validate({"event_type": "test_event"})

    def test_event_type_required(self):
        with pytest.raises(ValidationError):
            CaseEvent.model_validate({"object_id": "urn:uuid:obj-1"})

    def test_object_id_must_be_non_empty(self):
        with pytest.raises(ValidationError):
            CaseEvent(object_id="", event_type="test_event")

    def test_event_type_must_be_non_empty(self):
        with pytest.raises(ValidationError):
            CaseEvent(object_id="urn:uuid:obj-1", event_type="")

    def test_received_at_defaults_to_utc(self):
        event = CaseEvent(
            object_id="urn:uuid:obj-1", event_type="embargo_accepted"
        )
        assert event.received_at.tzinfo is not None

    def test_explicit_received_at_accepted(self):
        dt = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        event = CaseEvent(
            object_id="urn:uuid:obj-1",
            event_type="embargo_accepted",
            received_at=dt,
        )
        assert event.received_at == dt

    def test_received_at_parses_iso_string(self):
        event = CaseEvent.model_validate(
            {
                "object_id": "urn:uuid:obj-1",
                "event_type": "embargo_accepted",
                "received_at": "2026-01-01T12:00:00+00:00",
            }
        )
        assert event.received_at.year == 2026

    def test_received_at_parses_z_suffix(self):
        event = CaseEvent.model_validate(
            {
                "object_id": "urn:uuid:obj-1",
                "event_type": "embargo_accepted",
                "received_at": "2026-01-01T12:00:00Z",
            }
        )
        assert event.received_at.tzinfo is not None

    def test_json_serialization_includes_received_at(self):
        event = CaseEvent(
            object_id="urn:uuid:obj-1", event_type="embargo_accepted"
        )
        dumped = event.model_dump(mode="json")
        assert "received_at" in dumped


class TestCaseEventBackwardCompatAlias:
    """VultronCaseEvent must be an alias for CaseEvent."""

    def test_alias_is_same_class(self):
        assert VultronCaseEvent is CaseEvent

    def test_alias_construction_works(self):
        e = VultronCaseEvent(
            object_id="urn:uuid:obj-1", event_type="participant_joined"
        )
        assert isinstance(e, CaseEvent)
