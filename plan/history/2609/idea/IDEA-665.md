---
source: IDEA-665
timestamp: '2026-09-24T18:52:00.027134+00:00'
title: Add SSE stream endpoint for live case log updates
type: idea
---

## Summary

Add a Server-Sent Events (SSE) endpoint that streams new `CaseLogEntry`
objects as they are committed by the CaseActor. This is the live-display
backend for the Interactive Demo UI (Priority 510, #533).

## Motivation

The case log REST endpoints (#664) enable batch export and offline replay.
Live display — showing a case evolve in real time during a demo — requires
a long-lived push connection. SSE is well-suited: browser-native, no
WebSocket handshake overhead, and naturally append-only (matching the
append-only `CaseEventLog` model).

## Proposed endpoint

```text
GET /actors/{actor_id:path}/cases/{case_id:path}/log/stream
```

- Response: `text/event-stream` (SSE).
- On connect: optionally replay all existing entries for the case
  (controlled by a `?since={log_index}` query param; omit or `since=0`
  to replay from the beginning).
- On new entry: emit an SSE event with `data:` set to the JSON-serialised
  `CaseLogEntry`.
- On case closed / actor shutdown: emit a terminal `event: close` and
  end the stream.

## Implementation sketch

The main design question is the notification mechanism — how does the SSE
handler learn that a new `CaseLogEntry` was appended:

1. **Polling** (simplest): the handler polls
   `datalayer.by_type("CaseLogEntry")` every N ms, comparing against the
   last-seen `log_index`. No new infrastructure; works with the current
   SQLite DataLayer.
2. **In-memory queue** (cleaner): `AnnounceLogEntryReceivedUseCase` (or
   the `CaseEventLog.append` path) pushes new entries onto a
   per-case `asyncio.Queue`; the SSE handler awaits the queue.
   Requires a lightweight pub/sub registry (e.g., a dict of
   `{case_id: Queue}` stored on `app.state`).

Option 1 is lower-risk for the prototype; option 2 is cleaner and avoids
busy-wait but requires care around `create_app()` isolation
(see notes on not mutating module-level singletons).

## Acceptance criteria

- [ ] `GET .../log/stream` returns `text/event-stream` content type.
- [ ] Existing entries are replayed on connect (unless `?since` skips them).
- [ ] New entries are pushed as they arrive without the client polling.
- [ ] Stream terminates gracefully when the client disconnects.
- [ ] Integration test covering at least: connect → receive existing entries
  → commit a new entry → receive new entry → disconnect.

## Dependencies

- Blocked by #664 (case log REST endpoints) — shares the same route prefix
  and the same `datalayer.by_type` query path; implement that first.
- Related to #533 (Interactive Demo UI) — this is the live data feed for
  the UI's real-time swim-lane updates.

## Notes

- Use FastAPI's `StreamingResponse` with `media_type="text/event-stream"`
  and an `async_generator` body, or the `sse-starlette` package if it is
  already a dependency (check `pyproject.toml`).
- The `{actor_id:path}` and `{case_id:path}` path converters follow the
  existing pattern in `routers/actors.py` (#618 open concern about full-URI
  path segments applies here too).

**Processed**: 2026-09-24 — planned in group G19 (#2847); implementation tracked in #3640, #3641, #3642, #3643.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3639>.
Notes: `notes/demo-interactive-ui.md`. ADR: `docs/adr/0104-interactive-demo-ui-live-ledger-watcher.md`.
