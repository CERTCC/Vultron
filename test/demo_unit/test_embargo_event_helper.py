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
it moves no recording (ADR-0176).
"""

from datetime import UTC, datetime, timedelta

import pytest

from test.support.act_clock import recorded_clock_reads
from vultron.demo.helpers.embargo import case_minted_at, make_embargo_event
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_MINTED = datetime(2026, 3, 1, 12, 34, 56, 789, tzinfo=UTC)


def _case() -> as_VulnerabilityCase:
    return as_VulnerabilityCase(
        name="Embargo helper case",
        attributed_to="https://example.org/actors/embargo-helper-vendor",
        published=_MINTED,
    )


@pytest.mark.spec("CS-13-002")
def test_the_event_is_dated_from_the_callers_instant() -> None:
    case = _case()

    with recorded_clock_reads() as clock_reads:
        first = make_embargo_event(case, _MINTED, days=45, seq=1)
        again = make_embargo_event(case, _MINTED, days=45, seq=1)

    assert clock_reads == []
    assert first.model_dump() == again.model_dump()
    assert first.start_time == datetime(2026, 3, 1, 12, 34, tzinfo=UTC)
    assert first.end_time == datetime(2026, 4, 15, tzinfo=UTC)
    assert first.published == first.start_time
    assert first.id_ == f"{case.id_}/embargo_events/45d-2026-04-15-1"


def test_a_naive_instant_is_refused() -> None:
    naive = datetime(2026, 3, 1, 12)  # noqa: DTZ001 — deliberately naive
    with pytest.raises(ValueError, match="timezone-aware"):
        make_embargo_event(_case(), naive)


def test_the_case_is_minted_at_its_published_time() -> None:
    assert case_minted_at(_case()) == _MINTED


def test_a_case_without_a_published_time_has_no_minted_instant() -> None:
    case = _case()
    case.published = None

    with pytest.raises(ValueError, match="no published time"):
        case_minted_at(case)


def test_a_later_instant_moves_the_event_with_it() -> None:
    later = _MINTED + timedelta(days=1)

    event = make_embargo_event(_case(), later, days=45)

    assert event.end_time == datetime(2026, 4, 16, tzinfo=UTC)
