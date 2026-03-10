# Architectural Review: Ports and Adapters Adherence

Review against `notes/architecture-ports-and-adapters.md`.

> **Status (2026-03-10):** All 12 violations identified in this review have
> been remediated through incremental refactoring (ARCH-1.1–ARCH-1.4 and
> ARCH-CLEANUP-1 through ARCH-CLEANUP-3). See
> `docs/adr/0009-hexagonal-architecture.md` for the full remediation inventory.
> The violation descriptions below are preserved for historical reference.
> The remediation plan items (R-01 through R-06) in Section 2 are now
> complete; they are kept for record.

---

## 1. Violations (Historical — All Remediated)

### V-01 — `vultron/enums.py`, entire file

**Rule:** Rule 3 (SemanticIntent is a domain type, defined in core)  
**Severity:** Major  
**Remediated by:** ARCH-1.1 + ARCH-CLEANUP-2

`MessageSemantics` now lives in `vultron/core/models/events.py` (moved in
ARCH-1.1). AS2 structural enums (`as_ObjectType`, `as_TransitiveActivityType`,
etc.) moved to `vultron/wire/as2/enums.py` (ARCH-CLEANUP-2). `vultron/enums.py`
re-exports only `MessageSemantics`, `OfferStatusEnum`, and `VultronObjectType`
for backward compatibility.

---

### V-02 — `vultron/types.py`, `DispatchActivity.payload: as_Activity`

**Rule:** Rule 5 (core functions take and return domain types)  
**Severity:** Critical  
**Remediated by:** ARCH-1.2

`DispatchActivity.payload` is now typed as `InboundPayload` (a domain type
defined in `vultron/core/models/events.py`). The extractor stage populates it
from an `as_Activity`; no AS2 types flow past the wire/core boundary.

---

### V-03 — `vultron/behavior_dispatcher.py`, lines 9 and 17–38

**Rules:** Rule 1 (core has no wire format imports), Rule 5 (core takes domain
types)  
**Severity:** Critical  
**Remediated by:** ARCH-1.2

`behavior_dispatcher.py` previously imported `as_Activity` directly and accepted
it in `prepare_for_dispatch`. After ARCH-1.2, the dispatcher accepts
`InboundPayload` (a domain type); no AS2 import remains in the core dispatcher.

---

### V-04 — `vultron/semantic_map.py` re-invoked from `vultron/api/v2/backend/handlers/_base.py` (line 30)

**Rule:** Rule 4 (the semantic extractor is the only AS2-to-domain mapping
point)  
**Severity:** Major  
**Remediated by:** ARCH-1.3

`find_matching_semantics` was called twice per activity: once in
`prepare_for_dispatch` and once in the `verify_semantics` decorator. The
decorator now compares `dispatchable.semantic_type` directly without
re-invoking the extractor.

---

### V-05 — `vultron/activity_patterns.py`, `ActivityPattern.match()` method

**Rule:** Rule 4 (extractor is the only AS2-to-domain mapping point)  
**Severity:** Major  
**Remediated by:** ARCH-1.3, ARCH-CLEANUP-1

`ActivityPattern.match()` and `find_matching_semantics` were split across
`activity_patterns.py` and `semantic_map.py`. Both were consolidated into
`vultron/wire/as2/extractor.py`. The old shim files were deleted in
ARCH-CLEANUP-1.

---

### V-06 — `vultron/api/v2/routers/actors.py`, `parse_activity()` function (lines 138–168)

**Rule:** Rule 4 (extractor is the only AS2-to-domain mapping point)  
**Severity:** Major  
**Remediated by:** ARCH-1.3

`parse_activity` was moved from the HTTP router to `vultron/wire/as2/parser.py`.
The router now calls `parser.parse_activity(body)` as a thin wrapper.

---

### V-07 — `vultron/api/v2/backend/inbox_handler.py`, `raise_if_not_valid_activity()` and module-level import

**Rule:** Rule 1 (core has no wire format imports)  
**Severity:** Major  
**Remediated by:** ARCH-1.3

`inbox_handler.py` previously imported `VOCABULARY` from `vultron.as_vocab`
and used it in `raise_if_not_valid_activity`. After ARCH-1.3, structural AS2
validation happens in the wire layer (parser/extractor); the backend handler
no longer imports AS2 vocabulary.

---

### V-08 — `vultron/api/v2/backend/inbox_handler.py`, `handle_inbox_item()` collapses three pipeline stages

**Rule:** Rule 4 (parse → extract → dispatch are distinct stages)  
**Severity:** Critical  
**Remediated by:** ARCH-1.3

`handle_inbox_item` collapsed parse, extract, and dispatch. After ARCH-1.3,
the router performs parse (via `wire/as2/parser.py`) and extract (via
`wire/as2/extractor.py`) before the dispatcher stage; the stages are now
clearly separated.

---

### V-09 — `vultron/semantic_handler_map.py`, lazy import of `vultron.api.v2.backend.handlers`

**Rule:** Rule 2 (core has no framework imports), Rule 6 (driven adapters
injected via ports)  
**Severity:** Major  
**Remediated by:** ARCH-1.4, ARCH-CLEANUP-1

`semantic_handler_map.py` (top-level) was deleted in ARCH-CLEANUP-1. The
handler map now lives in `vultron/api/v2/backend/handler_map.py` (adapter
layer), removing the domain→adapter dependency.

---

### V-10 — All handler files in `vultron/api/v2/backend/handlers/`, direct datalayer instantiation

**Rule:** Rule 6 (driven adapters injected via ports)  
**Severity:** Major  
**Remediated by:** ARCH-1.4

All handler functions now receive `dl: DataLayer` via parameter injection.
`get_datalayer()` is no longer called inside handler bodies.

---

### V-11 — Handler files use `isinstance` checks against AS2 types

**Rule:** Rule 5 (core functions take and return domain types)  
**Severity:** Major  
**Remediated by:** ARCH-CLEANUP-3

Handler functions checked `isinstance(created_obj, VulnerabilityReport)` (e.g.,
`report.py` lines 33, 93) and `isinstance(accepted_report, VulnerabilityReport)`
(line 170) where `VulnerabilityReport` was imported from
`vultron.as_vocab.objects.vulnerability_report`. These checks were inside handler
functions — nominally domain logic — but they operated on AS2 structural types
rather than domain types. Remediated by completing `InboundPayload` adoption
so the payload type now guarantees what kind of object is present.

---

### V-12 — `test/test_behavior_dispatcher.py`, core test uses AS2 types

**Rule:** Tests section — "core tests should call service functions directly
with domain Pydantic objects"  
**Severity:** Minor  
**Remediated by:** ARCH-CLEANUP-3

`test_behavior_dispatcher.py` previously imported `as_Create`, `VulnerabilityReport`,
and `as_TransitiveActivityType` from `vultron.as_vocab` to construct test inputs
for `prepare_for_dispatch` and `DirectActivityDispatcher.dispatch`. Updated to
use domain types from `vultron.core.models.events`.

---

## 2. Remediation Plan (Completed)

### R-01: Separate `MessageSemantics` from AS2 enums (addresses V-01)

**What moves where:**  
Create `vultron/core/models/events.py` (or equivalent) containing only
`MessageSemantics`. Move AS2 structural enums (`as_ObjectType`,
`as_TransitiveActivityType`, etc.) to `vultron/wire/as2/enums.py`.

**New abstraction needed:** None. Pure file reorganisation.

**Dependency:** Must happen before R-02, because R-02 defines a domain
`InboundPayload` that imports `MessageSemantics`.

---

### R-02: Introduce `InboundPayload` domain type; remove AS2 from `DispatchActivity` (addresses V-02, V-03, V-11)

**What moves where:**  
Define `InboundPayload` in `vultron/core/models/events.py` as a domain Pydantic
model. The extractor produces it from an `as_Activity`. `DispatchActivity.payload`
becomes `InboundPayload`, not `as_Activity`.

```python
# core/models/events.py (notional sketch)
class InboundPayload(BaseModel):
    semantic_type: MessageSemantics
    activity_id: str
    actor_id: str
    object_type: str           # domain vocabulary, not AS2 type string
    object_id: str | None
    raw_object: dict           # opaque; handlers that need detail use this
```

**New abstraction needed:** `InboundPayload` in `core/`.

**Dependency:** Requires R-01 first.

---

### R-03: Consolidate parsing into `wire/as2/parser.py`; remove `parse_activity` from router (addresses V-06)

**What moves where:**  
Move `parse_activity` from `vultron/api/v2/routers/actors.py` to a new
`vultron/wire/as2/parser.py`. The router calls `parser.parse_activity(body)`.

```python
# adapters/driving/http_inbox.py (notional)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.extractor import extract_intent

@router.post("/{actor_id}/inbox/")
async def post_actor_inbox(...):
    as2_activity = parse_activity(body)          # stage 2
    intent, payload = extract_intent(as2_activity)  # stage 3
    background_tasks.add_task(dispatch, intent, payload)  # stage 4
    return Response(status_code=202)
```

**New abstraction needed:** `wire/as2/parser.py` module.

**Dependency:** Requires R-04 (extractor consolidation) to be started
concurrently, because the router change calls both.

---

### R-04: Consolidate semantic extraction into `wire/as2/extractor.py`; remove second call site (addresses V-04, V-05, V-07, V-08)

**What moves where:**  
Move `find_matching_semantics` and the `ActivityPattern.match()` logic into
`vultron/wire/as2/extractor.py`. `extractor.extract_intent(as2_activity)` returns
`(MessageSemantics, InboundPayload)`. Remove the second invocation of
`find_matching_semantics` from `handlers/_base.py`'s `verify_semantics`
decorator. Remove `raise_if_not_valid_activity` from `inbox_handler.py`
(structural AS2 validation belongs in the parser, not the backend).

`vultron/semantic_map.py` and `vultron/activity_patterns.py` at the root of
`vultron/` become dead code and are deleted after their logic moves.

**New abstraction needed:** `wire/as2/extractor.py` that is the sole owner of the
pattern list and matching logic.

**Dependency:** Requires R-02 (`InboundPayload`) to exist, and R-01 (enums
split) to avoid pulling AS2 enums into the extractor's return type.

---

### R-05: Inject the data layer into handlers via a port; remove `get_datalayer()` calls (addresses V-10)

**What moves where:**  
Add a `DataLayer` parameter (or context object) to each handler's call
signature, or inject it via a dependency container. The handler registry
(`semantic_handler_map.py`) or the dispatcher binds the concrete implementation
at startup, not inside the handler body.

```python
# notional handler signature after injection
def create_report(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    ...
```

The lazy local imports of `get_datalayer` in every handler file are replaced by
a parameter or a bound partial provided by the dispatcher.

**New abstraction needed:** No new interface (DataLayer Protocol already exists
in `datalayer/abc.py`). Requires wiring change in the dispatcher and/or a
context object passed through.

**Dependency:** Can proceed in parallel with other remediations.

---

### R-06: Move `semantic_handler_map.py` into the adapter layer (addresses V-09)

**What moves where:**  
`semantic_handler_map.py` should move to `vultron/adapters/driving/` or into the
dispatcher configuration. The handler map is an adapter-layer concern — it binds
domain `MessageSemantics` values to concrete handler implementations. Placing it
in the root `vultron/` package allows it to be imported by core-level modules,
creating implicit dependencies on the adapter layer.

**New abstraction needed:** None.

**Dependency:** Should happen after R-04 (extractor consolidation) so the
handler map no longer needs to be imported by extractor-adjacent code.

---

## 3. What Is Already Clean

**`DataLayer` Protocol (`vultron/api/v2/datalayer/abc.py`)** — Correctly defines
the persistence port as a Protocol class, allowing duck-typed injection and
decoupling the domain from the concrete TinyDB implementation.

**`ActivityDispatcher` Protocol and `DispatcherBase` in `behavior_dispatcher.py`** —
The Protocol-based dispatcher design is architecturally sound. The `dispatch`
method signature accepts `DispatchActivity` rather than a raw dict or HTTP
request, which is the correct abstraction. The problem is in what `DispatchActivity`
carries (see V-02), not in the dispatcher pattern itself.

**`DispatchActivity` wrapper concept in `vultron/types.py`** — The idea of
wrapping an activity with its pre-computed semantic type before dispatching is
exactly right. It models the hand-off between the extractor stage and the
dispatch stage. Only the `payload` type needs to change (see R-02).

**FastAPI 202 + `BackgroundTasks` in `actors.py`** — The inbox endpoint correctly
returns 202 and schedules work via `background_tasks.add_task`, satisfying the
spec requirement that the HTTP layer return quickly without blocking on
processing.

**`@verify_semantics` decorator pattern** — The intent of wrapping handlers with a
semantic-type guard is good practice: it catches misrouted activities early.
The implementation flaw is that the guard re-invokes the AS2 pattern matcher
(V-04) rather than comparing the pre-computed semantic type already present in
`dispatchable.semantic_type`. The fix is one line: compare
`dispatchable.semantic_type != expected_semantic_type` directly and remove the
`find_matching_semantics` call.

**`MessageSemantics` enum values** — The vocabulary itself is well-designed. The
values express domain-level intent (`CREATE_REPORT`, `ENGAGE_CASE`,
`INVITE_TO_EMBARGO_ON_CASE`) without leaking AS2 verb names or object type names
into the enum values. This is the correct abstraction; it just needs to live in
the right file (see R-01).

**Handler function naming and `@verify_semantics` usage** — Every handler
consistently uses the decorator and accepts `DispatchActivity`. This uniformity
makes R-02 (changing the payload type) a tractable mechanical refactor rather
than a deep logic change.

**`vultron/errors.py` and `VultronError` base** — The domain exception hierarchy
is cleanly defined in a neutral module with no framework or wire-format
dependencies.
