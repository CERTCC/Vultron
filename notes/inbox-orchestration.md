---
title: Inbox Orchestration — BT Module Design
status: active
kind: guidance
description: >
  Rules for the core BT-backed inbox orchestration module: orchestration
  belongs in core/, the narrow route-level guard exception, the two-adapter
  seam and verdict mapping, pending-queue port injection, and the test surface.
related_specs:
  - specs/inbox-orchestration.yaml
  - specs/use-case-organization.yaml
  - specs/handler-protocol.yaml
  - specs/inbox-endpoint.yaml
related_notes:
  - notes/architecture-hexagonal.md
  - notes/use-case-protocol.md
  - notes/bt-integration.md
  - notes/architecture-adapters.md
  - notes/case-communication-model.md
  - notes/inbox-pipeline.md
relevant_packages:
  - vultron/core/behaviors/inbox
  - vultron/adapters/driving/fastapi
---

# Inbox Orchestration — BT Module Design

## Orchestration Belongs in `core/`

A change to inbox processing (parse, rehydrate, defer-check, dispatch) belongs in
`vultron/core/behaviors/inbox/` (IO-02-001), never in the FastAPI router or a new
adapter-layer pipeline helper. `process_payload` is the sole caller-facing entry point
(IO-02-003) and all policy is internal to the BT. Logic in the router is unavailable to
non-HTTP entry points (CLI, tests) and violates ADR-0009.

The FastAPI inbox endpoint is thin glue: parse the body, return 202, and schedule
`process_payload` through `BackgroundTasks`. The scheduled task is a coroutine, so it
runs `process_payload` and the pending-queue replay through `asyncio.to_thread`; a
synchronous BT tick on the event loop stalls every other request, delivery, and outbox
drain on the container (IE-06-003). See [bt-integration](bt-integration.md) §
"Concurrency Model".

---

## Exception: Synchronous Route-Level Guards

IO-03-003b forbids inbox policy in the FastAPI path, with one narrow exception: a
**synchronous guard that refuses an activity before the 202** may live at the route,
because the sender needs a 4xx and the check must run before `BackgroundTasks`
schedules the handler. The addressing check (IE-11-001, ADR-0068) is the example. A
route-level guard:

- produces a synchronous HTTP response, not a flag for a downstream node;
- does not duplicate orchestration logic that belongs in the core BT;
- is justified in an ADR that acknowledges IO-03-003b.

---

## Two-Adapter Seam

`process_payload` takes exactly two adapters (`vultron/core/behaviors/inbox/models.py`):
`IngressPayloadAdapter` owns parse and rehydrate, keeping wire knowledge out of the BT;
`DispatchAdapter` runs the use-case path and returns its `HandlerResult` (IO-03-001).
Collapsing them re-couples parsing to dispatch; splitting further lets callers invoke
the steps out of order.

`DispatchNode` is the only place a verdict becomes an outcome (HP-01-004):
`APPLIED`/`SKIPPED` → `processed`, `DEFERRED` → `deferred`, `REFUSED` → `rejected` with
the handler's reason. A dispatch that returns no `HandlerResult` is rejected ("did not
raise" is not a verdict), and an unroutable activity gets a synthesized `REFUSED`
(UCORG-05-012). `run_inbox_pipeline` logs every `rejected` outcome at WARNING with actor
and activity ids (UCORG-05-013); the BT nodes log their own outcome writes at INFO, so
a refusal is not reported twice.

Activities held pending a case bootstrap are replayed only when the bootstrap's verdict
maps to `processed` (the legacy adapter paths gate on `HandlerResult.took_effect`): a
refused or deferred bootstrap has not made the case available, so replay would only
defer them again. A replay that raises is logged and does not turn an applied bootstrap
into `rejected` (MV-01-007).

---

## Pending-Queue Port Injection

The defer-check step reads and writes the pending-case queue through the injected
`PendingCaseQueuePort` (IO-03-002), never by importing `inbox_pending_queue` from the
adapter layer. The FastAPI adapter supplies the concrete implementation; tests supply an
in-memory stub. This keeps `core/` free of adapter imports (ADR-0009).

---

## Test Surface

Tests target `process_payload` and observe `InboxOutcome.status`, `context_id`, and the
queue port's recorded calls. They MUST NOT monkeypatch internal BT node helpers.
