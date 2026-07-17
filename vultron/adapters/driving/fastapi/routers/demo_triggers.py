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

import json
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from fastapi.responses import JSONResponse, Response

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
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.protocols import is_case_model
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)
from vultron.core.ports.datalayer import ActorScopedDataLayer, DataLayer
from vultron.core.ports.trigger_service import TriggerServicePort

router = APIRouter(prefix="/actors", tags=["Demo Triggers"])


def _resolve_case_id(case_key: str, dl: DataLayer) -> str:
    case_obj = dl.read(case_key)
    if case_obj is None or not is_case_model(case_obj):
        case_obj = dl.find_case_by_short_id(case_key)
    if case_obj is None or not is_case_model(case_obj):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found.",
        )
    return case_obj.id_


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
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
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
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
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
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
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
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
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
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
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


@router.post(
    "/{actor_id}/demo/sync-log-entry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Commit a case ledger entry and fan it out to participants.",
    description=(
        "Demo-only trigger. Commits a ``VultronCaseLedgerEntry`` for the "
        "given case via the canonical BT commit path and queues an "
        "``Announce(CaseLedgerEntry)`` per participant for fan-out delivery. "
        "Uses ``Announce(VulnerabilityCase)`` as the canonical payload type. "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: TRIG-09-001, SYNC-02-002, SYNC-02-003."
    ),
    operation_id="actors_demo_sync_log_entry",
)
def demo_sync_log_entry(
    actor_id: str,
    body: SyncLogEntryRequest,
    background_tasks: BackgroundTasks,
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
) -> JSONResponse:
    """Commit a case ledger entry and fan it out (demo scaffold, BT-06-006 compliant).

    Uses BTBridge + create_commit_log_entry_tree via a canonical
    Announce(VulnerabilityCase) payload so the entry passes canonical
    validation (CLP-07).  The caller-supplied event_type is stored verbatim.

    Spec: TRIG-09-001, SYNC-02-002, SYNC-02-003.
    """
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.sync.commit_tree import (
        create_commit_log_entry_tree,
    )
    from vultron.core.sync_helpers import _find_equivalent_recorded_entry
    from vultron.core.use_cases._helpers import _find_case_actor_id

    case_id = body.case_id
    object_id = body.object_id
    event_type = body.event_type

    # Resolve canonical actor URI (slug from path param → full ID).
    _actor = dl.read(actor_id) or dl.find_actor_by_short_id(actor_id)
    canonical_actor_id = (
        _actor.id_ if _actor and hasattr(_actor, "id_") else actor_id
    )
    case_actor_id = _find_case_actor_id(dl, case_id) or canonical_actor_id
    payload_snapshot = {
        "type": "Announce",
        "object": {"type": "VulnerabilityCase", "id": case_id},
        "actor": case_actor_id,
        "context": case_id,
    }

    with domain_error_translation():
        from typing import cast as _cast

        from vultron.adapters.driven.sync_activity_adapter import (
            SyncActivityAdapter,
        )
        from vultron.core.ports.case_persistence import CaseOutboxPersistence

        cop = _cast(CaseOutboxPersistence, dl)
        sync_port = SyncActivityAdapter(cop)
        bridge = BTBridge(datalayer=dl)
        bridge.execute_with_setup(
            tree=create_commit_log_entry_tree(
                case_id=case_id,
                object_id=object_id,
                event_type=event_type,
                payload_snapshot=payload_snapshot,
            ),
            actor_id=case_actor_id,
            sync_port=sync_port,
        )

    entry = _find_equivalent_recorded_entry(
        case_id=case_id,
        object_id=object_id,
        event_type=event_type,
        payload_snapshot=payload_snapshot,
        dl=dl,
    )

    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)

    if entry is None:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Log entry commit did not persist."},
        )

    from vultron.core.models.case_ledger_entry import (
        VultronCaseLedgerEntry as DomainEntry,
    )

    if not isinstance(entry, DomainEntry):
        entry = DomainEntry.model_validate(entry.model_dump(mode="json"))

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "log_entry_id": entry.id_,
            "entry_hash": entry.entry_hash,
            "log_index": entry.log_index,
        },
    )


@router.get(
    "/{actor_id}/demo/cases/{case_id}/log",
    status_code=status.HTTP_200_OK,
    summary="[Demo] List all case ledger entries for a case, sorted by log_index.",
    description=(
        "Demo-only read endpoint. "
        "Returns all ``VultronCaseLedgerEntry`` objects for the specified case, "
        "sorted ascending by ``log_index``. "
        "Default response is ``application/json``. "
        "Request ``Accept: application/x-ndjson`` or pass ``?format=ndjson`` "
        "to receive NDJSON — one JSON object per line — suitable for direct "
        "file capture (``curl ... > case.jsonl``). "
        "This endpoint is for demo tooling, test scripts, and live display "
        "only. It MUST NOT be used as a participant-facing log-replication "
        "mechanism (use the ActivityStreams inbox channel per SYNC-07). "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: TRIG-09-001, SYNC-01-002, SYNC-02-003."
    ),
    operation_id="actors_demo_get_case_ledger",
)
def demo_get_case_ledger(
    actor_id: str,  # noqa: ARG001
    case_id: str,
    request: Request,
    fmt: str | None = Query(
        default=None,
        alias="format",
        description="Response format: 'ndjson' for NDJSON output.",
    ),
    dl: DataLayer = Depends(get_trigger_dl),
) -> Response:
    """Return ordered case ledger entries for a case (demo scaffold).

    Implements:
        TRIG-09-001, SYNC-01-002, SYNC-02-003.

    Demo/observability only — do not expose as a participant-facing endpoint.
    """
    canonical_case_id = _resolve_case_id(case_id, dl)
    raw_entries = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, (VultronCaseLedgerEntry, WireCaseLedgerEntry))
        and e.case_id == canonical_case_id
    ]
    raw_entries.sort(key=lambda e: e.log_index)
    wire_entries = [
        (
            e
            if isinstance(e, WireCaseLedgerEntry)
            else WireCaseLedgerEntry.model_validate(
                e.model_dump(by_alias=True, serialize_as_any=True)
            )
        )
        for e in raw_entries
    ]
    payloads = [
        e.model_dump(mode="json", by_alias=True, exclude_none=True)
        for e in wire_entries
    ]

    accept = request.headers.get("accept", "")
    if fmt == "ndjson" or "application/x-ndjson" in accept:
        content = "\n".join(json.dumps(p) for p in payloads)
        return Response(content=content, media_type="application/x-ndjson")
    return JSONResponse(content=payloads)


@router.get(
    "/{actor_id}/demo/cases/{case_id}/log/{index}",
    status_code=status.HTTP_200_OK,
    summary="[Demo] Get a single case ledger entry by log_index.",
    description=(
        "Demo-only read endpoint. "
        "Returns the single ``VultronCaseLedgerEntry`` at the given ``log_index`` "
        "for the specified case. "
        "Returns HTTP 404 if no entry exists at that index. "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: TRIG-09-001, SYNC-01-002, SYNC-02-003."
    ),
    operation_id="actors_demo_get_case_ledger_entry",
)
def demo_get_case_ledger_entry(
    actor_id: str,  # noqa: ARG001
    case_id: str,
    index: int = Path(ge=0, description="Zero-based log entry index."),
    dl: DataLayer = Depends(get_trigger_dl),
) -> dict[str, Any]:
    """Return the case ledger entry at the given index (demo scaffold).

    Implements:
        TRIG-09-001, SYNC-01-002, SYNC-02-003.

    Demo/observability only — do not expose as a participant-facing endpoint.
    """
    canonical_case_id = _resolve_case_id(case_id, dl)
    entry_id = f"{canonical_case_id}/log/{index}"
    obj = dl.read(entry_id)
    if not isinstance(obj, (VultronCaseLedgerEntry, WireCaseLedgerEntry)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": 404,
                "error": "NotFound",
                "message": (
                    f"No log entry at index {index} for case {case_id!r}."
                ),
                "activity_id": None,
            },
        )
    wire_obj = (
        obj
        if isinstance(obj, WireCaseLedgerEntry)
        else WireCaseLedgerEntry.model_validate(
            obj.model_dump(by_alias=True, serialize_as_any=True)
        )
    )
    return wire_obj.model_dump(mode="json", by_alias=True)
