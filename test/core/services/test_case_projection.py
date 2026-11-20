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
"""Projecting an actor's replica through a render port (ADR-0219).

:func:`~vultron.core.services.case_projection.project_case` is the core half
of both projection call sites: it reads the case whole from the actor's own
store, cuts it, gathers the call site's inputs and hands both to the port.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import JsonValue

from test.support.case_projection import (
    CASE_ID,
    COMMITTED_AT,
    COORDINATOR,
    PROJECTOR,
    REPORTER,
    VENDOR,
    ledger_entry,
    position_of,
    projected_case,
    store_projected_replica,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.datalayer_sqlite.engine import fresh_memory_url
from vultron.core.models.case_projection import (
    Acknowledgment,
    ProjectionCut,
    ProjectionInputs,
    PublicationStatus,
)
from vultron.core.models.case_projection_profile import (
    JOINED_PROFILE,
    PUBLIC_PROFILE,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.vulnerability_item import VulnerabilityItem
from vultron.core.ports.case_projection import CaseProjectionPort
from vultron.core.services.case_projection import (
    case_held_whole,
    position_committed_at,
    project_case,
    projecting_actor,
)
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronNotFoundError,
    VultronProjectionError,
    VultronWiringError,
)


class _Recording:
    """A projection port that records what it is given."""

    def __init__(self) -> None:
        self.calls: list[tuple[ProjectionCut, ProjectionInputs]] = []

    def render(
        self, cut: ProjectionCut, inputs: ProjectionInputs
    ) -> dict[str, JsonValue]:
        self.calls.append((cut, inputs))
        return {"rendered": cut.profile_name}


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    with SqliteDataLayer(
        fresh_memory_url("case-projection"), actor_id=COORDINATOR
    ) as store:
        yield store


def _project(dl: SqliteDataLayer, port: Any, **overrides: Any):
    args: dict[str, Any] = {
        "case_id": CASE_ID,
        "actor_id": COORDINATOR,
        "profile": JOINED_PROFILE,
        "status": PublicationStatus.INTERIM,
        "port": port,
        **overrides,
    }
    return project_case(dl, **args)


def test_the_recording_port_is_a_projection_port() -> None:
    assert isinstance(_Recording(), CaseProjectionPort)


@pytest.mark.spec("CSAF-06-001")
@pytest.mark.parametrize("profile", [PUBLIC_PROFILE, JOINED_PROFILE])
def test_the_port_gets_the_cut_by_the_call_sites_profile(
    dl: SqliteDataLayer, profile: Any
) -> None:
    store_projected_replica(dl)
    port = _Recording()

    rendered = _project(dl, port, profile=profile)

    assert rendered == {"rendered": profile.name}
    ((cut, _),) = port.calls
    assert cut.profile is profile
    assert cut.preview.id_ == CASE_ID


@pytest.mark.parametrize(
    "status", [PublicationStatus.FINAL, PublicationStatus.INTERIM]
)
def test_the_inputs_carry_the_call_sites_status(
    dl: SqliteDataLayer, status: PublicationStatus
) -> None:
    store_projected_replica(dl)
    port = _Recording()

    _project(dl, port, status=status)

    ((_, inputs),) = port.calls
    assert inputs.status is status


@pytest.mark.spec("CSAF-06-007")
def test_the_inputs_date_the_document_by_the_positions_commit(
    dl: SqliteDataLayer,
) -> None:
    store_projected_replica(dl)
    port = _Recording()

    _project(dl, port)

    ((_, inputs),) = port.calls
    assert inputs.position_committed_at == COMMITTED_AT


def test_the_publisher_is_the_projecting_actor_with_its_case_roles(
    dl: SqliteDataLayer,
) -> None:
    store_projected_replica(dl)
    port = _Recording()

    _project(dl, port)

    ((_, inputs),) = port.calls
    assert inputs.projecting_actor.id_ == COORDINATOR
    assert inputs.projecting_actor.name == PROJECTOR.name
    assert inputs.projecting_actor.roles == (CVDRole.COORDINATOR,)


@pytest.mark.spec("CSAF-06-009")
def test_the_default_credit_is_the_reporter_the_store_holds_by_id(
    dl: SqliteDataLayer,
) -> None:
    """The stored case names its participants by id; the default still
    credits its ``REPORTER``, read from the store, and no caller credit is
    given."""
    case = store_projected_replica(dl)
    assert all(isinstance(p, str) for p in case.case_participants)
    port = _Recording()

    _project(dl, port)

    ((_, inputs),) = port.calls
    assert inputs.caller_acknowledgments is None
    (credit,) = inputs.default_acknowledgments
    assert isinstance(credit, Acknowledgment)
    assert len(credit.names) == 1


def test_a_case_the_store_does_not_hold_is_not_found(
    dl: SqliteDataLayer,
) -> None:
    with pytest.raises(VultronNotFoundError):
        _project(dl, _Recording())


@pytest.mark.parametrize("port", [None, object()], ids=["missing", "wrong"])
def test_a_missing_port_is_a_wiring_error_before_any_read(
    dl: SqliteDataLayer, port: object
) -> None:
    """No case is stored: the port is checked first, so the error is the
    wiring fault, not the missing case."""
    with pytest.raises(VultronWiringError):
        _project(dl, port)


def test_an_object_the_replica_does_not_hold_refuses_the_projection(
    dl: SqliteDataLayer,
) -> None:
    store_projected_replica(
        dl, vulnerability_items=["urn:uuid:an-item-this-store-lacks"]
    )

    with pytest.raises(VultronProjectionError, match="does not hold"):
        _project(dl, _Recording())


def test_the_case_is_read_whole_and_the_store_is_not_changed(
    dl: SqliteDataLayer,
) -> None:
    case = store_projected_replica(dl)
    item = next(
        i for i in case.vulnerability_items if isinstance(i, VulnerabilityItem)
    )
    dl.create(item)
    case.vulnerability_items = [item.id_]
    dl.save(case)

    whole = case_held_whole(case, dl)

    assert [type(p).__name__ for p in whole.case_participants] == [
        "CaseParticipant"
    ] * 3
    assert whole.vulnerability_items == [item]
    stored = dl.read_case(CASE_ID)
    assert stored is not None
    assert stored.vulnerability_items == [item.id_]
    assert all(isinstance(p, str) for p in stored.case_participants)


def test_the_commit_time_is_the_entry_at_the_position() -> None:
    later = COMMITTED_AT.replace(hour=13)
    tail = ledger_entry(1, MessageSemantics.VALIDATE_REPORT, actor=VENDOR)
    entries = [
        ledger_entry(0, MessageSemantics.SUBMIT_REPORT, actor=REPORTER),
        tail.model_copy(update={"published": later}),
    ]
    case = projected_case(ledger_position=position_of(entries))

    assert position_committed_at(case, entries) == later


@pytest.mark.parametrize(
    "position",
    [
        LedgerPosition(log_index=5, entry_hash="05" * 32),
        LedgerPosition(log_index=0, entry_hash="ff" * 32),
    ],
    ids=["index-not-held", "hash-differs"],
)
def test_a_position_the_ledger_does_not_hold_refuses_the_projection(
    position: LedgerPosition,
) -> None:
    entries = [ledger_entry(0, MessageSemantics.SUBMIT_REPORT, actor=REPORTER)]

    with pytest.raises(VultronProjectionError, match="no entry there"):
        position_committed_at(
            projected_case(ledger_position=position), entries
        )


def test_an_actor_with_no_record_publishes_under_its_id(
    dl: SqliteDataLayer,
) -> None:
    case = case_held_whole(store_projected_replica(dl), dl)

    actor = projecting_actor(case, VENDOR, dl)

    assert actor.name == VENDOR
    assert actor.roles == (CVDRole.VENDOR,)


def test_a_register_embargo_named_by_id_is_read_whole(
    dl: SqliteDataLayer,
) -> None:
    """The disclosure date reads the in-force embargo's end, so an embargo
    the register names by id is read from the store."""
    case = store_projected_replica(dl)
    (entry,) = case.embargo_register
    embargo = entry.embargo
    assert isinstance(embargo, EmbargoEvent)
    dl.save(embargo)
    by_id = case.model_copy(
        update={
            "embargo_register": [
                entry.model_copy(update={"embargo": embargo.id_})
            ]
        }
    )

    (held,) = case_held_whole(by_id, dl).embargo_register

    assert held.embargo == embargo
