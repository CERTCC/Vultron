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

"""``CoreObject`` reads every timestamp as UTC (CS-13-001, #3784).

The core twin of ``as_Object.validate_datetime``'s coverage in
``test/wire/as2/vocab/base/test_wire_base_hierarchy.py``
(``test_as_object_naive_datetime_string_normalized_to_utc`` /
``test_as_object_naive_datetime_object_normalized_to_utc``).  Under ADR-0099
detail 3 a collapsed type validates into ``CoreObject`` directly, so the
guarantee has to hold on this branch by itself.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from vultron.core.models._helpers import INBOUND_CONTEXT_KEY
from vultron.core.models.base import CoreObject
from vultron.core.models.case_participant import CaseParticipant

TIME_FIELDS = ("start_time", "end_time", "published", "updated")
NAIVE_ISO = "2026-01-15T12:00:00"
NAIVE_DT = datetime(2026, 1, 15, 12, 0, 0)


@pytest.mark.spec("CS-13-001")
@pytest.mark.parametrize("field", TIME_FIELDS)
def test_core_object_naive_datetime_string_normalized_to_utc(field):
    """Mirror of the wire-branch string test, per time field."""
    obj = CoreObject.model_validate({field: NAIVE_ISO})
    value = getattr(obj, field)
    assert isinstance(value, datetime)
    assert value.tzinfo == UTC
    assert (value.year, value.hour) == (2026, 12)


@pytest.mark.spec("CS-13-001")
@pytest.mark.parametrize("field", TIME_FIELDS)
def test_core_object_naive_datetime_object_normalized_to_utc(field):
    """Mirror of the wire-branch datetime-object test, per time field."""
    assert NAIVE_DT.tzinfo is None
    obj = CoreObject.model_validate({field: NAIVE_DT})
    value = getattr(obj, field)
    assert isinstance(value, datetime)
    assert value.tzinfo == UTC
    assert value == NAIVE_DT.replace(tzinfo=UTC)


@pytest.mark.spec("CS-13-001")
@pytest.mark.parametrize("field", TIME_FIELDS)
def test_core_object_aware_datetime_keeps_its_offset(field):
    """An aware value is the sender's claim and is carried as received."""
    plus_five = timezone(timedelta(hours=5))
    aware = NAIVE_DT.replace(tzinfo=plus_five)
    obj = CoreObject.model_validate({field: aware})
    value = getattr(obj, field)
    assert value == aware
    assert value.utcoffset() == timedelta(hours=5)


@pytest.mark.spec("CLP-15-007")
@pytest.mark.parametrize("field", TIME_FIELDS)
def test_core_object_explicit_none_stays_none(field):
    """Normalisation never fabricates a time: ``None`` stays ``None``."""
    obj = CoreObject.model_validate({field: None})
    assert getattr(obj, field) is None


@pytest.mark.spec("CLP-15-007")
@pytest.mark.parametrize("field", ("published", "updated"))
def test_core_object_absent_inbound_time_stays_none(field):
    """The inbound absent-time rule (ADR-0103) is unaffected by normalisation."""
    obj = CoreObject.model_validate(
        {"id": "urn:uuid:obj"}, context={INBOUND_CONTEXT_KEY: True}
    )
    assert getattr(obj, field) is None


@pytest.mark.spec("CS-13-001")
def test_subclass_inherits_normalisation():
    """A collapsed type (here ``CaseParticipant``) gets the same guarantee."""
    participant = CaseParticipant(
        attributed_to="https://example.org/actors/vendor",
        context="urn:uuid:case",
        published=NAIVE_DT,
        updated=NAIVE_DT,
    )
    assert participant.published is not None
    assert participant.updated is not None
    assert participant.published.tzinfo == UTC
    assert participant.updated.tzinfo == UTC
