---
title: Use-Case Protocol — Result Envelope and Request Paths
status: active
description: >
  Design decisions for the UseCaseResult type hierarchy, the HandlerDisposition
  vocabulary and its route to InboxOutcome, the two semantically distinct request
  paths (VultronEvent vs TriggerRequest), and why a shared UseCaseRequest base
  was not introduced. Received side and dispatcher chain migrated; trigger side
  decided (ADR-0110: one dispatcher method over a verb registry), not yet built.
related_specs:
  - specs/use-case-organization.yaml
  - specs/handler-protocol.yaml
  - specs/inbox-orchestration.yaml
  - specs/triggerable-behaviors.yaml
related_notes:
  - notes/use-case-behavior-trees.md
  - notes/architecture-hexagonal.md
  - notes/inbox-orchestration.md
relevant_packages:
  - vultron/core/models
  - vultron/core/ports
  - vultron/core/use_cases
  - vultron/core/use_cases/received
  - vultron/core/use_cases/triggers
  - vultron/core/behaviors/inbox
---

# Use-Case Protocol — Result Envelope and Request Paths

This note records the design decisions for the `UseCase` Protocol contract:
the result envelope type hierarchy and the two semantically distinct request
paths.

See `specs/use-case-organization.yaml` UCORG-05 for the normative requirements.
See `docs/adr/0040-use-case-result-envelope.md` for the original decision record
and `docs/adr/0095-received-side-handler-result.md` for the received-side half.

> **Status: received half adopted, trigger half not.** `UseCaseResult`,
> `HandlerResult`, and `HandlerDisposition` exist in
> `vultron/core/models/use_case_result.py` (#3371). Every received-side
> `execute()` declares `-> HandlerResult`, and the `UseCase` Protocol declares
> `-> UseCaseResult` (#3372); the query use case returns `ActionRulesResult`.
> `test/architecture/test_use_case_execute_returns_result.py` enforces
> UCORG-05-004 outside `triggers/`. The dispatcher returns the value and
> `DispatchNode` maps its disposition onto `InboxOutcome.status` (#3373). Each
> handler exit returns the disposition it earned (#2255; see
> [Assigning a disposition](#assigning-a-disposition)). On the trigger side, a standalone
> `TriggerResult` envelope lives in `vultron/core/use_cases/triggers/results.py`
> (#3398), plus a demo-layer `ActivityResult` subtype, introduced only so
> `ActorSession` can type demo trigger responses at the HTTP boundary; it does
> not yet inherit `UseCaseResult`, and trigger `execute()` methods still return
> `dict` (#3831). Earlier revisions of this note described the whole migration
> in the past tense while no part of it had been written — that drift is what
> concern #1769 was filed to correct.

---

## UseCaseResult Hierarchy

```text
UseCaseResult (base, Pydantic BaseModel)
  ├── HandlerResult      — returned by received-side use cases
  └── TriggerResult      — returned by trigger-side use cases
```

### HandlerResult

Handler use cases process inbound `VultronEvent`s. Their primary effect is
domain state change, but they are *not* fire-and-forget: the handler is the only
component that knows what actually happened to the activity, and that verdict has
a destination (`InboxOutcome`). `HandlerResult` carries it:

- `disposition: HandlerDisposition` — what the handler did
- `reason: str | None` — required when the disposition is `REFUSED` (it becomes
  `failure_reason`), rejected on `APPLIED`, and optional on `SKIPPED` and
  `DEFERRED`, where it says why the no-op was correct or what a parked item
  awaits. Enforced at construction; the model is frozen.

`REFUSED` covers protocol outcomes only — the handler decided the assertion must
not be applied. A programming error is not a refusal: it propagates as an
exception, as it does today, so the dispatcher side can keep telling the two
apart the way `BTExecutionResult.internal_error` does for a behavior tree
(CONCERN-3019).

`HandlerDisposition` is a `StrEnum`, following the project idiom for closed
value sets (`CVDRole`, `VultronObjectType`) — not a `Literal`:

| Value | Meaning | `InboxOutcome.status` |
|---|---|---|
| `APPLIED` | Local state changed to reflect the inbound assertion. | `processed` |
| `SKIPPED` | Correct no-op — duplicate, already-present, or otherwise legitimately nothing to do. | `processed` |
| `DEFERRED` | Parked for later replay, not acted on and not declined. | `deferred` |
| `REFUSED` | The inbound assertion was rejected; `reason` is populated. | `rejected` |

Two things to note about the vocabulary:

- **`DEFERRED` is here even though `DeferCheckNode` runs before dispatch.** That
  node handles one kind of deferral — the case context is not known locally yet —
  and it is tempting to conclude from it that a handler can never defer. The
  ledger-sync path does: `BufferOutOfOrderEntryNode` and
  `BufferPreGenesisEntryNode` (`core/behaviors/sync/nodes/receive.py`) return
  `SUCCESS` after parking an entry in the `LedgerGapBuffer` for replay once its
  predecessor arrives, and `AnnounceLedgerEntryReceivedUseCase` reaches them
  through normal dispatch. So `deferred` has two producers, pre- and
  post-dispatch, and only the second flows through `HandlerDisposition`.
- **`APPLIED` and `SKIPPED` both map to `processed`,** and that is intentional.
  They are the same *report* but not the same *event*. Today both look identical
  — a line in a log file — and `received/status.py` already special-cases
  `CASE_STATUS_ALREADY_PRESENT` to keep a benign skip from reading as a failure.
  Naming the distinction in the type keeps it available without changing what the
  pipeline reports.

Subclasses MAY add domain-specific fields, but MUST NOT carry raw `dict`
payloads (UCORG-05-005).

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

## Trigger Side: One Dispatcher Method over a Verb Registry

Decided in ADR-0110, planned from concern #3354, not yet built. The trigger
half does **not** get the mechanical "type the 27 methods" migration this note
once described. The driving port collapses to one method and the two request
families become one:

- `TriggerResult` becomes a fieldless `UseCaseResult` subtype in
  `vultron/core/models/`; the required fields move down to `ActivityResult`
  (`activity`, `emitting_actor_id`), with sibling subtypes for the verbs whose
  live bodies differ (`NoteResult`, `StatusResult`, `OfferResult`,
  `RoleOfferResult`). Every subtype forbids extra keys (UCORG-05-005).
- Each `TriggerRequest` subclass is generic in its result type, so the port is
  one method — `TriggerDispatcher.trigger(request, dl) -> ResultT` — and mypy
  and pyright resolve the verb's result at the call site (UCORG-05-006).
- A verb-keyed registry under `vultron/trigger_registry/` (mirroring
  `vultron/semantic_registry/`) maps verb → request model, use case, result
  type, exposure. It is a data table with a lookup; the ratchets iterate it
  (TRIG-12-004). It exists for enumeration, not routing.
- Routes stay hand-written; each body becomes one call into a shared
  `run_trigger(...)` helper and declares `response_model` (TRIG-12-001).
- `TriggerService`, `TriggerServicePort`, and the adapter-layer duplicate
  request models are deleted at the end, behind a golden OpenAPI snapshot and
  exact-key-set tests (TRIG-12-002, TRIG-12-003).

The response bodies stay byte-identical throughout; the typed conversion is one
layer above the BT: `SvcBTTriggerBase`'s template (`_prepare` / `_build_tree` /
`_handle_result`, `BTBridge` construction, the guards) does not change; only its
final `return {...}` becomes the typed `ActivityResult`.
Migration order and the reasons for it are in the ADR.

---

## Dispatcher Behavior — the Verdict Chain

No ADR before ADR-0095 reached the question of whether `UseCaseResult` crosses
the dispatcher boundary — ADR-0040 does not mention it, and an earlier revision
of *this note* was the only place it was ever addressed, with a bare "separate
architectural decision." ADR-0095 decides it: **it does**, because that boundary
is the only road from the handler to `InboxOutcome`.

`InboxOutcome` (`vultron/core/behaviors/inbox/models.py`) models
`processed`/`deferred`/`rejected` and carries `failure_reason`, and
`_read_inbox_outcome()` assembles it from inbox-BT blackboard keys. Before the
change in #3373, `DispatchNode.update()` treated "dispatch did not raise" as
SUCCESS and every link from `execute()` to `DispatchNode` was typed `-> None`, so a
handler's verdict could not reach `InboxOutcome`: a handler could find nothing
it could act on, log a warning, return, and the pipeline still reported
`processed`. #3373 put the plumbing in place and #2255 gave each handler its real
disposition.

Each link returns `HandlerResult`:

```text
execute() -> HandlerResult
  → DispatcherBase._handle()           core/dispatcher.py — calls execute()
  → DispatcherBase.dispatch()          core/dispatcher.py
  → ActivityDispatcher Protocol        core/ports/dispatcher.py
  → dispatch()                         adapters/driving/fastapi/inbox_handler.py
  → FastAPIDispatchAdapter.dispatch()  adapters/driving/fastapi/inbox_orchestration.py
  → DispatchAdapter Protocol           core/behaviors/inbox/models.py
  → DispatchNode.update()              maps disposition → InboxOutcome
```

Six return-type declarations (UCORG-05-010): two Protocols, two methods on the
one concrete dispatcher, two adapter-level functions. The change is additive:
callers that ignore the returned value keep working, so the blast radius is
bounded by the type declarations rather than by call-site rewrites.

Two things are easy to get wrong here:

- **`_handle()` is the link that calls `execute()`**, not `dispatch()` — the
  latter only logs and delegates. Working from the public method names alone
  leaves the first hop at `-> None` and loses the verdict before any other link
  sees it. It is named explicitly in UCORG-05-010 for that reason.
- **`_handle()` can return without a handler running at all.** It catches
  `UnroutableActivityError` and returns, and `_get_use_case()` raises
  `VultronApiHandlerNotFoundError` for unrecognised semantics. The first path
  raises nothing, so before #3373 a dropped activity was reported `processed`.
  A return type alone does not fix it; UCORG-05-012 requires the dispatcher
  layer to synthesize a verdict when no handler ran, so `_handle()` now
  returns `REFUSED("unroutable: …")` there.

Most `SKIPPED` decisions also do not live in `execute()` — `_idempotent_create`
and peers in `vultron/core/use_cases/_helpers.py` return without storing when the
record already exists. Five handlers delegate their whole duplicate-skip decision
there, so that layer has to return a disposition too or `SKIPPED` is unreachable
for the commonest skip in the codebase. `_idempotent_create` therefore returns a
`HandlerResult` (`SKIPPED` with a reason, or `APPLIED`) describing its own act;
escalating a skip to `REFUSED` stays the calling handler's verdict (#2255).

`DispatchNode` owns the mapping (`APPLIED`/`SKIPPED` → `processed`, `DEFERRED` →
`deferred`, `REFUSED` → `rejected` + `failure_reason`). Handlers do not know about
`InboxOutcome`'s vocabulary and MUST NOT reach for it — that is a layering rule
(HP-01-004), not a claim about which outcomes a handler can cause.

**What this does not do.** The verdict reaches `InboxOutcome` and the actor log.
Reaching the log takes a deliberate step: `run_inbox_pipeline` debug-logs every
`outcome.status`, and `_warn_if_rejected` also logs a `rejected` one at WARNING
so a refusal is visible at normal log levels (UCORG-05-013).

It does not reach the *sender* over the HTTP response — `post_actor_inbox`
returns 202 before any handler runs, so the response cannot carry a processing
verdict. One path does already reach the sender by another route:
`received/status.py` emits a `Create(ProcessingFault)` carrying
`VULTRON_FAILURE_STATUS_ASSERTION_REFUSED` when a status assertion fails
non-idempotently. That predates this design and must not regress. A
participant status the adoption gate withholds (RSH-01-002) is `SKIPPED`
and emits no fault: the claim was recorded, and only its adoption as
canonical waits for the CASE_OWNER (RSH-05-022). Acceptance
("is this a well-formed activity addressed to me?") and processing ("did handling
it succeed?") are distinct paths, and only the first is synchronous. Surfacing
processing outcomes to a remote party is #2682's problem, and at the protocol
level it is an ack/`ProcessingFault` message, not a response code.

### Assigning a disposition

Most handlers run a behavior tree, whose root status says only whether it
succeeded. `vultron/core/use_cases/received/_bt_verdict.py` turns a finished
run into a `HandlerResult`. `verdict_from_bt` gives the default reading:

- `SUCCESS` → `APPLIED`; a leadership skip (the tree never ran) → `SKIPPED`.
- `internal_error`, or a node missing its DataLayer or a port → raise
  `VultronBTInternalError`. `VultronWiringError` is the exception a node raises
  for a missing port; `BTBridge` flags it `internal_error` even though it is a
  `VultronError`.
- Any other `FAILURE` → `REFUSED`, carrying the failing leaf's reason.

`applied_or_raise` is the variant for a tree that only stores or commits what
the handler already accepted: there any failure raises, because it can only be
the DataLayer's.

A handler refines the default where its tree says more. It asks which node
decided with `node_failed`, `node_succeeded`, `find_node` (by type) or
`find_named` (by name, for composites). It does not match on a node's
`feedback_message`, which usually embeds ids. A duplicate guard's `FAILURE` is
`SKIPPED`, a role gate that reports "not my job" as `SUCCESS` is `SKIPPED`, and
a gap-buffer park is `DEFERRED`. Where later steps must run only on `APPLIED`,
the handler returns the verdict early when it is anything else.

The rules the handlers follow:

| Exit | Disposition |
|---|---|
| Internal or infrastructure failure, missing port | raise |
| Malformed activity (missing id, object or field) | `REFUSED` |
| Activity about a case this actor does not hold | `REFUSED` |
| Invalid transition; untrusted, non-participant or non-owner sender | `REFUSED` |
| The handler answered with a `Reject` or a decline | `REFUSED` |
| Not this actor's role, nothing to record it on | `SKIPPED` |
| Duplicate or redelivery | `SKIPPED` |
| Buffered out-of-order or pre-genesis ledger entry | `DEFERRED` |

The authorization rows cover the checks the handlers make. Some handlers make
none yet; that gap is #3733.

---

## Ratchet Test

`test/architecture/test_use_case_execute_returns_result.py` inspects every
top-level class under `vultron/core/use_cases/` that defines `execute()` and
asserts its return annotation resolves to `UseCaseResult` or a subtype, catching
drift when new use cases are added without the correct return type, independent
of mypy configuration (UCORG-05-004). "Registered subtype" is the subclass
relation itself, resolved with `typing.get_type_hints`, so a new result type
needs no list edit.

It excludes `triggers/` until #3831 migrates those classes from `dict`
(UCORG-05-004b). The exclusion names #3831 in the test, and a companion test
fails once every trigger conforms, so the carve-out cannot outlive its reason.

Nothing yet types a call site against the `UseCase` Protocol — the dispatcher's
routing table is `dict[MessageSemantics, type]` — so mypy does not enforce the
Protocol's return type on its own. The ratchet is the enforcement.

ADR-0040's Validation section listed this test as realized validation for three
months while the file was never written. Do not cite a ratchet as validation
before it exists.
