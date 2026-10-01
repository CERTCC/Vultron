---
title: Use-Case Protocol — Result Envelope and Request Paths
status: active
description: >
  Design decisions for the UseCaseResult type hierarchy, the HandlerDisposition
  vocabulary and its route to InboxOutcome, the two semantically distinct request
  paths (VultronEvent vs TriggerRequest), and why a shared UseCaseRequest base
  was not introduced. Received side and dispatcher chain migrated; trigger side
  collapsed to one dispatcher method over a verb registry (ADR-0110): the
  golden OpenAPI snapshot, the typed result hierarchy with one request-model
  family (#3831), the verb registry with the one-method TriggerDispatcher port
  (#3832) and the route cutover that retired TriggerService (#3833).
related_specs:
  - specs/use-case-organization.yaml
  - specs/handler-protocol.yaml
  - specs/inbox-orchestration.yaml
  - specs/triggerable-behaviors.yaml
related_notes:
  - notes/use-case-behavior-trees.md
  - notes/architecture-hexagonal.md
  - notes/inbox-orchestration.md
  - notes/case-communication-model.md
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

> **Status: both halves return typed results and both enter core through a
> one-method driving port; the per-verb `TriggerService` is gone (#3833).**
> `UseCaseResult`, `HandlerResult`, and
> `HandlerDisposition` exist
> in `vultron/core/models/use_case_result.py` (#3371), and so does the
> trigger-side hierarchy rooted at `TriggerResult` (#3831). Every received-side
> `execute()` declares `-> HandlerResult`, every trigger-side one its verb's
> `TriggerResult` subtype, and the `UseCase` Protocol declares
> `-> UseCaseResult` (#3372); the query use case returns `ActionRulesResult`.
> `test/architecture/test_use_case_execute_returns_result.py` enforces
> UCORG-05-004 over every package under `use_cases/`. The dispatcher returns
> the value and `DispatchNode` maps its disposition onto `InboxOutcome.status`
> (#3373). Each handler exit returns the disposition it earned (#2255; see
> [Assigning a disposition](#assigning-a-disposition)). The demo layer keeps
> its own wire-typed views of the trigger response bodies (`WireTriggerResult`,
> `WireActivityResult`, `WireNoteResult`, `WireSyncLogEntryResult` in
> `vultron/demo/actor_session.py`, UCORG-05-014). The trigger-side port is
> `TriggerDispatcher.trigger(request, dl) -> ResultT_co`
> (`vultron/core/ports/trigger_dispatcher.py`), implemented by
> `RegistryTriggerDispatcher` over `vultron/trigger_registry/` (#3832); every
> route under `/trigger/` and `/demo/` is one `run_trigger(...)` call into it
> and declares its row's `response_model` (#3833). Earlier revisions of this
> note described the whole migration in the past tense while no part of it had
> been written — that drift is what concern #1769 was filed to correct; the
> tests ADR-0110 § Validation names are what make the present tense true now.

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
ActivityStreams activity. `TriggerResult` is the fieldless root; each verb's
use case returns the subtype whose fields are exactly its response-body keys
(UCORG-05-005), and every subtype forbids unknown keys so a use case that grows
a return key fails at construction rather than having the key silently dropped
from the body:

```text
TriggerResult          (no fields)
  ActivityResult       activity, emitting_actor_id
    NoteResult         + note                (add-note-to-case)
    CaseResult         + case_id             (create-case)
  StatusResult         activity_id, status_id (add-participant-status, on-behalf)
  OfferResult          offer                 (submit-report)
  RoleOfferResult      activity_id, activity (offer-case-participant-role)
  SyncLogEntryResult   log_entry_id, entry_hash, log_index, emitting_actor_id
                       (demo sync-log-entry; the CASE_MANAGER it ran as)
```

- `activity` — the emitted activity's JSON object as the BT captured it
  (optional; `None` when the tree completed without capturing one, and the key
  is still emitted as `null`, TRIG-12-002)
- `emitting_actor_id` — the actor whose outbox holds the activity; on a
  delegated emit that is the CASE_MANAGER (CM-24-001)

`activity`, `offer` and `note` stay `dict`s: core captures them from the
blackboard as JSON and cannot type them as wire activities without importing
the wire layer (ARCH-01-001). `SvcBTTriggerBase` is generic in the subtype
(`SvcBTTriggerBase[TriggerResultT]`); `SvcActivityTriggerBase` binds it to
`ActivityResult` for the verbs whose body is the activity and its emitter, and
the others bind their own subtype and implement `_build_result()`. The
routers serialise the result with `model_dump()`, so the response bytes did
not change when the `dict` returns became typed (#3831; the golden OpenAPI
snapshot is the proof).

Each `TriggerRequest` binds the subtype its verb returns
(`TriggerRequest[ResultT_co]`, `ResultT_co` bound to `TriggerResult`,
covariant), so one `trigger(request) -> ResultT_co` signature resolves the
verb's result statically; `result_type_of()` recovers it at runtime. The
request models are one family: `request_bodies.py` owns each verb's body
model (the OpenAPI component, which the FastAPI routers import by name) and
`requests.py` derives the core request from it, adding `actor_id`.

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

Decided in ADR-0110, planned from concern #3354, built in four steps: the
gating golden OpenAPI snapshot of the trigger and demo endpoints (#3828,
`test/adapters/driving/fastapi/test_openapi_trigger_snapshot.py`); the
additive typed result hierarchy plus one request-model family (#3831), landed
with the snapshot unchanged; the verb registry, the one-method port and the
shared route body (#3832), landed with the snapshot moved for exactly one
added path (`add-on-behalf-status`); and the cutover (#3833), which moved the
other 28 routes onto `run_trigger(...)`, declared a `response_model` on every
route, regenerated the snapshot once for exactly those response schemas, and
deleted `TriggerService`, `TriggerServicePort` and the adapter re-export module.
The trigger half did **not** get the mechanical "type the 27 methods" migration
this note once described. The driving port is one method and the two request
families are one:

- `TriggerResult` is a fieldless `UseCaseResult` subtype in
  `vultron/core/models/`; the required fields move down to `ActivityResult`
  (`activity`, `emitting_actor_id`), with sibling subtypes for the verbs whose
  live bodies differ (`NoteResult`, `StatusResult`, `OfferResult`,
  `RoleOfferResult`). Every subtype forbids extra keys (UCORG-05-005).
- Each `TriggerRequest` subclass is generic in its result type, so the port is
  one method — `TriggerDispatcher.trigger(request, dl) -> ResultT` — and mypy
  and pyright resolve the verb's result at the call site (UCORG-05-006).
- A verb-keyed registry under `vultron/trigger_registry/` (mirroring
  `vultron/semantic_registry/`) maps verb → request model, use case, result
  type, exposure, `bt_backed`, `spec_ids`. It is a data table with a lookup
  (`lookup_entry(verb)`, `entries()`, `index_by_request_model(rows)`); the
  ratchets iterate it (TRIG-12-004,
  `test/architecture/test_trigger_registry_ratchets.py`,
  `test/adapters/driving/fastapi/test_trigger_registry_routes.py`). It exists
  for enumeration, not routing. `RegistryTriggerDispatcher`
  (`vultron/core/trigger_dispatcher.py`) resolves a request's *type* to its
  row and injects the driven ports by the row's `bt_backed` flag: the BT port
  bundle (`trigger_activity`, `wire_render_port`, `sync_port`) for a BT-backed
  use case, `trigger_activity` alone for the one non-BT-backed use case.
- Routes stay hand-written; each body is one call into the shared
  `run_trigger(...)` helper (`vultron/adapters/driving/fastapi/trigger_runner.py`)
  and declares `response_model` (TRIG-12-001). The helper calls `trigger()`
  under `domain_error_translation()` and queues the outbox flush only after it
  returns (TRIG-07-001), draining the *emitting* actor's outbox when the
  result names one (`EmittingResult`: `ActivityResult`, `SyncLogEntryResult`)
  and the requester's otherwise — the delegated-emit rule `trigger_actor.py`
  applied by hand (`emitting_outbox`, CM-24-001) now lives in the helper. The
  route keeps its own `Depends(get_trigger_dl)` chain and passes the store in,
  so `app.dependency_overrides` still reaches it (TRIG-06-002) — that one
  override is the whole test wiring, since `get_trigger_dispatcher` resolves
  its store through the same seam. The routers import the body models from
  `vultron/core/use_cases/triggers/request_bodies.py` directly; the adapter
  re-export module (`trigger_models.py`) was a pure shim and is gone
  (CS-15-001). One route body is two calls: the demo `notify-fix-ready` is the
  two-hop VF ratchet (vf→Vf→VF), each hop validated by the tree.
- The per-route checks every router suite used to repeat — 202, the store the
  dispatcher is handed, the queued flush — are asserted once per registry row
  in `test/adapters/driving/fastapi/test_trigger_routes_contract.py`, which is
  also the exact-response-key test (TRIG-12-002); the per-verb domain
  assertions stay in the per-router suites, which run the real dispatcher over
  an in-memory store (`vultron/core/ports/AGENTS.md`: never
  `Mock(spec=<driving port>)`).
- `TriggerService`, `TriggerServicePort`, `get_trigger_service` and the
  adapter-layer re-exports were deleted behind the golden OpenAPI snapshot and
  the exact-key-set tests (TRIG-12-002, TRIG-12-003); the 48 tests of
  `test_service.py` were ported to the per-use-case files and the per-router
  suites (UCORG-03-001) before the file went. `test/architecture/test_trigger_port_single_method.py`
  keeps the port at one public method and `vultron/core/` free of a per-verb
  facade (UCORG-05-006).

The response bodies stayed byte-identical throughout (the one deliberate
change, `emitting_actor_id` on the demo `sync-log-entry` body, is recorded in
the ADR); the typed conversion is one layer above the BT: `SvcBTTriggerBase`'s
template (`_prepare` / `_build_tree` / `_handle_result`, `BTBridge`
construction, the guards) did not change; only its final `return {...}` became
the typed result. Migration order and the reasons for it are in the ADR.

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
`SKIPPED`, a gap-buffer park is `DEFERRED`, and a role gate that skipped as
`SUCCESS` because this actor is not the case's CASE_MANAGER is `REFUSED`
through `not_case_manager_refusal()` (HP-01-005, #3752): the message was the
manager's to act on and reached the wrong party, which the receiver's own
record should say. `SKIPPED` is reserved for a redundant or idempotent
re-delivery of a message the receiver was entitled to act on. Where later
steps must run only on `APPLIED`, the handler returns the verdict early when
it is anything else.

The rules the handlers follow:

| Exit | Disposition |
|---|---|
| Internal or infrastructure failure, missing port | raise |
| Malformed activity (missing id, object or field) | `REFUSED` |
| Activity about a case this actor does not hold | `REFUSED` |
| Invalid transition; untrusted, non-participant or non-owner sender | `REFUSED` |
| The handler answered with a `Reject` or a decline | `REFUSED` |
| Not this actor's role (a CASE_MANAGER-addressed message at a non-manager), a copy naming it in neither `to` nor `cc`, or an addressing the message's protocol gives it no standing to act on (`cc`-only `Offer(Report)`, HP-09-001) | `REFUSED` (HP-01-005) |
| An addressee's first receipt of a message now pending its own decision (the Case Owner and `Offer(CaseParticipant)`): neither a duplicate nor a refusal | `APPLIED` |
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
needs no list edit. The same scan rejects an `execute()` that takes any
parameter beyond `self` (HP-01-001): everything a handler needs arrived through
`__init__(dl, request)`, so an argument on `execute()` is a second request path
the dispatcher cannot supply. Its companions under `test/architecture/` pin the
rest of the handler contract: `test_use_cases_no_inbox_outcome.py` keeps
`InboxOutcome` vocabulary out of `vultron/core/use_cases/` (HP-01-004), and
`test_no_record_level_persistence_in_core.py` keeps hand-built records and the
record-level `update(id_, record)` out of core writes (HP-08-001).

It scans every package under `use_cases/`, `triggers/` included. The
exclusion it once carried (UCORG-05-004b) was retired with #3831 — the test
that named the issue failed the day every trigger conformed, and both the
exclusion and the requirement were removed in the same PR (MS-09-001). A
generic base whose `execute()` returns a `TypeVar` conforms when the variable
is bound to a `UseCaseResult` subtype (`SvcBTTriggerBase[TriggerResultT]`);
an unbound variable still fails.

Nothing yet types a call site against the `UseCase` Protocol — the dispatcher's
routing table is `dict[MessageSemantics, type]` — so mypy does not enforce the
Protocol's return type on its own. The ratchet is the enforcement.

ADR-0040's Validation section listed this test as realized validation for three
months while the file was never written. Do not cite a ratchet as validation
before it exists.
