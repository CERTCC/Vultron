#!/usr/bin/env python
"""
Tests for data layer API serialization completeness.

Verifies that GET endpoints return all fields from stored objects,
not just base class fields.
"""

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

import pytest
from fastapi.testclient import TestClient

from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import (
    get_datalayer,
    reset_datalayer as _reset_datalayer,
)
from vultron.adapters.driving.fastapi.main import app
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# The read endpoint is actor-scoped: `/actors/{actor_id}/datalayer/{key}`
# (ADR-0072 — there is no unscoped `/datalayer/…` view, because it would read
# across actors).  The path segment resolves to a canonical URI by computation,
# so the actor these tests address has to be one this node could host: an id
# under some other authority resolves to a *different* actor, in a different
# store, and every read 404s.
ACTOR_SEGMENT = "test-actor"
ACTOR_ID = canonical_actor_uri(ACTOR_SEGMENT)


@pytest.fixture(autouse=True)
def datalayer():
    """The addressed actor's own in-memory store, reset around each test.

    The actor object itself is seeded, not just the objects under test: the read
    endpoint now lives under ``/actors/{actor_id}/``, so it resolves the actor
    before serving anything and answers ``404 Actor not found`` otherwise.  An
    actor's own record living in its own store is the Actor Knowledge Model, so
    this is setup the endpoint is entitled to expect.
    """
    _reset_datalayer(ACTOR_ID)
    dl = get_datalayer(ACTOR_ID, db_url="sqlite:///:memory:")
    dl.clear_all()
    dl.create(as_Service(id_=ACTOR_ID, name="Test Actor"))
    yield dl
    dl.clear_all()
    _reset_datalayer(ACTOR_ID)


@pytest.fixture
def client(datalayer):
    """A test client against the real dependency, over the fixture's store.

    There is deliberately no ``dependency_overrides`` here.  Two reasons, and
    the first is a trap worth naming: ``app`` *mounts* ``app_v2`` at
    ``/api/v2``, and Starlette does not propagate ``dependency_overrides`` into
    a mounted sub-app.  Overrides set on ``app`` never fire for any route under
    ``/api/v2`` — which is why the version of this fixture that overrode
    ``get_datalayer`` was inert twice over: wrong function *and* wrong app.

    Nothing needs overriding anyway.  The route's real dependency resolves the
    path segment and asks ``get_datalayer`` for that actor's store, and the
    ``datalayer`` fixture has already put an in-memory store for exactly that
    actor in the registry ``get_datalayer`` consults.  Passing ``db_url`` there
    is the documented alternative to injection, so the store under test is the
    fixture's without the request path being faked.
    """
    with TestClient(app) as c:
        yield c


def _dl_url(key: str) -> str:
    """The actor-scoped datalayer read URL for *key*."""
    return f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer/{key}"


def test_get_vulnerability_case_includes_vulnerability_reports_field(
    client, datalayer
):
    """
    Test that GET /datalayer/{key} includes vulnerability_reports field.

    Regression test for bug where FastAPI's response_model filtering
    excluded subclass-specific fields.
    """
    # Create a report
    report = as_VulnerabilityReport(
        name="Test Report", content="Test vulnerability content"
    )

    # Create a case with the report
    case = as_VulnerabilityCase(
        name=f"Case for Report {report.id_}",
        vulnerability_reports=[report],
        attributed_to="https://example.org/actor",
    )

    # Store both in data layer
    datalayer.create(report)
    datalayer.create(case)

    # Retrieve via API
    response = client.get(_dl_url(case.id_))

    assert response.status_code == 200
    data = response.json()

    # Verify response includes vulnerabilityReports field (camelCase)
    assert (
        "vulnerabilityReports" in data
    ), f"Response missing 'vulnerabilityReports' field. Keys: {list(data.keys())}"

    # Verify the field contains the report
    assert isinstance(data["vulnerabilityReports"], list)
    assert len(data["vulnerabilityReports"]) == 1
    assert data["vulnerabilityReports"][0] == report.id_


def test_get_vulnerability_case_includes_all_fields(client, datalayer):
    """
    Test that GET /datalayer/{key} includes all as_VulnerabilityCase fields.

    Ensures subclass-specific fields are not filtered by response_model.
    """
    # Create a case with various fields populated
    case = as_VulnerabilityCase(
        name="Comprehensive Test Case",
        attributed_to="https://example.org/actor",
        case_participants=[],  # Empty but should be included
        vulnerability_reports=[],  # Empty but should be included
        proposed_embargoes=[],  # Empty but should be included
        case_activity=[],  # Empty but should be included
    )

    # Store in data layer
    datalayer.create(case)

    # Retrieve via API
    response = client.get(_dl_url(case.id_))

    assert response.status_code == 200
    data = response.json()

    # Verify as_VulnerabilityCase-specific fields are present
    expected_fields = [
        "caseParticipants",
        "vulnerabilityReports",
        "caseStatuses",
        "proposedEmbargoes",
        "caseActivity",
        "parentCases",
        "childCases",
        "siblingCases",
    ]

    for field in expected_fields:
        assert (
            field in data
        ), f"Response missing '{field}' field. Keys: {list(data.keys())}"


def test_get_vulnerability_report_includes_all_fields(client, datalayer):
    """
    Test that GET /datalayer/{key} includes all as_VulnerabilityReport fields.

    Verifies the fix works for other subclasses too.
    """
    report = as_VulnerabilityReport(
        name="Test Report",
        content="Test vulnerability content",
        attributed_to="https://example.org/finder",
    )

    # Store in data layer
    datalayer.create(report)

    # Retrieve via API
    response = client.get(_dl_url(report.id_))

    assert response.status_code == 200
    data = response.json()

    # Verify as_VulnerabilityReport has content field (not in as_Base)
    assert (
        "content" in data
    ), f"Response missing 'content' field. Keys: {list(data.keys())}"
    assert data["content"] == "Test vulnerability content"


def test_test_datalayer_uses_in_memory_storage(datalayer):
    """Regression test: the test datalayer must use in-memory storage.

    Ensures the autouse fixture forces an in-memory SQLite database so no
    on-disk files are created during the test suite.

    This used to assert only ``isinstance(dl, SqliteDataLayer)``, which is true
    of a file-backed store too — so it could not have caught the thing its
    docstring describes.  Worse, it called ``get_datalayer`` without a
    ``db_url``, so on a cache miss it would resolve the *configured* URL and
    create the very on-disk file it was meant to rule out.  Assert the engine
    URL instead, and assert it of the fixture's store rather than a fresh one.
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    assert isinstance(datalayer, SqliteDataLayer)
    engine_url = str(datalayer._engine.url)
    assert "mode=memory" in engine_url or ":memory:" in engine_url, (
        f"Test datalayer must be in memory, got {engine_url!r}. "
        "Fix the autouse fixture to pass db_url='sqlite:///:memory:'."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
