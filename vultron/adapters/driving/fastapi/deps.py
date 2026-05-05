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
get_trigger_dl
    Return the shared (non-actor-scoped) DataLayer for trigger use cases.
get_canonical_actor_dl
    Return the actor-scoped DataLayer keyed by the actor's canonical URI.
get_trigger_service
    Construct and return a :class:`~vultron.core.use_cases.triggers.service.TriggerService`.
"""

from fastapi import Depends, Path

from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_service import TriggerServicePort
from vultron.core.use_cases.triggers.service import TriggerService


def get_trigger_dl(actor_id: str = Path(...)) -> DataLayer:  # noqa: ARG001
    """FastAPI dependency: return the shared DataLayer for trigger use cases.

    Operational data (actors, offers, reports, cases) is stored in the
    shared DataLayer.  The ``actor_id`` path parameter is accepted but unused
    so that ``app.dependency_overrides[get_trigger_dl]`` works in tests
    (ADR-0012).
    """
    return get_datalayer()


def get_canonical_actor_dl(
    actor_id: str = Path(...),
    dl: DataLayer = Depends(get_trigger_dl),
) -> DataLayer:
    """FastAPI dependency: actor-scoped DataLayer keyed by canonical URI.

    Resolves *actor_id* (which may be a short UUID from the URL path) to the
    actor's full canonical URI via the shared DataLayer, then returns the
    actor-scoped DataLayer instance keyed by that URI.  This ensures that
    ``outbox_handler`` reads from the same ``{canonical_uri}_outbox`` table
    that ``record_outbox_item`` wrote to during use-case execution
    (BUG-2026040901).
    """
    actor = dl.read(actor_id) or dl.find_actor_by_short_id(actor_id)
    canonical_id = actor.id_ if actor and hasattr(actor, "id_") else actor_id
    return get_datalayer(canonical_id)


def get_trigger_service(
    dl: DataLayer = Depends(get_trigger_dl),
) -> TriggerServicePort:
    """FastAPI dependency: construct and return a :class:`TriggerService`.

    Inject ``app.dependency_overrides[get_trigger_service] = lambda: mock``
    in tests to replace the service with a ``Mock(spec=TriggerServicePort)``.
    """
    return TriggerService(
        dl,
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
    )
