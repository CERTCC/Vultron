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
"""An in-process delivery survives FastAPI losing its warning suppression (#6039).

FastAPI builds a ``ModelField`` for each route and override parameter, lazily on
the first request, on the ``TestClient`` portal thread.  Its ``TypeAdapter``
makes pydantic warn (``UnsupportedFieldAttributeWarning``) about the alias
FastAPI sets on every parameter.  FastAPI hides that warning inside
``warnings.catch_warnings()``, which on this interpreter edits the
process-global filter list.  When two portal threads do this at once, one
thread's exit drops the other's ``ignore`` entry, so ``filterwarnings =
["error"]`` used to turn the warning into a failed delivery.

The race cannot be scheduled, so these tests take FastAPI's suppression away,
which is the state the losing thread is in, and run under the project's own
``filterwarnings``.  The narrow ``ignore`` entry in ``pyproject.toml`` is what
lets the request succeed; without it these tests fail with the warning.
"""

from collections.abc import Callable, Iterator
from contextlib import nullcontext
from types import SimpleNamespace

import fastapi._compat.v2 as fastapi_v2
import pytest
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.app import create_app
from vultron.demo.in_process import InProcessRouter, create_isolated_actor_app


@pytest.fixture
def fastapi_suppression_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make FastAPI's own ``ignore`` of the warning a no-op, as the race does."""
    monkeypatch.setattr(
        fastapi_v2,
        "warnings",
        SimpleNamespace(
            catch_warnings=nullcontext,
            simplefilter=lambda *args, **kwargs: None,
        ),
    )


def _isolated_actor_client() -> Iterator[TestClient]:
    iso = create_isolated_actor_app(
        "http://warning-node.test", InProcessRouter(), actor_slug="vendor"
    )
    try:
        with iso.client as client:
            yield client
    finally:
        iso.close()


def _create_app_client() -> Iterator[TestClient]:
    with TestClient(create_app(docs_url=None, openapi_url=None)) as client:
        yield client


@pytest.mark.usefixtures("fastapi_suppression_lost")
@pytest.mark.parametrize(
    "client_factory",
    [_isolated_actor_client, _create_app_client],
    ids=["create_isolated_actor_app", "create_app"],
)
def test_actor_route_passes_under_project_filters_without_fastapis_suppression(
    client_factory: Callable[[], Iterator[TestClient]],
):
    """An actor-scoped request succeeds though FastAPI's ``ignore`` is gone."""
    for client in client_factory():
        resp = client.post(
            "/api/v2/actors/", json={"name": "Vendor", "id": "vendor"}
        )
        assert resp.status_code == 201

        resp = client.get("/api/v2/actors/vendor")

        assert resp.status_code == 200
