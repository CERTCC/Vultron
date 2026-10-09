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

Every trigger here is a thin wrapper: it validates the HTTP body, builds the
verb's core request and hands it to
:func:`~vultron.adapters.driving.fastapi.trigger_runner.run_trigger`.

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
    get_trigger_dispatcher,
    get_trigger_dl,
)
from vultron.adapters.driving.fastapi.trigger_runner import run_trigger
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.use_case_result import (
    ActivityResult,
    NoteResult,
    StatusResult,
    SyncLogEntryResult,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.use_cases.triggers.request_bodies import (
    AddNoteToCaseRequest,
    CloseCaseRequest,
    NotifyFixDeployedRequest,
    NotifyFixReadyRequest,
    NotifyPublishedRequest,
    SetStubSummaryRequest,
    SyncLogEntryRequest,
)
from vultron.core.use_cases.triggers.requests import (
    AddNoteToCaseTriggerRequest,
    AddParticipantStatusTriggerRequest,
    LeaveCaseTriggerRequest,
    SetStubSummaryTriggerRequest,
    SyncLogEntryTriggerRequest,
)
from vultron.errors import VultronCanonicalEntryError

router = APIRouter(prefix="/actors", tags=["Demo Triggers"])


def _resolve_case_id(case_key: str, dl: DataLayer) -> str:
    case_obj = dl.read(case_key)
    if case_obj is None or not isinstance(case_obj, VulnerabilityCase):
        case_obj = dl.find_case_by_short_id(case_key)
    if case_obj is None or not isinstance(case_obj, VulnerabilityCase):
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
    response_model=NoteResult,
)
def demo_add_note_to_case(
    actor_id: str,
    body: AddNoteToCaseRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> NoteResult:
    """Create a Note and add it to a case (demo scaffold).

    Implements:
        TRIG-09-001, TRIG-09-004, TRIG-10-003,
        TRIG-01-002, HTTP-03-005, TRIG-02-006,
        TRIG-03-001, TRIG-03-002, TRIG-04-001, TRIG-06-001, TRIG-06-002,
        TRIG-12-001
    """
    return run_trigger(
        AddNoteToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            note_name=body.note_name,
            note_content=body.note_content,
            in_reply_to=body.in_reply_to,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


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
    response_model=StatusResult,
)
def demo_notify_fix_ready(
    actor_id: str,
    body: NotifyFixReadyRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> StatusResult:
    """Report that the actor has a fix ready (demo scaffold).

    Implements: DEMOMA-07-001, TRIG-09-001, TRIG-09-004, TRIG-02-003, TRIG-06-001,
        TRIG-12-001.
    """
    # VF hypercube: vf → Vf is the only valid first hop from the initial
    # state; Vf → VF is the second hop.  The verb is two protocol steps, so
    # it is two trigger runs — each validated by ValidateTriggerTransitionsNode
    # — and the response is the second hop's status.
    run_trigger(
        AddParticipantStatusTriggerRequest(
            actor_id=actor_id, case_id=body.case_id, vf_state=CS_vf.Vf
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )
    return run_trigger(
        AddParticipantStatusTriggerRequest(
            actor_id=actor_id, case_id=body.case_id, vf_state=CS_vf.VF
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


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
    response_model=StatusResult,
)
def demo_notify_fix_deployed(
    actor_id: str,
    body: NotifyFixDeployedRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> StatusResult:
    """Report that the actor has deployed a fix (demo scaffold).

    Implements: DEMOMA-07-001, TRIG-09-001, TRIG-09-004, TRIG-02-003, TRIG-06-001,
        TRIG-12-001.
    """
    return run_trigger(
        AddParticipantStatusTriggerRequest(
            actor_id=actor_id, case_id=body.case_id, d_state=CS_d.D
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


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
    response_model=StatusResult,
)
def demo_notify_published(
    actor_id: str,
    body: NotifyPublishedRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> StatusResult:
    """Report that the vulnerability is publicly disclosed (demo scaffold).

    Implements: DEMOMA-07-001, TRIG-09-001, TRIG-09-004, TRIG-02-003, TRIG-06-001,
        TRIG-12-001.
    """
    return run_trigger(
        AddParticipantStatusTriggerRequest(
            actor_id=actor_id, case_id=body.case_id, pxa_state=CS_pxa.Pxa
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/demo/close-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Actor sends Leave(VulnerabilityCase) to close the case.",
    description=(
        "Demo-only scaffold. "
        "Triggers Leave(VulnerabilityCase) via the canonical RM closure path "
        "(ADR-0050). "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: DEMOMA-07-001."
    ),
    operation_id="actors_demo_close_case",
    response_model=ActivityResult,
)
def demo_close_case(
    actor_id: str,
    body: CloseCaseRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """Trigger Leave(VulnerabilityCase) for the given actor and case.

    Implements the canonical RM case closure path (ADR-0050): emits
    Leave(VulnerabilityCase) to the Case Actor inbox, which commits a
    ``close_case`` CaseLedgerEntry and fans it out to all participants.

    Implements: DEMOMA-07-001, TRIG-09-001, TRIG-09-004, TRIG-02-006, TRIG-06-001,
        TRIG-12-001.
    """
    return run_trigger(
        LeaveCaseTriggerRequest(actor_id=actor_id, case_id=body.case_id),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/demo/sync-log-entry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Commit a case ledger entry and fan it out to participants.",
    description=(
        "Demo-only trigger. Commits a ``CaseLedgerEntry`` for the "
        "given case via the canonical BT commit path and queues an "
        "``Announce(CaseLedgerEntry)`` per participant for fan-out delivery. "
        "Uses ``Announce(VulnerabilityCase)`` as the canonical payload type. "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: TRIG-09-001, SYNC-02-002, SYNC-02-003."
    ),
    operation_id="actors_demo_sync_log_entry",
    response_model=SyncLogEntryResult,
)
def demo_sync_log_entry(
    actor_id: str,
    body: SyncLogEntryRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> SyncLogEntryResult:
    """Commit a case ledger entry and fan it out (demo scaffold, BT-06-006 compliant).

    Runs :class:`~vultron.core.use_cases.triggers.sync_log_entry.SvcSyncLogEntryUseCase`
    through the trigger dispatcher: the commit tree executes as the case's
    CASE_MANAGER with a canonical ``Announce(VulnerabilityCase)`` payload so the
    entry passes canonical validation (CLP-07), and the caller-supplied
    ``event_type`` is stored verbatim.

    Implements:
        TRIG-09-001, TRIG-09-004, TRIG-02-006, TRIG-10-004, TRIG-06-001,
        TRIG-06-002, SYNC-02-002, SYNC-02-003, TRIG-12-001
    """
    try:
        return run_trigger(
            SyncLogEntryTriggerRequest(
                actor_id=actor_id,
                case_id=body.case_id,
                object_id=body.object_id,
                event_type=body.event_type,
            ),
            dispatcher=dispatcher,
            dl=actor_dl,
            background_tasks=background_tasks,
        )
    except VultronCanonicalEntryError:
        # The tree ran but this store does not hold the canonical log, so the
        # ledger-authority guard declined the mint (ADR-0073).  Kept as the
        # 500 this route has always answered; ``domain_error_translation()``
        # has no mapping for it because it is neither a client fault nor a
        # state conflict.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Log entry commit did not persist.",
        ) from None


@router.post(
    "/{actor_id}/demo/set-stub-summary",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Demo] Seed stub_summary on the actor's DataLayer copy of a case.",
    description=(
        "Demo-only scaffold. "
        "Seeds ``stub_summary`` on the actor's local DataLayer copy of the "
        "case so that a subsequent ``invite-actor-to-case`` trigger can build "
        "the stub Invite (CM-17-010, MV-10-001, #4165). "
        "Only available in ``RunMode.PROTOTYPE``."
    ),
    operation_id="actors_demo_set_stub_summary",
    response_model=StatusResult,
)
def demo_set_stub_summary(
    actor_id: str,
    body: SetStubSummaryRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> StatusResult:
    """Seed stub_summary on the actor's DataLayer copy of a case (demo scaffold).

    Call this before ``invite-actor-to-case`` to satisfy the stub-Invite
    precondition (CM-17-010, MV-10-001).

    Implements: CM-17-010, MV-10-001, TRIG-09-001, TRIG-09-004.
    """
    return run_trigger(
        SetStubSummaryTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            stub_summary=body.stub_summary,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.get(
    "/{actor_id}/demo/cases/{case_id}/log",
    status_code=status.HTTP_200_OK,
    summary="[Demo] List all case ledger entries for a case, sorted by log_index.",
    description=(
        "Demo-only read endpoint. "
        "Returns all ``CaseLedgerEntry`` objects for the specified case, "
        "sorted ascending by ``log_index``. "
        "Default response is ``application/json``. "
        "Request ``Accept: application/x-ndjson`` or pass ``?format=ndjson`` "
        "to receive NDJSON — one JSON object per line — suitable for direct "
        "file capture (``curl ... > case.jsonl``). "
        "This endpoint is for demo tooling, test scripts, and live display "
        "only. It MUST NOT be used as a participant-facing log-replication "
        "mechanism (use the ActivityStreams inbox channel per SYNC-02-001). "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: TRIG-09-001, SYNC-01-002, SYNC-02-003."
    ),
    operation_id="actors_demo_get_case_ledger",
)
def demo_get_case_ledger(
    actor_id: str,
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
    entries = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry) and e.case_id == canonical_case_id
    ]
    entries.sort(key=lambda e: e.log_index)
    payloads = [
        e.model_dump(mode="json", by_alias=True, exclude_none=True)
        for e in entries
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
        "Returns the single ``CaseLedgerEntry`` at the given ``log_index`` "
        "for the specified case. "
        "Returns HTTP 404 if no entry exists at that index. "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: TRIG-09-001, SYNC-01-002, SYNC-02-003."
    ),
    operation_id="actors_demo_get_case_ledger_entry",
)
def demo_get_case_ledger_entry(
    actor_id: str,
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
    if not isinstance(obj, CaseLedgerEntry):
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
    return obj.model_dump(mode="json", by_alias=True)
