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

"""Tests for wire as_EmbargoEvent domain boundary methods — ADR-0017."""

from datetime import datetime, timezone

from vultron.core.models.embargo_event import EmbargoEvent as CoreEmbargoEvent
from vultron.wire.as2.vocab.objects.embargo_event import (
    as_EmbargoEvent as WireEmbargoEvent,
)

_CONTEXT = "https://example.org/cases/abc"
_FUTURE = datetime(2099, 12, 31, tzinfo=timezone.utc)
_START = datetime(2099, 1, 1, tzinfo=timezone.utc)


class TestWireEmbargoEventBasics:
    """Wire as_EmbargoEvent is an as_Event projection."""

    def test_default_type(self):
        e = WireEmbargoEvent()
        assert e.type_ == "EmbargoEvent"

    def test_to_json_has_camelcase_keys(self):
        import json

        e = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        data = json.loads(e.to_json())
        assert "endTime" in data
        assert "startTime" in data

    def test_set_name_populated(self):
        e = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        assert e.name is not None
        assert "Embargo for" in e.name


class TestWireEmbargoEventFromCore:
    """from_core() creates a valid wire projection — ADR-0017."""

    def test_from_core_produces_wire_instance(self):
        core = CoreEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        wire = WireEmbargoEvent.from_core(core)
        assert isinstance(wire, WireEmbargoEvent)

    def test_from_core_preserves_times(self):
        core = CoreEmbargoEvent(
            context=_CONTEXT,
            start_time=_START,
            end_time=_FUTURE,
        )
        wire = WireEmbargoEvent.from_core(core)
        assert wire.end_time == _FUTURE
        assert wire.start_time == _START

    def test_from_core_sets_name(self):
        core = CoreEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        wire = WireEmbargoEvent.from_core(core)
        assert wire.name is not None
        assert "Embargo for" in wire.name


class TestWireEmbargoEventToCore:
    """to_core() converts wire projection back to core domain object."""

    def test_to_core_produces_core_instance(self):
        wire = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        core = wire.to_core()
        assert isinstance(core, CoreEmbargoEvent)

    def test_to_core_preserves_times(self):
        wire = WireEmbargoEvent(
            context=_CONTEXT,
            start_time=_START,
            end_time=_FUTURE,
        )
        core = wire.to_core()
        assert core.end_time == _FUTURE
        assert core.start_time == _START

    def test_to_core_preserves_context(self):
        wire = WireEmbargoEvent(context=_CONTEXT, end_time=_FUTURE)
        core = wire.to_core()
        assert core.context == _CONTEXT

    def test_roundtrip_core_wire_core(self):
        core1 = CoreEmbargoEvent(
            context=_CONTEXT,
            start_time=_START,
            end_time=_FUTURE,
        )
        wire = WireEmbargoEvent.from_core(core1)
        core2 = wire.to_core()
        assert core2.context == core1.context
        assert core2.end_time == core1.end_time
        assert core2.start_time == core1.start_time
        # Wire-synthesized name must not bleed into the core round-trip result.
        assert core2.name == core1.name
