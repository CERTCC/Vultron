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

"""``EmbargoEvent`` — the core embargo object (ADR-0099 detail 3).

Covers the fail-fast field contract (``context`` and ``end_time`` required,
no default duration — EP-04-010, #3404) and the UTC contract on its time
fields (CS-13-001, #3784), including the inbound path where a nested
``EmbargoEvent`` inside an ``Invite`` validates straight into this class.
"""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from vultron.core.models.base import CoreObject
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.wire.as2.factories.embargo import em_propose_embargo_activity
from vultron.wire.as2.parser import parse_activity

_FUTURE_DT = datetime(2099, 12, 31, tzinfo=UTC)
_NAIVE_DT = datetime(2099, 12, 31, 12, 30)  # noqa: DTZ001 — deliberately naive
_CONTEXT = "urn:uuid:case-123"


class TestCoreEmbargoEventBasics:
    """EmbargoEvent is a CoreObject with Literal type_ — core migration."""

    def test_inherits_core_object(self):
        assert issubclass(EmbargoEvent, CoreObject)

    def test_type_literal(self):
        e = EmbargoEvent(context=_CONTEXT, end_time=_FUTURE_DT)
        assert e.type_ == "EmbargoEvent"

    def test_context_required(self):
        with pytest.raises(ValidationError):
            EmbargoEvent(end_time=_FUTURE_DT)

    def test_start_time_has_default(self):
        e = EmbargoEvent(context=_CONTEXT, end_time=_FUTURE_DT)
        assert e.start_time is not None

    def test_explicit_end_time_accepted(self):
        e = EmbargoEvent(context=_CONTEXT, end_time=_FUTURE_DT)
        assert e.end_time == _FUTURE_DT


class TestCoreEmbargoEventNoDefaultDuration:
    """``end_time`` carries no implicit duration (EP-04-010, ADR-0096, #3404).

    The protocol default is the single fallback duration in the system and is
    resolved at case creation; an object built without stating its end is a
    construction error, not a 45-day embargo.
    """

    @pytest.mark.spec("EP-04-010")
    def test_end_time_is_required(self):
        with pytest.raises(ValidationError) as exc_info:
            EmbargoEvent(context=_CONTEXT)
        assert any(
            err["loc"] == ("endTime",) and err["type"] == "missing"
            for err in exc_info.value.errors()
        )

    @pytest.mark.spec("EP-04-010")
    def test_end_time_field_has_no_default(self):
        """Inspection clause of EP-04-010: no default, no default_factory."""
        field = EmbargoEvent.model_fields["end_time"]
        assert field.is_required()
        assert field.default_factory is None

    @pytest.mark.spec("EP-04-005")
    @pytest.mark.spec("EP-04-007")
    def test_any_stated_duration_is_honoured(self):
        """The model bounds no duration: a 12-hour or 400-day end is the
        sender's claim (EP-04-007).  The bounded value is the protocol default
        alone, enforced on ``ActorConfig`` (EP-04-005, test_actor_config)."""
        start = datetime(2030, 1, 1, tzinfo=UTC)
        for delta in (timedelta(hours=12), timedelta(days=400)):
            e = EmbargoEvent(
                context=_CONTEXT, start_time=start, end_time=start + delta
            )
            assert e.end_time - start == delta


class TestCoreEmbargoEventTimesAreUtc:
    """Both time fields are UTC-aware after construction (CS-13-001, #3784).

    ``EmbargoEvent`` redeclares ``start_time`` and ``end_time``; these tests
    confirm the ``CoreObject`` validator still applies to the overriding
    fields, not only to the inherited ``published``/``updated``.
    """

    @pytest.mark.spec("CS-13-001")
    def test_naive_end_time_is_read_as_utc(self):
        e = EmbargoEvent(context=_CONTEXT, end_time=_NAIVE_DT)
        assert e.end_time.tzinfo == UTC
        assert e.end_time == _NAIVE_DT.replace(tzinfo=UTC)

    @pytest.mark.spec("CS-13-001")
    def test_aware_end_time_is_kept(self):
        plus_five = timezone(timedelta(hours=5))
        aware = _NAIVE_DT.replace(tzinfo=plus_five)
        e = EmbargoEvent(context=_CONTEXT, end_time=aware)
        assert e.end_time == aware
        assert e.end_time.utcoffset() is not None

    @pytest.mark.spec("CS-13-001")
    def test_naive_start_time_is_read_as_utc(self):
        e = EmbargoEvent(
            context=_CONTEXT, start_time=_NAIVE_DT, end_time=_FUTURE_DT
        )
        assert e.start_time is not None
        assert e.start_time.tzinfo == UTC

    @pytest.mark.spec("CLP-15-007")
    def test_absent_start_time_stays_none(self):
        """Normalisation never fabricates a time."""
        e = EmbargoEvent(
            context=_CONTEXT, start_time=None, end_time=_FUTURE_DT
        )
        assert e.start_time is None

    @pytest.mark.spec("CM-28-006")
    @pytest.mark.spec("CS-13-001")
    def test_inbound_invite_with_offset_less_end_time_parses_to_utc(self):
        """A nested ``endTime`` with no offset reaches core UTC-aware.

        The wire validator on ``as_Object`` never runs for the nested object
        (it validates straight into ``EmbargoEvent``), so this is the path
        #3784 exists for.
        """
        embargo = EmbargoEvent(context=_CONTEXT, end_time=_FUTURE_DT)
        invite = em_propose_embargo_activity(
            embargo, actor="https://example.org/actors/vendor"
        )
        body = json.loads(invite.model_dump_json(by_alias=True))
        body["object"]["endTime"] = "2099-12-31T12:30:00"

        parsed = parse_activity(body)

        nested = getattr(parsed, "object_", None)
        assert isinstance(nested, EmbargoEvent)
        assert nested.end_time.tzinfo == UTC
        assert nested.end_time == datetime(2099, 12, 31, 12, 30, tzinfo=UTC)


class TestCoreEmbargoEventRegistration:
    """EmbargoEvent auto-registers in CORE_VOCABULARY — ADR-0017."""

    def test_registered_in_core_vocabulary(self):
        assert "EmbargoEvent" in CORE_VOCABULARY
        assert CORE_VOCABULARY["EmbargoEvent"] is EmbargoEvent


@pytest.mark.spec("EP-04-004")
def test_with_subject_relabels_a_derived_name_for_the_new_subject() -> None:
    """The label ``_set_name`` derived for the report is not a sender's name;
    the case-scoped copy is labelled by the case."""
    event = EmbargoEvent(
        context="https://example.org/reports/r-1",
        end_time=datetime(2099, 6, 1, tzinfo=UTC),
    )
    moved = event.with_subject("https://example.org/cases/c-1")
    assert moved.id_ == event.id_
    assert moved.end_time == event.end_time
    assert moved.context == "https://example.org/cases/c-1"
    assert moved.name is not None
    assert "cases/c-1" in moved.name
    assert "reports/r-1" not in moved.name


@pytest.mark.spec("EP-04-004")
def test_with_subject_keeps_a_name_the_sender_chose() -> None:
    event = EmbargoEvent(
        name="Widget parser embargo",
        context="https://example.org/reports/r-1",
        end_time=datetime(2099, 6, 1, tzinfo=UTC),
    )
    moved = event.with_subject("https://example.org/cases/c-1")
    assert moved.name == "Widget parser embargo"
    assert moved.context == "https://example.org/cases/c-1"
