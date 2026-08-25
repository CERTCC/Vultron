#!/usr/bin/env python
"""
Actor lookup helpers for the Vultron FastAPI actors router.

Provides pure helper functions for finding actor records in an actor's own
DataLayer. No route handlers here.

Under ADR-0073 the URL path segment is resolved to a canonical actor URI by
**computation** (``{base_url}actors/{segment}``), not by scanning actor rows.
The old scan required a view across every actor's rows, and with per-actor
stores it could not work at all: choosing which store to open required the
canonical URI that the scan was being used to discover.
"""

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

from typing import Any, cast

from fastapi import HTTPException, status

from vultron.core.models.actor import (
    CoreActor,
    VultronApplication,
    VultronGroup,
    VultronOrganization,
    VultronPerson,
    VultronService,
)
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.core.ports.datalayer import DataLayer

_ACTOR_RECORD_TYPES = [
    "Actor",
    "CoreActor",
    "Application",
    "Group",
    "Organization",
    "Person",
    "Service",
]

_ACTOR_TYPE_MAP: dict[str, type[CoreActor]] = {
    "Person": VultronPerson,
    "Organization": VultronOrganization,
    "Service": VultronService,
    "Application": VultronApplication,
    "Group": VultronGroup,
}


def _find_actor_record_by_id(
    datalayer: DataLayer, actor_id: str
) -> dict[str, object] | None:
    for actor_type in _ACTOR_RECORD_TYPES:
        rec = datalayer.get(actor_type, actor_id)
        if isinstance(rec, dict):
            return rec
    return None


def _actor_class_for_record(
    rec: dict[str, Any],
) -> type[CoreActor]:
    data = rec.get("data_", {})
    payload_type = None
    if isinstance(data, dict):
        payload_type = data.get("type_") or data.get("type")

    if isinstance(payload_type, str) and payload_type in _ACTOR_TYPE_MAP:
        return _ACTOR_TYPE_MAP[payload_type]

    record_type = rec.get("type_")
    if isinstance(record_type, str) and record_type in _ACTOR_TYPE_MAP:
        return _ACTOR_TYPE_MAP[record_type]

    return CoreActor


def _candidate_ids(datalayer: DataLayer, actor_id: str) -> list[str]:
    """Return the ids under which *actor_id*'s record may be stored, in order.

    Two independent sources can name the actor a request addresses, and they do
    not always agree:

    1. The canonical URI computed from the path segment. Correct whenever the
       node's base URL is the configured one — i.e. in any deployment, where one
       process is one node.
    2. The store's *own* ``actor_id``. Under ADR-0073 a store is always exactly
       one actor's, and ``get_actor_dl`` has already decided which store this
       request addresses, so the store carries the answer directly.

    (1) is tried first because it is the documented contract — a segment resolves
    by computation, not by lookup. (2) is the fallback that makes a harness
    running several nodes in one process work: there, an actor created under
    ``http://testserver/api/v2`` was looked up as ``http://localhost:7999/api/v2``
    and reported missing, because process-global configuration cannot describe
    more than one node at a time.

    Deduplicated, preserving order, so the common case where both agree costs one
    lookup.
    """
    own = getattr(datalayer, "actor_id", None)
    candidates = [canonical_actor_uri(actor_id)]
    if isinstance(own, str) and own and own not in candidates:
        candidates.append(own)
    return candidates


def _find_actor_record(
    datalayer: DataLayer, actor_id: str
) -> dict[str, object] | None:
    """Return the raw actor record for *actor_id* from this actor's own store.

    *actor_id* may be a URL path segment or an already-canonical URI. See
    :func:`_candidate_ids` for the names tried and why there is more than one.

    The trailing "scan every actor row for one whose id ends in /segment"
    fallback is gone. It was a cross-actor read, and it also silently accepted
    a *peer's* record when the segment happened to match one — returning an
    actor this node does not host.
    """
    candidates = _candidate_ids(datalayer, actor_id)

    for canonical in candidates:
        rec = _find_actor_record_by_id(datalayer, canonical)
        if rec is not None:
            return rec

    # Preserve DataLayer.read() fallback behavior (e.g., bare UUID -> urn:uuid:).
    for probe in [*candidates, actor_id]:
        resolved = datalayer.read(probe)
        if resolved is None:
            continue
        resolved_id = getattr(resolved, "id_", None)
        if isinstance(resolved_id, str):
            rec = _find_actor_record_by_id(datalayer, resolved_id)
            if rec is not None:
                return rec
    return None


def _resolve_actor_or_404(actor_id: str, dl: DataLayer) -> CoreActor:
    """Return the actor named by *actor_id*, or raise 404.

    *dl* MUST already be that actor's own DataLayer — see
    ``deps.get_actor_dl``, which computes the canonical URI from the path
    segment and opens the corresponding store. See :func:`_candidate_ids` for the
    names tried and why there is more than one.
    """
    actor_record = None
    for probe in [*_candidate_ids(dl, actor_id), actor_id]:
        actor_record = dl.read(probe)
        if actor_record is not None:
            break
    if actor_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )
    return cast(CoreActor, actor_record)
