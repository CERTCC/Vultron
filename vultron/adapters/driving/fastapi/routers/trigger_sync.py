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

"""
Trigger router for SYNC log-replication behaviors.

Thin wrapper: validates request → resolves actor → calls core trigger →
returns response.  All domain logic lives in
``vultron.core.use_cases.triggers.sync``.

Spec: SYNC-02-002, SYNC-02-003.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Path, status

from vultron.adapters.driven.datalayer_tinydb import get_datalayer
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.trigger_models import SyncLogEntryRequest
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.triggers.sync import commit_log_entry_trigger

router = APIRouter(prefix="/actors", tags=["Triggers"])


def _actor_dl(actor_id: str = Path(...)) -> DataLayer:  # noqa: ARG001
    """FastAPI dependency: return the shared DataLayer for sync trigger use cases."""
    return get_datalayer()


def _canonical_actor_dl(
    actor_id: str = Path(...),
    dl: DataLayer = Depends(_actor_dl),
) -> DataLayer:
    """FastAPI dependency: actor-scoped DataLayer keyed by the canonical URI."""
    actor = dl.read(actor_id) or dl.find_actor_by_short_id(actor_id)
    canonical_id = actor.id_ if actor and hasattr(actor, "id_") else actor_id
    return get_datalayer(canonical_id)


@router.post(
    "/{actor_id}/trigger/sync-log-entry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Commit a case log entry and replicate to peers.",
    description=(
        "Commits a new ``VultronCaseLogEntry`` to the local hash-chain and "
        "fans it out to all case participants as ``Announce(CaseLogEntry)`` "
        "activities queued in the actor's outbox. "
        "Returns the committed entry's ID, hash, and log index. "
        "Spec: SYNC-02-002, SYNC-02-003."
    ),
    operation_id="actors_trigger_sync_log_entry",
)
def trigger_sync_log_entry(
    actor_id: str,
    body: SyncLogEntryRequest,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(_actor_dl),
    actor_dl: DataLayer = Depends(_canonical_actor_dl),
) -> dict:
    """Commit a case log entry and fan it out to all case participants.

    Resolves *actor_id* to the canonical URI, then delegates to
    :func:`~vultron.core.use_cases.triggers.sync.commit_log_entry_trigger`.
    Schedules the outbox background task so queued
    ``Announce(CaseLogEntry)`` activities are delivered immediately.

    Implements:
        SYNC-02-002, SYNC-02-003, TB-01-001, TB-01-002, TB-04-001,
        TB-06-001, TB-06-002, TB-07-001
    """
    actor = dl.read(actor_id) or dl.find_actor_by_short_id(actor_id)
    canonical_actor_id = (
        actor.id_ if actor and hasattr(actor, "id_") else actor_id
    )

    entry = commit_log_entry_trigger(
        case_id=body.case_id,
        object_id=body.object_id,
        event_type=body.event_type,
        actor_id=canonical_actor_id,
        dl=dl,
    )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return {
        "log_entry_id": entry.id_,
        "entry_hash": entry.entry_hash,
        "log_index": entry.log_index,
    }
