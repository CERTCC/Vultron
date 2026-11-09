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
"""``InProcessObjectFetcher`` GETs a profile from the app that serves it."""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchUse,
    ObjectReference,
)
from vultron.demo.in_process import InProcessObjectFetcher, InProcessRouter

BASE = "http://served.test"
ACTOR = f"{BASE}/api/v2/actors/author"


def _reference(actor_id: str = ACTOR) -> ObjectReference:
    return ObjectReference(
        object_id=actor_id,
        source=ObjectFetchSource.ACTOR_PROFILE,
        host_actor_id=actor_id,
        use=ObjectFetchUse.HAND_OFF,
    )


@pytest.fixture
def served() -> Iterator[tuple[InProcessRouter, dict[str, Any]]]:
    """A router with one app whose profile route answers as told."""
    answer: dict[str, Any] = {
        "status": 200,
        "body": {"id": ACTOR, "type": "Person"},
    }
    app = FastAPI()

    @app.get("/api/v2/actors/author/profile")
    def _profile() -> JSONResponse:
        return JSONResponse(answer["body"], status_code=answer["status"])

    router = InProcessRouter()
    with TestClient(app, base_url=BASE) as client:
        router.register(BASE, client)
        yield router, answer


def _fetch(router: InProcessRouter, actor_id: str = ACTOR) -> Any:
    fetcher = InProcessObjectFetcher(router)
    return asyncio.run(fetcher.fetch(_reference(actor_id), "receiver"))


def test_a_profile_is_fetched_from_the_app_that_serves_it(served):
    router, answer = served

    result = _fetch(router)

    assert result.body == answer["body"]
    assert result.failure is None
    assert result.attempts == 1


def test_a_host_no_app_serves_is_a_failed_fetch(served):
    router, _answer = served

    result = _fetch(router, "http://nobody.test/api/v2/actors/author")

    assert result.body is None
    assert "no in-process app serves" in result.failure


def test_an_error_status_is_a_failed_fetch(served):
    router, answer = served
    answer["status"] = 404

    result = _fetch(router)

    assert result.body is None
    assert "HTTP 404" in result.failure


def test_a_body_that_is_not_an_object_is_a_failed_fetch(served):
    router, answer = served
    answer["body"] = ["not", "an", "object"]

    result = _fetch(router)

    assert result.body is None
    assert "no JSON object" in result.failure
