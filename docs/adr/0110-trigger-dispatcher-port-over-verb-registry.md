---
status: accepted-provisional
date: 2026-09-28
deciders: Allen D. Householder
stakeholder_type: [project-contributor]
---

# The Trigger Driving Port Is One `trigger()` Method over a Verb Registry, Returning a Typed Result Bound to the Request

## Context and Problem Statement

The received half of the protocol enters core through one driving-port method: `ActivityDispatcher.dispatch(event, dl)`, routed by `SEMANTIC_REGISTRY`, a data table with one row per semantic type.
ADR-0009 names that port as a clean point to preserve.

The trigger half enters core through `TriggerServicePort`, a `Protocol` with 27 methods, one per verb, every one returning `dict[str, Any]`.
Behind it `TriggerService` implements 27 near-identical pass-throughs: rebuild a request model from loose scalars, construct the use case, call `execute()`, return the dict.
Two parallel Pydantic request families describe the same requests, one in the FastAPI adapter and one in core, near one-to-one by name and with the same class name (`CaseTriggerRequest`) defined in both.
The embargo end-time validator is copy-pasted four times across them.

The port flattens a validated request into positional scalars and the layer beneath reassembles the same model.
Nothing is added between, and type information is lost: `add_participant_status` declares four state parameters as `Any` where the core model types them as `RM | None`, `CS_vf | None`, `CS_d | None`, `CS_pxa | None`.
The port is less type-safe than the model it flattens.

The port's stated justification does not hold.
Its docstring says adapters type-hint against it and tests inject `Mock(spec=TriggerServicePort)`; no test does, the CLI does not import it, there is no MCP adapter, and the router test fixture wires a real `TriggerService`.
The service also stores a `SyncActivityPort` that nothing reads.

This is the shape UCORG-05-006 forbids, 27 times over, and it is why the UCORG-05-004 ratchet still excludes `vultron/core/use_cases/triggers/`.

Concern #3354 measured all of this and asked whether to type the 27 methods or replace them.

### Why this exists: a misreading of Rule 9

`notes/architecture-hexagonal.md` Rule 9 read "Port interfaces must not use `BaseModel` as boundary type hints."
Taken literally it forbids the received-side port the project already accepted, since `VultronEvent` is a `BaseModel`.
Its intent was never to ban Pydantic; it was to keep wire-layer and adapter-layer models out of ports.
A core-owned request model is an explicit domain type.
The 27-method port is what literal compliance with the misread rule produces.
This ADR narrows the rule to what it meant.

## Decision Drivers

- The spec (UCORG-05-001, UCORG-05-006, UCORG-05-007) requires typed trigger results and forbids `dict` at the port, and the received-side ratchet carries a named exclusion until the trigger side conforms.
- Both halves of the protocol solve the same problem: map a discriminator to a use case, inject its driven ports, construct, execute.
  One half does it with a one-method port and a 51-row table; the other with 27 methods and 598 lines of procedure.
- Adding a trigger verb today costs five edits across five files that can silently disagree.
- Response bodies are a client-visible contract.
  Six distinct body shapes exist (five when this ADR was written; measuring each live body for #3831 found `create-case` also returning `case_id`), no route declares a `response_model`, and no test pins an exact key set, so the shapes are invisible to OpenAPI and to review.
- `SvcBTTriggerBase` and everything below it is already correct and is the floor of this change.
  Its template (`_prepare` / `_build_tree` / `_handle_result`, `BTBridge` construction, the port and failure guards) does not move; only its final `return {...}` becomes the typed `ActivityResult`, so the use case itself satisfies UCORG-05-007.
- A second driving adapter (CLI beyond the demo, MCP) is not on the current priority list.
  If one were imminent and needed a per-verb typed method surface, that would weigh the other way.

## Considered Options

1. **Type the 27 methods in place.**
   Re-parent `TriggerResult` onto `UseCaseResult`, make the seven `execute()` methods return it, change the 27 port and service signatures from `dict` to `TriggerResult`.
   Satisfies the spec's letter.
   Leaves five layers, two request families, four validator copies, and a port that grows with every verb.
2. **One `trigger()` method over a verb-keyed registry.**
   Collapse the port to a single method whose return type is bound to the request's type; put the verb → use-case mapping in a data table mirroring `SEMANTIC_REGISTRY`; merge the request families; give each response shape a result subtype; keep routes hand-written but one line each.
3. **One helper, no registry.**
   Delete the port and service; each route constructs its use case directly through a shared helper.
   Thinnest possible stack.
   Nothing to iterate, so the bijection, exposure, and exact-key-set checks would have to be derived by scanning the FastAPI app and the module tree instead.

## Decision Outcome

**Chosen: option 2.**

### What the registry is for, and what it is not

The registry is not for routing.
On the received side a table is necessary because the discriminator is derived from inbound data by pattern matching.
On the trigger side the client hit a specific URL, and that route already knows which use case it wants.
A verb-keyed table buys nothing for routing.

It is for enumeration.
The route-to-registry bijection, the use-case-to-row bijection, the exact response key set per verb, the `/trigger/` versus `/demo/` exposure axis, and the single pinned non-BT-backed row all need a table to iterate.
Today those properties are asserted by inspection or not at all; with a table they are tests.

Because that is its whole purpose, the registry stays a data table with a lookup.
It must not acquire per-verb behavior.
If it does, it has become the per-verb facade it replaced, under a new name.
That is the failure mode this ADR is most concerned to prevent, and TRIG-12-004 states it as a requirement.

Option 3 was rejected because deriving the same checks from the app and the module tree is more code than the table, is less legible, and puts the enumeration in the tests rather than in the artifact the tests check.
Option 1 was rejected because it preserves the asymmetry this ADR exists to remove.

### Interface

The port will declare one method.
Each `TriggerRequest` subclass will be generic in its result type so the return type resolves per verb:

```python
# vultron/core/ports/trigger_dispatcher.py  (replaces trigger_service.py)
ResultT_co = TypeVar("ResultT_co", bound=TriggerResult, covariant=True)

class TriggerDispatcher(Protocol):
    def trigger(
        self, request: TriggerRequest[ResultT_co], dl: CaseOutboxPersistence
    ) -> ResultT_co: ...
```

Both mypy and pyright resolve the precise subtype through the single method; this was checked on the repo's toolchain before this ADR was written.
Driving-port method count across the hexagon goes from 27 + 1 to 1 + 1.

### Result hierarchy

`TriggerResult` will be a fieldless `UseCaseResult` subtype.
The fields UCORG-05-005 previously required on the base move down to the subtype the BT-backed verbs return:

```text
TriggerResult          (no fields)
  ActivityResult       activity, emitting_actor_id
    NoteResult         + note
    CaseResult         + case_id
  StatusResult         activity_id, status_id
  OfferResult          offer
  RoleOfferResult      activity_id, activity
```

Four verbs return bodies with no `emitting_actor_id` and one with no `activity`; a base requiring both could not be satisfied without changing live bodies.
`CaseResult` was added when #3831 measured the live bodies: `create-case` returns the activity body plus the created case's id, which the demo layer reads.
Every subtype forbids extra keys, so a use case whose return dict gains a key fails loudly rather than being filtered out of the response.

`activity`, `offer`, and `note` are `dict[str, Any]`, not wire models.
Every producer stores `json.loads(activity_blob)` from the BT blackboard, and annotating the field as `as_TransitiveActivity` would make FastAPI revalidate and reserialize it, changing bytes, and would import a wire type into core.
The demo layer's wire-typed view of the response keeps its own class with a `Wire` prefix (`WireActivityResult`), following `WireCaseLedgerEntry`; the plain names belong to core (UCORG-05-014).

### Request models

Both existing class names survive, so no OpenAPI component name moves and no use-case-side rename happens.
The body model is the base and the core request derives from it:

```python
class ProposeEmbargoRequest(CaseFields):          # OpenAPI component name, unchanged
    end_time: datetime
    @field_validator("end_time")
    def end_time_must_be_tz_aware_and_future(cls, v): ...      # one copy, was four

class ProposeEmbargoTriggerRequest(ActorScoped[ActivityResult], ProposeEmbargoRequest): ...
```

`actor_id` is structurally absent from the body type: it is the URL path parameter, never a body field, so a client cannot act as another actor (TRIG-06-001).
The body models are declared as classes, not derived with `create_model`, because `create_model` loses class docstrings and FastAPI renders those as the OpenAPI schema `description`.

### Routes

The route functions stay hand-written with their decorators verbatim.
Each body collapses from six lines to one call into a shared helper, and each decorator gains a `response_model`:

```python
@router.post(
    "/{actor_id}/trigger/propose-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an embargo proposal.",
    description=(...unchanged...),
    operation_id="actors_trigger_propose_embargo",
    response_model=ActivityResult,
)
def trigger_propose_embargo(actor_id, body, background_tasks, ctx, actor_dl) -> ActivityResult:
    return run_trigger(PROPOSE_EMBARGO, actor_id, body, ctx, background_tasks, actor_dl)
```

No `__signature__` synthesis: that would couple every endpoint to a FastAPI internal, and a break would take all of them at once.
The `Depends(get_trigger_dl)` → `Depends(get_actor_dl)` chain is preserved because `app.dependency_overrides` keys on it (TRIG-06-002).
The outbox flush is scheduled via `BackgroundTasks` after `trigger()` returns and not at all when it raises (TRIG-07-001).

### Named exceptions and cleanups

- `SvcOfferCaseParticipantRoleUseCase` is not a `SvcBTTriggerBase` subclass: a bare class with a hand-rolled `__init__`, an `execute()` that never builds a `BTBridge`, and `object` annotations it never reads.
  That is why its body has no `emitting_actor_id`.
  It is pinned as the one non-BT-backed row, with a ratchet asserting exactly one such row exists and that such a row declares no `emitting_actor_id`.
  Bringing it under the base would add a key to a live response body and needs its own decision.
- `SvcAddOnBehalfStatusUseCase` is reachable only from its own tests.
  It gets a route and a registry row.
  It is general-purpose, not demo-only: a coordinator recording a vendor's awareness on evidence is an intentional actor decision under TRIG-08-002, so it is mounted under `/trigger/`, making PRM-06-003 and PRM-06-004 reachable and the PRM-06-005 guard testable over HTTP.
  This adds one path; the contract freeze covers the existing ones.
- The dead `sync_port` wiring in `deps.py` and `TriggerService.__init__` is deleted, with the grep evidence in the PR so it is not restored by habit.
- `svc.close_case` builds a `CloseReportTriggerRequest` and closes a report; `svc.close_report` is a deprecated alias with no production callers; `svc.leave_case` closes the case.
  The registry names each verb once, by what it does.

### Spec citations

The trigger routers and adapter request models carry 236 `TB-` citations where `TRIG-` was meant (`TB` is the Testability topic).
They are fixed with per-file judgment, not a prefix swap, because `TRIG-02` splits by domain, and a topic-scoped ratchet is added: no module under `vultron/` may cite a `TB-` requirement.
An existence-only check passes on all 236 today because every one of them resolves.

### Migration order

Additive first.
The golden OpenAPI snapshot is captured from the shipped routes before any other change, because a snapshot captured after `response_model` is added freezes whatever the new models happened to emit.
Result types, the merged request models, the registry, and the registry ratchets land while `TriggerService` still exists and delegates.
Only the final step, switching the routes and deleting the service, port, and duplicate models, is load-bearing, and it lands behind the snapshot and the exact-key-set tests.

### Consequences

- Good: driving-port method count across the hexagon drops from 28 to 2, and adding a trigger verb becomes one registry row plus one route.
- Good: per-verb static typing survives and improves; the four `Any` state parameters become the core model's real types.
- Good: six response shapes become six declared types, visible in OpenAPI and pinned by test.
- Good: the UCORG-05-004 ratchet's `triggers/` exclusion is deleted, and UCORG-05-006 is satisfied rather than violated 27 times.
- Good: one validator copy, one request family, one `CaseTriggerRequest`.
- Bad: `test/core/use_cases/triggers/test_service.py` (48 tests, real BT execution against a real store, covering 10 of 27 verbs) tests the facade being removed.
  It must be migrated, not deleted: error-translation tests to the router suite, state-transition and outbox tests to the per-use-case files under `test/core/use_cases/triggers/` (UCORG-03-001).
  Net coverage should rise.
- Bad: the ~4,400-line router suite shrinks but does not disappear.
  The per-endpoint tax (202, dependency resolved, background task queued) becomes a few tests parametrized over the registry; the per-verb domain assertions stay.
- Neutral: the 177 direct `Svc*UseCase(...)` constructions across 23 test files are untouched.
  They test the floor, and the floor does not move.
- Risk: the registry accumulating behavior.
  TRIG-12-004 forbids it, and the review checklist for any registry change is "is this a row, or is this a method?"

## Validation

Two steps are built.
The gating step is the golden OpenAPI snapshot test at `test/adapters/driving/fastapi/test_openapi_trigger_snapshot.py`, which covers the trigger and demo paths; its first commit (#3828) predates the route rewrite.
The additive step (#3831) landed behind it with the snapshot unchanged: `TriggerResult` and its subtypes exist in `vultron/core/models/use_case_result.py`, every trigger `execute()` returns one, the two request families are one (`request_bodies.py` owns the bodies, `requests.py` derives the generic `TriggerRequest[ResultT_co]` requests from them), and `TriggerService` still delegates.
Built and passing:

- `test/architecture/test_use_case_execute_returns_result.py` scans `triggers/` with no exclusion.
- `test/core/models/test_use_case_result.py` constructs each result subtype, asserts its exact field set, and asserts an unknown key raises.
- `test/core/use_cases/triggers/test_requests.py` resolves each verb's result through one `trigger(request) -> ResultT_co` signature under mypy and pyright, and pins the `end_time` validator to one declaration.

The rest is not yet built.
This ADR is provisional until the trigger side's port collapses and the remaining tests named here exist.

Expected, once built:

- A trigger-registry test module asserts the route-to-registry and use-case-to-row bijections as exact set equalities, exactly one non-BT-backed row, and that row declaring no `emitting_actor_id`.
- An exact-response-key test parametrized over the registry asserts `set(response.json()) == expected_keys` per verb.
- A `response_model` coverage test fails on any trigger route without one.
- A topic-scoped citation ratchet fails on any `TB-` citation under `vultron/`.
- One outbox-ordering test asserts the flush is queued only after `trigger()` returns and not when it raises.

Per ADR-0095's own rule: no entry here asserts a test exists until it does.

## More Information

Extends [ADR-0040](0040-use-case-result-envelope.md), which introduced the `UseCaseResult` hierarchy, and [ADR-0095](0095-received-side-handler-result.md), which built its received-side half.
ADR-0040 said the trigger side would use "typed attribute access instead of dict-key access"; this ADR keeps that and changes the port it happens through.
Neither earlier ADR becomes wrong.

Amends the reading of Rule 9 in `notes/architecture-hexagonal.md` and `vultron/core/ports/AGENTS.md`.
[ADR-0009](0009-hexagonal-architecture.md) is unchanged; the received-side port it endorses is the precedent this ADR follows.

Design note: `notes/use-case-protocol.md`.

Source concern: #3354.
Generated or amended spec requirements: `specs/use-case-organization.yaml` UCORG-05-005, UCORG-05-006, UCORG-05-014; `specs/triggerable-behaviors.yaml` TRIG-08-003, TRIG-08-004 (verification), TRIG-12-001 through TRIG-12-004.
Related: #2369 and #2682 (asynchronous trigger outcome observability), which the typed results make easier and this ADR does not address.
