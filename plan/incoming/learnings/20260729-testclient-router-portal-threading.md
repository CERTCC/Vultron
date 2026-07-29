---
title: Cross-actor TestClient router must offload blocking POST off the portal loop
type: learning
timestamp: 2026-07-29
source: ISSUE-1779
signal: design-question
---

## Context

Issue #1779 asked to route cross-actor delivery in the isolated multi-actor
demo harness (`test/demo/conftest.py`) through each target actor's FastAPI
`TestClient` inbox instead of a hand-rolled `httpx.ASGITransport`, per ADR-0042
/ `outbox.yaml` OX-12-003. The issue specified *what* transport to use but not
*how* to invoke it safely given the harness's threading model.

## Design decision (beyond the issue text)

`_TestClientRouter.emit()` is `async` and runs inside a FastAPI
`BackgroundTask` on the **sending** app's `TestClient` portal event loop.
`TestClient.post()` is **blocking** and drives the target app through its own
portal (an `anyio` blocking portal on a separate thread). Two hazards:

1. Calling the blocking `TestClient.post()` directly on the sending portal's
   event loop blocks that loop.
2. For CaseActor `cc:`-to-self loopback delivery (CLP-10-001), the sender and
   target are the **same** `TestClient` / same portal — a direct blocking call
   would deadlock (this is the exact reentrancy the retired `ASGIEmitter`
   papered over with its `_asgi_delivery_depth` contextvar guard).

**Resolution:** dispatch the blocking POST via
`anyio.to_thread.run_sync(functools.partial(client.post, ...))`. The POST runs
on a fresh worker thread, freeing the calling event loop; the target portal can
then service the inbound request without self-deadlock. This is the standard
pattern for nested/loopback `TestClient` calls.

## How to apply

When any in-process test harness routes a message from one FastAPI
`TestClient` into another (or back into itself) from within an already-running
request/BackgroundTask, run the blocking `TestClient.post()` via
`anyio.to_thread.run_sync`, not directly. Register `TestClient` instances (not
raw ASGI apps) with the router, and enter every client's context before any
delivery is routed to it so its portal is live.

Candidate destination if promoted: `test/AGENTS.md` §"SYNC Replication Test
Patterns" or a short note under `notes/` on the multi-actor test harness
threading model. Relates to [[sync-ledger-adapter-write-conflict]] (same
isolated-app harness).
