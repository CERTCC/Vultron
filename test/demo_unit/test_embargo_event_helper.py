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
"""The demo's embargo proposal is dated from its caller's instant.

``make_embargo_event`` takes the instant from the demo step that calls it
and reads no clock, so the same instant builds the same event and building
it moves no recording.  ``case_minted_at`` gives that step the instant its
CASE_MANAGER's store stamped on the case, not a clock read of its own
(ADR-0176).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from test.support.act_clock import recorded_clock_reads
from test.support.objects import make
from vultron.demo.helpers.embargo import case_minted_at, make_embargo_event
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_MINTED = datetime(2026, 3, 1, 12, 34, 56, 789, tzinfo=UTC)
_MANAGER = "https://example.org/actors/embargo-helper-vendor"


def _case() -> as_VulnerabilityCase:
    return make(
        as_VulnerabilityCase,
        name="Embargo helper case",
        attributed_to=_MANAGER,
        published=_MINTED,
    )


def _client_holding(
    monkeypatch: pytest.MonkeyPatch, stored: dict[str, Any]
) -> tuple[DataLayerClient, list[str]]:
    """A client whose GET answers *stored*; returns it and the paths read."""
    client = DataLayerClient(base_url="http://vendor:7999/api/v2")
    paths: list[str] = []

    def _get(_self: DataLayerClient, path: str, **_: Any) -> dict[str, Any]:
        paths.append(path)
        return stored

    monkeypatch.setattr(DataLayerClient, "get", _get)
    return client, paths


@pytest.mark.spec("CS-13-002")
def test_the_event_is_dated_from_the_callers_instant() -> None:
    case = _case()

    with recorded_clock_reads() as clock_reads:
        first = make_embargo_event(case, at=_MINTED, days=45, seq=1)
        again = make_embargo_event(case, at=_MINTED, days=45, seq=1)

    assert clock_reads == []
    assert first.model_dump() == again.model_dump()
    assert first.start_time == datetime(2026, 3, 1, 12, 34, tzinfo=UTC)
    assert first.end_time == datetime(2026, 4, 15, tzinfo=UTC)
    assert first.published == first.start_time
    assert first.id_ == f"{case.id_}/embargo_events/45d-2026-04-15-1"


def test_a_later_instant_moves_the_event_with_it() -> None:
    later = _MINTED + timedelta(days=1)

    event = make_embargo_event(_case(), at=later, days=45)

    assert event.end_time == datetime(2026, 4, 16, tzinfo=UTC)


@pytest.mark.spec("CS-13-002")
def test_the_case_is_minted_at_its_holders_stored_published_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case()
    stored = "2026-02-01T09:00:00.000001+00:00"
    client, paths = _client_holding(monkeypatch, {"published": stored})

    with recorded_clock_reads() as clock_reads:
        minted = case_minted_at(client, case, _MANAGER)

    assert clock_reads == []
    assert minted == datetime.fromisoformat(stored)
    assert paths == [client.dl_path(case.id_, actor_id=_MANAGER)]


@pytest.mark.parametrize(
    ("stored", "match"),
    [
        ({}, "no published time"),
        ({"published": ""}, "no published time"),
        ({"published": "not-a-timestamp"}, "no published time"),
    ],
    ids=["absent", "empty", "malformed"],
)
def test_a_stored_copy_without_a_parseable_published_time_is_refused(
    monkeypatch: pytest.MonkeyPatch, stored: dict[str, Any], match: str
) -> None:
    client, _ = _client_holding(monkeypatch, stored)

    with pytest.raises(ValueError, match=match):
        case_minted_at(client, _case(), _MANAGER)
