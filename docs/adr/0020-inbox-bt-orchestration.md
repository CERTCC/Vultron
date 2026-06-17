---
status: proposed
date: 2026-06-16
deciders:
  - vultron maintainers
consulted:
  - project stakeholders
informed:
  - contributors
---

# Move Inbox Orchestration into a Core BT Module with a Typed `process_payload` Seam

## Context and Problem Statement

The Vultron inbox pipeline — parse → rehydrate → extract semantics →
defer-check → dispatch — is currently implemented across two modules in
`vultron/adapters/driving/fastapi/`: `inbox_handler.py` and
`inbox_pipeline.py`. Both modules live in the adapter layer, which means:

1. Non-HTTP entry points (CLI, tests, future MCP adapter) cannot reuse the
   pipeline without importing adapter-layer code, violating ADR-0009 Rule 1.
2. The ordering of pipeline steps is not enforced; callers can invoke helpers
   in any order.
3. Errors surface as exceptions, not typed outcomes, so callers must use
   exception-driven control flow at the integration boundary.
4. Tests are patch-heavy and fragile against internal refactors.

A structured, BT-backed orchestration module in `core/` addresses all four
issues while extending the BT-as-auditable-process-model established in
ADR-0002.

## Decision Drivers

- **Hexagonal architecture compliance**: Core policy must not live in the
  adapter layer (ADR-0009 Rule 1).
- **Reusability**: The same pipeline should be available to FastAPI, CLI, and
  tests without code duplication.
- **Auditability**: Fixed BT ordering makes the pipeline inspectable and
  prevents step misordering.
- **Typed outcomes**: A `process_payload(...) -> InboxOutcome` seam gives
  callers a uniform, exception-free way to handle all outcome cases.
- **Testability**: Interface-level assertions on `InboxOutcome` are resilient
  to internal refactors.

## Considered Options

1. **Keep pipeline in the adapter layer, improve `InboxPipeline`** — refine
   the existing `InboxPipeline` class without moving it to `core/`.
2. **Move pipeline to `core/` as a plain function** — extract a
   procedural `process_payload` function without BT backing.
3. **Move pipeline to `core/` as a BT-backed module (chosen)** — implement
   orchestration as a Behavior Tree in `vultron/core/behaviors/inbox/` with
   `process_payload(...) -> InboxOutcome` as the sole public entry point.

## Decision Outcome

Chosen option: **Move pipeline to `core/` as a BT-backed module**, because
it satisfies the hexagonal architecture constraint, enforces fixed pipeline
ordering through BT Sequence nodes, and aligns with the project's
BT-as-process-model pattern established in ADR-0002.

### Seam Design

`process_payload` accepts two injected adapters and a pending-queue port:

- **`IngressPayloadAdapter`**: raw input (bytes/dict) → rehydrated
  `as_Activity`. Owns parse + rehydrate; keeps wire-format knowledge out of
  the BT nodes.
- **`DispatchAdapter`**: `VultronEvent` → use-case execution. Wraps the
  existing `ActivityDispatcher` port.
- **Pending-queue port** (injected): provides defer/replay queue operations
  to the `DeferCheckNode` without importing adapter-layer code.

The FastAPI inbox endpoint constructs production adapter implementations and
calls `process_payload` in a `BackgroundTask`. CLI and test callers supply
alternative adapters.

### BT Node Ordering

```text
Sequence
  ├─ ParsePayloadNode
  ├─ RehydrateActivityNode
  ├─ ExtractSemanticsNode
  ├─ DeferCheckNode
  ├─ DispatchNode
  └─ BuildOutcomeNode
```

### Consequences

- Good, because the pipeline is reusable from any entry point.
- Good, because BT Sequence ordering is enforced and observable.
- Good, because `InboxOutcome` gives callers a uniform, typed result.
- Good, because interface-level tests replace fragile patch-heavy tests.
- Bad, because the existing `InboxPipeline`/`inbox_handler` must be migrated
  or shimmed, adding short-term transition overhead.
- Bad, because a third injected parameter (pending-queue port) increases
  construction complexity at the adapter layer.

## Validation

- `specs/inbox-orchestration.yaml` IO-01 through IO-04 define testable
  requirements for this decision.
- `process_payload` is located in `vultron/core/behaviors/inbox/` with no
  imports from `vultron/adapters/`.
- `InboxOutcome.status` covers `processed | deferred | rejected`; no
  `process_payload` code path raises for protocol-invalid input.
- Tests assert on `InboxOutcome` fields, not on internal BT node helpers.

## Pros and Cons of the Options

### Keep pipeline in the adapter layer (Option 1)

- Good: no migration cost; existing callers unchanged.
- Bad: non-HTTP entry points cannot reuse the pipeline without adapter
  imports — ADR-0009 violation persists.
- Bad: step ordering remains unenforced; callers can invoke helpers
  out of order.

### Move to `core/` as a plain function (Option 2)

- Good: satisfies hexagonal architecture constraint.
- Good: reusable from any entry point.
- Bad: ordering is still procedural and not intrinsically observable.
- Bad: errors must be caught and translated at every call site rather than
  surfaced as typed outcomes automatically.

### Move to `core/` as a BT-backed module (Option 3, chosen)

- Good: satisfies hexagonal architecture (ADR-0009 Rule 1).
- Good: BT Sequence enforces and documents pipeline order.
- Good: aligns with ADR-0002 BT-as-process-model.
- Good: typed `InboxOutcome` gives uniform caller contract.
- Neutral: BT node granularity adds slight structural overhead vs procedural.
- Bad: migration of existing adapter-layer callers required.

## More Information

- `notes/inbox-orchestration.md` — design decisions, adapter injection
  rationale, InboxOutcome contract, and migration path.
- `specs/inbox-orchestration.yaml` — testable requirements (IO-01–IO-04).
- `docs/adr/0002-model-processes-with-behavior-trees.md` — BT-as-process-model
  rationale.
- `docs/adr/0009-hexagonal-architecture.md` — hexagonal architecture rules
  this decision extends.
- GitHub issue #977 — source Idea issue.
