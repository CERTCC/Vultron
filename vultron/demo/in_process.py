#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""In-process multi-node hosting for demo scenarios.

Each container of the Docker demo topology becomes one FastAPI app with its own
in-memory storage deployment, driven through a :class:`TestClient`.  Deliveries
between the apps go through :class:`InProcessRouter`, the only sanctioned
in-process transport (ADR-0042, OX-12-003).

The demo tests (``test/demo/``) and the scenario recorder
(:mod:`vultron.demo.recordings`) share these pieces, so a
recording runs on the same harness the tests trust.
"""

import functools
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import anyio.to_thread
import httpx2 as httpx
from fastapi import FastAPI, Path as FastAPIPath
from fastapi.testclient import TestClient

from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    get_datalayer,
)
from vultron.adapters.driven.http_delivery import DeliveryError, inbox_url_for
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.deps import get_actor_dl

logger = logging.getLogger(__name__)

_NODE_NAME_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def node_db_url(base_url: str) -> str:
    """Return a named in-memory storage deployment private to one node.

    ``actor_db_url`` derives a store from the **final path segment** of an actor
    id, dropping scheme and netloc, so ``http://vendor.test/…/actors/case-actor``
    and ``http://coordinator.test/…/actors/case-actor`` resolve to one store
    (:func:`~vultron.adapters.driven.datalayer_sqlite.engine.actor_slug`).
    Under Docker that is harmless-by-accident: each container has its own volume,
    so the two ``mydb-case-actor.sqlite`` files are different files.
    In this harness every node is an app in one process, so the anonymous
    ``sqlite:///:memory:`` template would put them in the *same* store — and a
    node that wrongly opened a store for a **foreign** actor would find the real
    one sitting there, fully populated, making the defect undetectable locally.
    After ADR-0081 the collision is unreachable in production, but naming the
    deployment per node remains the right discipline for a multi-node harness.

    Naming the deployment per node restores the container boundary: the base
    name is carried through to every per-actor store, so a cross-node slug
    collision resolves to two distinct empty stores exactly as it does in
    Docker (``_memory_base_name``).

    Args:
        base_url: The node's base URL, e.g. ``"http://vendor.test"``.

    Returns:
        A named shared-cache in-memory URL template for that node alone.
    """
    name = _NODE_NAME_UNSAFE_RE.sub("_", base_url.rstrip("/"))
    return f"sqlite:///file:node-{name}?mode=memory&cache=shared&uri=true"


#: Hosts that are intentionally unreachable in tests (known-fictional external URLs).
#: Drops to these hosts are expected and logged at DEBUG.
#: Drops to any other unregistered host are logged at WARNING — almost always
#: a config-cache leak or missing :meth:`InProcessRouter.register` call.
_KNOWN_FICTIONAL_HOSTS: frozenset[str] = frozenset({"vultron.example"})


class InProcessRouter:
    """Cross-app delivery adapter for isolated multi-actor test setups.

    Routes outbound activity delivery to the correct actor app based on the
    recipient's base URL, POSTing to that app's :class:`TestClient` inbox
    endpoint.  Install via ``configure_default_emitter`` so that when Actor A
    delivers to a recipient hosted on Actor B's app, the activity is routed
    to Actor B's ``TestClient`` — the only sanctioned in-process transport
    (ADR-0042, ``outbox.yaml`` OX-12-003) — instead of a real HTTP request.

    Use :meth:`register` to map base URLs to their ``TestClient`` instances
    after entering each client's context (the ``TestClient`` must be entered so
    its portal is live before any delivery is routed to it).

    .. note::

       ``emit()`` runs inside a FastAPI ``BackgroundTask`` on the *sending*
       app's ``TestClient`` portal event loop.  The target ``TestClient.post``
       call is blocking and drives the target app on its own portal thread, so
       it is dispatched via :func:`anyio.to_thread.run_sync` to avoid blocking
       (and, for CaseActor ``cc:``-to-self loopback delivery where sender and
       target share one portal, deadlocking) the calling event loop.
    """

    def __init__(self) -> None:
        self._clients: dict[str, TestClient] = {}
        self._failing_hosts: set[str] = set()

    def register(self, base_url: str, client: "TestClient") -> None:
        """Register *client* as the delivery target for *base_url*."""
        self._clients[base_url.rstrip("/")] = client

    def inject_failure(self, base_url: str) -> None:
        """Cause all subsequent emits to *base_url* to raise ``DeliveryError``.

        The failure persists until the caller removes *base_url* from
        ``_failing_hosts`` directly.  Use this to simulate a temporarily
        unreachable host: inject the failure before a drain pass, assert the
        activity was requeued, then clear the set and drain again to verify
        the retry path.
        """
        self._failing_hosts.add(base_url.rstrip("/"))

    async def emit(
        self,
        activity_id: str,
        json_body: str,
        recipients: list[str],
        inboxes: Mapping[str, str] | None = None,
    ) -> None:
        """Deliver the sealed *json_body* to each recipient's registered client.

        Posts the body exactly as the outbox handler hands it over, as the
        production ``HttpDeliveryAdapter`` does (VM-08-003): a test double
        that re-serialised would mask any divergence between what the ledger
        recorded and what the wire carried.  It posts to the same inbox the
        production adapter would (OX-12-009).
        """
        for recipient_id in recipients:
            parsed = urlparse(inbox_url_for(recipient_id, inboxes))
            base = f"{parsed.scheme}://{parsed.netloc}"
            if base in self._failing_hosts:
                raise DeliveryError([recipient_id], activity_id)
            client = self._clients.get(base)
            if client is None:
                host = parsed.hostname or ""
                level = (
                    logging.DEBUG
                    if host in _KNOWN_FICTIONAL_HOSTS
                    else logging.WARNING
                )
                logger.log(
                    level,
                    "InProcessRouter: no client registered for %s,"
                    " dropping delivery to %s",
                    base,
                    recipient_id,
                )
                continue
            if client.portal is None:
                # The target's `with client` block has exited (a timeout trip
                # or a failed assertion), but a delivery chain is still running
                # in a worker thread.  Posting now would start a one-shot
                # portal whose loop the inbox lock is not bound to, logging
                # `is bound to a different event loop` as if it were the
                # failure's cause (#4882).
                logger.warning(
                    "InProcessRouter: client for %s is not entered,"
                    " dropping delivery to %s",
                    base,
                    recipient_id,
                )
                continue
            inbox_path = parsed.path
            try:
                # TestClient.post is blocking and drives the target app on its
                # own portal thread; run it off the calling event loop so a
                # loopback delivery (sender == target) cannot deadlock.
                post = functools.partial(
                    client.post,
                    inbox_path,
                    content=json_body,
                    headers={"Content-Type": "application/json"},
                )
                response = await anyio.to_thread.run_sync(post)
                response.raise_for_status()
                logger.info(
                    "InProcessRouter: delivered to %s (HTTP %s)",
                    inbox_path,
                    response.status_code,
                )
            except Exception as exc:  # noqa: BLE001  # ruff-baseline #3989
                logger.warning(
                    "InProcessRouter: delivery to %s failed: %s",
                    inbox_path,
                    exc,
                )


@dataclass
class IsolatedActorApp:
    """Holds a FastAPI app and TestClient pair with isolated per-actor state.

    Each ``IsolatedActorApp`` instance represents a separate logical actor
    container in tests.  The ``app`` has its own ``DataLayer`` injected via
    ``dependency_overrides`` and its own ``HttpDeliveryAdapter`` stored on
    ``app.state.emitter``, so no state leaks between actors.

    Attributes:
        app: The FastAPI application instance for this actor.
        client: A ``TestClient`` wrapping ``app`` with a deterministic
            ``base_url`` (e.g. ``http://actor-name.test``).
        dl: The isolated in-memory ``SqliteDataLayer`` for this actor.
        base_url: The base URL used to construct actor IDs.
        actor_id: Canonical URI of this app's own actor — the one ``dl`` belongs
            to. Exposed so a test can address it without rebuilding the URL.
        db_url: This node's storage-deployment template, private to it the way a
            container's volume is (see :func:`node_db_url`).
    """

    app: FastAPI
    client: TestClient
    dl: SqliteDataLayer
    base_url: str
    actor_id: str = ""
    db_url: str = "sqlite:///:memory:"

    def store_for(self, actor_id: str) -> SqliteDataLayer:
        """Return the store of *actor_id* as hosted by this app.

        ``dl`` is only ever *one* actor's store — the app's own, named by
        ``actor_slug`` at construction.  A container may host more actors than
        that (a participant plus the CaseActors it self-hosts, CP-08-003), and a
        test that creates its actor under a per-test slug is asking about a
        different store than ``dl``.  Reading ``dl`` in that case reports an empty
        store and the assertion fails for the wrong reason.

        Built through ``get_datalayer`` with the same ``db_url`` the app's
        ``get_actor_dl`` override uses, so it is the *same instance* the routes
        are handed — and, because that template is this node's alone, a store
        this method opens is this node's copy and not a same-slug actor's on
        another node (:func:`node_db_url`).

        Args:
            actor_id: Canonical URI of an actor hosted by this app.
        """
        return get_datalayer(actor_id, db_url=self.db_url)


def create_isolated_actor_app(
    base_url: str,
    router: "InProcessRouter",
    actor_slug: str = "primary",
) -> "IsolatedActorApp":
    """Create an isolated FastAPI app for a single actor in tests.

    Creates a fresh :class:`FastAPI` application via :func:`create_app`,
    injects an in-memory :class:`SqliteDataLayer` via ``dependency_overrides``,
    and registers the app with the shared :class:`InProcessRouter` so that
    deliveries to this actor are routed to its ``TestClient`` inbox instead of
    making real HTTP requests (ADR-0042, OX-12-003).

    The actor's ``TestClient`` is registered with *router* under *base_url*.
    The client reference is stable, but callers MUST enter its context
    (``with iso.client``) before any delivery is routed to it so its portal is
    live.

    Args:
        base_url: Base URL for this actor (e.g. ``"http://reporter.test"``).
            Actor IDs will use this as their URL prefix.
        router: Shared :class:`InProcessRouter` instance that all apps
            register with so cross-app deliveries are routed correctly.
        actor_slug: Final path segment of *this app's own* actor. Determines
            which store ``dl`` addresses, so a test that seeds or asserts through
            ``dl`` MUST pass the slug it creates its actor under. Routing does not
            depend on it — every actor gets its own store via the per-actor
            override below — but ``dl`` has to name one of them.

    Returns:
        An :class:`IsolatedActorApp` whose ``client`` context manager has
        *not* been entered yet — callers must use it as a context manager.
    """
    # This app's own node root, declared on the app so every dependency resolves
    # segments into *this* node's namespace rather than the process-global
    # configured one — several of these apps run in one process, so there is no
    # single configured answer that is right for all of them (ISSUE-2238).
    node_root = f"{base_url.rstrip('/')}/api/v2"

    # This node's own storage deployment, so a store opened for a foreign actor
    # is this node's empty copy rather than the owning node's populated one —
    # the container boundary Docker gets from separate volumes (see node_db_url).
    db_url = node_db_url(base_url)

    def _in_memory_actor_dl(actor_id: str = FastAPIPath(...)):
        """Route per actor, in memory.

        Overriding with a single fixed DataLayer pinned every actor id to one
        store, which is what made this harness unable to find an actor it had
        just created: ``create_actor`` writes through the per-actor factory
        (correctly), so creation and lookup landed in different stores and the
        actor came back ``404 Actor not found`` (ADR-0073 / ISSUE-2238). Only the
        backing URL is replaced here; which store a segment selects is part of
        what these tests exercise.
        """
        return get_datalayer(
            canonical_actor_uri(actor_id, base_url=node_root),
            db_url=db_url,
        )

    app = create_app(docs_url=None, openapi_url=None, node_base_url=node_root)
    app.dependency_overrides[get_actor_dl] = _in_memory_actor_dl
    # Declared on the app, not only wired into the override: routes whose subject
    # actor is named in the request body (actor creation) have no path segment to
    # scope on and read this instead (``deps.node_db_url_template``).  Without it
    # they would open the process-global store while every other route reads this
    # node's, so an actor would 404 immediately after being created.
    app.state.db_url = db_url

    # `dl` is this app's own actor's store, for tests that seed or assert
    # directly. Built through `get_datalayer` so it is the *same instance* the
    # override hands the routes, and so the actor registers as hosted here.
    own_actor_id = f"{base_url.rstrip('/')}/api/v2/actors/{actor_slug}"
    isolated_dl = get_datalayer(own_actor_id, db_url=db_url)

    # TestClient is not yet entered; the caller drives the lifecycle.
    client = TestClient(app, base_url=base_url)
    router.register(base_url, client)
    return IsolatedActorApp(
        app=app,
        client=client,
        dl=isolated_dl,
        base_url=base_url,
        actor_id=own_actor_id,
        db_url=db_url,
    )


def response_value(response: httpx.Response, method: str, url: str) -> Any:
    """Return what :meth:`DataLayerClient.call` returns for *response*.

    For a :class:`TestClient` standing in for a container.  An error status
    raises :class:`httpx.HTTPStatusError`, as the real client does, **not** a
    bare ``AssertionError``: callers branch on the code, and
    ``ledger_dump._fetch_entries`` reads a 404 as "this container does not
    hold this case".  A body that is not JSON is returned as text.
    """
    if response.status_code >= 400:
        raise httpx.HTTPStatusError(
            f"API call failed: {method.upper()} {url} --> "
            f"{response.status_code} {response.text}",
            request=response.request,
            response=response,
        )
    try:
        return response.json()
    except ValueError:
        return response.text
