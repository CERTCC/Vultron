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

"""Tests for the core EmbargoEvent domain model."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from vultron.core.models.base import CoreObject
from vultron.core.models.embargo_event import EmbargoEvent, VultronEmbargoEvent
from vultron.core.models.registry import CORE_VOCABULARY

_FUTURE_DT = datetime(2099, 12, 31, tzinfo=timezone.utc)
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
            EmbargoEvent()

    def test_end_time_has_default(self):
        e = EmbargoEvent(context=_CONTEXT)
        assert e.end_time is not None

    def test_start_time_has_default(self):
        e = EmbargoEvent(context=_CONTEXT)
        assert e.start_time is not None

    def test_explicit_end_time_accepted(self):
        e = EmbargoEvent(context=_CONTEXT, end_time=_FUTURE_DT)
        assert e.end_time == _FUTURE_DT


class TestCoreEmbargoEventRegistration:
    """EmbargoEvent auto-registers in CORE_VOCABULARY — ADR-0017."""

    def test_registered_in_core_vocabulary(self):
        assert "EmbargoEvent" in CORE_VOCABULARY
        assert CORE_VOCABULARY["EmbargoEvent"] is EmbargoEvent


class TestVultronEmbargoEventAlias:
    """VultronEmbargoEvent is the backward-compat alias for EmbargoEvent."""

    def test_alias_is_same_class(self):
        assert VultronEmbargoEvent is EmbargoEvent

    def test_alias_creates_correct_type(self):
        e = VultronEmbargoEvent(context=_CONTEXT, end_time=_FUTURE_DT)
        assert e.type_ == "EmbargoEvent"
        assert isinstance(e, EmbargoEvent)
