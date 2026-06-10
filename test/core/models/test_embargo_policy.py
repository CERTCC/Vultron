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

"""Tests for the core EmbargoPolicy domain model."""

import json
from datetime import timedelta

import pytest
from pydantic import ValidationError

from vultron.core.models.embargo_policy import EmbargoPolicy, parse_duration
from vultron.core.models.base import CoreObject
from vultron.core.models.registry import CORE_VOCABULARY

ACTOR_ID = "https://example.org/actors/vendor"
INBOX = "https://example.org/actors/vendor/inbox"

_P90D = timedelta(days=90)
_P45D = timedelta(days=45)
_P180D = timedelta(days=180)


class TestCoreEmbargoPolicyCreation:
    """EmbargoPolicy is a CoreObject with required fields — EP-01-001."""

    def test_inherits_core_object(self):
        assert issubclass(EmbargoPolicy, CoreObject)

    def test_type_literal(self):
        p = EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration=_P90D,
        )
        assert p.type_ == "EmbargoPolicy"

    def test_required_fields(self):
        p = EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration=_P90D,
            minimum_duration=_P45D,
            maximum_duration=_P180D,
            notes="Prefer 90 days.",
        )
        assert p.actor_id == ACTOR_ID
        assert p.inbox == INBOX
        assert p.preferred_duration == _P90D
        assert p.minimum_duration == _P45D
        assert p.maximum_duration == _P180D
        assert p.notes == "Prefer 90 days."

    def test_optional_fields_default_to_none(self):
        p = EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration=_P90D,
        )
        assert p.minimum_duration is None
        assert p.maximum_duration is None
        assert p.notes is None

    def test_missing_actor_id_raises(self):
        with pytest.raises(ValidationError):
            EmbargoPolicy(inbox=INBOX, preferred_duration=_P90D)  # type: ignore[call-arg]

    def test_missing_inbox_raises(self):
        with pytest.raises(ValidationError):
            EmbargoPolicy(actor_id=ACTOR_ID, preferred_duration=_P90D)  # type: ignore[call-arg]

    def test_missing_preferred_duration_raises(self):
        with pytest.raises(ValidationError):
            EmbargoPolicy(actor_id=ACTOR_ID, inbox=INBOX)  # type: ignore[call-arg]

    def test_empty_actor_id_raises(self):
        with pytest.raises(ValidationError):
            EmbargoPolicy(actor_id="", inbox=INBOX, preferred_duration=_P90D)

    def test_empty_inbox_raises(self):
        with pytest.raises(ValidationError):
            EmbargoPolicy(
                actor_id=ACTOR_ID, inbox="", preferred_duration=_P90D
            )

    def test_empty_notes_raises(self):
        with pytest.raises(ValidationError):
            EmbargoPolicy(
                actor_id=ACTOR_ID,
                inbox=INBOX,
                preferred_duration=_P90D,
                notes="",
            )


class TestCoreEmbargoPolicyDurationParsing:
    """ISO 8601 duration strings are accepted and parsed — DUR-04-001, DUR-04-002."""

    def test_iso8601_string_parsed(self):
        p = EmbargoPolicy.model_validate(
            {
                "actor_id": ACTOR_ID,
                "inbox": INBOX,
                "preferred_duration": "P90D",
            }
        )
        assert p.preferred_duration == _P90D

    def test_timedelta_accepted_directly(self):
        p = EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration=_P90D,
        )
        assert p.preferred_duration == _P90D

    def test_iso8601_week_rejected(self):
        with pytest.raises(ValidationError, match="DUR-02-002"):
            EmbargoPolicy.model_validate(
                {
                    "actor_id": ACTOR_ID,
                    "inbox": INBOX,
                    "preferred_duration": "P2W",
                }
            )

    def test_iso8601_calendar_units_rejected(self):
        with pytest.raises(ValidationError, match="calendar units"):
            EmbargoPolicy.model_validate(
                {
                    "actor_id": ACTOR_ID,
                    "inbox": INBOX,
                    "preferred_duration": "P1Y",
                }
            )

    def test_invalid_iso8601_rejected(self):
        with pytest.raises(ValidationError):
            EmbargoPolicy.model_validate(
                {
                    "actor_id": ACTOR_ID,
                    "inbox": INBOX,
                    "preferred_duration": "not-a-duration",
                }
            )


class TestCoreEmbargoPolicySerialization:
    """Durations serialize to ISO 8601 strings in JSON mode — DUR-05-002."""

    def test_duration_serializes_to_iso8601(self):
        p = EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration=_P90D,
            minimum_duration=_P45D,
            maximum_duration=_P180D,
        )
        data = json.loads(p.model_dump_json())
        assert data["preferred_duration"] == "P90D"
        assert data["minimum_duration"] == "P45D"
        assert data["maximum_duration"] == "P180D"

    def test_none_duration_serializes_to_null(self):
        p = EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration=_P90D,
        )
        data = json.loads(p.model_dump_json())
        assert data["minimum_duration"] is None
        assert data["maximum_duration"] is None

    def test_json_roundtrip(self):
        p = EmbargoPolicy(
            actor_id=ACTOR_ID,
            inbox=INBOX,
            preferred_duration=_P90D,
            minimum_duration=_P45D,
        )
        data = json.loads(p.model_dump_json())
        p2 = EmbargoPolicy.model_validate(data)
        assert p2.preferred_duration == p.preferred_duration
        assert p2.minimum_duration == p.minimum_duration
        assert p2.actor_id == p.actor_id


class TestCoreEmbargoPolicyCoreVocabulary:
    """EmbargoPolicy registers in CORE_VOCABULARY — ADR-0017."""

    def test_registered_in_core_vocabulary(self):
        assert "EmbargoPolicy" in CORE_VOCABULARY
        assert CORE_VOCABULARY["EmbargoPolicy"] is EmbargoPolicy


class TestParseDuration:
    """Unit tests for the parse_duration helper."""

    def test_none_returns_none(self):
        assert parse_duration(None) is None

    def test_timedelta_passthrough(self):
        td = timedelta(days=5)
        assert parse_duration(td) is td

    def test_string_p90d(self):
        assert parse_duration("P90D") == timedelta(days=90)

    def test_string_p45d(self):
        assert parse_duration("P45D") == timedelta(days=45)

    def test_week_raises(self):
        with pytest.raises(ValueError, match="DUR-02-002"):
            parse_duration("P2W")

    def test_calendar_units_raises(self):
        with pytest.raises(ValueError, match="calendar units"):
            parse_duration("P1Y")

    def test_unsupported_type_raises(self):
        with pytest.raises(TypeError, match="Unsupported"):
            parse_duration(42)
