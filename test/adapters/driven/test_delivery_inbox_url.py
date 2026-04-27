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

"""Integration test: inbox URL derivation consistency (D5-1-G6).

Verifies that ``DeliveryQueueAdapter``'s inbox URL derivation formula
(``{actor_id}/inbox/``) produces URLs that are routable by the FastAPI
actors router registered in
``vultron/adapters/driving/fastapi/routers/actors.py``.

Spec: notes/multi-actor-architecture.md §4 G6,
      specs/multi-actor-demo.md DEMOMA-01-002.
"""

from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driving.fastapi.routers import actors as actors_router
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Organization

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTAINER_BASE = "http://finder:7999/api/v2"
_ACTOR_UUID = "aaaabbbb-0000-0000-0000-000000000001"
_ACTOR_ID = f"{_CONTAINER_BASE}/actors/{_ACTOR_UUID}"


def _derive_inbox_url(actor_id: str) -> str:
    """Mirror of the DeliveryQueueAdapter inbox URL derivation logic."""
    return actor_id.rstrip("/") + "/inbox/"


# ---------------------------------------------------------------------------
# URL derivation unit tests
# ---------------------------------------------------------------------------


def test_inbox_url_derived_by_appending_inbox_slash():
    """G6: inbox URL is actor_id with /inbox/ appended (no trailing slash on actor_id)."""
    actor_id = "http://finder:7999/api/v2/actors/test-uuid"
    assert (
        _derive_inbox_url(actor_id)
        == "http://finder:7999/api/v2/actors/test-uuid/inbox/"
    )


def test_inbox_url_trailing_slash_on_actor_id_normalised():
    """G6: trailing slash on actor_id is stripped before appending /inbox/."""
    actor_id = "http://finder:7999/api/v2/actors/test-uuid/"
    assert (
        _derive_inbox_url(actor_id)
        == "http://finder:7999/api/v2/actors/test-uuid/inbox/"
    )


def test_inbox_url_ends_with_inbox_slash():
    """G6: derived inbox URL always ends with /inbox/."""
    actor_id = _ACTOR_ID
    inbox_url = _derive_inbox_url(actor_id)
    assert inbox_url.endswith("/inbox/")


def test_inbox_url_contains_actor_uuid():
    """G6: derived inbox URL preserves the actor UUID segment."""
    inbox_url = _derive_inbox_url(_ACTOR_ID)
    assert _ACTOR_UUID in inbox_url


# ---------------------------------------------------------------------------
# FastAPI route consistency tests
# ---------------------------------------------------------------------------


def test_derived_inbox_path_matches_fastapi_route(dl):
    """G6: POST to derived inbox path returns 202, not 404.

    Creates an actor whose id_ matches the Docker-style full URI
    (``http://finder:7999/api/v2/actors/{uuid}``), derives the inbox URL,
    strips the container base URL prefix to get the path relative to the
    mounted app_v2, and verifies the FastAPI actors router accepts a POST
    to that path.
    """
    actor = as_Organization(
        name="Finder",
        id_=_ACTOR_ID,
    )
    dl.create(object_to_record(actor))

    app = FastAPI()
    app.include_router(actors_router.router)
    app.dependency_overrides[get_datalayer] = lambda: dl
    app.dependency_overrides[actors_router._shared_dl] = lambda: dl

    client = TestClient(app, raise_server_exceptions=False)

    # Derive inbox URL using the same formula as DeliveryQueueAdapter.
    inbox_url = _derive_inbox_url(_ACTOR_ID)

    # Strip the container prefix to get the path relative to app_v2.
    # app_v2 is mounted at /api/v2, so the remaining path is /actors/{uuid}/inbox/
    parsed = urlparse(inbox_url)
    # path = /api/v2/actors/{uuid}/inbox/ → relative to app_v2: /actors/{uuid}/inbox/
    path_relative_to_app_v2 = parsed.path.removeprefix("/api/v2")

    # POST a minimal activity to the derived inbox path.
    activity = as_Activity(actor=_ACTOR_ID)
    payload = activity.model_dump(
        by_alias=True, exclude_none=True, mode="json"
    )

    resp = client.post(path_relative_to_app_v2, json=payload)

    # 202 Accepted (not 404) confirms the route pattern is consistent.
    assert resp.status_code == 202, (
        f"Expected 202 Accepted; got {resp.status_code}. "
        f"Path: {path_relative_to_app_v2}. "
        "This indicates inbox URL derivation is inconsistent with FastAPI routing."
    )

    app.dependency_overrides = {}


def test_inbox_url_path_relative_to_app_v2_has_actors_prefix():
    """G6: path relative to app_v2 starts with /actors/ followed by the actor UUID."""
    inbox_url = _derive_inbox_url(_ACTOR_ID)
    parsed = urlparse(inbox_url)
    path_relative = parsed.path.removeprefix("/api/v2")
    assert path_relative == f"/actors/{_ACTOR_UUID}/inbox/"
