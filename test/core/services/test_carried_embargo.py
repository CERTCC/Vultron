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

"""``store_carried_embargo``: a received case's embargo is held first (EMB-18-003)."""

from collections.abc import Generator

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.report import VulnerabilityReport
from vultron.core.services.carried_embargo import store_carried_embargo
from vultron.core.services.embargo_ordering import read_embargo_event
from vultron.errors import VultronNotFoundError, VultronValidationError

_ACTOR = "https://example.org/actors/receiver"
_CASE = "https://example.org/cases/carried"


def _embargo() -> EmbargoEvent:
    return EmbargoEvent(
        id_=f"{_CASE}/embargo_events/e1",
        context=_CASE,
        end_time=days_from_now_utc(45),
    )


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


def test_a_case_with_no_embargo_needs_nothing(dl: SqliteDataLayer) -> None:
    store_carried_embargo(VulnerabilityCase(id_=_CASE, name="c"), dl)

    assert dl.list_objects("EmbargoEvent") == []


@pytest.mark.spec("EMB-18-003")
def test_an_inline_embargo_is_stored_as_its_own_record(
    dl: SqliteDataLayer,
) -> None:
    embargo = _embargo()
    case = VulnerabilityCase(id_=_CASE, name="c", active_embargo=embargo)

    store_carried_embargo(case, dl)

    assert isinstance(dl.read(embargo.id_), EmbargoEvent)


@pytest.mark.spec("EMB-18-003")
def test_a_bare_reference_the_store_holds_passes(dl: SqliteDataLayer) -> None:
    embargo = _embargo()
    dl.create(embargo)
    case = VulnerabilityCase(id_=_CASE, name="c", active_embargo=embargo.id_)

    store_carried_embargo(case, dl)


@pytest.mark.spec("EMB-18-003")
def test_a_bare_reference_the_store_lacks_is_refused(
    dl: SqliteDataLayer,
) -> None:
    missing = f"{_CASE}/embargo_events/missing"
    case = VulnerabilityCase(id_=_CASE, name="c", active_embargo=missing)

    with pytest.raises(VultronNotFoundError) as excinfo:
        store_carried_embargo(case, dl)

    assert excinfo.value.resource_id == missing


@pytest.mark.spec("EMB-18-003")
def test_a_reference_to_a_non_embargo_record_is_refused(
    dl: SqliteDataLayer,
) -> None:
    report = VulnerabilityReport(
        id_="https://example.org/reports/r1", name="r", content="c"
    )
    dl.create(report)
    case = VulnerabilityCase(id_=_CASE, name="c", active_embargo=report.id_)

    with pytest.raises(VultronValidationError):
        store_carried_embargo(case, dl)


@pytest.mark.spec("EMB-18-003")
def test_read_embargo_event_returns_the_held_record(
    dl: SqliteDataLayer,
) -> None:
    embargo = _embargo()
    dl.create(embargo)

    assert read_embargo_event(dl, embargo.id_).id_ == embargo.id_


@pytest.mark.spec("EMB-18-003")
def test_read_embargo_event_refuses_an_unheld_id(dl: SqliteDataLayer) -> None:
    with pytest.raises(VultronNotFoundError):
        read_embargo_event(dl, f"{_CASE}/embargo_events/missing")
