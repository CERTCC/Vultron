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

"""Demo ledger reads: a case's ledger, its live stream, and one entry."""

import json
import threading
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from fastapi.responses import JSONResponse, Response, StreamingResponse

from vultron.adapters.driving.fastapi.deps import (
    get_ledger_stream_shutdown,
    get_trigger_dl,
)
from vultron.adapters.driving.fastapi.ledger_stream import (
    EVENT_STREAM_MEDIA_TYPE,
    case_ledger_entries,
    ledger_entry_payload,
    resolve_resume_index,
    stream_case_ledger,
)
from vultron.config import get_config
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.datalayer import DataLayer

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
    payloads = [
        ledger_entry_payload(e)
        for e in case_ledger_entries(dl, canonical_case_id)
    ]

    accept = request.headers.get("accept", "")
    if fmt == "ndjson" or "application/x-ndjson" in accept:
        content = "\n".join(json.dumps(p) for p in payloads)
        return Response(content=content, media_type="application/x-ndjson")
    return JSONResponse(content=payloads)


# Declared before ``…/log/{index}``: declared after it, ``stream`` would be
# parsed as the integer ``index`` and the request would fail with 422.
@router.get(
    "/{actor_id}/demo/cases/{case_id}/log/stream",
    status_code=status.HTTP_200_OK,
    summary="[Demo] Stream case ledger entries as server-sent events.",
    description=(
        "Demo-only read endpoint. "
        "Returns a ``text/event-stream`` of the actor's ``CaseLedgerEntry`` "
        "objects for the specified case. Each event's ``id:`` is the entry's "
        "``log_index`` and its ``data:`` is the entry serialized exactly as "
        "the ``…/log`` list endpoint serializes it. "
        "Stored entries are replayed first, in ``log_index`` order; "
        "``?since=<log_index>`` or the ``Last-Event-ID`` header (sent by a "
        "browser ``EventSource`` on reconnect) skips entries at or below "
        "that index — when both are given, the higher one wins. "
        "The server then re-reads the actor's DataLayer on a short interval "
        "(``server.ledger_stream_poll_seconds``, default 0.25 s) and pushes "
        "each new entry, whether committed locally or replicated in. "
        "The stream ends when the client disconnects, and ends with a "
        "terminal ``event: close`` when the server shuts down. "
        "Tail it with ``curl -N``. "
        "This endpoint is for demo tooling, test scripts, and live display "
        "only. It MUST NOT be used as a participant-facing log-replication "
        "mechanism (use the ActivityStreams inbox channel per SYNC-02-001). "
        "Only available in ``RunMode.PROTOTYPE``. "
        "Spec: TRIG-09-001, SYNC-01-002, SYNC-02-003; ADR-0104."
    ),
    operation_id="actors_demo_stream_case_ledger",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {EVENT_STREAM_MEDIA_TYPE: {}},
            "description": "Server-sent events, one per case ledger entry.",
        },
        404: {"description": "Case not found."},
        422: {"description": "Invalid ``since`` or ``Last-Event-ID``."},
    },
)
def demo_stream_case_ledger(
    actor_id: str,
    case_id: str,
    request: Request,
    since: int | None = Query(
        default=None,
        ge=0,
        description="Skip entries whose log_index is at or below this value.",
    ),
    last_event_id: str | None = Header(
        default=None,
        alias="Last-Event-ID",
        description="The id of the last event received; same effect as since.",
    ),
    dl: DataLayer = Depends(get_trigger_dl),
    shutdown: threading.Event = Depends(get_ledger_stream_shutdown),
) -> StreamingResponse:
    """Stream case ledger entries for a case as SSE (demo scaffold).

    Implements:
        TRIG-09-001, TRIG-09-004, SYNC-01-002, SYNC-02-003; ADR-0104.

    Demo/observability only — do not expose as a participant-facing endpoint.
    """
    try:
        after_index = resolve_resume_index(since, last_event_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None
    canonical_case_id = _resolve_case_id(case_id, dl)
    return StreamingResponse(
        stream_case_ledger(
            dl,
            canonical_case_id,
            actor_id=actor_id,
            after_index=after_index,
            poll_seconds=get_config().server.ledger_stream_poll_seconds,
            is_disconnected=request.is_disconnected,
            shutdown=shutdown,
        ),
        media_type=EVENT_STREAM_MEDIA_TYPE,
        # Proxies must pass each event through as it is written.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
