---
source: NOTES-demo-interactive-ui--live-case-log-stream
timestamp: '2026-10-12T23:51:12.615239+00:00'
title: 'Demo interactive UI: live case log stream design (delivered by #3641)'
type: note
---

Archived from `notes/demo-interactive-ui.md` by #4497 (notes sweep). Delivered by #3641
(closed): the stream is `GET /api/v2/actors/{actor_id}/demo/cases/{case_id}/log/stream`
in `vultron/adapters/driving/fastapi/routers/demo_triggers.py` and
`vultron/adapters/driving/fastapi/ledger_stream.py` (TRIG-09), tested by
`test/adapters/driving/fastapi/test_ledger_stream.py` and `test_ledger_stream_live.py`.
The route-order and shutdown-hook rules are recorded in the code comments and docstrings
there.

---

## Live case log stream

Extends the existing prototype-only ledger read endpoints in
`vultron/adapters/driving/fastapi/routers/demo_triggers.py`
(`GET /actors/{actor_id}/demo/cases/{case_id}/log` and `…/log/{index}`,
TRIG-09).

- **Path**: `GET /actors/{actor_id}/demo/cases/{case_id}/log/stream`, beside
  the existing ledger endpoints — not the `/actors/{actor_id:path}/cases/…`
  path first proposed in #665. Like every route here it is mounted under
  `/api/v2`, so the full path the reverse proxy forwards is
  `/api/v2/actors/{actor_id}/demo/cases/{case_id}/log/stream`. It resolves
  the case id with the same `_resolve_case_id` helper as its siblings.
- **Route order**: the stream route MUST be declared before `…/log/{index}`.
  Declared after it, `stream` is parsed as the integer `index` and the request
  fails with 422. A test must prove the stream route is reachable.
- **Mounted only in `RunMode.PROTOTYPE`** (TRIG-09-002/003); returns 404
  otherwise because the route is absent.
- **Response**: `text/event-stream`. Each event's `id:` is the entry's
  `log_index` and its `data:` is the entry serialized exactly as the list
  endpoint serializes it (wire form, by alias, `exclude_none`).
- **Replay**: `?since=<log_index>` (or the browser's `Last-Event-ID` on
  reconnect) skips entries at or below that index; absent means replay from
  the beginning. A browser reconnect keeps the original URL and adds the
  header, so when both are present the higher index wins.
- **Notification: server-side polling.** The handler re-reads the case's
  ledger entries on a short interval (`server.ledger_stream_poll_seconds`,
  default 0.25 s) and emits those above the last index sent. Chosen over an
  in-process queue because it needs no hook in the commit path, catches
  entries however they arrived (local commit or replicated in), and needs no
  app-scoped pub/sub state that could leak between test apps. The bounded
  read load is acceptable for a prototype-only endpoint.
- **Termination**: stops cleanly when the client disconnects; emits a
  terminal `event: close` when the server shuts down. It does not end when
  the case closes: the stream is a plain tail of whatever the actor records.
- **Shutdown needs a signal hook, not the lifespan.** uvicorn's graceful
  shutdown waits for open connections to close *before* it runs lifespan
  shutdown, and its default wait is unbounded. A stream that ended only on
  lifespan shutdown would hold the server open forever. The lifespan
  therefore chains onto the server's SIGINT/SIGTERM handler
  (`install_shutdown_signal_hook` in
  `vultron/adapters/driving/fastapi/ledger_stream.py`) and publishes the
  resulting event in ASGI lifespan state, which — unlike `app.state` — also
  reaches `app_v2` mounted under `main.py`'s root app. An app with no
  lifespan has no event, and the route refuses to start a stream there.
- **Testing**: `TestClient` reads a response to its end, so it cannot follow
  an open stream. Route tests hand the route an already-set shutdown event;
  the live tests (`test/adapters/driving/fastapi/test_ledger_stream_live.py`)
  serve the app with uvicorn, and send a real SIGTERM to a subprocess for the
  shutdown path.
- **Not a replication channel.** Like its siblings, it is demo tooling;
  participants replicate through the ActivityStreams inbox (SYNC-02-001).
