#!/usr/bin/env python

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

"""Shared FastAPI dependency providers for driving adapters.

This module centralises the DataLayer and TriggerService dependencies so
that all trigger routers share the same injectable seams.  Tests override
a single dependency (``get_trigger_dl`` or ``get_trigger_service``) rather
than overriding per-router local functions.

Functions
---------
get_actor_dl
    Return the DataLayer belonging to the actor named by the ``{actor_id}``
    path segment.  This is the single actor-scoping seam for all routes.
node_db_url_template
    Return the storage template the serving app was built with, so a route
    whose subject actor is named in the *body* opens a store in the same
    deployment the path-scoped routes read.
get_trigger_dl
    Alias of :func:`get_actor_dl`, kept as a distinct override point for
    trigger-route tests.
get_canonical_actor_dl
    Alias of :func:`get_actor_dl`.
get_hosted_actor_dls
    Return every store this node hosts, keyed by canonical actor URI, for
    node-level operations such as the admin reset.
get_trigger_service
    Construct and return a :class:`~vultron.core.use_cases.triggers.service.TriggerService`.

Under ADR-0072 there is no shared DataLayer to inject, so every one of these
resolves the path segment to a canonical actor URI by computation and returns
that actor's own store.  The ``{actor_id}`` path parameter is no longer
"accepted but unused".
"""

from fastapi import Depends, Path, Request
from typing import cast

from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_service import TriggerServicePort
from vultron.core.use_cases.triggers.service import TriggerService


def node_base_url(request: Request | None) -> str | None:
    """Return the base URL of the node serving *request*, if it declares one.

    An actor's canonical URI is ``{node base URL}/actors/{slug}``, so resolving a
    path segment needs to know which node is answering.  Process-global
    configuration is the right answer in deployment, where one process is one
    node.  It is the wrong answer in a harness that runs several nodes in one
    process: every app would resolve segments into the same node's namespace.

    So the value is *app*-scoped — fixed when the app is built (``create_app``)
    and read from ``app.state`` here.  Deliberately not derived from the incoming
    request's URL: that would let a client change which store the node opens by
    changing its ``Host`` header, and would break every test that reaches an app
    through ``TestClient``'s ``http://testserver`` default.

    Returns ``None`` when the app declares nothing, leaving callers to fall back
    to configuration — which keeps production behaviour unchanged.
    """
    if request is None:
        return None
    value = getattr(request.app.state, "node_base_url", None)
    return value if isinstance(value, str) and value else None


def node_db_url_template(request: Request | None) -> str | None:
    """Return the storage template the serving app was built with, if any.

    Every store this node opens must come from one deployment.  ``get_actor_dl``
    guarantees that for routes whose subject actor arrives as a path segment,
    because they can be given an overridden dependency.  A route whose subject
    actor is named in the *request body* — actor creation — has no segment to
    scope on and so reached for the module-global ``get_datalayer`` instead,
    which reads process-global configuration and ignores
    ``dependency_overrides`` entirely.

    In deployment the two agree: one process is one node with one configured
    ``db_url``.  In a harness running several nodes in one process they do not,
    and the split is silent — the *record* of a newly created actor lands in the
    process-global store while every subsequent route reads the app's own, so
    the actor answers ``404`` immediately after a ``201``.

    App-scoped for the same reason :func:`node_base_url` is: it is fixed when
    the app is built and is not derivable from the incoming request.  Returning
    ``None`` when the app declares nothing leaves callers on configuration,
    which keeps production behaviour unchanged.
    """
    if request is None:
        return None
    value = getattr(request.app.state, "db_url", None)
    return value if isinstance(value, str) and value else None


def get_actor_dl(
    actor_id: str = Path(...),
    request: Request = None,  # type: ignore[assignment]
) -> DataLayer:
    """FastAPI dependency: the DataLayer belonging to the addressed actor.

    Resolves the ``{actor_id}`` path segment to a canonical actor URI by
    computation and returns that actor's own store (ADR-0072).

    This replaces the previous two-step dance — inject the shared DataLayer,
    scan it to turn a short id into a canonical URI, then ``clone_for_actor`` —
    which existed only because actor identity had to be *discovered* from a
    shared pool.  It also retires BUG-2026040901 structurally: there is only
    one store for an actor, so a queue can no longer be written under one
    spelling of its id and read under another.

    The segment is resolved against the *serving app's* base URL when it declares
    one (see :func:`node_base_url`), so a harness hosting several nodes in one
    process resolves each app's segments into that app's own namespace.
    """
    return cast(
        DataLayer,
        get_datalayer(
            canonical_actor_uri(actor_id, base_url=node_base_url(request)),
            db_url=node_db_url_template(request),
        ),
    )


def get_trigger_dl(
    dl: DataLayer = Depends(get_actor_dl),
) -> DataLayer:
    """FastAPI dependency: the addressed actor's DataLayer for trigger routes.

    Kept as a separate name from :func:`get_actor_dl` purely so that trigger
    routes remain independently overridable in tests
    (``app.dependency_overrides[get_trigger_dl]``).

    Delegates through ``Depends`` rather than calling :func:`get_actor_dl`
    directly: a plain call bypasses the override table, so
    ``app.dependency_overrides[get_actor_dl]`` would apply to ``/actors/*``
    routes and *not* to ``/actors/{id}/trigger/*`` — one app reading two
    different stores for the same actor.
    """
    return dl


def get_canonical_actor_dl(
    dl: DataLayer = Depends(get_actor_dl),
) -> DataLayer:
    """FastAPI dependency: alias of :func:`get_actor_dl`.

    Retained so existing trigger routes and their test overrides keep working;
    the "canonical" qualifier is now redundant because every actor DataLayer is
    keyed by the canonical URI.

    Delegates through ``Depends`` for the reason given in
    :func:`get_trigger_dl`.
    """
    return dl


def get_hosted_actor_dls(
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, DataLayer]:
    """FastAPI dependency: every store this node hosts, keyed by actor URI.

    Node-level operations (the admin reset) have no single store to act on under
    ADR-0072, so they need the whole set.  Resolving it through a dependency
    rather than calling ``get_datalayer`` in a loop is what makes it
    *overridable*: an app whose stores were supplied by
    ``_auto_inject_isolated_datalayer`` or a test fixture keeps them in
    ``app.state.actor_dls``, and a loop over the process-global factory would
    reset the on-disk stores while reporting success and leaving the app's real
    stores untouched.

    Falls back to ``hosted_actor_ids()`` + ``get_datalayer`` when the app
    registers nothing, which is the deployment case.
    """
    registry = getattr(getattr(request, "app", None), "state", None)
    actor_dls = getattr(registry, "actor_dls", None) if registry else None
    if actor_dls:
        return dict(actor_dls)

    from vultron.adapters.driven import actor_hosts

    return {
        actor_id: cast(DataLayer, get_datalayer(actor_id))
        for actor_id in actor_hosts.hosted_actor_ids()
    }


def get_trigger_service(
    dl: DataLayer = Depends(get_trigger_dl),
) -> TriggerServicePort:
    """FastAPI dependency: construct and return a :class:`TriggerService`.

    Inject ``app.dependency_overrides[get_trigger_service] = lambda: mock``
    in tests to replace the service with a ``Mock(spec=TriggerServicePort)``.

    ``get_trigger_dl`` returns a ``SqliteDataLayer`` at runtime, which
    satisfies ``CaseOutboxPersistence`` structurally.  The cast below is
    safe; see DL-07-001 / DL-07-002 (which retired ARCH-13-001 / ARCH-13-002:
    with every DataLayer belonging to exactly one actor there is no unscoped
    instance the cast could smuggle in).
    """
    cop = cast(CaseOutboxPersistence, dl)
    return TriggerService(
        cop,
        sync_port=SyncActivityAdapter(cop),
        trigger_activity=TriggerActivityAdapter(cop),
    )
