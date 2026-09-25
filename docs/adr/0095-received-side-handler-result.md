---
status: accepted
date: 2026-09-17
deciders: Allen D. Householder
stakeholder_type: [project-contributor]
---

# Received-Side `HandlerResult` Carries a Handler Disposition Across the Dispatcher Boundary

## Context and Problem Statement

ADR-0040 introduced the `UseCaseResult` envelope with `HandlerResult` and
`TriggerResult` subtypes. It said nothing at all about whether that envelope
crosses the dispatcher boundary — the words "dispatch" and "scope" do not appear
in it. The only place that question was ever addressed is a design note:

> The dispatcher's own `dispatch()` return type is **not** changed in this
> issue. Surfacing `UseCaseResult` through the dispatcher boundary is a
> separate architectural decision.
>
> — `notes/use-case-protocol.md`, before this ADR

So the boundary was never decided in either direction, and nothing of ADR-0040's
needs overturning to decide it now. (Concern #1769 cites "ADR-0040 'Out of
Scope'" as having settled the boundary at `-> None`. There is no such section;
that citation is mistaken, and the note above is what it was reaching for.)

That silence left the received-side half of the envelope without a purpose.
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
  → DispatcherBase._handle() -> None             (core/dispatcher.py — calls execute())
  → DispatcherBase.dispatch() -> None            (core/dispatcher.py)
  → ActivityDispatcher Protocol -> None          (core/ports/dispatcher.py)
  → dispatch() -> None                           (adapters/.../inbox_handler.py)
  → FastAPIDispatchAdapter.dispatch() -> None    (adapters/.../inbox_orchestration.py)
  → DispatchAdapter Protocol -> None             (core/behaviors/inbox/models.py)
  → DispatchNode.update()
```

`_handle()` is the link that actually calls `execute()`; `dispatch()` only logs
and delegates to it. It is easy to miss and it is the first hop the verdict has
to survive.

So a handler can inspect an activity, find nothing it can act on, log a warning,
return, and the pipeline still reports `status="processed"`. Bug #2255 records
this, names the same three-layer drop, and points at this ADR for the contract.

## Decision Drivers

- The handler is the only component that knows what happened to its activity.
- `InboxOutcome` already exists and already models the destination vocabulary;
  a second parallel vocabulary would be worse than none.
- Not every behavior-tree `FAILURE` is a refusal, and not every `SUCCESS` is
  applied work. Benign idempotent skips must keep reporting `processed`, and the
  ledger-sync buffer nodes return `SUCCESS` for an entry they have only parked, so
  the contract must distinguish all three from a refusal.
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

`HandlerDisposition` is a `StrEnum` with four values:

| Value | Meaning | Maps to `InboxOutcome.status` |
|---|---|---|
| `APPLIED` | The handler changed local state to reflect the inbound assertion. | `processed` |
| `SKIPPED` | The handler correctly did nothing — duplicate, already-present, or otherwise a legitimate no-op. | `processed` |
| `DEFERRED` | The handler parked the item for later replay rather than acting on it or declining it. | `deferred` |
| `REFUSED` | The handler rejected the inbound assertion. `reason` is populated. | `rejected` |

`DEFERRED` is a member because handler-side deferral is real, and it is easy to
talk oneself out of. `DeferCheckNode` runs *before* dispatch and handles one kind
of deferral — the case context is not known locally yet — which makes it tempting
to conclude that a handler can never produce one. But the ledger-sync path does
exactly that: `BufferOutOfOrderEntryNode` and `BufferPreGenesisEntryNode`
(`core/behaviors/sync/nodes/receive.py`) return `SUCCESS` after parking an entry
in the actor-local `LedgerGapBuffer`, to be replayed once its predecessor or its
`VulnerabilityCase` seed arrives. `AnnounceLedgerEntryReceivedUseCase` reaches
them through normal dispatch.

A parked entry is not applied, is not a benign no-op, and is not refused. Forcing
it into `APPLIED` would claim the assertion landed; forcing it into `SKIPPED`
would claim there was nothing to do. Both discard the one fact a reader needs —
that a replay is pending — and `InboxOutcome` already models `deferred`, so there
is nothing to invent. The two producers of `deferred` stay distinct: pre-dispatch
(`DeferCheckNode`, missing case context) and post-dispatch (a handler returning
`DEFERRED`).

This does not weaken HP-01-004. A handler reports in its own vocabulary;
`DispatchNode` still owns the mapping onto `InboxOutcome`.

`SKIPPED` exists because `APPLIED` and `SKIPPED` collapse to the same
`InboxOutcome.status` but are not the same event. Today both look identical — a
line in a log file — and `received/status.py` already special-cases
`CASE_STATUS_ALREADY_PRESENT` to keep a benign skip from being read as a
failure. Naming the distinction in the type preserves it for any future
consumer without changing what the pipeline reports.

### Why the dispatcher boundary changes

The dispatcher boundary is the only road from the handler to `InboxOutcome`, so
option 2 requires deciding a question no prior ADR reached. This ADR decides it:
the boundary returns `HandlerResult`.

The change is additive and cheap: six return-type declarations — two Protocols
(`ActivityDispatcher`, `DispatchAdapter`), two methods on the single concrete
dispatcher (`_handle`, `dispatch`), and two adapter-level functions. Callers that
ignore the returned value keep working, so the blast radius is bounded by the
type declarations rather than by call-site rewrites.

Two parts of the chain need explicit handling and are easy to overlook:

- **`_handle()` can return without a handler running.** It catches
  `UnroutableActivityError`, logs, and returns (no `case_id` extractable), and
  `_get_use_case()` raises `VultronApiHandlerNotFoundError` for unrecognised
  semantics. In the first case no exception escapes, so a dropped activity is
  reported as `processed` today. A `HandlerResult` return type alone does not fix
  that: the dispatcher layer has to synthesise a verdict when no handler ran, and
  UCORG-05-012 requires it.
- **Most `SKIPPED` decisions do not live in `execute()`.** `_idempotent_create`
  and its peers in `vultron/core/use_cases/_helpers.py` return without storing
  when the record already exists, and are themselves `-> None`. Five handlers
  delegate their entire duplicate-skip decision to that layer, so it has to
  return a disposition too or `SKIPPED` is unreachable for the most common skip
  in the codebase.

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
  `failure_reason` instead of being observable only in the actor's own log.
  (One path is already better than that: `received/status.py` emits a
  `Create(ProcessingFault)` carrying
  `VULTRON_FAILURE_STATUS_ASSERTION_REFUSED` for a non-idempotent status
  failure. That behaviour predates this ADR and must not regress.)
- Good: the skip-vs-deferral-vs-refusal distinction becomes a typed fact rather
  than something a reader infers from log phrasing. A ledger entry parked pending
  its predecessor stops reporting as `processed`.
- Good: `UseCaseResult` gains a real definition, which #3354 needs as
  `TriggerResult`'s parent.
- Good: HP-01-002 and UCORG-05-002 stop contradicting each other.
- Bad: the migration is mostly judgment, not a mechanical pass. Of the 51
  handlers, 34 carry at least one early-return guard clause and 9 more log a
  failure and fall through without changing state, so roughly 43 need a
  refusal-vs-skip determination; only a handful do unconditional work. (#2255
  enumerates ~20 BT-non-success call sites — that is the narrower population of
  sites where a `Status.FAILURE` is logged, not the full set of handlers needing a
  disposition decision.) #3372 therefore returns `APPLIED` everywhere and leaves
  every classification to #2255, so the contract can land without waiting on 43
  judgments.
- Bad: the migration touches all 51 handler modules plus the shared helpers in
  `use_cases/_helpers.py`. It is partitioned by module so a stalled pass cannot
  strand the contract work.
- Neutral: ADR-0040 needs a pointer here so a reader of the older ADR learns the
  boundary has since been decided. Nothing in ADR-0040 becomes wrong.

## Validation

Implemented for the received side and the dispatcher boundary; the trigger side is #3354.

Realized:

- The architecture ratchet `test/architecture/test_use_case_execute_returns_result.py` (UCORG-05-004) asserts that every concrete use-case class in `vultron/core/use_cases/` declares an `execute()` return annotation that resolves to `UseCaseResult` or a subtype (#3372).
  It excludes `triggers/` until #3354 migrates them, names that issue, and fails once the exclusion is no longer needed.
- The `UseCase` Protocol declares `execute() -> UseCaseResult`.
  No call site is yet typed against the Protocol, so mypy does not report a non-conforming class by itself; the ratchet does.
- `test/adapters/driving/fastapi/test_inbox_outcome_chain.py` covers the two paths a ratchet cannot see, driving the real FastAPI dispatch adapters, dispatcher, and inbox BT with only the use case stubbed (#3373).
  A `REFUSED` disposition reaches `InboxOutcome.status == "rejected"` with the handler's reason as `failure_reason`, and an unroutable or unrecognised-semantics activity does **not** report `processed` (UCORG-05-012).
  The same file checks that `run_inbox_pipeline` logs a rejection at WARNING (UCORG-05-013).

Per this ADR's own subject matter: no Validation entry here asserts that a test
exists until it does. ADR-0040's Validation section claimed the ratchet as
existing validation for three months while the file was never written, and that
claim is a direct cause of concern #1769.

## More Information

Extends [ADR-0040](0040-use-case-result-envelope.md), which introduced the
`UseCaseResult` hierarchy but did not reach the dispatcher boundary. ADR-0040
stands unchanged; it gains only a pointer here.

Design note: `notes/use-case-protocol.md`.

Source concern: #1769. Consumer: #2255. Trigger-side counterpart: #3354.
Related: #2369 and #2682 (surfacing outcomes to the *sender*, which this ADR
does not address — the 202 is already sent before a handler runs).

Generated spec requirements: `specs/use-case-organization.yaml` UCORG-05-004b,
UCORG-05-005, and UCORG-05-009 through UCORG-05-013 (this ADR also relies on the
pre-existing UCORG-05-001 through UCORG-05-008);
`specs/handler-protocol.yaml` HP-01-002 (amended), HP-01-003, and HP-01-004.
