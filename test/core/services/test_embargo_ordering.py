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

"""The shared shortest-wins comparator (EP-08-001, EP-04-003, ADR-0100, #3470)."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.services.embargo_ordering import (
    earliest_ending,
    earliest_expiring_embargo_id,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

_ACTOR = "https://example.org/actors/owner"
_CASE = "https://example.org/cases/1"
_START = datetime(2030, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def dl() -> Generator[SqliteDataLayer, None, None]:
    reset_datalayer(_ACTOR)
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    store.clear_all()
    try:
        yield store
    finally:
        store.close()
        reset_datalayer(_ACTOR)


def _embargo(days: int) -> EmbargoEvent:
    return EmbargoEvent(
        id_=f"{_CASE}/embargo_events/{days}d",
        context=_CASE,
        start_time=_START,
        end_time=_START + timedelta(days=days),
    )


@pytest.mark.spec("EP-08-001")
def test_earliest_ending_picks_the_smallest_end_whatever_the_order() -> None:
    assert earliest_ending([60, 15, 30], end=lambda d: d) == 15
    assert (
        earliest_ending(
            [_embargo(60), _embargo(15), _embargo(30)],
            end=lambda e: e.end_time,
        ).id_
        == _embargo(15).id_
    )


@pytest.mark.spec("EP-04-003")
def test_earliest_ending_keeps_the_first_of_a_tie() -> None:
    """A tie resolves to the earlier candidate — the sender's terms at case
    creation, where the sender is listed first."""
    first = ("sender", timedelta(days=30))
    second = ("actor_default", timedelta(days=30))
    assert earliest_ending([first, second], end=lambda c: c[1]) is first


def test_earliest_ending_refuses_an_empty_set() -> None:
    """What "no candidate" means is the caller's decision, not a silent pick."""
    empty: list[int] = []
    with pytest.raises(ValueError, match="no candidates"):
        earliest_ending(empty, end=lambda d: d)


@pytest.mark.spec("EP-08-002")
def test_earliest_expiring_embargo_id_reads_the_store(
    dl: SqliteDataLayer,
) -> None:
    for days in (60, 15, 30):
        dl.create(_embargo(days))
    ids = [_embargo(d).id_ for d in (60, 15, 30)]

    assert earliest_expiring_embargo_id(dl, ids) == _embargo(15).id_


@pytest.mark.spec("EP-08-002")
def test_earliest_expiring_embargo_id_fails_closed_on_a_missing_record(
    dl: SqliteDataLayer,
) -> None:
    """An unresolvable candidate is refused, not skipped and not chosen."""
    dl.create(_embargo(30))
    missing = f"{_CASE}/embargo_events/missing"

    with pytest.raises(VultronNotFoundError, match="missing"):
        earliest_expiring_embargo_id(dl, [_embargo(30).id_, missing])


@pytest.mark.spec("EP-08-002")
def test_earliest_expiring_embargo_id_refuses_a_record_that_is_not_an_embargo(
    dl: SqliteDataLayer,
) -> None:
    policy = EmbargoPolicy(
        actor_id=_ACTOR,
        inbox=f"{_ACTOR}/inbox",
        preferred_duration=timedelta(days=30),
    )
    dl.create(policy)
    dl.create(_embargo(30))

    with pytest.raises(VultronValidationError, match="not an EmbargoEvent"):
        earliest_expiring_embargo_id(dl, [_embargo(30).id_, policy.id_])
