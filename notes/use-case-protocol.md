---
title: Use-Case Protocol — Result Envelope and Request Paths
status: active
description: >
  Design decisions for the UseCaseResult type hierarchy, the two semantically
  distinct request paths (VultronEvent vs TriggerRequest), and why a shared
  UseCaseRequest base was not introduced.
related_specs:
  - specs/use-case-organization.yaml
related_notes:
  - notes/use-case-behavior-trees.md
  - notes/architecture-hexagonal.md
relevant_packages:
  - vultron/core/ports
  - vultron/core/use_cases
  - vultron/core/use_cases/received
  - vultron/core/use_cases/triggers
---

# Use-Case Protocol — Result Envelope and Request Paths

This note records the design decisions for the `UseCase` Protocol contract:
the result envelope type hierarchy and the two semantically distinct request
paths.

See `specs/use-case-organization.yaml` UCORG-05 for the normative requirements.
See `docs/adr/0040-use-case-result-envelope.md` for the full decision record.

---

## UseCaseResult Hierarchy

```text
UseCaseResult (base, Pydantic BaseModel)
  ├── HandlerResult      — returned by received-side use cases
  └── TriggerResult      — returned by trigger-side use cases
```

### HandlerResult

Handler use cases (processing inbound `VultronEvent`s) are fire-and-process:
their primary effect is domain state change, not producing a value for the
caller. `HandlerResult` makes this explicit with no required payload fields.
Subclasses MAY add domain-specific fields (e.g. a resolved entity ID) when
the handler needs to surface something to the dispatcher for logging.

### TriggerResult

Trigger use cases (actor-initiated actions) construct and emit an outbound
ActivityStreams activity. `TriggerResult` carries:

- `activity` — the constructed outbound AS2 activity (optional; `None` for
  best-effort paths where no activity was emitted)
- `emitting_actor_id` — the actor URI that sent the activity

This formalizes what `SvcBTTriggerBase.execute()` previously returned as a
raw `dict`.

---

## Two Request Paths

Use cases accept one of two semantically distinct request types:

| Path | Type | Meaning | Source |
|------|------|---------|--------|
| Received (handler) | `VultronEvent` | "What a remote actor asserted happened" | Wire layer via semantic extractor |
| Trigger | `TriggerRequest` | "What our local actor intends to do" | Adapter layer from HTTP request body |

These are not the same concept. A `VultronEvent` carries:

- `semantic_type` (what the inbound activity means)
- `activity_id` (the remote activity's URI)
- Rich domain objects extracted from wire payload

A `TriggerRequest` carries:

- `actor_id` (the local actor initiating the action)
- Domain IDs for the operation's targets (e.g. `offer_id`, `case_id`)
- No wire-layer fields

Both hierarchies are already well-typed at their base classes and add no
fields that belong to a common ancestor.

---

## Why UseCaseRequest Was Not Introduced

The `UseCase` Protocol is structural (implicit conformance via duck typing).
Concrete classes do not need to inherit from a base for Protocol compliance —
mypy checks the shape, not the inheritance.

Two approaches were evaluated:

**Option A: Marker base (empty `UseCaseRequest(BaseModel)`)**

Both `VultronEvent` and `TriggerRequest` would gain `UseCaseRequest` as a
parent. The Protocol becomes `UseCase[UseCaseRequest, UseCaseResult]`.

Problem: the marker provides no contract. Any `UseCaseRequest` subclass
satisfies the Protocol. It adds an inheritance layer for no enforcement gain.

**Option B: Shared-field base (push `actor_id` into `UseCaseRequest`)**

`actor_id: NonEmptyString` appears in both `VultronEvent` and `TriggerRequest`.
A shared base could own this field.

Problem: the two types carry `actor_id` in different semantic roles.

- On `VultronEvent`, `actor_id` is the **identity of the remote actor** who
  sent the inbound activity — extracted from the wire payload.
- On `TriggerRequest`, `actor_id` is the **identity of our local actor**
  initiating the trigger — injected by the driving adapter from the URL path.

These are not the same thing wearing the same name. Merging them into a shared
base would conflate inbound remote identity with local outbound intent. That
confusion is a security boundary issue, not just a naming coincidence: a use
case that accepted either type at the same parameter would lose the distinction
between "what they told us" and "what we are doing."

**Decision: skip `UseCaseRequest` entirely.**

The `UseCase` Protocol declares `execute() -> UseCaseResult`. The `__init__`
parameter remains typed as `Any` at the Protocol level; concrete classes
carry the precise request type. This is explicit, honest, and avoids the
semantic conflation described above.

See ADR-0040 for the full decision record.

---

## TriggerService and TriggerServicePort Migration

`TriggerService` methods previously returned `dict[str, Any]` because
`SvcBTTriggerBase.execute()` returned a raw `dict`. After the result-envelope
migration:

- `SvcBTTriggerBase.execute()` returns `TriggerResult`
- `TriggerService.*` methods return `TriggerResult`
- `TriggerServicePort` Protocol method signatures declare `TriggerResult`
- Routers access typed fields (`result.activity`, `result.emitting_actor_id`)
  instead of dict keys

This propagation is mechanical: the only semantic change is that callers use
attribute access instead of dict-key access.

---

## Dispatcher Behavior

The dispatcher calls `use_case_class(dl, event, **extra_kwargs).execute()`.
After the migration it captures the result in a local variable for logging:

```python
result = use_case_class(dl, event, **extra_kwargs).execute()
logger.debug("use case result: %s", result)
```

The dispatcher's own `dispatch()` return type is **not** changed in this
issue. Surfacing `UseCaseResult` through the dispatcher boundary is a
separate architectural decision.

---

## Ratchet Test

`test/architecture/test_execute_return_types.py` inspects all concrete
use-case classes in `vultron/core/use_cases/` and asserts that their
`execute()` annotation is `UseCaseResult` or a subtype. This catches drift
when new use cases are added without the correct return type, independent
of mypy configuration.
