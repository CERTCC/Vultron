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
"""Shared helpers for the FastAPI failed-act redelivery tests.

Each test serves one actor's store with a real app, posts a body to its
inbox, and checks that a later post of the same body was routed as the copy
intake archived (IE-10-001).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from test.support.emitter import RecordingEmitter
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.core.models.actor import CoreActor
from vultron.core.ports.datalayer import DataLayer


@contextmanager
def served_store(
    dl: DataLayer, actor_id: str, name: str
) -> Iterator[tuple[TestClient, RecordingEmitter]]:
    """Serve *dl*, the store of actor *actor_id*, with a real app."""
    dl.create(
        object_to_record(
            CoreActor(
                id_=actor_id,
                name=name,
                inbox=f"{actor_id}/inbox",
                outbox=f"{actor_id}/outbox",
            )
        )
    )
    app = create_app(docs_url=None, openapi_url=None)
    app.dependency_overrides[get_actor_dl] = lambda actor_id: dl
    emitter = RecordingEmitter()
    with TestClient(app) as client:
        app.state.emitter = emitter
        yield client, emitter


def post(client: TestClient, inbox: str, body: dict[str, Any]) -> None:
    """Post *body* to *inbox*; the inbox accepts it for processing."""
    response = client.post(inbox, json=body)
    assert response.status_code == 202, response.text


def assert_routed_as_archived_redelivery(
    caplog: pytest.LogCaptureFixture, activity_id: str
) -> None:
    """The ingress adapter found intake's archive and rebuilt the activity.

    Without this the test could pass on a path that never meets the archive
    (IE-10-001).
    """
    assert any(
        activity_id in r.getMessage()
        and "already held (archived)" in r.getMessage()
        for r in caplog.records
    ), "the post was not routed as a redelivery"


def faults(emitter: RecordingEmitter) -> list[dict[str, Any]]:
    """Every delivered ``Create(ProcessingFault)``."""
    return [
        body
        for body, _to in emitter.sent
        if body["type"] == "Create"
        and isinstance(body.get("object"), dict)
        and body["object"].get("type") == "ProcessingFault"
    ]
