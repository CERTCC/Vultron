---
source: NOTES-use-case-behavior-trees--standardized-use-case-interface
timestamp: '2026-09-17T17:32:56.949352+00:00'
title: Standardized Use Case Interface + SEMANTICS_HANDLERS Migration
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** vultron/core/ports/use_case.py UseCase Protocol; USE_CASE_MAP in core/ports/dispatcher.py

---

## Standardized Use Case Interface

### Problem

Use cases in `core/use_cases/` are currently standalone functions with
heterogeneous signatures. Each adapter must know the exact calling convention
for every function, creating tight coupling and complicating future
extensibility.

### Proposed Protocol

Define a generic `UseCase` protocol with explicit request and response types:

```python
from typing import Protocol, TypeVar

Req = TypeVar("Req")
Res = TypeVar("Res")


class UseCase(Protocol[Req, Res]):
    def execute(self, request: Req) -> Res: ...
```

Each use case:

* accepts **exactly one request object** (a Pydantic model)
* returns **exactly one response object** (a Pydantic model)
* implements an `execute()` method

### Rationale

* **Consistent invocation** — all adapters call use cases the same way.
* **Loose coupling** — adapters depend on the protocol, not individual
  function signatures.
* **Stable evolution** — request/response objects allow fields to evolve
  without breaking adapters.
* **Clear boundary** — `execute()` is the explicit entry point into core.
* **Tooling compatibility** — structured request objects are easier to
  serialize, validate, log, or expose to agent/tool interfaces.

### Important Ordering Note

The use-case interface standardization SHOULD be implemented **before**
P75-4 (refactoring driving adapters to call use cases directly). A
consistent `execute()` interface makes P75-4 significantly simpler.

### Use Case Naming Convention

Handler use cases (processing incoming messages from another party) SHOULD carry
a `Received` suffix: `CreateReportReceivedUseCase`. Trigger use cases
(actor-initiated actions) SHOULD carry a `Svc` prefix: `SvcEngageCaseUseCase`.
This mirrors the `FooReceivedEvent` / `FooTriggerEvent` convention for domain
events (CS-10-002) and makes the origin unambiguous at a glance. See
`specs/code-style.yaml` CS-12-002 and TECHDEBT-21.

### UseCaseRequest Envelope (Evaluated and Rejected — see ADR-0040)

`UseCaseRequest` was evaluated during the planning of issue #423 and
**rejected**. The core finding: `VultronEvent` and `TriggerRequest` share the
field name `actor_id` but carry it in semantically opposite roles — one
represents inbound remote actor identity, the other represents local outbound
intent. Merging them under a shared base collapses a security boundary.

See `docs/adr/0040-use-case-result-envelope.md` for the full decision
rationale and `notes/use-case-protocol.md` for implementation guidance on the
`UseCaseResult` hierarchy that was introduced instead.

### SEMANTICS_HANDLERS Migration

`SEMANTICS_HANDLERS` in `vultron/api/v2/backend/handler_map.py` maps
`MessageSemantics` values (domain concepts) to handler callables (domain
code). Because this mapping is domain knowledge, it belongs in
`core/use_cases/use_case_map.py`, not in the adapter layer. This migration
should happen as part of P75-2c.

**See**: `notes/domain-model-separation.md` "Post-P75-2 Architecture
Findings" for additional context.
