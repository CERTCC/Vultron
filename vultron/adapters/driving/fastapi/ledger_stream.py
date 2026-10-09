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
Server-sent event stream of one actor's case ledger entries (demo tooling).

Backs ``GET /actors/{actor_id}/demo/cases/{case_id}/log/stream`` in
:mod:`vultron.adapters.driving.fastapi.routers.demo_triggers`.  The stream
learns of new entries by re-reading the actor's DataLayer on a short interval
rather than through a hook in the ledger write paths, so it sees an entry
however it arrived — committed locally or replicated in (ADR-0104).

Like the list endpoint it sits beside, this is observability tooling, not a
replication channel: participants replicate through the ActivityStreams inbox
(SYNC-02-001).

Server shutdown
    uvicorn's graceful shutdown waits for open connections to close *before*
    it runs lifespan shutdown, so a stream that waited for lifespan shutdown
    would hold the server open until the graceful-shutdown timeout cancelled
    it.  :func:`install_shutdown_signal_hook` therefore chains onto the
    server's own SIGINT/SIGTERM handler and sets a
    :class:`threading.Event` the moment the server is asked to exit; every
    open stream sees it on its next poll, sends ``event: close`` and ends.
    The lifespan also sets the event on shutdown, for hosts that install no
    signal handler (``TestClient``, a server run off the main thread).
"""

import asyncio
import json
import logging
import signal
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from types import FrameType
from typing import Any

from starlette.concurrency import run_in_threadpool

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)

#: Media type of the stream response.
EVENT_STREAM_MEDIA_TYPE = "text/event-stream"

#: Key under which the lifespan publishes the shutdown event in ASGI lifespan
#: state.  Lifespan state travels in the request scope, so it reaches routes
#: of a sub-application mounted under the app whose lifespan ran — which
#: ``app.state`` does not.
SHUTDOWN_STATE_KEY = "ledger_stream_shutdown"

#: Signals a server treats as "exit".  The hook chains onto whichever of these
#: already has a Python-level handler.
_EXIT_SIGNALS = (signal.SIGINT, signal.SIGTERM)

_SignalHandler = Callable[[int, FrameType | None], Any]


def case_ledger_entries(
    dl: DataLayer, canonical_case_id: str
) -> list[CaseLedgerEntry]:
    """Return the case's ledger entries in *dl*, ascending by ``log_index``."""
    entries = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry) and e.case_id == canonical_case_id
    ]
    entries.sort(key=lambda e: e.log_index)
    return entries


def ledger_entry_payload(entry: CaseLedgerEntry) -> dict[str, Any]:
    """Serialize *entry* the way the demo ledger list endpoint returns it."""
    return entry.model_dump(mode="json", by_alias=True, exclude_none=True)


def format_entry_event(entry: CaseLedgerEntry) -> str:
    """Frame *entry* as one SSE event: ``id:`` is its ``log_index``."""
    data = json.dumps(ledger_entry_payload(entry))
    return f"id: {entry.log_index}\ndata: {data}\n\n"


def format_close_event() -> str:
    """Frame the terminal ``close`` event sent when the server shuts down."""
    return "event: close\ndata: \n\n"


def resolve_resume_index(
    since: int | None, last_event_id: str | None
) -> int | None:
    """Return the highest ``log_index`` the client already holds, if any.

    ``since`` is the query parameter; ``last_event_id`` is the
    ``Last-Event-ID`` header a browser's ``EventSource`` sends on reconnect,
    carrying the ``id:`` of the last event it received.  A reconnect keeps
    the original URL, so both may be present; the higher one is the client's
    real position.

    Raises:
        ValueError: ``last_event_id`` is not a non-negative integer.  Every
            ``id:`` this stream sends is one, so anything else did not come
            from it.
    """
    candidates = [] if since is None else [since]
    if last_event_id is not None:
        text = last_event_id.strip()
        if not text.isdigit():
            raise ValueError(
                f"Last-Event-ID must be a non-negative log_index, got "
                f"{last_event_id!r}."
            )
        candidates.append(int(text))
    return max(candidates) if candidates else None


async def stream_case_ledger(
    dl: DataLayer,
    canonical_case_id: str,
    *,
    actor_id: str,
    after_index: int | None,
    poll_seconds: float,
    is_disconnected: Callable[[], Awaitable[bool]],
    shutdown: threading.Event,
) -> AsyncIterator[str]:
    """Yield SSE frames for the case's ledger entries, then follow new ones.

    Replays every stored entry above *after_index* (all of them when it is
    ``None``), then re-reads the store every *poll_seconds* and yields each
    entry above the last one sent.  The gap buffer commits replicated entries
    in ``log_index`` order (SYNC-14), so "above the last one sent" misses
    nothing.

    Ends when the client disconnects, or yields :func:`format_close_event`
    and ends once *shutdown* is set.  *actor_id* names the actor whose store
    is read, for the lifecycle log lines.
    """
    last_sent = after_index
    # Overwritten on every other way out; a disconnect may arrive as a
    # cancellation or a generator close, which pass through ``finally`` only.
    reason = "client disconnected"
    logger.info(
        "Ledger stream opened (actor_id=%s case_id=%s after log_index %s)",
        actor_id,
        canonical_case_id,
        last_sent,
    )
    try:
        while True:
            entries = await run_in_threadpool(
                case_ledger_entries, dl, canonical_case_id
            )
            for entry in entries:
                if last_sent is None or entry.log_index > last_sent:
                    yield format_entry_event(entry)
                    last_sent = entry.log_index
            if shutdown.is_set():
                reason = "server shutting down"
                yield format_close_event()
                return
            if await is_disconnected():
                return
            await asyncio.sleep(poll_seconds)
    except Exception:
        # Re-raised for the server to report; recorded here so the close
        # line does not blame the client.
        reason = "stream failed"
        raise
    finally:
        logger.info(
            "Ledger stream closed (actor_id=%s case_id=%s at log_index %s): %s",
            actor_id,
            canonical_case_id,
            last_sent,
            reason,
        )


def install_shutdown_signal_hook(
    shutdown: threading.Event,
) -> Callable[[], None]:
    """Set *shutdown* when the server is asked to exit; return an undo.

    For each exit signal whose current handler is a Python callable — the
    server's own exit handler — installs a handler that sets *shutdown* and
    then calls the original, so the server still shuts down as before.  A
    signal left at its default or ignored disposition is not touched: no
    server is listening for it, and replacing the default would change what
    the signal does.

    Signal handlers can only be installed from the main thread.  Off it (a
    ``TestClient`` lifespan, a server run in a worker thread) nothing is
    installed and the returned undo is a no-op; the lifespan's own shutdown
    then sets the event.

    The undo restores each original handler, unless something has replaced
    the hook in the meantime.
    """
    if threading.current_thread() is not threading.main_thread():
        logger.debug(
            "Ledger stream shutdown hook not installed: not on the main thread"
        )
        return lambda: None

    installed: list[tuple[int, _SignalHandler, _SignalHandler]] = []
    for sig in _EXIT_SIGNALS:
        original = signal.getsignal(sig)
        if not callable(original):
            continue
        hook = _chained_handler(shutdown, original)
        signal.signal(sig, hook)
        installed.append((sig, original, hook))

    def _undo() -> None:
        for sig, original, hook in installed:
            if signal.getsignal(sig) is hook:
                signal.signal(sig, original)

    return _undo


def _chained_handler(
    shutdown: threading.Event, original: _SignalHandler
) -> _SignalHandler:
    def _handler(signum: int, frame: FrameType | None) -> Any:
        shutdown.set()
        return original(signum, frame)

    return _handler
