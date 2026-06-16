---
title: Inbox Orchestration — BT Module Design
status: active
description: >
  Design decisions and implementation guidance for the core BT-backed inbox
  orchestration module: why orchestration belongs in core/, adapter injection
  rationale, InboxOutcome contract, and pending-queue port design.
related_specs:
  - specs/inbox-orchestration.yaml
related_notes:
  - notes/architecture-hexagonal.md
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

## Two-Adapter Seam Design

`process_payload` accepts exactly two injected adapters:

- **`IngressPayloadAdapter`** — translates raw input (bytes or dict) into a
  rehydrated `as_Activity`. Owns parse + rehydrate; isolates wire-format
  knowledge from the orchestration BT.
- **`DispatchAdapter`** — accepts a `VultronEvent` and executes the
  appropriate use-case path. Wraps the existing `ActivityDispatcher` port.

This two-adapter design was chosen over:

- **Single adapter** (collapsed ingress + dispatch): rejected because the
  seam becomes opaque and re-couples wire parsing to dispatch.
- **Three+ adapters** (separate parse, rehydrate, extract): rejected because
  each intermediate step becomes an external dependency that callers could
  invoke out of order, undermining the module's depth invariant.

---

## BT Node Ordering Invariant

The BT implementation enforces a fixed pipeline via Sequence nodes:

```text
Sequence
  ├─ ParsePayloadNode       (ingress_adapter → as_Activity)
  ├─ RehydrateActivityNode  (rehydrate nested objects)
  ├─ ExtractSemanticsNode   (as_Activity → MessageSemantics)
  ├─ DeferCheckNode         (case context readiness check)
  ├─ DispatchNode           (dispatch_adapter → use case)
  └─ BuildOutcomeNode       (assemble InboxOutcome)
```

The Sequence guarantees that callers can never invoke steps out of order.
BT node names are descriptive and observable — the tree structure is the
workflow documentation.

---

## InboxOutcome Contract

`InboxOutcome` is a Pydantic model returned by every `process_payload` call:

```python
class InboxOutcome(BaseModel):
    status: Literal["processed", "deferred", "rejected"]
    context_id: str | None = None
    failure_reason: str | None = None
```

- `processed` — activity was dispatched successfully.
- `deferred` — activity was queued for replay (case context not yet known).
- `rejected` — activity could not be processed (parse failure, unknown type,
  or protocol violation). `failure_reason` is always populated for `rejected`
  outcomes.

`process_payload` MUST NOT raise for protocol-invalid payloads. All error
conditions produce a typed `rejected` outcome with an explicit
`failure_reason`. Callers use the outcome status to decide logging severity
and response codes.

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
assert outcome.status == "processed"
assert outcome.context_id == expected_case_id
```

Tests MUST NOT monkeypatch internal BT node helpers. Ordering effects and
deferred-queue behavior are observable through `InboxOutcome.status` and
the queue port's recorded calls.

Both a production adapter (wrapping the FastAPI/ASGI stack) and an
in-memory test adapter should implement `IngressPayloadAdapter` so the
same interface is exercised in both contexts.

---

## Migration Path

The existing `InboxPipeline` class and `inbox_handler` function can be
kept temporarily as thin wrappers that delegate to `process_payload` with
production adapters. Once all callers use `process_payload` directly,
the adapter-layer wrappers can be deleted.

See GitHub issue #977 and implementation issue (wired as blocked-by #977)
for task tracking.
