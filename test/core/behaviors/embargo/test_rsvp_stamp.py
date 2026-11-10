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

"""The CASE_MANAGER's RSVP-deadline stamp (``rsvp_stamp.py``, CM-28-012)."""

from datetime import UTC, datetime, timedelta

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.config.actor import ActorConfig
from vultron.core.behaviors.embargo.rsvp_stamp import (
    stamp_invite_rsvp_deadline,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

CASE_ID = "https://example.org/cases/rsvp-stamp"
MANAGER = "https://example.org/actors/rsvp-manager"
# The sending act's instant; every stamp is measured from it (ADR-0176).
AT = datetime.now(tz=UTC)


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)


def _embargo(dl: SqliteDataLayer, days: int) -> str:
    embargo = as_EmbargoEvent(
        context=CASE_ID, end_time=days_from_now_utc(days)
    )
    dl.create(embargo)
    return embargo.id_


@pytest.mark.spec("CM-28-012")
@pytest.mark.spec("CM-18-023")
@pytest.mark.spec("EP-07-010")
def test_the_default_window_is_seven_days_from_published(dl) -> None:
    stamp = stamp_invite_rsvp_deadline(dl, _embargo(dl, 45), AT)

    assert stamp.rsvp_deadline - stamp.published == timedelta(days=7)
    assert stamp.min_rsvp_window == timedelta(hours=72)


@pytest.mark.spec("CS-13-002")
def test_the_invite_is_published_at_the_act_instant(dl) -> None:
    """The stamp takes the act's instant as ``published``; no clock is read."""
    # Ten days ago, so a clock read in its place would show.
    at = AT - timedelta(days=10)

    stamp = stamp_invite_rsvp_deadline(dl, _embargo(dl, 45), at)

    assert stamp.published == at
    assert stamp.rsvp_deadline == at + timedelta(days=7)


@pytest.mark.spec("CM-28-012")
@pytest.mark.spec("EP-07-007")
@pytest.mark.spec("EP-07-008")
@pytest.mark.spec("EP-07-012")
def test_the_configured_window_and_floor_are_used(dl) -> None:
    config = ActorConfig(
        default_rsvp_window=timedelta(days=10),
        min_rsvp_window=timedelta(days=4),
    )

    stamp = stamp_invite_rsvp_deadline(dl, _embargo(dl, 45), AT, config)

    assert stamp.rsvp_deadline - stamp.published == timedelta(days=10)
    assert stamp.min_rsvp_window == timedelta(days=4)


@pytest.mark.spec("CM-28-012")
@pytest.mark.spec("EP-07-006")
def test_the_deadline_never_passes_the_embargo_end(dl) -> None:
    embargo_id = _embargo(dl, 5)
    embargo = dl.read(embargo_id)

    stamp = stamp_invite_rsvp_deadline(dl, embargo_id, AT)

    assert stamp.rsvp_deadline == embargo.end_time


def test_a_missing_embargo_raises(dl) -> None:
    with pytest.raises(VultronNotFoundError):
        stamp_invite_rsvp_deadline(dl, f"{CASE_ID}/embargo_events/none", AT)


@pytest.mark.spec("CM-28-012")
@pytest.mark.spec("EP-07-002")
def test_a_default_window_below_the_floor_is_raised_to_it(dl) -> None:
    config = ActorConfig(
        default_rsvp_window=timedelta(days=1),
        min_rsvp_window=timedelta(hours=72),
    )

    stamp = stamp_invite_rsvp_deadline(dl, _embargo(dl, 45), AT, config)

    assert stamp.rsvp_deadline - stamp.published == timedelta(hours=72)
