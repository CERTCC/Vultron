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
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.routers import health as health_router


@pytest.fixture
def client_health():
    """A client for the health router.

    No DataLayer is injected: readiness probes the configured storage *location*
    via ``actor_hosts.storage_ready()``, not any actor's store.  Under ADR-0070
    there is no shared store to ``ping()``, and a node that has not seeded an
    actor yet is still ready.
    """
    app = FastAPI()
    app.include_router(health_router.router)
    client = TestClient(app)
    yield client


@pytest.fixture
def client_health_unready(monkeypatch):
    """A client whose storage probe reports not-ready.

    This used to inject a ``FailingDataLayer`` by overriding ``get_actor_dl``.
    The route has no such dependency any more, so the override did nothing and
    readiness kept answering 200 — the test could not fail for the reason it
    named.  Patch what readiness actually consults.
    """
    monkeypatch.setattr(
        "vultron.adapters.driven.actor_hosts.storage_ready", lambda: False
    )
    app = FastAPI()
    app.include_router(health_router.router)
    client = TestClient(app)
    yield client


@pytest.fixture
def client_health_probe_raises(monkeypatch):
    """A client whose storage probe raises rather than returning False."""

    def _boom():
        raise OSError("storage unavailable")

    monkeypatch.setattr(
        "vultron.adapters.driven.actor_hosts.storage_ready", _boom
    )
    app = FastAPI()
    app.include_router(health_router.router)
    client = TestClient(app)
    yield client


def test_liveness_returns_200(client_health):
    """OB-05-001: /health/live MUST return 200 when process is running."""
    resp = client_health.get("/health/live")
    assert resp.status_code == 200


def test_liveness_response_body(client_health):
    """OB-05-001: /health/live response body indicates status."""
    resp = client_health.get("/health/live")
    data = resp.json()
    assert data["status"] == "ok"


def test_readiness_returns_200(client_health):
    """OB-05-002: /health/ready MUST return 200 when ready to accept requests."""
    resp = client_health.get("/health/ready")
    assert resp.status_code == 200


def test_readiness_response_body(client_health):
    """OB-05-002: /health/ready response body indicates status."""
    resp = client_health.get("/health/ready")
    data = resp.json()
    assert data["status"] == "ok"


def test_readiness_returns_503_when_storage_not_ready(client_health_unready):
    """OB-05-002: /health/ready MUST return 503 when dependencies unavailable."""
    resp = client_health_unready.get("/health/ready")
    assert resp.status_code == 503


def test_readiness_returns_503_when_storage_probe_raises(
    client_health_probe_raises,
):
    """Readiness must never propagate an exception (OB-05-002).

    The route catches everything from the probe and reports not-ready, so a
    storage failure that raises is answered the same as one that returns False.
    """
    resp = client_health_probe_raises.get("/health/ready")
    assert resp.status_code == 503
