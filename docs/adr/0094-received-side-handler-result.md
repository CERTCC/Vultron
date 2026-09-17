---
status: accepted
date: 2026-09-17
deciders: Allen D. Householder
---

# Received-Side `HandlerResult` Carries a Handler Disposition Across the Dispatcher Boundary

## Context and Problem Statement

ADR-0040 introduced the `UseCaseResult` envelope with `HandlerResult` and
`TriggerResult` subtypes, and explicitly declined to decide one question:

> The dispatcher's own `dispatch()` return type is **not** changed in this
> issue. Surfacing `UseCaseResult` through the dispatcher boundary is a
> separate architectural decision.

That deferral left the received-side half of the envelope without a purpose.
`HandlerResult` was specified (UCORG-05-002) as a required return type carrying
no required fields, and nothing downstream could read it — so implementing it
literally would change 51 signatures to convey nothing. Concern #1769 asked what
a received-side `HandlerResult` is *for* before writing that code.

It is for carrying a handler's own verdict to `InboxOutcome`.

Two failure paths exist on the received side, and they are distinct:

- **Acceptance.** "Is this a well-formed activity addressed to me?" Decided
  synchronously in `post_actor_inbox`, answered as HTTP 400 or 202. Works today.
- **Processing.** "Did handling that well-formed activity actually succeed?"
  Decided later, in the background task, and reported as `InboxOutcome`.

The second path is unobservable. `InboxOutcome` already models `rejected` and
carries `failure_reason`, but `_read_inbox_outcome()` assembles it from
inbox-BT blackboard keys rather than from the handler, and `DispatchNode` treats
"dispatch did not raise" as SUCCESS. Every link between the handler and the
outcome is typed `-> None`:

```text
execute() -> None
  → ActivityDispatcher.dispatch() -> None        (core/dispatcher.py)
  → dispatch() -> None                           (adapters/.../inbox_handler.py)
  → FastAPIDispatchAdapter.dispatch() -> None    (adapters/.../inbox_orchestration.py)
  → DispatchAdapter Protocol -> None             (core/behaviors/inbox/models.py)
  → DispatchNode.update()
```

So a handler can inspect an activity, find nothing it can act on, log a warning,
return, and the pipeline still reports `status="processed"`. Bug #2255 records
this, names the same three-layer drop, and points at this ADR for the contract.

## Decision Drivers

- The handler is the only component that knows what happened to its activity.
- `InboxOutcome` already exists and already models the destination vocabulary;
  a second parallel vocabulary would be worse than none.
- Not every behavior-tree `FAILURE` is a refusal. Benign idempotent skips must
  keep reporting `processed`, so the contract must distinguish them.
- The received-side use-case layer has no base class — all 51 handler classes
  are standalone — so the contract cannot rely on inherited default behavior.
- `specs/handler-protocol.yaml` HP-01-002 (`MAY` return None or HandlerResult)
  and `specs/use-case-organization.yaml` UCORG-05-002 (`MUST` return
  HandlerResult) contradict each other. One of them has to lose.

## Considered Options

1. **Empty envelope.** Give all 51 handlers a fieldless `HandlerResult`.
   Satisfies UCORG-05-002 literally.
2. **Disposition-carrying envelope threaded through the dispatcher boundary.**
   `HandlerResult` carries the handler's verdict; every link in the chain
   returns it; `InboxOutcome` is derived from it.
3. **Narrow UCORG-05 to the trigger side.** Delete UCORG-05-002, keep
   HP-01-002, leave received handlers at `-> None`.
4. **Side channel.** Keep every `dispatch()` at `-> None`; handlers write their
   verdict to a collector object or blackboard key that `DispatchNode` reads.

## Decision Outcome

**Chosen: option 2.**

`HandlerResult` carries a `HandlerDisposition` and an optional `reason`, and the
dispatcher boundary propagates it so that `InboxOutcome` is derived from the
handler's own verdict.

### The disposition vocabulary

`HandlerDisposition` is a `StrEnum` with three values:

| Value | Meaning | Maps to `InboxOutcome.status` |
|---|---|---|
| `APPLIED` | The handler changed local state to reflect the inbound assertion. | `processed` |
| `SKIPPED` | The handler correctly did nothing — duplicate, already-present, or otherwise a legitimate no-op. | `processed` |
| `REFUSED` | The handler rejected the inbound assertion. `reason` is populated. | `rejected` |

`deferred` is deliberately **not** a handler disposition. Deferral is decided by
`DeferCheckNode` *before* dispatch, so a handler is never in a position to
return it. Giving handlers a value they cannot legitimately produce would invite
misuse.

`SKIPPED` exists because `APPLIED` and `SKIPPED` collapse to the same
`InboxOutcome.status` but are not the same event. Today both look identical — a
line in a log file — and `received/status.py` already special-cases
`CASE_STATUS_ALREADY_PRESENT` to keep a benign skip from being read as a
failure. Naming the distinction in the type preserves it for any future
consumer without changing what the pipeline reports.

### Why the dispatcher boundary changes

Option 2 requires overturning ADR-0040's out-of-scope note, because the
dispatcher boundary is the only road from the handler to `InboxOutcome`. ADR-0040
did not decide that the boundary stays `-> None`; it declined to decide, and
this ADR makes the call it deferred.

The change is additive and cheap: 6 call sites, 2 Protocol declarations, and 1
concrete dispatcher. Callers that ignore the returned value keep working, so the
blast radius is bounded by the type declarations rather than by call-site
rewrites.

### Why not the alternatives

**Option 1 (empty envelope)** would satisfy UCORG-05-002 and add a ratchet while
leaving the defect untouched: a fieldless object carries no verdict, so
`InboxOutcome` would still be assembled from blackboard bookkeeping and a no-op
handler would still report `processed`. It is 51 edits that buy a green test.

**Option 3 (narrow to the trigger side)** is the honest choice *if* nothing
consumes a handler verdict — but #2255 is a consumer, filed and open. Deleting
UCORG-05-002 would leave that bug with no contract to build on.

**Option 4 (side channel)** preserves ADR-0040's boundary at the cost of putting
a protocol-relevant verdict in implicit shared state. It is harder to type-check
than a return value and cuts against the project's rule against global mutable
state. The boundary is not valuable enough to protect at that price.

### Consequences

- Good: a genuine refusal reaches `InboxOutcome` with a populated
  `failure_reason` instead of vanishing into a log file.
- Good: the skip-vs-refusal distinction becomes a typed fact rather than
  something a reader infers from log phrasing.
- Good: `UseCaseResult` gains a real definition, which #3354 needs as
  `TriggerResult`'s parent.
- Good: HP-01-002 and UCORG-05-002 stop contradicting each other.
- Neutral: ~31 of the 51 handlers return `APPLIED` unconditionally. The uniform
  contract is what makes the ratchet possible and keeps `-> None` from meaning
  two different things.
- Bad: the migration touches all 51 handler modules. It is partitioned by module
  so a stalled pass cannot strand the contract work.
- Bad: ADR-0040's out-of-scope note is now wrong and must be amended to point
  here, or a future reader will inherit a retired premise.

## Validation

Not yet implemented. This ADR records the decision; the work is tracked
separately, and this section will describe realized validation once it lands.

Planned:

- An architecture ratchet (UCORG-05-004) asserting that every concrete use-case
  class in `vultron/core/use_cases/` declares an `execute()` return annotation
  of `UseCaseResult` or a registered subtype. The ratchet excludes trigger-side
  classes until #3354 migrates them; that exclusion is temporary and tied to
  that issue, not open-ended.
- mypy: the `UseCase` Protocol declares `execute() -> UseCaseResult`, so a
  non-conforming concrete class is reported statically.

Per this ADR's own subject matter: no Validation entry here asserts that a test
exists until it does. ADR-0040's Validation section claimed the ratchet as
existing validation for three months while the file was never written, and that
claim is a direct cause of concern #1769.

## More Information

Supersedes the out-of-scope note in
[ADR-0040](0040-use-case-result-envelope.md) regarding the dispatcher boundary.
The rest of ADR-0040 — the `UseCaseResult` hierarchy and the decision not to
introduce `UseCaseRequest` — stands unchanged.

Design note: `notes/use-case-protocol.md`.

Source concern: #1769. Consumer: #2255. Trigger-side counterpart: #3354.
Related: #2369 and #2682 (surfacing outcomes to the *sender*, which this ADR
does not address — the 202 is already sent before a handler runs).

Generated spec requirements: `specs/use-case-organization.yaml` UCORG-05-001
through UCORG-05-009; `specs/handler-protocol.yaml` HP-01-002.
