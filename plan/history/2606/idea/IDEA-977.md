---
source: IDEA-977
timestamp: '2026-06-16T15:49:04.230855+00:00'
title: Inbox BT orchestration with typed process_payload seam
type: idea
---

## Summary

Deepen the Inbox flow into one core module whose interface is a single
`process_payload` entry point and whose implementation is an auditable
Behavior Tree. The module should own end-to-end orchestration of inbound
Activity handling instead of spreading policy across shallow helpers.

## Motivation

The current Inbox flow is shallow: interface knowledge and implementation
behavior are split across multiple modules (`inbox_handler` and
`inbox_pipeline`) with duplicated/delegated helper behavior. This reduces
locality and makes review/debugging depend on cross-file tracing.

This idea captures the agreed direction to increase:

- **locality**: one module owns parse → rehydrate → semantic extraction →
  defer check → dispatch
- **leverage**: one interface serves both runtime Inbox adapters and tests
- **auditability**: explicit BT nodes provide observable ordered behavior

## Rough Approach

### Deep module shape

Create a core Inbox orchestration module with a single caller-facing interface:

- `process_payload(...) -> InboxOutcome`

Where `InboxOutcome` is typed and includes:

- status: `processed | deferred | rejected`
- `context_id`
- `failure_reason`

### Enforced internal ordering (inside module implementation)

The module implementation enforces fixed ordering with BT sequence nodes:

1. Parse inbound payload
2. Rehydrate Activity
3. Extract `MessageSemantics`
4. Duplicate / defer eligibility check (Case context readiness)
5. Dispatch to use-case path
6. Build typed outcome

### Seam and adapter discipline

Use one explicit seam with exactly two adapters:

1. **Ingress payload adapter**
2. **Dispatch adapter**

Keep parse/extract orchestration implementation internal to the deep module.

### Error and outcome behavior

- For protocol-invalid payloads, return typed `rejected` outcomes (do not
  throw).
- Preserve explicit failure_reason values for observability and triage.

### Placement

- BT orchestration module lives in core.
- Adapters are injected by adapter-layer construction.
- The FastAPI Inbox path remains simple caller glue around the deep module
  interface.

**Processed**: 2026-06-16 — implementation tracked in #997.
Docs PR: <https://github.com/CERTCC/Vultron/pull/996>.
Spec: `specs/inbox-orchestration.yaml`.
Notes: `notes/inbox-orchestration.md`.
