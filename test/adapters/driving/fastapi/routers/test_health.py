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

from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driving.fastapi.routers import health as health_router


@pytest.fixture
def client_health(datalayer):
    app = FastAPI()
    app.include_router(health_router.router)
    app.dependency_overrides[get_datalayer] = lambda: datalayer
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def client_health_failing():
    class FailingDataLayer:
        def read(self, *args, **kwargs):
            raise OSError("storage unavailable")

    app = FastAPI()
    app.include_router(health_router.router)
    app.dependency_overrides[get_datalayer] = lambda: FailingDataLayer()
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


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


def test_readiness_returns_503_when_datalayer_fails(client_health_failing):
    """OB-05-002: /health/ready MUST return 503 when dependencies unavailable."""
    resp = client_health_failing.get("/health/ready")
    assert resp.status_code == 503
