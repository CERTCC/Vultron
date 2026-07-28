---
status: accepted
date: 2026-07-28
deciders: Allen D. Householder
---

# Introduce UseCaseResult Envelope; Do Not Introduce UseCaseRequest

## Context and Problem Statement

All use-case `execute()` methods previously declared bare `None` (received
path) or `dict` (trigger path) return types. The `UseCase` Protocol declared
`execute() -> Any`. This meant:

- mypy could not check that a use-case subtype returned a conforming result.
- Callers that consumed the trigger result used untyped dict-key access
  (`result["activity"]`), which silently broke when keys changed.
- The interface contract between core and its driving adapters was invisible
  to static analysis.

A related question arose: should a `UseCaseRequest` base class be introduced
to unify the two request paths (`VultronEvent` for received-side and
`TriggerRequest` for trigger-side)?

## Decision Drivers

- Make the use-case interface contract explicit and machine-checkable.
- Preserve the semantic distinction between received-side events and
  trigger-side requests.
- Avoid conflating inbound remote actor identity with local actor intent.
- Keep the change mechanical on the result side; avoid regressions from
  request-side restructuring.

## Considered Options (result side)

1. **`UseCaseResult` base with `HandlerResult` / `TriggerResult` subtypes**
   — formalises the existing two-path return contract with typed models.
2. **Generic `UseCaseResult[T]`** — a single generic model with a typed
   `payload: T` field. Defers subtype decisions to call sites.
3. **Fixed plain envelope** — `UseCaseResult(ok: bool, payload: dict | None)`.
   Simple but loses payload type safety.

## Considered Options (request side)

A. **Skip `UseCaseRequest` entirely** — `UseCase` Protocol stays
   `execute() -> UseCaseResult`; `__init__` request parameter remains `Any`
   at the Protocol level, concretely typed in each class.
B. **Marker base `UseCaseRequest(BaseModel)` with no fields** — `VultronEvent`
   and `TriggerRequest` gain a shared parent; Protocol becomes
   `UseCase[UseCaseRequest, UseCaseResult]`.
C. **Shared-field base — push `actor_id` into `UseCaseRequest`** — both
   hierarchies share a common required field.

## Decision Outcome

**Result side: option 1 — `UseCaseResult` with `HandlerResult` / `TriggerResult`.**

**Request side: option A — skip `UseCaseRequest` entirely.**

### Why HandlerResult / TriggerResult over generic

The two paths have genuinely different payload shapes. `HandlerResult` carries
no required payload; `TriggerResult` carries `activity` and `emitting_actor_id`.
A generic would push the type parameter to every call site and complicate the
Protocol definition. Named subtypes are more readable and allow mypy to infer
the correct shape from the concrete class.

### Why UseCaseRequest was not introduced

`VultronEvent` and `TriggerRequest` share the field name `actor_id`, but the
two carry it in semantically opposite roles:

- On `VultronEvent`: `actor_id` is the **remote actor's identity** — extracted
  from the inbound wire-format activity, representing what a remote party
  asserted. The event is "what they told us happened."
- On `TriggerRequest`: `actor_id` is the **local actor's identity** — injected
  by the driving adapter from the URL path, representing an intent our actor
  is about to execute. The request is "what we intend to do."

Merging these into a shared base would collapse the distinction between
inbound remote identity and local outbound intent. A use case accepting
`UseCaseRequest` could no longer statically distinguish which role `actor_id`
played. This is a security-boundary concern, not merely a naming coincidence:
the direction of trust is opposite.

A marker base (option B) avoids the semantic conflation but provides no
enforcement gain — it carries no fields and the structural `Protocol` typing
does not require inheritance. A marker adds an inheritance layer for no benefit.

The `UseCase` Protocol is structural (implicit conformance). Concrete classes
do not need a common base for Protocol compliance. Keeping the `__init__`
request parameter as `Any` at the Protocol level, with precise types at each
concrete class, is explicit and honest.

### Consequences

- Good: `execute()` return type is statically checkable at all 82 call sites.
- Good: Trigger routers use typed attribute access instead of dict-key access.
- Good: The two request paths remain semantically distinct and auditable.
- Neutral: `UseCase` Protocol `__init__` parameter stays `Any`; request typing
  is enforced at the concrete class level, not the Protocol level.
- Bad: Adding a new use case requires the author to return the correct subtype;
  the ratchet test (UCORG-05-004) catches omissions at CI time.

## Validation

- Architecture ratchet test: `test/architecture/test_execute_return_types.py`
  — asserts all concrete use-case classes declare `execute()` → `UseCaseResult`
  or a registered subtype.
- mypy: `UseCase` Protocol declares `execute() -> UseCaseResult`; mypy reports
  non-conforming concrete classes.

## More Information

Generated spec requirements: `specs/use-case-organization.yaml` UCORG-05-001
through UCORG-05-006.

Design note: `notes/use-case-protocol.md`.

Source idea: #423.
