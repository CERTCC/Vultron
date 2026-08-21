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
get_trigger_dl
    Alias of :func:`get_actor_dl`, kept as a distinct override point for
    trigger-route tests.
get_canonical_actor_dl
    Alias of :func:`get_actor_dl`.
get_trigger_service
    Construct and return a :class:`~vultron.core.use_cases.triggers.service.TriggerService`.

Under ADR-0069 there is no shared DataLayer to inject, so every one of these
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


def get_actor_dl(
    actor_id: str = Path(...),
    request: Request = None,  # type: ignore[assignment]
) -> DataLayer:
    """FastAPI dependency: the DataLayer belonging to the addressed actor.

    Resolves the ``{actor_id}`` path segment to a canonical actor URI by
    computation and returns that actor's own store (ADR-0069).

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
            canonical_actor_uri(actor_id, base_url=node_base_url(request))
        ),
    )


def get_trigger_dl(
    actor_id: str = Path(...),
    request: Request = None,  # type: ignore[assignment]
) -> DataLayer:
    """FastAPI dependency: the addressed actor's DataLayer for trigger routes.

    Kept as a separate name from :func:`get_actor_dl` purely so that trigger
    routes remain independently overridable in tests
    (``app.dependency_overrides[get_trigger_dl]``).
    """
    return get_actor_dl(actor_id, request)


def get_canonical_actor_dl(
    actor_id: str = Path(...),
    request: Request = None,  # type: ignore[assignment]
) -> DataLayer:
    """FastAPI dependency: alias of :func:`get_actor_dl`.

    Retained so existing trigger routes and their test overrides keep working;
    the "canonical" qualifier is now redundant because every actor DataLayer is
    keyed by the canonical URI.
    """
    return get_actor_dl(actor_id, request)


def get_trigger_service(
    dl: DataLayer = Depends(get_trigger_dl),
) -> TriggerServicePort:
    """FastAPI dependency: construct and return a :class:`TriggerService`.

    Inject ``app.dependency_overrides[get_trigger_service] = lambda: mock``
    in tests to replace the service with a ``Mock(spec=TriggerServicePort)``.

    ``get_trigger_dl`` returns a ``SqliteDataLayer`` at runtime, which
    satisfies ``CaseOutboxPersistence`` structurally.  The cast below is
    safe; see ARCH-13-001 / ARCH-13-002.
    """
    cop = cast(CaseOutboxPersistence, dl)
    return TriggerService(
        cop,
        sync_port=SyncActivityAdapter(cop),
        trigger_activity=TriggerActivityAdapter(cop),
    )
