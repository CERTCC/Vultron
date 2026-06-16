#!/usr/bin/env python
"""
Actor lookup helpers for the Vultron FastAPI actors router.

Provides pure helper functions for finding actor records in the DataLayer
by canonical ID, short-ID, or record type. No route handlers here.
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


def _find_actor_record(
    datalayer: DataLayer, actor_id: str
) -> dict[str, object] | None:
    """Return raw actor record for full-ID or short-ID lookup."""
    rec = _find_actor_record_by_id(datalayer, actor_id)
    if rec is not None:
        return rec

    # Preserve DataLayer.read() fallback behavior (e.g., bare UUID -> urn:uuid:).
    resolved = datalayer.read(actor_id)
    if resolved is not None:
        resolved_id = getattr(resolved, "id_", None)
        if isinstance(resolved_id, str):
            rec = _find_actor_record_by_id(datalayer, resolved_id)
            if rec is not None:
                return rec

    for actor_type in _ACTOR_RECORD_TYPES:
        for candidate in datalayer.get_all(actor_type):
            rec_id = candidate.get("id_")
            if isinstance(rec_id, str) and (
                rec_id == actor_id or rec_id.endswith(f"/{actor_id}")
            ):
                return candidate
    return None


def _resolve_actor_or_404(actor_id: str, dl: DataLayer) -> CoreActor:
    actor_record = dl.read(actor_id)
    if actor_record is None:
        actor_record = dl.find_actor_by_short_id(actor_id)
    if actor_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actor not found."
        )
    return cast(CoreActor, actor_record)
