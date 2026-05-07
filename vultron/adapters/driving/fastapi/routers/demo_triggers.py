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
Demo-only trigger router.

Exposes endpoints used exclusively by demo scripts to puppeteer actors through
steps their own BTs would handle autonomously in a real deployment.

This router is conditionally mounted only when
``get_config().server.run_mode == RunMode.PROTOTYPE`` (TRIG-09-002).
In ``RunMode.PROD`` these paths are simply not registered, so any request to
``/actors/{id}/demo/`` returns HTTP 404 (TRIG-09-003).

Spec: TRIG-08-004, TRIG-09-001 through TRIG-09-005, TRIG-10-003, TRIG-10-004.
"""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, status

from vultron.adapters.driving.fastapi.deps import (
    get_canonical_actor_dl,
    get_trigger_dl,
    get_trigger_service,
)
from vultron.adapters.driving.fastapi.errors import domain_error_translation
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.trigger_models import (
    AddNoteToCaseRequest,
    CloseCaseRequest,
    NotifyFixDeployedRequest,
    NotifyFixReadyRequest,
    NotifyPublishedRequest,
    SyncLogEntryRequest,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_service import TriggerServicePort

router = APIRouter(prefix="/actors", tags=["Demo Triggers"])


@router.post(
    "/{actor_id}/demo/add-note-to-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Create a Note and add it to a case.",
    description=(
        "Demo-only convenience wrapper. "
        "Creates a Note object, adds it to the actor's local copy of the "
        "case, and queues Create(Note) and AddNoteToCase(Note, Case) "
        "activities in the actor's outbox for delivery to case participants. "
        "In a production deployment the actor's own BT would handle this "
        "step autonomously. Use the general ``add-object-to-case`` trigger "
        "at ``/trigger/`` when the Note already exists. "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: TRIG-09-001, TRIG-10-003."
    ),
    operation_id="actors_demo_add_note_to_case",
)
def demo_add_note_to_case(
    actor_id: str,
    body: AddNoteToCaseRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """Create a Note and add it to a case (demo scaffold).

    Implements:
        TRIG-09-001, TRIG-09-004, TRIG-10-003,
        TB-01-001, TB-01-002, TB-01-003, TB-02-001,
        TB-03-001, TB-03-002, TB-04-001, TB-06-001, TB-06-002
    """
    with domain_error_translation():
        result = svc.add_note_to_case(
            actor_id=actor_id,
            case_id=body.case_id,
            note_name=body.note_name,
            note_content=body.note_content,
            in_reply_to=body.in_reply_to,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/demo/sync-log-entry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Commit a case log entry and replicate to peers.",
    description=(
        "Demo-only scaffold. "
        "Commits a new ``VultronCaseLogEntry`` to the local hash-chain and "
        "fans it out to all case participants as ``Announce(CaseLogEntry)`` "
        "activities queued in the actor's outbox. "
        "In a production deployment, log entries are committed automatically "
        "as a cascade effect of every state-changing operation; this endpoint "
        "exists only to let demo scripts inject entries manually. "
        "Returns the committed entry's ID, hash, and log index. "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: TRIG-09-001, TRIG-10-004, SYNC-02-002, SYNC-02-003."
    ),
    operation_id="actors_demo_sync_log_entry",
)
def demo_sync_log_entry(
    actor_id: str,
    body: SyncLogEntryRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """Commit a case log entry and fan it out to all case participants (demo).

    Implements:
        TRIG-09-001, TRIG-09-004, TRIG-10-004,
        SYNC-02-002, SYNC-02-003, TB-01-001, TB-01-002, TB-04-001,
        TB-06-001, TB-06-002, TB-07-001
    """
    actor = dl.read(actor_id) or dl.find_actor_by_short_id(actor_id)
    canonical_actor_id = (
        actor.id_ if actor and hasattr(actor, "id_") else actor_id
    )

    with domain_error_translation():
        entry = svc.commit_log_entry(
            case_id=body.case_id,
            object_id=body.object_id,
            event_type=body.event_type,
            actor_id=canonical_actor_id,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return {
        "log_entry_id": entry.id_,
        "entry_hash": entry.entry_hash,
        "log_index": entry.log_index,
    }


@router.post(
    "/{actor_id}/demo/notify-fix-ready",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Report that the actor's fix is ready (VFd).",
    description=(
        "Demo-only scaffold. "
        "Self-reports VFD state VFd (fix ready, not yet deployed) "
        "to the Case Manager via Add(ParticipantStatus, CaseParticipant). "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: DEMOMA-07-001."
    ),
    operation_id="actors_demo_notify_fix_ready",
)
def demo_notify_fix_ready(
    actor_id: str,
    body: NotifyFixReadyRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict[str, Any]:
    """Report that the actor has a fix ready (demo scaffold).

    Implements: DEMOMA-07-001, TRIG-09-001, TB-01-001, TB-06-001.
    """
    from vultron.core.states.cs import CS_vfd

    with domain_error_translation():
        result = svc.add_participant_status(
            actor_id=actor_id,
            case_id=body.case_id,
            vfd_state=CS_vfd.VFd,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/demo/notify-fix-deployed",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Report that the actor's fix is deployed (VFD).",
    description=(
        "Demo-only scaffold. "
        "Self-reports VFD state VFD (fix deployed) "
        "to the Case Manager via Add(ParticipantStatus, CaseParticipant). "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: DEMOMA-07-001."
    ),
    operation_id="actors_demo_notify_fix_deployed",
)
def demo_notify_fix_deployed(
    actor_id: str,
    body: NotifyFixDeployedRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict[str, Any]:
    """Report that the actor has deployed a fix (demo scaffold).

    Implements: DEMOMA-07-001, TRIG-09-001, TB-01-001, TB-06-001.
    """
    from vultron.core.states.cs import CS_vfd

    with domain_error_translation():
        result = svc.add_participant_status(
            actor_id=actor_id,
            case_id=body.case_id,
            vfd_state=CS_vfd.VFD,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/demo/notify-published",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Report that the vulnerability has been publicly disclosed.",
    description=(
        "Demo-only scaffold. "
        "Self-reports VFD=VFD and PXA=Pxa (public aware) "
        "to the Case Manager via Add(ParticipantStatus, CaseParticipant). "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: DEMOMA-07-001."
    ),
    operation_id="actors_demo_notify_published",
)
def demo_notify_published(
    actor_id: str,
    body: NotifyPublishedRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict[str, Any]:
    """Report that the vulnerability is publicly disclosed (demo scaffold).

    Implements: DEMOMA-07-001, TRIG-09-001, TB-01-001, TB-06-001.
    """
    from vultron.core.states.cs import CS_pxa, CS_vfd

    with domain_error_translation():
        result = svc.add_participant_status(
            actor_id=actor_id,
            case_id=body.case_id,
            vfd_state=CS_vfd.VFD,
            pxa_state=CS_pxa.Pxa,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/demo/close-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Report that the actor is closing the case (RM.CLOSED).",
    description=(
        "Demo-only scaffold. "
        "Self-reports RM state CLOSED "
        "to the Case Manager via Add(ParticipantStatus, CaseParticipant). "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: DEMOMA-07-001."
    ),
    operation_id="actors_demo_close_case",
)
def demo_close_case(
    actor_id: str,
    body: CloseCaseRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict[str, Any]:
    """Report that the actor is closing the case (demo scaffold).

    Implements: DEMOMA-07-001, TRIG-09-001, TB-01-001, TB-06-001.
    """
    from vultron.core.states.rm import RM

    with domain_error_translation():
        result = svc.add_participant_status(
            actor_id=actor_id,
            case_id=body.case_id,
            rm_state=RM.CLOSED,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result
