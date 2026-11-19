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

from test.support.objects import make, with_times
from vultron.core.models.base import CoreObject
from vultron.core.models.embargo_policy import EmbargoPolicy, parse_duration
from vultron.core.models.registry import CORE_VOCABULARY

ACTOR_ID = "https://example.org/actors/vendor"

_P90D = timedelta(days=90)
_P45D = timedelta(days=45)
_P180D = timedelta(days=180)


class TestCoreEmbargoPolicyCreation:
    """EmbargoPolicy is a CoreObject with required fields — EP-01-001."""

    def test_inherits_core_object(self):
        assert issubclass(EmbargoPolicy, CoreObject)

    def test_type_literal(self):
        p = make(
            EmbargoPolicy,
            attributed_to=ACTOR_ID,
            preferred_duration=_P90D,
        )
        assert p.type_ == "EmbargoPolicy"

    def test_required_fields(self):
        p = make(
            EmbargoPolicy,
            attributed_to=ACTOR_ID,
            preferred_duration=_P90D,
            minimum_duration=_P45D,
            maximum_duration=_P180D,
            content="Prefer 90 days.",
        )
        assert p.attributed_to == ACTOR_ID
        assert p.preferred_duration == _P90D
        assert p.minimum_duration == _P45D
        assert p.maximum_duration == _P180D
        assert p.content == "Prefer 90 days."

    def test_optional_fields_default_to_none(self):
        p = make(
            EmbargoPolicy,
            attributed_to=ACTOR_ID,
            preferred_duration=_P90D,
        )
        assert p.minimum_duration is None
        assert p.maximum_duration is None
        assert p.content is None

    def test_missing_attributed_to_raises(self):
        with pytest.raises(ValidationError):
            make(EmbargoPolicy, preferred_duration=_P90D)  # type: ignore[call-arg]

    def test_missing_preferred_duration_raises(self):
        with pytest.raises(ValidationError):
            make(EmbargoPolicy, attributed_to=ACTOR_ID)  # type: ignore[call-arg]

    def test_empty_attributed_to_raises(self):
        with pytest.raises(ValidationError):
            make(
                EmbargoPolicy,
                attributed_to="",
                preferred_duration=_P90D,
            )

    @pytest.mark.spec("EP-01-002")
    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("inbox", f"{ACTOR_ID}/inbox"),
            ("actor_id", ACTOR_ID),
            ("actorId", ACTOR_ID),
            ("notes", "Prefer 90 days."),
        ],
    )
    def test_a_retired_key_is_refused(self, key, value):
        """The old ``actorId``, ``notes`` and ``inbox`` keys match no field,
        so ``extra="forbid"`` refuses them rather than dropping them
        (ADR-0175, ADR-0194)."""
        with pytest.raises(ValidationError, match=key):
            EmbargoPolicy.model_validate(
                with_times(
                    EmbargoPolicy,
                    {
                        "attributed_to": ACTOR_ID,
                        "preferred_duration": "P90D",
                        key: value,
                    },
                )
            )

    def test_wire_spelling_is_attributed_to_and_content(self):
        p = make(
            EmbargoPolicy,
            attributed_to=ACTOR_ID,
            preferred_duration=_P90D,
            content="Prefer 90 days.",
        )
        data = p.model_dump(by_alias=True, mode="json", exclude_none=True)
        assert data["attributedTo"] == ACTOR_ID
        assert data["content"] == "Prefer 90 days."
        assert not {"actorId", "inbox", "notes"} & data.keys()

    def test_empty_content_raises(self):
        with pytest.raises(ValidationError):
            make(
                EmbargoPolicy,
                attributed_to=ACTOR_ID,
                preferred_duration=_P90D,
                content="",
            )


class TestCoreEmbargoPolicyDurationParsing:
    """ISO 8601 duration strings are accepted and parsed — DUR-04-001, DUR-04-002."""

    def test_iso8601_string_parsed(self):
        p = EmbargoPolicy.model_validate(
            with_times(
                EmbargoPolicy,
                {
                    "attributed_to": ACTOR_ID,
                    "preferred_duration": "P90D",
                },
            )
        )
        assert p.preferred_duration == _P90D

    def test_timedelta_accepted_directly(self):
        p = make(
            EmbargoPolicy,
            attributed_to=ACTOR_ID,
            preferred_duration=_P90D,
        )
        assert p.preferred_duration == _P90D

    def test_iso8601_week_rejected(self):
        with pytest.raises(ValidationError, match="DUR-02-002"):
            EmbargoPolicy.model_validate(
                with_times(
                    EmbargoPolicy,
                    {
                        "attributed_to": ACTOR_ID,
                        "preferred_duration": "P2W",
                    },
                )
            )

    def test_iso8601_calendar_units_rejected(self):
        with pytest.raises(ValidationError, match="calendar units"):
            EmbargoPolicy.model_validate(
                with_times(
                    EmbargoPolicy,
                    {
                        "attributed_to": ACTOR_ID,
                        "preferred_duration": "P1Y",
                    },
                )
            )

    def test_invalid_iso8601_rejected(self):
        with pytest.raises(ValidationError):
            EmbargoPolicy.model_validate(
                with_times(
                    EmbargoPolicy,
                    {
                        "attributed_to": ACTOR_ID,
                        "preferred_duration": "not-a-duration",
                    },
                )
            )

    def test_out_of_range_duration_rejected_cleanly(self):
        """An astronomically large duration is bad input, not a crash.

        ``isodate.parse_duration`` raises ``OverflowError`` (not
        ``ISO8601Error``) for a value like ``P<many-digits>D``.  It must be
        folded into a ``ValidationError`` (→ 422), never escape as an
        unhandled 500 (CS-23-001 regression guard).
        """
        with pytest.raises(ValidationError):
            EmbargoPolicy.model_validate(
                with_times(
                    EmbargoPolicy,
                    {
                        "attributed_to": ACTOR_ID,
                        "preferred_duration": "P999999999999999999999999D",
                    },
                )
            )

    def test_parse_duration_out_of_range_raises_value_error(self):
        """``parse_duration`` maps an OverflowError to a clean ValueError."""
        with pytest.raises(ValueError, match="Invalid ISO 8601 duration"):
            parse_duration("P999999999999999999999999D")


class TestCoreEmbargoPolicySerialization:
    """Durations serialize to ISO 8601 strings in JSON mode — DUR-05-002."""

    @pytest.mark.spec("DUR-01-002")
    def test_duration_serializes_to_iso8601(self):
        p = make(
            EmbargoPolicy,
            attributed_to=ACTOR_ID,
            preferred_duration=_P90D,
            minimum_duration=_P45D,
            maximum_duration=_P180D,
        )
        data = json.loads(p.model_dump_json())
        assert data["preferred_duration"] == "P90D"
        assert data["minimum_duration"] == "P45D"
        assert data["maximum_duration"] == "P180D"

    @pytest.mark.spec("DUR-03-004")
    def test_a_whole_day_duration_carries_no_time_units(self):
        """A whole-day policy duration is written in days alone, never mixed
        with hours, minutes or seconds."""
        p = make(
            EmbargoPolicy,
            attributed_to=ACTOR_ID,
            preferred_duration=_P90D,
            minimum_duration=_P45D,
            maximum_duration=_P180D,
        )
        data = json.loads(p.model_dump_json())
        for field in (
            "preferred_duration",
            "minimum_duration",
            "maximum_duration",
        ):
            assert "T" not in data[field], data[field]

    def test_none_duration_serializes_to_null(self):
        p = make(
            EmbargoPolicy,
            attributed_to=ACTOR_ID,
            preferred_duration=_P90D,
        )
        data = json.loads(p.model_dump_json())
        assert data["minimum_duration"] is None
        assert data["maximum_duration"] is None

    def test_json_roundtrip(self):
        p = make(
            EmbargoPolicy,
            attributed_to=ACTOR_ID,
            preferred_duration=_P90D,
            minimum_duration=_P45D,
        )
        data = json.loads(p.model_dump_json())
        p2 = EmbargoPolicy.model_validate(with_times(EmbargoPolicy, data))
        assert p2.preferred_duration == p.preferred_duration
        assert p2.minimum_duration == p.minimum_duration
        assert p2.attributed_to == p.attributed_to


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


@pytest.mark.spec("EP-01-002")
def test_a_policy_requires_attributed_to_and_carries_no_inbox() -> None:
    fields = EmbargoPolicy.model_fields
    assert fields["attributed_to"].is_required()
    assert fields["preferred_duration"].is_required()
    assert not {"actor_id", "inbox"} & fields.keys()


@pytest.mark.spec("EP-01-003")
def test_a_policys_free_text_is_its_content() -> None:
    fields = EmbargoPolicy.model_fields
    assert "content" in fields
    assert "notes" not in fields


@pytest.mark.spec("EP-01-005")
def test_a_policys_attributed_to_must_be_a_full_uri() -> None:
    policy = make(
        EmbargoPolicy, attributed_to=ACTOR_ID, preferred_duration=_P90D
    )
    assert policy.attributed_to == ACTOR_ID
    with pytest.raises(ValidationError, match="must be a URI"):
        make(EmbargoPolicy, attributed_to="vendor", preferred_duration=_P90D)
