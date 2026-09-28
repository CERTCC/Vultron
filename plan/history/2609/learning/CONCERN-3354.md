---
source: CONCERN-3354
timestamp: '2026-09-28T18:23:49.271415+00:00'
title: 'Trigger stack is five shallow layers: 27-method port over 27 pass-throughs
  over two model families'
type: learning
---

## Summary

The outbound (trigger) half of the protocol passes one operation through five
layers, destroying type information in the middle and reconstructing it eight
lines later, 27 times over. `TriggerServicePort` declares 27 methods whose bodies
are all `...`; `TriggerService` implements 27 near-identical 8-line pass-throughs;
two parallel Pydantic model families describe the same requests. This violates
UCORG-05-006 (a `MUST_NOT`) 27 times.

## Surface Symptom vs. Underlying Problem

**Surface reading:** "there is some boilerplate in the trigger routers."

**Underlying problem:** the port *flattens* a validated request model into loose
positional scalars, and the layer immediately below reconstructs the same model
from them. Nothing is added between. The flattening actively loses type safety —
`TriggerServicePort.add_participant_status` (`trigger_service.py:150-158`) declares
`rm_state: Any, vf_state: Any, d_state: Any, pxa_state: Any` where the core model
has `RM | None, CS_vf | None, CS_d | None, CS_pxa | None`
(`triggers/requests.py:248-251`). **The port is less type-safe than the model it
flattens.**

The likely cause is literal compliance with `notes/architecture-hexagonal.md:110`
Rule 9 ("Port interfaces must not use `BaseModel` as boundary type hints"). But the
repo's own accepted driving port on the *received* side already passes a `BaseModel`:
`ActivityDispatcher.dispatch()` takes a `VultronEvent`, and
`VultronEvent(ValidatedAssignmentMixin, BaseModel)` (`core/models/events/base.py:92`).
ADR-0009 cites that port as a clean point to preserve. Rule 9's intent is *don't
leak wire/adapter models*; a core-owned request model is an explicit domain type.

The asymmetry is the measurement. Both halves of one protocol solve the same
routing problem — map a discriminator to a use case, inject its driven ports,
construct, `execute()`:

| | Received half | Trigger half |
|---|---|---|
| Driving port | `ActivityDispatcher` — **1 method** | `TriggerServicePort` — **27 methods** |
| Behind it | 51 use cases, 9,349 LOC | 27 use cases, 3,763 LOC |
| Routing table | `SEMANTIC_REGISTRY`, 51 rows of data | none — 598 lines of procedure |
| Request models | 1 family | **2 families**, near-1:1 by name |

An interface whose size grows linearly with the functionality behind it hides nothing.

**Already correct — do not touch.** `SvcBTTriggerBase` and everything below it
(`_prepare` / `_build_tree` / `_handle_result`, `BTBridge` construction, the
`TriggerActivityPort` guard, the failure guard) is the floor of this refactor. It
keeps returning `dict`; the typed conversion happens one layer above.

## Category

- [x] Technical debt

## Severity

high

## Evidence

- `vultron/core/ports/trigger_service.py` — 259 lines, 27 methods, every body `...`
- `vultron/core/use_cases/triggers/service.py` — 598 lines; `:366-382` is the
  representative pass-through (build model, construct use case, `.execute()`)
- `vultron/adapters/driving/fastapi/trigger_models.py` — 29 request models
- `vultron/core/use_cases/triggers/requests.py` — 30 request models, near-1:1 by
  name with the above (`ProposeEmbargoRequest` ↔ `ProposeEmbargoTriggerRequest`).
  `CaseTriggerRequest` is defined in **both** files with the same name.
- The `end_time` tz-aware/future validator is copy-pasted **four times**
  (`requests.py:109-116`, `:134-141`, `trigger_models.py:129-136`, `:192-199`).
  The `propose-embargo-revision` copy is asserted by **zero** tests.
- **The port's stated justification is false.** Its docstring claims tests inject
  `Mock(spec=TriggerServicePort)` and that FastAPI, CLI and MCP adapters type-hint
  against it. `grep -rn "TriggerServicePort" test/` → 0 hits; `cli.py` never imports
  it; there is no MCP adapter. `routers/conftest.py` wires a **real** `TriggerService`.
- **Dead port wiring.** `deps.py:225` constructs a `SyncActivityAdapter` on every
  trigger request; `service.py:135` stores it as `self._sync_port`; nothing ever
  reads it. `SvcBTTriggerBase.execute()` builds `BTBridge` without `sync_port`, so
  it cannot reach a tree.
- **Three concepts, four names, all crossed.** `svc.close_case(actor_id, offer_id, note)`
  builds a `CloseReportTriggerRequest` and closes a *report*; it is called only by
  `/trigger/close-report`. `svc.close_report` is a self-declared "Deprecated alias"
  with **zero** production callers. `svc.leave_case` closes the *case* and is called
  only by `/demo/close-case`.
- **236 stale spec citations** across 6 files. `TB` is the **Testability** topic;
  the trigger spec is `TRIG`. So `trigger_propose_embargo` claims to implement
  `TB-01-001` = *"The system MUST use pytest as the testing framework"*, and its
  comment "Returns the resulting activity in the response body (TB-04-001)" points
  at *"Test structure MUST mirror source code structure"*. `trigger_embargo.py` has
  52 `TB-` and 0 `TRIG-`; `trigger_actor.py` has both (42 / 4), so the rename was
  partial.
- **No test anywhere asserts an exact response key set** for any trigger operation.
  `submit-report` returns `{"offer"}` only, and is checked as `assert "offer" in body`.
- `SvcAddOnBehalfStatusUseCase` is unreachable: 415 lines of use case + BT tree +
  guard module, 357 lines of tests, no route and no service method.

## Impact if Ignored

- Adding trigger verb #28 costs 5 edits across 5 files that can silently disagree
- UCORG-05-006 stays violated; UCORG-05 stays 0% implemented while
  `notes/use-case-protocol.md` and ADR-0040 describe it as done
- The 236 mis-citations stay, and they *resolve*, so any existence-only
  traceability check reports them green
- `PRM-06-003/004` (Case Manager asserts `v→V` / `d→D` on behalf of a Vendor or
  Deployer) stay unreachable, and the `PRM-06-005` guard forbidding on-behalf
  `f→F` cannot be exercised end-to-end
- Response-shape divergence stays invisible: five distinct bodies, no
  `response_model`, nothing in OpenAPI

## Suggested Action

Collapse the port to one method over a registry, mirroring the received side.

### Interface

```python
# vultron/core/ports/trigger_dispatcher.py     (replaces trigger_service.py)
ResultT_co = TypeVar("ResultT_co", bound=TriggerResult, covariant=True)

class TriggerDispatcher(Protocol):
    def trigger(
        self, request: TriggerRequest[ResultT_co], dl: CaseOutboxPersistence
    ) -> ResultT_co: ...
```

Per-verb static typing survives. Verified on this repo's toolchain — both checkers
resolve the precise result type through the single method:

```text
mypy    → Revealed type is "ActivityResult"   /   "OfferResult"
pyright → Type of "a" is "ActivityResult"     /   "OfferResult"     0 errors
```

Driving-port method count across the hexagon goes 27 + 1 → 1 + 1.

### Result hierarchy

`TriggerResult` base carries **no** fields; the required fields move down to the
subtype the BT-backed verbs return:

```text
TriggerResult          (no fields)
  ActivityResult       activity, emitting_actor_id      x21
    NoteResult         + note                            x1
  StatusResult         activity_id, status_id             x2
  OfferResult          offer                              x1
  RoleOfferResult      activity, activity_id              x1
```

`activity` / `offer` / `note` are `dict[str, Any]`, not AS2 models: every producer
stores `json.loads(activity_blob)` (`behaviors/helpers.py:767`,
`report/nodes/emit.py:132,409`, `triggers/actor.py:543`), so annotating them as
`as_TransitiveActivity` would make FastAPI revalidate and reserialize, changing bytes.

### Request models

Both existing class names survive, so no OpenAPI component name moves and no
use-case-side rename happens. The validator is declared once:

```python
class ProposeEmbargoRequest(CaseFields):          # OpenAPI component name, unchanged
    end_time: datetime
    @field_validator("end_time")
    def end_time_must_be_tz_aware_and_future(cls, v): ...      # ONE copy, was four

class ProposeEmbargoTriggerRequest(ActorScoped[ActivityResult], ProposeEmbargoRequest): ...
```

`actor_id` is structurally absent from the body type — it is the URL path
parameter, never a body field, so a client cannot act as another actor (TRIG-06-001).

Do **not** derive the body models with `create_model`: it loses class docstrings,
which FastAPI renders as the OpenAPI schema `description`. That is a silent
surface change.

### Registry

A new registry package mirroring `vultron/semantic_registry/`, keyed by verb, with
columns that turn today's invisible anomalies into ratcheted table cells:

- `response_shape` — the five shapes above
- `bt_backed` — `False` on exactly one row, ratchet-pinned
- `exposure` — `/trigger/` vs `/demo/` (TRIG-08-003 / TRIG-08-004), making those
  requirements' "Inspection of … confirms" verifications executable

### Routes

The 29 route functions stay **hand-written**. Decorators verbatim as today; the
body collapses from 6 lines to 1. No `__signature__` synthesis — that couples every
endpoint to a FastAPI internal, and a break would take all 29 at once.

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
    """Implements: TRIG-01-001, TRIG-01-002, TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001"""
    return run_trigger(PROPOSE_EMBARGO, actor_id, body, ctx, background_tasks, actor_dl)
```

### Response bodies

Byte-identical, all five shapes. Add `response_model` per shape so OpenAPI
documents the real bodies. Four `response_model_exclude_*` settings **must** stay
`False` — each one silently drops a key that is returned today (`activity` is
`None` whenever the BT captured nothing, `_base.py:116`). Set
`extra="forbid"` on the result base so a use case's return dict gaining a key
fails loudly instead of being silently filtered out of the body.

### Named exceptions

- `SvcOfferCaseParticipantRoleUseCase` (`triggers/actor.py:512`) is **not a
  `SvcBTTriggerBase` subclass at all** — a bare class, hand-rolled `__init__`,
  `execute()` never calls `super()`, never builds a `BTBridge`, calls
  `factory.offer_case_participant_role(...)` directly, and types `dl: object`
  which it never reads. That is *why* its body has no `emitting_actor_id`: nothing
  ever resolved an emitting actor. Pin it `bt_backed=False` with a ratchet asserting
  exactly one such row, and give its three `object` annotations real types.
  Do **not** bring it under the base here — that would add `emitting_actor_id` to a
  live response body. TRIG-05-001/002 are `SHOULD`, so a declared exception is legal;
  the conversion needs its own ADR and its own body-change decision.
- `add-on-behalf-status` gets a route under `/demo/` and a registry row, making
  `PRM-06-003/004` reachable and the `PRM-06-005` `f→F` guard testable over HTTP.
  This adds one new path; the freeze covers the existing ones.
- Delete the dead `sync_port` wiring, with the grep evidence in the PR body so it
  is not restored by cargo cult.

### Spec and notes amendments

- `notes/architecture-hexagonal.md:110` Rule 9 → *"must not use **wire-layer or
  adapter-layer** models as boundary type hints; core-owned domain models
  (`VultronEvent`, `TriggerRequest`) are the correct boundary types."* As written it
  forbids the repo's own accepted `ActivityDispatcher`.
- `vultron/core/ports/AGENTS.md:68` → same narrowing. Add: driving ports are O(1)
  in the behaviors they hide, and `Mock(spec=<driving port>)` is banned — a driving
  port is a seam for the code *in front of* it, not behind it.
- UCORG-05-005 → re-scoped from `TriggerResult` to `ActivityResult`. Four verbs
  falsify it as written and cannot comply without changing live bodies.

### Spec citations

Fix all 236 `TB-` → `TRIG-` and add a **topic-scoped** `Implements:` ratchet. A
resolution-only check passes on all 236, because every stale ID resolves — to a
Testability requirement. The rule must be: no module under `vultron/` may cite a
`TB-` requirement.

Not a `sed`. TRIG-02 splits by domain, so the 16 `TB-02-001` hits need per-file
judgment: `trigger_report.py` → `TRIG-02-001`, `trigger_embargo.py` → `TRIG-02-002`,
`trigger_case.py` → **`TRIG-02-004`**, `trigger_actor.py` → **`TRIG-02-005`**,
`demo_triggers.py` → **`TRIG-02-006`**. A blind prefix swap mints three fresh
wrong-but-resolving citations. Once `spec_ids` live in registry rows, the check
becomes an import-time assertion instead of a docstring scanner.

## Dependency Strategy

Everything here is **in-process** or **local-substitutable**. Nothing is a true
external, so no mock is justified anywhere in this stack.

- `CaseOutboxPersistence` — local-substitutable; real `SqliteDataLayer` on
  `sqlite:///:memory:`, which is already universal practice. Resolution path
  unchanged: `Depends(get_trigger_dl)` → `Depends(get_actor_dl)`, per actor
  (TRIG-06-001/002). The `Depends` chain must be preserved — a direct call bypasses
  `app.dependency_overrides`, which is why `get_trigger_dl` exists as a separate name.
- `TriggerActivityPort` — in-process translation seam; real adapter in tests, since
  it *is* the wire construction under test.
- `SyncActivityPort` — removed from this path (dead, see Evidence).
- `ActivityEmitter` / `outbox_handler` — remote-but-owned; stays outside the port,
  scheduled via `BackgroundTasks` **after** `trigger()` returns (TRIG-07-001).
- Both per-actor DataLayers stay separate router parameters and independently
  overridable.

## Testing Strategy

**Gate: capture a golden OpenAPI snapshot from `main` before any other change.**
It is the only mechanical enforcement that the ~20 existing paths, their
`operation_id`s, 202 codes, summaries, descriptions and request schemas do not move.
A snapshot captured *after* `response_model` is added would freeze whatever the new
models happened to emit, defeating the purpose.

New boundary tests:

- **Exact response key set per verb** — parametrized over the registry,
  `assert set(r.json()) == expected_keys`. Nothing like this exists today.
- **Registry integrity** — every `Svc*UseCase` under `triggers/` appears in exactly
  one row (this fails on today's tree and catches the orphan); every declared port
  has a factory and no factory is unused (catches the dead `sync_port`); exactly one
  `bt_backed=False` row; a `bt_backed=False` row must not declare `emitting_actor_id`.
- **Route ↔ registry bijection** — no endpoint without a row, no row unrouted.
- **Outbox ordering** — one test, not 29: the flush is queued only after
  `trigger()` returns and not at all when it raises (TRIG-07-001, currently
  unasserted).
- **`response_model` coverage** — every trigger route declares one, so the current
  state (zero) cannot recur.
- **Topic-scoped `Implements:` ratchet** — see above.

Delete: `test/core/use_cases/triggers/test_service.py` (960 lines) — it tests the
facade being removed. Its coverage is **not** plumbing-only: all 48 tests drive real
BT execution against a real in-memory store, and it covers only 10 of 27 verbs.
Migrate before deleting — error-translation tests to the router suite,
state-transition and outbox tests to the per-use-case files under
`test/core/use_cases/triggers/**` (UCORG-03-001). Net coverage should *increase*.

Shrink, do not delete, the ~4,400-line router suite: the per-endpoint tax (202,
dependency resolved, background task queued) becomes four parametrized tests over
the registry; the per-verb domain assertions stay.

Untouched: the 177 direct `Svc*UseCase(...)` constructions across 23 files. They
test the floor, and the floor does not move.

## Implementation Recommendations

**Own:** the verb → use-case mapping, per-verb driven-port injection, the
`(dl, request, **ports).execute()` construction protocol, the `dict` → typed-result
conversion, and the `/trigger` vs `/demo` exposure axis.

**Hide:** which `Svc*` class serves a verb, how many use-case invocations a verb
takes, which verbs redirect their outbox flush to a different actor's store, and
the five response shapes.

**Expose:** one `trigger(request, dl)` returning the request's bound result type,
plus a module-level catalog function for enumeration. Keep the catalog a plain
function, not a port method, until a second adapter exists — promoting it early is
exactly the mistake this port already made once.

**Migration:** additive first. Result types, registry, and registry ratchets land
while `TriggerService` still exists and delegates. The golden OpenAPI snapshot
lands before the routers change. Only the final step is load-bearing, and it lands
behind two golden tests.

## References

Spec: `specs/triggerable-behaviors.yaml` (TRIG), `specs/use-case-organization.yaml`
(UCORG-05), `specs/participant-role-management.yaml` (PRM-06-003/004/005)
ADR: `docs/adr/0009-hexagonal-architecture.md`, `docs/adr/0040-use-case-result-envelope.md`
Notes: `notes/architecture-hexagonal.md` (Rule 9), `notes/use-case-protocol.md`
Related: #2682 / #2369 (async trigger outcome observability — orthogonal, but the
typed results make that design work easier)

**Resolved**: 2026-09-28 — implementation tracked in #3828, #3831, #3832, #3833 (staged: OpenAPI snapshot → typed results and one request family → registry and one-method port → route cutover and deletions) and #3829 (TB- → TRIG- citations, topic-scoped ratchet). Decision recorded in ADR-0108 (accepted-provisional). One override of the concern: `add-on-behalf-status` is routed under `/trigger/`, not `/demo/`, because a coordinator recording evidenced vendor awareness is an intentional actor decision under TRIG-08-002.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3826>.
Spec: `specs/use-case-organization.yaml` UCORG-05-005/006/014, `specs/triggerable-behaviors.yaml` TRIG-08-003/004, TRIG-12.
Notes: `notes/use-case-protocol.md`, `notes/architecture-hexagonal.md`, `notes/spec-authoring-rules.md`, `vultron/core/ports/AGENTS.md`.
