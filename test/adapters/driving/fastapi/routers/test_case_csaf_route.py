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
"""The operator's CSAF read, ``GET {actor}/cases/{case_key}/csaf`` (ADR-0219).

The route returns the joined projection of a case from the addressed
actor's own replica, with ``tracking.status`` ``interim``, and writes
nothing (CSAF-06-012, CSAF-06-013).
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from test.support.case_projection import (
    CASE_ID,
    JOINED_ONLY_VALUES,
    store_projected_replica,
)
from test.support.csaf_schema import schema_errors
from test.support.objects import make
from vultron.adapters.driven import case_projection as projection_adapters
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    get_datalayer,
    reset_datalayer,
)
from vultron.adapters.utils import strip_id_prefix
from vultron.core.models.case_projection_profile import JOINED_PROFILE
from vultron.core.models.ledger_position import LedgerPosition
from vultron.errors import VultronValidationError

_SLUG = "csaf-operator"


@pytest.fixture
def host() -> Iterator[SqliteDataLayer]:
    """The addressed actor's own store, holding a replica of the case."""
    host_id = canonical_actor_uri(_SLUG)
    reset_datalayer(host_id)
    dl = get_datalayer(host_id, db_url="sqlite:///:memory:")
    yield dl
    reset_datalayer(host_id)


def _get(client: TestClient, case_key: str = strip_id_prefix(CASE_ID)):
    return client.get(f"/actors/{_SLUG}/cases/{case_key}/csaf")


def _snapshot(dl: SqliteDataLayer) -> dict[str, Any]:
    """Every row of every table, and the inbox and outbox queues."""
    rows: dict[str, Any] = {
        table: dl.get_all(table) for table in dl.count_all()
    }
    rows["inbox"] = dl.inbox_list()
    rows["outbox"] = dl.outbox_list()
    return rows


@pytest.mark.spec("CSAF-06-012")
@pytest.mark.spec("CSAF-06-004")
def test_the_endpoint_returns_the_joined_interim_projection(
    client_actors: TestClient, host: SqliteDataLayer
) -> None:
    store_projected_replica(host)

    response = _get(client_actors)

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("application/json")
    rendered = response.json()
    assert schema_errors(rendered) == []
    document = rendered["document"]
    assert document["category"] == "csaf_base"
    assert document["tracking"]["status"] == "interim"
    assert document["distribution"]["tlp"]["label"] == (
        JOINED_PROFILE.distribution.value
    )
    assert f"/{JOINED_PROFILE.name}/" in document["tracking"]["id"]
    assert JOINED_ONLY_VALUES["content"] in response.text


def test_the_publisher_is_the_addressed_actor(
    client_actors: TestClient, host: SqliteDataLayer
) -> None:
    store_projected_replica(host)

    publisher = _get(client_actors).json()["document"]["publisher"]

    assert publisher["namespace"] == "http://localhost:7999/"
    assert publisher["name"] == canonical_actor_uri(_SLUG)


@pytest.mark.spec("CSAF-06-004")
def test_the_endpoint_takes_its_category_from_the_shared_selection(
    client_actors: TestClient,
    host: SqliteDataLayer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_projected_replica(host)
    asked: list[object] = []

    def selection(preview: object) -> str:
        asked.append(preview)
        return "csaf_base"

    monkeypatch.setattr(projection_adapters.csaf, "csaf_category", selection)

    _get(client_actors)

    (preview,) = asked
    assert getattr(preview, "id_", None) == CASE_ID


def test_a_case_the_actor_does_not_hold_is_404(
    client_actors: TestClient, host: SqliteDataLayer
) -> None:
    response = _get(client_actors, "https://example.org/cases/unknown")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_a_replica_without_the_entry_at_its_position_is_409(
    client_actors: TestClient, host: SqliteDataLayer
) -> None:
    case = store_projected_replica(host)
    case.ledger_position = LedgerPosition(log_index=9, entry_hash="09" * 32)
    host.save(case)

    response = _get(client_actors)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "ledger index 9" in response.json()["detail"]


def test_a_preview_that_renders_no_document_is_409(
    client_actors: TestClient,
    host: SqliteDataLayer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cut that gives no document fails the read as the draft step fails:
    the projection could not be made, answered 409, never a 500."""
    store_projected_replica(host)

    def refuse(*_: object, **__: object) -> None:
        raise VultronValidationError("the preview shows no ledger position")

    monkeypatch.setattr(projection_adapters.csaf, "render_csaf", refuse)

    response = _get(client_actors)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "no ledger position" in response.json()["detail"]


@pytest.mark.spec("CSAF-06-013")
def test_the_endpoint_writes_nothing(
    client_actors: TestClient, host: SqliteDataLayer
) -> None:
    """No row changes, no ledger entry is added and no activity is queued
    for delivery, nor is anything held for the inbox."""
    store_projected_replica(host)
    before = _snapshot(host)
    ledger_before = before["CaseLedgerEntry"]

    response = _get(client_actors)

    assert response.status_code == status.HTTP_200_OK
    after = _snapshot(host)
    assert after == before
    assert after["CaseLedgerEntry"] == ledger_before
    assert after["outbox"] == []


@pytest.mark.spec("CSAF-06-013")
def test_the_write_check_is_not_vacuous(host: SqliteDataLayer) -> None:
    """The snapshot sees a write: a saved record changes it."""
    from vultron.core.models.note import VultronNote

    store_projected_replica(host)
    before = _snapshot(host)

    host.save(make(VultronNote, content="A write", context=CASE_ID))

    assert _snapshot(host) != before
