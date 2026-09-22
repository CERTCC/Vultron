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

"""Tests for as_EmbargoEvent / EmbargoEvent — ADR-0099 detail 3 identity."""

import json
from datetime import datetime, timezone

from vultron.core.models.embargo_event import EmbargoEvent as CoreEmbargoEvent
from vultron.wire.as2.vocab.objects.embargo_event import (
    as_EmbargoEvent as WireEmbargoEvent,
)

_CONTEXT = "https://example.org/cases/abc"
_FUTURE = datetime(2099, 12, 31, tzinfo=timezone.utc)
_START = datetime(2099, 1, 1, tzinfo=timezone.utc)


class TestWireEmbargoEventBasics:
    """Wire as_EmbargoEvent IS the core EmbargoEvent (ADR-0099 detail 3)."""

    def test_wire_is_core_identity(self):
        assert WireEmbargoEvent is CoreEmbargoEvent

    def test_default_type(self):
        e = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        assert e.type_ == "EmbargoEvent"

    def test_json_has_camelcase_keys(self):
        e = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        data = json.loads(e.model_dump_json(exclude_none=True, by_alias=True))
        assert "endTime" in data
        assert "startTime" in data

    def test_name_defaults_to_none(self):
        """Core EmbargoEvent does not auto-populate name."""
        e = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        assert e.name is None

    def test_fields_accessible(self):
        e = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        assert e.end_time == _FUTURE
        assert e.context == _CONTEXT


class TestWireEmbargoEventFromCore:
    """Wire class IS the core class — direct instantiation replaces from_core()."""

    def test_wire_is_core_identity(self):
        assert WireEmbargoEvent is CoreEmbargoEvent

    def test_direct_instantiation_preserves_times(self):
        e = WireEmbargoEvent(
            context=_CONTEXT,
            start_time=_START,
            end_time=_FUTURE,
        )
        assert e.end_time == _FUTURE
        assert e.start_time == _START

    def test_core_instance_is_wire_instance(self):
        core = CoreEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        assert isinstance(core, WireEmbargoEvent)


class TestWireEmbargoEventToCore:
    """Wire instances ARE core instances — no to_core() conversion needed."""

    def test_wire_instance_is_core_instance(self):
        wire = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        assert isinstance(wire, CoreEmbargoEvent)

    def test_fields_directly_accessible(self):
        wire = WireEmbargoEvent(
            context=_CONTEXT,
            start_time=_START,
            end_time=_FUTURE,
        )
        assert wire.end_time == _FUTURE
        assert wire.start_time == _START

    def test_context_directly_accessible(self):
        wire = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        assert wire.context == _CONTEXT

    def test_roundtrip_model_dump_validate(self):
        core1 = CoreEmbargoEvent(
            context=_CONTEXT,
            start_time=_START,
            end_time=_FUTURE,
        )
        data = core1.model_dump(by_alias=True, exclude_none=True, mode="json")
        core2 = CoreEmbargoEvent.model_validate(data)
        assert core2.context == core1.context
        assert core2.end_time == core1.end_time
        assert core2.start_time == core1.start_time
        assert core2.name == core1.name
