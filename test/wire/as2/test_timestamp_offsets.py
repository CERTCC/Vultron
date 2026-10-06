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

"""Wire timestamps carry an explicit offset end to end (CS-13-005).

A timestamp carried from a peer keeps the offset it arrived with through
parse, storage and serialisation (CLP-15-007, CLP-07-011); a timestamp this
node mints serialises in UTC.
"""

import json
import re
from typing import Any

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
)

CASE_ID = "https://example.org/cases/offsets"
EMBARGO_ID = "https://example.org/embargoes/offsets"
CARRIED_END = "2026-09-01T12:00:00+05:00"
UTC_OFFSET = re.compile(r"(Z|\+00:00)$")


def _announce_embargo(end_time: str) -> dict[str, Any]:
    return {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Announce",
        "id": "https://example.org/activities/offsets",
        "actor": "https://example.org/actors/alice",
        "published": "2026-03-04T05:06:07+00:00",
        "object": {
            "type": "EmbargoEvent",
            "id": EMBARGO_ID,
            "context": CASE_ID,
            "endTime": end_time,
        },
    }


@pytest.mark.spec("CS-13-005")
def test_carried_non_utc_offset_round_trips_through_storage() -> None:
    """A peer's ``+05:00`` survives parse, store and serialise unchanged."""
    activity = parse_activity(_announce_embargo(CARRIED_END))
    assert isinstance(activity, as_Announce)
    embargo = activity.object_
    assert isinstance(embargo, EmbargoEvent)

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_ID)
    dl.save(embargo)
    stored = dl.read(EMBARGO_ID)
    assert isinstance(stored, EmbargoEvent)

    wire = json.loads(stored.model_dump_json(by_alias=True, exclude_none=True))
    assert wire["endTime"] == CARRIED_END


@pytest.mark.spec("CS-13-005")
def test_minted_timestamp_serialises_with_a_utc_offset() -> None:
    """A time this node generates is written with ``Z`` or ``+00:00``."""
    embargo = EmbargoEvent(context=CASE_ID, end_time=days_from_now_utc(30))
    wire = json.loads(
        embargo.model_dump_json(by_alias=True, exclude_none=True)
    )
    for key in ("published", "updated", "startTime", "endTime"):
        assert UTC_OFFSET.search(wire[key]), (key, wire[key])
