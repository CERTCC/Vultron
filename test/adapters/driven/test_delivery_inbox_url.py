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

Verifies that ``HttpDeliveryAdapter``'s inbox URL derivation formula
(``{actor_id}/inbox/``) produces URLs that are routable by the FastAPI
actors router registered in
``vultron/adapters/driving/fastapi/routers/actors.py``, that the inbox a
held profile names is used in its place (OX-12-009), and that the inbox a
hosted actor's profile states is routable too.

Spec: notes/multi-actor-architecture.md §4 G6,
      specs/multi-actor-demo.yaml DEMOMA-01-002, specs/outbox.yaml OX-12-009.
"""

from urllib.parse import urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test.support.emitter import RecordingEmitter
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.http_delivery import (
    HttpDeliveryAdapter,
    inbox_url_for,
)
from vultron.adapters.driving.fastapi import outbox_handler
from vultron.adapters.driving.fastapi.outbox_addressing import held_inboxes
from vultron.adapters.driving.fastapi.routers import actors as actors_router
from vultron.core.models.actor import (
    CoreActor,
    VultronOrganization,
    hosted_endpoints,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Organization

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTAINER_BASE = "http://finder:7999/api/v2"
_ACTOR_UUID = "aaaabbbb-0000-0000-0000-000000000001"
_ACTOR_ID = f"{_CONTAINER_BASE}/actors/{_ACTOR_UUID}"


def _derive_inbox_url(actor_id: str) -> str:
    """The inbox HttpDeliveryAdapter posts to when it holds none."""
    return inbox_url_for(actor_id)


@pytest.fixture
def http_delivery_attempts(monkeypatch) -> list[str]:
    """Every activity id handed to a real ``HttpDeliveryAdapter``.

    A tripwire, not a stub: a route test that reaches it would otherwise wait
    out the delivery retries against a host that does not exist (#5428).
    """
    attempts: list[str] = []

    async def _record(self, activity_id, *args, **kwargs) -> None:
        attempts.append(activity_id)

    monkeypatch.setattr(HttpDeliveryAdapter, "emit", _record)
    return attempts


@pytest.fixture
def inbox_client(dl, monkeypatch, http_delivery_attempts) -> TestClient:
    """A client on the actors router whose outbox sends nothing over HTTP.

    No dispatcher is installed, so every inbox post raises and is answered
    with a fault to its sender (ASK-07-010).  Both emitter paths record it
    instead of delivering it (notes/testing-pitfalls.md § "Patch Both Outbox
    Emitter Paths").
    """
    emitter = RecordingEmitter()
    monkeypatch.setattr(outbox_handler._DEFAULT_EMITTER_SLOT, "value", emitter)
    app = FastAPI()
    app.include_router(actors_router.router)
    app.dependency_overrides[get_datalayer] = lambda: dl
    app.dependency_overrides[actors_router.get_actor_dl] = lambda: dl
    app.state.emitter = emitter
    return TestClient(app, raise_server_exceptions=False)


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


@pytest.mark.spec("OX-12-009")
def test_a_held_inbox_is_used_in_place_of_the_derived_one():
    """The inbox the held profile names wins over the derived address."""
    held = "https://elsewhere.example/boxes/finder-in"
    assert inbox_url_for(_ACTOR_ID, {_ACTOR_ID: held}) == held


@pytest.mark.spec("OX-12-009")
def test_a_recipient_with_no_held_inbox_gets_the_derived_one():
    """Only a recipient the sender holds no inbox for falls back."""
    other = "https://elsewhere.example/actors/other"
    assert inbox_url_for(other, {_ACTOR_ID: "https://x.example/in"}) == (
        f"{other}/inbox/"
    )


@pytest.mark.spec("OX-12-009")
def test_held_inboxes_reads_the_sender_store(dl):
    """A held profile's inbox is mapped; a peer known by URI only is not."""
    stated = "https://elsewhere.example/actors/stated"
    bare = "https://elsewhere.example/actors/bare"
    unknown = "https://elsewhere.example/actors/unknown"
    dl.create(
        VultronOrganization(
            id_=stated,
            name="Stated",
            inbox="https://elsewhere.example/boxes/stated-in",
        )
    )
    dl.create(CoreActor(id_=bare, published=None, updated=None))

    assert held_inboxes(dl, [stated, bare, unknown]) == {
        stated: "https://elsewhere.example/boxes/stated-in"
    }


@pytest.mark.spec("OX-12-009")
def test_held_inboxes_reads_a_wire_profile_inbox_collection():
    """A held wire profile's inbox collection maps to its address."""
    from unittest.mock import MagicMock

    stated = "https://elsewhere.example/actors/wire"
    held = as_Organization.model_validate(
        {"id": stated, "inbox": "https://elsewhere.example/boxes/wire-in"}
    )
    dl = MagicMock()
    dl.read.side_effect = {stated: held}.get

    assert held_inboxes(dl, [stated]) == {
        stated: "https://elsewhere.example/boxes/wire-in"
    }


@pytest.mark.spec("OX-12-009")
def test_the_inbox_a_hosted_profile_states_accepts_post(
    dl, inbox_client, http_delivery_attempts
):
    """A sender holding a hosted actor's profile posts to its stated inbox.

    ``hosted_endpoints`` states ``{id}/inbox`` without the trailing slash the
    derived address carries, so both must answer a POST.
    """
    from vultron.adapters.driven.actor_hosts import canonical_actor_uri

    local_actor_id = canonical_actor_uri(_ACTOR_UUID)
    dl.create(
        object_to_record(
            as_Organization.model_validate(
                {
                    "name": "Finder",
                    "id": local_actor_id,
                    **hosted_endpoints(local_actor_id),
                }
            )
        )
    )
    stated = hosted_endpoints(local_actor_id)["inbox"]
    base_path = urlparse(local_actor_id).path.removesuffix(
        f"/actors/{_ACTOR_UUID}"
    )
    path = urlparse(stated).path.removeprefix(base_path)
    payload = as_Activity(actor=_ACTOR_ID).model_dump(
        by_alias=True, exclude_none=True, mode="json"
    )

    resp = inbox_client.post(path, json=payload)

    assert resp.status_code == 202, (resp.status_code, path)
    assert http_delivery_attempts == []


def test_derived_inbox_path_matches_fastapi_route(
    dl, inbox_client, http_delivery_attempts
):
    """G6: POST to derived inbox path returns 202, not 404.

    Creates an actor this node hosts, derives its inbox URL with the delivery
    adapter's formula, reduces that to the path the mounted app_v2 sees, and
    verifies the FastAPI actors router accepts a POST to it.  What is under test
    is that the two agree on the route shape.
    """
    # The actor has to be one *this* node could host.  A trigger route resolves
    # its path segment by computation — ``base_url + "actors/" + segment``
    # (ADR-0073#url-segment-computed-not-looked-up) — so an id under another authority, like the
    # ``http://finder:7999`` one the derivation tests above use, resolves to a
    # different actor and the POST 404s for a reason that has nothing to do with
    # the route shape this test is checking.  The derivation tests keep the remote
    # id, because deriving an inbox URL for a remote recipient is exactly what
    # delivery does.
    from vultron.adapters.driven.actor_hosts import canonical_actor_uri

    local_actor_id = canonical_actor_uri(_ACTOR_UUID)
    actor = as_Organization(
        name="Finder",
        id_=local_actor_id,
    )
    dl.create(object_to_record(actor))

    # Derive inbox URL using the same formula as HttpDeliveryAdapter.
    inbox_url = _derive_inbox_url(local_actor_id)

    # Reduce to the path the mounted app_v2 sees. The base URL may carry a path
    # prefix (``/api/v2`` in the container images), so strip whatever it has
    # rather than a hard-coded one.
    parsed = urlparse(inbox_url)
    base_path = urlparse(local_actor_id).path.removesuffix(
        f"/actors/{_ACTOR_UUID}"
    )
    path_relative_to_app_v2 = parsed.path.removeprefix(base_path)

    # POST a minimal activity to the derived inbox path.
    activity = as_Activity(actor=_ACTOR_ID)
    payload = activity.model_dump(
        by_alias=True, exclude_none=True, mode="json"
    )

    resp = inbox_client.post(path_relative_to_app_v2, json=payload)

    # 202 Accepted (not 404) confirms the route pattern is consistent.
    assert resp.status_code == 202, (
        f"Expected 202 Accepted; got {resp.status_code}. "
        f"Path: {path_relative_to_app_v2}. "
        "This indicates inbox URL derivation is inconsistent with FastAPI routing."
    )
    assert http_delivery_attempts == []


def test_inbox_url_path_relative_to_app_v2_has_actors_prefix():
    """G6: path relative to app_v2 starts with /actors/ followed by the actor UUID."""
    inbox_url = _derive_inbox_url(_ACTOR_ID)
    parsed = urlparse(inbox_url)
    path_relative = parsed.path.removeprefix("/api/v2")
    assert path_relative == f"/actors/{_ACTOR_UUID}/inbox/"
