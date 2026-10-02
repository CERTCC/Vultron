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

"""StagedCasePersistence: writes held back, then committed as one (#4142)."""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle.staged_persistence import (
    StagedCasePersistence,
    StagedPersistenceError,
)
from vultron.errors import VultronAlreadyExistsError, VultronError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import _make_case, _record_save_many


@pytest.fixture()
def dl(owner_and_dl: tuple[as_Service, SqliteDataLayer]) -> SqliteDataLayer:
    return owner_and_dl[1]


def _case(dl: SqliteDataLayer) -> VulnerabilityCase:
    case, _ = _make_case(dl, "https://example.org/actors/owner")
    return case


def test_satisfies_the_case_persistence_port(dl: SqliteDataLayer) -> None:
    port: CasePersistence = StagedCasePersistence(dl)
    assert port.actor_id == dl.actor_id


# -- read after stage ---------------------------------------------------------


def test_a_staged_save_is_read_back_before_the_flush(
    dl: SqliteDataLayer,
) -> None:
    case = _case(dl)
    staged = StagedCasePersistence(dl)
    case.name = "renamed"
    staged.save(case)

    assert cast(VulnerabilityCase, staged.read(case.id_)).name == "renamed"
    read_case = staged.read_case(case.id_)
    assert read_case is not None and read_case.name == "renamed"
    # The underlying store has not seen it.
    assert cast(VulnerabilityCase, dl.read(case.id_)).name != "renamed"


def test_reads_are_copies_so_only_a_save_changes_the_staged_object(
    dl: SqliteDataLayer,
) -> None:
    case = _case(dl)
    staged = StagedCasePersistence(dl)
    staged.save(case)
    case.name = "changed after the save"

    first = cast(VulnerabilityCase, staged.read(case.id_))
    first.name = "changed after the read"

    assert cast(VulnerabilityCase, staged.read(case.id_)).name != (
        "changed after the read"
    )
    assert staged.staged[0].model_dump() != case.model_dump()


def test_a_staged_non_case_shadows_the_store_for_read_case(
    dl: SqliteDataLayer,
) -> None:
    case = _case(dl)
    staged = StagedCasePersistence(dl)
    embargo = as_EmbargoEvent(
        id_=case.id_, context=case.id_, end_time=days_from_now_utc(9)
    )
    staged.save(embargo)

    assert staged.read_case(case.id_) is None
    with pytest.raises(ValueError, match="not a VulnerabilityCase"):
        staged.read_case(case.id_, raise_on_missing=True)


def test_an_unstaged_read_delegates_to_the_store(dl: SqliteDataLayer) -> None:
    case = _case(dl)
    staged = StagedCasePersistence(dl)

    assert staged.read_case(case.id_) == dl.read_case(case.id_)
    assert staged.read("https://example.org/absent") is None
    assert staged.read_case("https://example.org/absent") is None


def test_a_staged_create_is_read_back_and_refused_twice(
    dl: SqliteDataLayer,
) -> None:
    case = _case(dl)
    staged = StagedCasePersistence(dl)
    embargo = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(9))
    staged.create(embargo)

    assert staged.read(embargo.id_) == embargo
    assert dl.read(embargo.id_) is None
    with pytest.raises(VultronAlreadyExistsError):
        staged.create(embargo)


def test_create_refuses_an_id_the_store_already_holds(
    dl: SqliteDataLayer,
) -> None:
    case = _case(dl)
    with pytest.raises(VultronAlreadyExistsError):
        StagedCasePersistence(dl).create(case)


# -- flush --------------------------------------------------------------------


def test_flush_commits_everything_through_one_save_many_in_staging_order(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _case(dl), _case(dl)
    calls = _record_save_many(dl, monkeypatch)
    staged = StagedCasePersistence(dl)
    staged.save(first)
    staged.save(second)
    first.name = "saved again"
    staged.save_many([first])

    staged.flush()

    (committed,) = calls
    # A later save replaces the content but keeps the first-staged position.
    assert [obj.id_ for obj in committed] == [first.id_, second.id_]
    assert cast(VulnerabilityCase, dl.read(first.id_)).name == "saved again"
    assert staged.staged == []


def test_flush_with_nothing_staged_writes_nothing(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _record_save_many(dl, monkeypatch)
    StagedCasePersistence(dl).flush()
    assert calls == []


def test_a_failed_flush_keeps_the_staging_and_writes_nothing(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(dl)
    staged = StagedCasePersistence(dl)
    case.name = "never committed"
    staged.save(case)

    def failing_save_many(objs: list[PersistableModel]) -> None:
        raise VultronError("forced store fault")

    monkeypatch.setattr(dl, "save_many", failing_save_many)
    with pytest.raises(VultronError, match="forced store fault"):
        staged.flush()

    assert [obj.id_ for obj in staged.staged] == [case.id_]
    assert cast(VulnerabilityCase, dl.read(case.id_)).name != (
        "never committed"
    )


# -- what the staging cannot answer -------------------------------------------


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("list_objects", ("VulnerabilityCase",)),
        ("find_case_by_report_id", ("https://example.org/reports/r",)),
        ("find_actor_by_short_id", ("owner",)),
        ("find_case_by_short_id", ("case",)),
        (
            "find_protocol_pair",
            ("https://example.org/cases/c", "Invite", "o", frozenset()),
        ),
    ],
)
def test_a_query_is_refused_while_writes_are_staged_and_delegated_otherwise(
    dl: SqliteDataLayer, method: str, args: tuple[object, ...]
) -> None:
    staged = StagedCasePersistence(dl)
    expected = getattr(dl, method)(*args)
    actual = getattr(staged, method)(*args)
    if method == "list_objects":
        expected, actual = list(expected), list(actual)
    assert actual == expected

    staged.save(_case(dl))
    with pytest.raises(StagedPersistenceError, match="staged"):
        getattr(staged, method)(*args)


def test_delete_and_a_store_switch_are_refused(dl: SqliteDataLayer) -> None:
    case = _case(dl)
    staged = StagedCasePersistence(dl)

    with pytest.raises(StagedPersistenceError):
        staged.delete("VulnerabilityCase", case.id_)
    with pytest.raises(StagedPersistenceError):
        staged.clone_for_actor("https://example.org/actors/other")
    assert dl.read(case.id_) is not None
