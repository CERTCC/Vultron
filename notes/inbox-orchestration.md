---
title: Inbox Orchestration — BT Module Design
status: active
description: >
  Design decisions and implementation guidance for the core BT-backed inbox
  orchestration module: why orchestration belongs in core/, adapter injection
  rationale, InboxOutcome contract, and pending-queue port design.
related_specs:
  - specs/inbox-orchestration.yaml
  - specs/use-case-organization.yaml
  - specs/handler-protocol.yaml
related_notes:
  - notes/architecture-hexagonal.md
  - notes/use-case-protocol.md
  - notes/bt-integration.md
  - notes/architecture-adapters.md
relevant_packages:
  - vultron/core/behaviors/inbox
  - vultron/adapters/driving/fastapi
---

# Inbox Orchestration — BT Module Design

## Why Orchestration Belongs in `core/`

The previous inbox pipeline lived in `vultron/adapters/driving/fastapi/` as
`InboxPipeline` and `inbox_handler`. This made the orchestration logic
unavailable to non-HTTP entry points (CLI, tests, future MCP adapter) without
importing adapter-layer code — a direct ADR-0009 violation.

Moving orchestration to `vultron/core/behaviors/inbox/` restores the
invariant: core owns the policy; adapters own the translation. The FastAPI
inbox endpoint becomes thin glue that:

1. Parses the HTTP request body into a raw payload.
2. Calls `process_payload(payload, ingress_adapter, dispatch_adapter)`.
3. Returns HTTP 202 immediately and schedules the call via `BackgroundTasks`.

The CLI, tests, and any future inbox entry point do the same but supply
different adapter implementations.

---

## Exception: Synchronous Route-Level Guards

IO-03-003b says the FastAPI inbox path MUST NOT contain inbox policy logic.
There is one narrow exception: a **synchronous guard that refuses an Activity
before the HTTP 202 is returned** may live at the route level.

The addressing check added in IE-11-001 is the canonical example. That check
must be synchronous — the sender needs a 4xx response, not a silent discard —
and must execute before `BackgroundTasks` schedules the handler. Both
constraints require route-level placement. ADR-0068 documents the tradeoff.

Rules for any future route-level guard:

- It must produce a synchronous HTTP response (not just set a flag for a
  downstream BT node).
- It must not duplicate orchestration logic that belongs in the core BT
  pipeline.
- The justification must be recorded in an ADR that acknowledges IO-03-003b.

---

## Two-Adapter Seam Design

`process_payload` accepts exactly two injected adapters:

- **`IngressPayloadAdapter`** — translates raw input (bytes or dict) into a
  rehydrated `as_Activity`. Owns parse + rehydrate; isolates wire-format
  knowledge from the orchestration BT.
- **`DispatchAdapter`** — accepts a `VultronEvent`, executes the
  appropriate use-case path, and returns the handler's `HandlerResult`
  (IO-03-001, UCORG-05-010). Wraps the existing `ActivityDispatcher` port.

`DispatchNode` is the only place the verdict becomes an outcome (HP-01-004):
`APPLIED`/`SKIPPED` → `processed`, `DEFERRED` → `deferred`, `REFUSED` →
`rejected` with the handler's reason. A dispatch that returns no
`HandlerResult` is rejected — "did not raise" is not a verdict. When no
handler runs at all (an unroutable activity), the dispatcher synthesizes a
`REFUSED` verdict, so the drop is never reported as `processed`
(UCORG-05-012). `run_inbox_pipeline` logs every `rejected` outcome at WARNING
with the actor and activity ids (UCORG-05-013, SL-02-001); the BT nodes log
their own outcome writes at INFO so a refusal is not reported twice.

Replay of activities held pending a case bootstrap runs only when the
bootstrap's verdict maps to `processed`. A bootstrap the handler refused or
deferred has not made the case locally available, so replaying its held
activities would only defer them again. The legacy adapter paths
(`inbox_handler._dispatch_or_defer_inbox_item`, `InboxPipeline.process`)
apply the same gate through `HandlerResult.took_effect`. A replay that raises
is logged and does not turn an applied bootstrap into `rejected`
(MV-01-007). This is inert while every received handler returns `APPLIED`,
and becomes live as handlers adopt real dispositions (#2255).

This two-adapter design was chosen over:

- **Single adapter** (collapsed ingress + dispatch): rejected because the
  seam becomes opaque and re-couples wire parsing to dispatch.
- **Three+ adapters** (separate parse, rehydrate, extract): rejected because
  each intermediate step becomes an external dependency that callers could
  invoke out of order, undermining the module's depth invariant.

---

## Pending-Queue Port Injection

The defer-check step (step 4) needs to read and write the pending case
activity queue. Rather than importing `inbox_pending_queue` directly from
the adapter layer, the BT module accepts a **pending-queue port** (a
Protocol interface) as an injected argument.

The concrete implementation (wrapping `_queue_pending_case_activity`,
`_expire_pending_case_activities`, `_replay_pending_case_activities`) is
provided by the FastAPI adapter at construction time.

This pattern:

- Keeps `core/` free of adapter imports (ADR-0009 Rule 1).
- Allows the test suite to supply an in-memory pending-queue stub.
- Preserves the existing queue semantics without duplication.

---

## Test Surface

Tests MUST target the `process_payload` interface:

```python
outcome = process_payload(raw_payload, ingress_adapter, dispatch_adapter)
assert outcome.status is InboxOutcomeStatus.PROCESSED
assert outcome.context_id == expected_case_id
```

Tests MUST NOT monkeypatch internal BT node helpers. Ordering effects and
deferred-queue behavior are observable through `InboxOutcome.status` and
the queue port's recorded calls.

Both a production adapter (wrapping the FastAPI/ASGI stack) and an
in-memory test adapter should implement `IngressPayloadAdapter` so the
same interface is exercised in both contexts.

---
