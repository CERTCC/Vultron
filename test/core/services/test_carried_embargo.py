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

from test.support.case_owner import CASE_OWNER_ID
from test.support.embargo_register import register
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.report import VulnerabilityReport
from vultron.core.services.carried_embargo import (
    carried_entry_embargo,
    entry_embargo,
    store_carried_embargo,
)
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
    store_carried_embargo(
        VulnerabilityCase(attributed_to=CASE_OWNER_ID, id_=_CASE, name="c"), dl
    )

    assert dl.list_objects("EmbargoEvent") == []


@pytest.mark.spec("EMB-18-003")
def test_an_inline_embargo_is_stored_as_its_own_record(
    dl: SqliteDataLayer,
) -> None:
    embargo = _embargo()
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE,
        name="c",
        embargo_register=register(active=embargo),
    )

    store_carried_embargo(case, dl)

    assert isinstance(dl.read(embargo.id_), EmbargoEvent)


@pytest.mark.spec("EMB-18-003")
@pytest.mark.spec("EMB-18-004")
def test_an_inline_embargo_of_another_case_is_refused_unstored(
    dl: SqliteDataLayer,
) -> None:
    """A sender cannot plant another case's embargo under its id."""
    other_case = "https://example.org/cases/other"
    foreign = EmbargoEvent(
        id_=f"{other_case}/embargo_events/e1",
        context=other_case,
        end_time=days_from_now_utc(45),
    )
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE,
        name="c",
        embargo_register=register(active=foreign),
    )

    with pytest.raises(VultronValidationError, match=other_case):
        store_carried_embargo(case, dl)

    assert dl.read(foreign.id_) is None


@pytest.mark.spec("EMB-18-003")
def test_a_bare_reference_the_store_holds_passes(dl: SqliteDataLayer) -> None:
    embargo = _embargo()
    dl.create(embargo)
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE,
        name="c",
        embargo_register=register(active=embargo.id_),
    )

    store_carried_embargo(case, dl)


@pytest.mark.spec("EMB-18-003")
def test_a_bare_reference_the_store_lacks_is_refused(
    dl: SqliteDataLayer,
) -> None:
    missing = f"{_CASE}/embargo_events/missing"
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE,
        name="c",
        embargo_register=register(active=missing),
    )

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
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE,
        name="c",
        embargo_register=register(active=report.id_),
    )

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


def _snapshot(**overrides: object) -> dict[str, object]:
    embargo = _embargo()
    return {
        "type": "EmbargoEvent",
        "id": embargo.id_,
        "context": _CASE,
        "endTime": embargo.end_time.isoformat(),
        **overrides,
    }


@pytest.mark.spec("EMB-18-003")
@pytest.mark.parametrize("key", ["id", "id_"])
def test_an_entrys_inline_embargo_is_returned_unstored(
    dl: SqliteDataLayer, key: str
) -> None:
    snapshot = _snapshot()
    embargo_id = _embargo().id_
    del snapshot["id"]
    snapshot[key] = embargo_id

    embargo = carried_entry_embargo(dl, _CASE, snapshot)

    assert isinstance(embargo, EmbargoEvent)
    assert embargo.id_ == embargo_id
    assert dl.read(embargo_id) is None


@pytest.mark.spec("EMB-18-003")
@pytest.mark.parametrize("as_reference", [True, False])
def test_an_entrys_embargo_the_store_holds_needs_nothing(
    dl: SqliteDataLayer, as_reference: bool
) -> None:
    embargo = _embargo()
    dl.create(embargo)
    data: object = embargo.id_ if as_reference else _snapshot()

    assert carried_entry_embargo(dl, _CASE, data) is None


@pytest.mark.spec("EMB-18-003")
@pytest.mark.parametrize("data", [None, "", {}, {"id": ""}, {"type": "x"}])
def test_an_entry_naming_no_embargo_is_refused(
    dl: SqliteDataLayer, data: object
) -> None:
    with pytest.raises(VultronValidationError, match="names no embargo"):
        carried_entry_embargo(dl, _CASE, data)


@pytest.mark.spec("EMB-18-003")
def test_an_entrys_bare_reference_the_store_lacks_is_refused(
    dl: SqliteDataLayer,
) -> None:
    missing = f"{_CASE}/embargo_events/missing"

    with pytest.raises(VultronNotFoundError) as excinfo:
        carried_entry_embargo(dl, _CASE, missing)

    assert excinfo.value.resource_id == missing


@pytest.mark.spec("EMB-18-003")
def test_an_entrys_malformed_inline_embargo_is_refused(
    dl: SqliteDataLayer,
) -> None:
    with pytest.raises(VultronValidationError, match="malformed"):
        carried_entry_embargo(dl, _CASE, _snapshot(endTime="not a time"))


@pytest.mark.spec("EMB-18-003")
@pytest.mark.spec("EMB-18-004")
def test_an_entrys_inline_embargo_of_another_case_is_refused(
    dl: SqliteDataLayer,
) -> None:
    other_case = "https://example.org/cases/other"

    with pytest.raises(VultronValidationError, match=other_case):
        carried_entry_embargo(dl, _CASE, _snapshot(context=other_case))


@pytest.mark.spec("EMB-18-003")
def test_an_entry_naming_a_held_non_embargo_record_is_refused(
    dl: SqliteDataLayer,
) -> None:
    report = VulnerabilityReport(
        id_="https://example.org/reports/r2", name="r", content="c"
    )
    dl.create(report)

    with pytest.raises(VultronValidationError):
        carried_entry_embargo(dl, _CASE, report.id_)


@pytest.mark.spec("EMB-18-003")
@pytest.mark.spec("CM-23-016")
def test_an_entrys_inline_embargo_is_copied_as_carried_not_as_held(
    dl: SqliteDataLayer,
) -> None:
    """The register copies the CASE_MANAGER's record, not a local copy."""
    held = _embargo()
    dl.create(held)

    embargo = entry_embargo(dl, _CASE, _snapshot(content="Terms"))

    assert embargo.content == "Terms"
    assert held.content is None


@pytest.mark.spec("EMB-18-003")
def test_an_entrys_bare_reference_reads_the_held_embargo(
    dl: SqliteDataLayer,
) -> None:
    held = _embargo()
    dl.create(held)

    assert entry_embargo(dl, _CASE, held.id_).id_ == held.id_


@pytest.mark.spec("EMB-18-003")
def test_an_entrys_unheld_bare_reference_is_not_found(
    dl: SqliteDataLayer,
) -> None:
    with pytest.raises(VultronNotFoundError):
        entry_embargo(dl, _CASE, f"{_CASE}/embargo_events/missing")


@pytest.mark.spec("EMB-18-004")
def test_an_entrys_copied_embargo_of_another_case_is_refused(
    dl: SqliteDataLayer,
) -> None:
    other_case = "https://example.org/cases/other"

    with pytest.raises(VultronValidationError, match=other_case):
        entry_embargo(dl, _CASE, _snapshot(context=other_case))


_OTHER_CASE = "https://example.org/cases/other"


def _held_for_other_case(dl: SqliteDataLayer) -> EmbargoEvent:
    """Store, under this case's embargo id, a record of another case."""
    foreign = EmbargoEvent(
        id_=_embargo().id_,
        context=_OTHER_CASE,
        end_time=days_from_now_utc(45),
    )
    dl.create(foreign)
    return foreign


@pytest.mark.spec("EMB-18-004")
@pytest.mark.parametrize("as_reference", [True, False])
def test_a_case_naming_a_held_embargo_of_another_case_is_refused_unwritten(
    dl: SqliteDataLayer, as_reference: bool
) -> None:
    """A bare id, or an inline copy, whose held record is another case's."""
    foreign = _held_for_other_case(dl)
    active: EmbargoEvent | str = foreign.id_ if as_reference else _embargo()
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE,
        name="c",
        embargo_register=register(active=active),
    )

    with pytest.raises(VultronValidationError, match=_OTHER_CASE):
        store_carried_embargo(case, dl)

    assert read_embargo_event(dl, foreign.id_).context == _OTHER_CASE
    assert len(dl.list_objects("EmbargoEvent")) == 1


@pytest.mark.spec("EMB-18-004")
@pytest.mark.parametrize("as_reference", [True, False])
def test_an_entry_naming_a_held_embargo_of_another_case_is_refused(
    dl: SqliteDataLayer, as_reference: bool
) -> None:
    foreign = _held_for_other_case(dl)
    data: object = foreign.id_ if as_reference else _snapshot()

    with pytest.raises(VultronValidationError, match=_OTHER_CASE):
        carried_entry_embargo(dl, _CASE, data)


@pytest.mark.spec("EMB-18-004")
@pytest.mark.parametrize("as_reference", [True, False])
def test_an_entrys_copied_held_embargo_of_another_case_is_refused(
    dl: SqliteDataLayer, as_reference: bool
) -> None:
    foreign = _held_for_other_case(dl)
    data: object = foreign.id_ if as_reference else _snapshot()

    with pytest.raises(VultronValidationError, match=_OTHER_CASE):
        entry_embargo(dl, _CASE, data)


_REPORT = "https://example.org/reports/carried-report"
_OTHER_REPORT = "https://example.org/reports/other-report"


def _held_for_report(dl: SqliteDataLayer, report_id: str) -> EmbargoEvent:
    """Store a Reporter's pre-case proposal, about *report_id* (EP-04-009)."""
    proposal = EmbargoEvent(
        id_=_embargo().id_,
        context=report_id,
        end_time=days_from_now_utc(45),
    )
    dl.create(proposal)
    return proposal


def _case_with_report(
    active: EmbargoEvent | str, *, inline_report: bool = False
) -> VulnerabilityCase:
    """This case, holding ``_REPORT`` by id or as an inline report."""
    report: VulnerabilityReport | str = (
        VulnerabilityReport(id_=_REPORT, name="r", content="c")
        if inline_report
        else _REPORT
    )
    return VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE,
        name="c",
        vulnerability_reports=[report],
        embargo_register=register(active=active),
    )


@pytest.mark.spec("EMB-18-004")
@pytest.mark.spec("EP-04-009")
@pytest.mark.parametrize("inline_report", [False, True])
@pytest.mark.parametrize("as_reference", [True, False])
def test_a_held_proposal_about_the_cases_own_report_is_accepted(
    dl: SqliteDataLayer, as_reference: bool, inline_report: bool
) -> None:
    """The Reporter holds its proposal about the report the case holds."""
    proposal = _held_for_report(dl, _REPORT)

    store_carried_embargo(
        _case_with_report(
            proposal.id_ if as_reference else _embargo(),
            inline_report=inline_report,
        ),
        dl,
    )

    assert read_embargo_event(dl, proposal.id_).context == _REPORT


@pytest.mark.spec("EMB-18-004")
@pytest.mark.parametrize("as_reference", [True, False])
def test_a_held_proposal_about_another_cases_report_is_refused(
    dl: SqliteDataLayer, as_reference: bool
) -> None:
    proposal = _held_for_report(dl, _OTHER_REPORT)

    with pytest.raises(VultronValidationError, match=_OTHER_REPORT):
        store_carried_embargo(
            _case_with_report(proposal.id_ if as_reference else _embargo()),
            dl,
        )

    assert len(dl.list_objects("EmbargoEvent")) == 1


@pytest.mark.spec("EMB-18-004")
def test_an_inline_embargo_about_another_cases_report_is_refused_unstored(
    dl: SqliteDataLayer,
) -> None:
    foreign = EmbargoEvent(
        id_=f"{_CASE}/embargo_events/e1",
        context=_OTHER_REPORT,
        end_time=days_from_now_utc(45),
    )

    with pytest.raises(VultronValidationError, match=_OTHER_REPORT):
        store_carried_embargo(_case_with_report(foreign), dl)

    assert dl.read(foreign.id_) is None


@pytest.mark.spec("EMB-18-004")
@pytest.mark.spec("EP-04-009")
@pytest.mark.parametrize("as_reference", [True, False])
def test_an_entry_naming_a_held_proposal_about_the_cases_report_is_accepted(
    dl: SqliteDataLayer, as_reference: bool
) -> None:
    """The ledger helpers read the report ids from the stored case."""
    dl.create(_case_with_report(_embargo().id_))
    proposal = _held_for_report(dl, _REPORT)
    data: object = proposal.id_ if as_reference else _snapshot()

    assert carried_entry_embargo(dl, _CASE, data) is None
    assert entry_embargo(dl, _CASE, data).id_ == proposal.id_


@pytest.mark.spec("EMB-18-004")
@pytest.mark.parametrize("as_reference", [True, False])
def test_an_entry_naming_a_held_proposal_about_another_report_is_refused(
    dl: SqliteDataLayer, as_reference: bool
) -> None:
    dl.create(_case_with_report(_embargo().id_))
    proposal = _held_for_report(dl, _OTHER_REPORT)
    data: object = proposal.id_ if as_reference else _snapshot()

    with pytest.raises(VultronValidationError, match=_OTHER_REPORT):
        carried_entry_embargo(dl, _CASE, data)
    with pytest.raises(VultronValidationError, match=_OTHER_REPORT):
        entry_embargo(dl, _CASE, data)


@pytest.mark.spec("EMB-18-004")
@pytest.mark.spec("EP-04-009")
def test_an_inline_embargo_about_the_cases_report_is_stored(
    dl: SqliteDataLayer,
) -> None:
    """With nothing held, an inline copy about the case's report is stored."""
    carried = EmbargoEvent(
        id_=_embargo().id_, context=_REPORT, end_time=days_from_now_utc(45)
    )

    store_carried_embargo(_case_with_report(carried), dl)

    assert read_embargo_event(dl, carried.id_).context == _REPORT


@pytest.mark.spec("EMB-18-004")
@pytest.mark.spec("EP-04-009")
def test_an_entrys_inline_embargo_about_the_cases_report_is_accepted(
    dl: SqliteDataLayer,
) -> None:
    """The entry helpers read the report from the stored case."""
    dl.create(_case_with_report(_embargo().id_))
    data = _snapshot(context=_REPORT)

    carried = carried_entry_embargo(dl, _CASE, data)
    assert carried is not None and carried.context == _REPORT
    assert entry_embargo(dl, _CASE, data).context == _REPORT


@pytest.mark.spec("EMB-18-004")
@pytest.mark.parametrize("as_reference", [True, False])
def test_an_entry_on_a_case_not_held_accepts_no_report_context(
    dl: SqliteDataLayer, as_reference: bool
) -> None:
    """A store without the case knows none of its reports."""
    proposal = _held_for_report(dl, _REPORT)
    data: object = proposal.id_ if as_reference else _snapshot(context=_REPORT)

    with pytest.raises(VultronValidationError, match=_REPORT):
        carried_entry_embargo(dl, _CASE, data)
    with pytest.raises(VultronValidationError, match=_REPORT):
        entry_embargo(dl, _CASE, data)


@pytest.mark.spec("EMB-18-004")
@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"context": _OTHER_CASE}, id="another-case"),
        pytest.param({"endTime": "not a time"}, id="malformed"),
    ],
)
def test_an_entrys_bad_inline_copy_is_refused_though_the_record_is_held(
    dl: SqliteDataLayer, overrides: dict[str, object]
) -> None:
    """The inline copy is checked even when this case's record is held."""
    dl.create(_embargo())

    with pytest.raises(VultronValidationError):
        carried_entry_embargo(dl, _CASE, _snapshot(**overrides))
    with pytest.raises(VultronValidationError):
        entry_embargo(dl, _CASE, _snapshot(**overrides))
