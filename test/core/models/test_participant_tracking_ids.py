#!/usr/bin/env python

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

"""A participant status carries its tracking IDs as a set (CM-35, #6748).

Every test here is held by a strict ``xfail`` until #6762 builds the
``ParticipantTrackingId`` type and the ``tracking_ids`` field.  Each asserts
the behavior CM-35 asks for, so it starts passing, and so fails the strict
mark, once the feature lands; #6762 removes the marks.
"""

import pytest
from pydantic import ValidationError

from test.support.objects import make
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.vulnerability_item import VulnerabilityItemId

CASE_ID = "https://example.org/cases/tracking-ids"
ACTOR_ID = "https://example.org/actors/vendor"

TRACKING_IDS_PENDING = (
    "CM-35: participant tracking IDs are not built yet. Tracked by #6762."
)


def _status(**fields: object) -> ParticipantStatus:
    return make(
        ParticipantStatus, context=CASE_ID, attributed_to=ACTOR_ID, **fields
    )


@pytest.mark.xfail(strict=True, reason=TRACKING_IDS_PENDING)
@pytest.mark.spec("CM-35-001")
def test_a_status_carries_a_list_of_value_and_optional_tracker_entries():
    status = _status(
        tracking_ids=[
            {"value": "SEC-1234", "tracker": "PSIRT Jira"},
            {"value": "48812"},
        ]
    )

    wire = status.model_dump(by_alias=True, exclude_none=True, mode="json")

    assert wire["trackingIds"] == [
        {"value": "SEC-1234", "tracker": "PSIRT Jira"},
        {"value": "48812"},
    ]
    assert _status().tracking_ids == []  # type: ignore[attr-defined]


@pytest.mark.xfail(strict=True, reason=TRACKING_IDS_PENDING)
@pytest.mark.spec("CM-35-002")
def test_a_tracking_id_value_and_tracker_are_kept_as_sent():
    status = _status(
        tracking_ids=[{"value": "  odd/#value::7  ", "tracker": "Any Name 9"}]
    )

    (entry,) = status.tracking_ids  # type: ignore[attr-defined]
    assert (entry.value, entry.tracker) == ("  odd/#value::7  ", "Any Name 9")


@pytest.mark.xfail(strict=True, reason=TRACKING_IDS_PENDING)
@pytest.mark.spec("CM-35-003")
def test_a_status_with_two_entries_sharing_a_value_is_refused():
    # Two distinct values are a valid set, so the refusal below is about the
    # shared value and not about the field being unknown.
    _status(
        tracking_ids=[
            {"value": "SEC-1234", "tracker": "PSIRT Jira"},
            {"value": "48812", "tracker": "Engineering"},
        ]
    )
    with pytest.raises(ValidationError, match="SEC-1234"):
        _status(
            tracking_ids=[
                {"value": "SEC-1234", "tracker": "PSIRT Jira"},
                {"value": "SEC-1234", "tracker": "Engineering"},
            ]
        )


@pytest.mark.xfail(strict=True, reason=TRACKING_IDS_PENDING)
@pytest.mark.spec("CM-35-006")
def test_a_status_keeps_its_tracking_ids_through_the_wire_form():
    status = _status(tracking_ids=[{"value": "SEC-1234", "tracker": "PSIRT"}])

    received = ParticipantStatus.model_validate(
        status.model_dump(by_alias=True, mode="json")
    )

    assert received.tracking_ids == status.tracking_ids  # type: ignore[attr-defined]


@pytest.mark.xfail(strict=True, reason=TRACKING_IDS_PENDING)
@pytest.mark.spec("CM-35-007")
def test_a_tracking_id_and_a_vulnerability_id_never_parse_as_each_other():
    from vultron.core.models.participant_status import ParticipantTrackingId  # type: ignore[attr-defined]

    tracking = ParticipantTrackingId(value="SEC-1234", tracker="PSIRT")
    vul_id = VulnerabilityItemId(system_name="VINCE", identifier="VU#123456")

    with pytest.raises(ValidationError):
        VulnerabilityItemId.model_validate(
            tracking.model_dump(by_alias=True, mode="json")
        )
    with pytest.raises(ValidationError):
        ParticipantTrackingId.model_validate(
            vul_id.model_dump(by_alias=True, mode="json")
        )
    # Each direction above also lacks a required field, so check the unknown
    # key on its own: an entry that holds all it needs and one key of the
    # other type is refused too.
    with pytest.raises(ValidationError, match="systemName"):
        ParticipantTrackingId.model_validate(
            {"value": "SEC-1234", "systemName": "VINCE"}
        )
