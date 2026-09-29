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

"""Unit tests for the effective RSVP deadline (EP-07, CM-28-011)."""

from datetime import datetime, timedelta, timezone

import pytest

from vultron.core.models.rsvp_deadline import (
    RsvpDeadlineClamp,
    resolve_rsvp_deadline,
)

PUBLISHED = datetime(2026, 9, 1, tzinfo=timezone.utc)
HOURS = timedelta(hours=1)
DAYS = timedelta(days=1)


def _resolve(
    requested: timedelta | None, embargo_end: timedelta | None
) -> tuple[datetime, RsvpDeadlineClamp]:
    deadline = resolve_rsvp_deadline(
        requested=None if requested is None else PUBLISHED + requested,
        published=PUBLISHED,
        embargo_end=None if embargo_end is None else PUBLISHED + embargo_end,
    )
    return deadline.effective, deadline.clamp


@pytest.mark.spec("EP-07-001")
def test_absent_request_uses_policy_window() -> None:
    assert _resolve(None, 30 * DAYS) == (
        PUBLISHED + 7 * DAYS,
        RsvpDeadlineClamp.NONE,
    )


@pytest.mark.spec("CM-28-011")
@pytest.mark.spec("EP-07-006")
def test_day_28_of_30_day_embargo_policy_window_is_the_end() -> None:
    assert _resolve(None, 2 * DAYS) == (
        PUBLISHED + 2 * DAYS,
        RsvpDeadlineClamp.LOWERED_TO_EMBARGO_END,
    )


@pytest.mark.spec("EP-07-006")
def test_explicit_request_past_end_is_lowered() -> None:
    assert _resolve(20 * DAYS, 10 * DAYS) == (
        PUBLISHED + 10 * DAYS,
        RsvpDeadlineClamp.LOWERED_TO_EMBARGO_END,
    )


@pytest.mark.spec("EP-07-003")
def test_sub_minimum_request_is_raised_to_72_hours() -> None:
    assert _resolve(1 * HOURS, 30 * DAYS) == (
        PUBLISHED + 72 * HOURS,
        RsvpDeadlineClamp.RAISED_TO_MINIMUM,
    )


@pytest.mark.spec("EP-07-002")
def test_minimum_is_remaining_embargo_when_shorter() -> None:
    """A 12-hour embargo: the minimum is 12 hours, not 72."""
    deadline = resolve_rsvp_deadline(
        requested=PUBLISHED + HOURS,
        published=PUBLISHED,
        embargo_end=PUBLISHED + 12 * HOURS,
    )
    assert deadline.minimum == PUBLISHED + 12 * HOURS
    assert deadline.effective == PUBLISHED + 12 * HOURS
    assert deadline.clamp is RsvpDeadlineClamp.RAISED_TO_MINIMUM


def test_no_embargo_end_means_no_down_clamp() -> None:
    assert _resolve(400 * DAYS, None) == (
        PUBLISHED + 400 * DAYS,
        RsvpDeadlineClamp.NONE,
    )


@pytest.mark.spec("EP-07-003")
@pytest.mark.spec("EP-07-006")
@pytest.mark.parametrize("requested_hours", [None, 0, 1, 11, 12, 13, 72, 500])
@pytest.mark.parametrize("embargo_hours", [1, 12, 71, 72, 73, 24 * 30])
def test_clamp_up_and_clamp_down_agree(
    requested_hours: int | None, embargo_hours: int
) -> None:
    """Whatever the request, the result is within [minimum, embargo end].

    The clamp up never carries the deadline past the embargo's end, so the
    two rules cannot disagree.
    """
    requested = None if requested_hours is None else requested_hours * HOURS
    deadline = resolve_rsvp_deadline(
        requested=None if requested is None else PUBLISHED + requested,
        published=PUBLISHED,
        embargo_end=PUBLISHED + embargo_hours * HOURS,
    )
    embargo_end = PUBLISHED + embargo_hours * HOURS
    assert deadline.minimum <= embargo_end
    assert deadline.minimum <= deadline.effective <= embargo_end


@pytest.mark.spec("CS-13-001")
def test_non_utc_offsets_compare_by_instant() -> None:
    """Aware non-UTC inputs are compared as instants and carried as given.

    The function no longer normalises its inputs (#3784): the objects they are
    read from — ``as_Object`` on the wire, ``CoreObject`` in core — guarantee
    a UTC-aware value at construction, and an aware offset is the sender's
    claim.  What this pins is that the arithmetic is offset-correct.
    """
    plus_five = timezone(timedelta(hours=5))
    deadline = resolve_rsvp_deadline(
        requested=(PUBLISHED + 5 * DAYS).astimezone(plus_five),
        published=PUBLISHED.astimezone(plus_five),
        embargo_end=(PUBLISHED + 30 * DAYS).astimezone(plus_five),
    )
    assert deadline.effective == PUBLISHED + 5 * DAYS
    assert deadline.clamp is RsvpDeadlineClamp.NONE
    for value in (
        deadline.requested,
        deadline.computed,
        deadline.minimum,
        deadline.effective,
    ):
        assert value is not None
        assert value.utcoffset() is not None


def test_absent_published_measures_from_now() -> None:
    before = datetime.now(tz=timezone.utc).replace(microsecond=0)
    deadline = resolve_rsvp_deadline(
        requested=None, published=None, embargo_end=None
    )
    after = datetime.now(tz=timezone.utc)
    assert before + 7 * DAYS <= deadline.effective <= after + 7 * DAYS
