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
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from test.support.emitter import RecordingEmitter
from test.support.signing import post_delivered, serve_published_profiles
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.core.models.actor import CoreActor
from vultron.core.ports.datalayer import DataLayer


@contextmanager
def served_store(
    dl: DataLayer,
    actor_id: str,
    name: str,
    actor: CoreActor | None = None,
    *,
    existing: bool = False,
) -> Iterator[tuple[TestClient, RecordingEmitter]]:
    """Serve *dl*, the store of actor *actor_id*, with a real app.

    The store's actor record is *actor* when given, else a bare actor named
    *name* with its hosted endpoints. With *existing*, *dl* already holds the
    actor, as a store does when its process restarts, so nothing is written.
    Every author that posts to it publishes its profile
    (:func:`serve_published_profiles`), so the inbox verifies each signed
    body by its author's key; a test of an unreadable key installs its own
    fetcher on ``client.app``.
    """
    if not existing:
        dl.create(
            object_to_record(
                actor
                or CoreActor(
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
        serve_published_profiles(app)
        yield client, emitter


def get_from_store(
    store: Path, segment: str, path: str, *, existing: bool = False
) -> httpx.Response:
    """GET *path* from a real app serving the store file *store*.

    The store belongs to the actor at *segment*. A new store is provisioned
    with that actor; with *existing*, the file already holds it, as it does
    when its process restarts. A file per store: two in-memory stores for one
    actor id share their rows, so the second would find the first one's actor
    record.
    """
    actor_id = canonical_actor_uri(segment)
    dl = SqliteDataLayer(f"sqlite:///{store}", actor_id=actor_id)
    try:
        with served_store(dl, actor_id, segment, existing=existing) as (
            client,
            _emitter,
        ):
            return client.get(path)
    finally:
        dl.close()


#: Post an already-signed body to an inbox and check it is accepted; the
#: redelivery suites post the same signed bytes twice (IE-10-001).
post = post_delivered


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
