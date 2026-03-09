# Architectural Review: Ports and Adapters Adherence

Review against `notes/architecture-ports-and-adapters.md`.

---

## 1. Violations

### V-01 — `vultron/enums.py`, entire file

**Rule:** Rule 3 (SemanticIntent is a domain type, defined in core)  
**Severity:** Major

`MessageSemantics` is a domain enum and must live in `core/models/events.py`. It
currently shares a file with AS2 structural enums (`as_ObjectType`,
`as_TransitiveActivityType`, `as_IntransitiveActivityType`, `as_ActorType`,
`as_AllObjectTypes`, and the merge helper). Placing domain vocabulary alongside
wire-format vocabulary in the same module allows any importer to access both
without noticing the layer crossing, and it signals to future maintainers that
these concerns are interchangeable.

---

### V-02 — `vultron/types.py`, `DispatchActivity.payload: as_Activity`

**Rule:** Rule 5 (core functions take and return domain types)  
**Severity:** Critical

`DispatchActivity` is the data carrier passed from the extractor into the
dispatcher and then into every handler. Its `payload` field is typed as
`as_Activity` — an AS2 structural type from `vultron.as_vocab`. This means the
entire dispatch chain, including all handler functions, is contractually required
to receive and inspect an AS2 object. The architecture requires that the inbound
pipeline complete its work (parse → extract) before core is invoked. Because
`payload` carries an AS2 type, that handoff never actually happens.

---

### V-03 — `vultron/behavior_dispatcher.py`, lines 9 and 17–38

**Rules:** Rule 1 (core has no wire format imports), Rule 5 (core takes domain
types)  
**Severity:** Critical

`behavior_dispatcher.py` is positioned as a core module — it houses the
`ActivityDispatcher` Protocol and the `DispatcherBase` class — but it imports
directly from the wire layer:

```python
from vultron.as_vocab.base.objects.activities.base import as_Activity
```

`prepare_for_dispatch(activity: as_Activity)` accepts an AS2 structural type,
meaning the dispatcher's entry point is defined in terms of the wire format.
A future wire format replacement would require changes to this core module,
which Rule 8 explicitly prohibits.

---

### V-04 — `vultron/semantic_map.py` re-invoked from `vultron/api/v2/backend/handlers/_base.py` (line 30)

**Rule:** Rule 4 (the semantic extractor is the only AS2-to-domain mapping
point)  
**Severity:** Major

`find_matching_semantics` is the semantic extraction function. The architecture
requires it to be called exactly once per inbound activity, as stage 3 of the
pipeline. Instead, it is called twice:

1. In `behavior_dispatcher.prepare_for_dispatch` (the intended location).
2. In `handlers/_base.py`'s `verify_semantics` decorator (line 30):
   `computed = find_matching_semantics(dispatchable.payload)`.

The second call re-runs AS2 pattern matching against the AS2 payload inside a
function decorated onto domain handler code. This means handler code depends on
the AS2 vocabulary even for internal validation, creating a second
AS2-to-domain coupling point that violates Rule 4's isolation guarantee.

---

### V-05 — `vultron/activity_patterns.py`, `ActivityPattern.match()` method

**Rule:** Rule 4 (extractor is the only AS2-to-domain mapping point)  
**Severity:** Major

`activity_patterns.py` defines `ActivityPattern.match(activity: as_Activity)`
which inspects `activity.as_type` and nested `as_type` fields to determine
whether an activity matches a pattern. This is AS2 structural inspection and
belongs in the extractor (`wire/as2/extractor.py`). It currently lives in a
separate top-level module, and `find_matching_semantics` (the nominal extractor)
delegates to it. The mapping logic is therefore split across two files
(`activity_patterns.py` and `semantic_map.py`) rather than consolidated in one
extractor, as Rule 4 requires.

---

### V-06 — `vultron/api/v2/routers/actors.py`, `parse_activity()` function (lines 138–168)

**Rule:** Rule 4 (extractor is the only AS2-to-domain mapping point)  
**Severity:** Major

`parse_activity` performs AS2 structural parsing inline inside the HTTP driving
adapter. It inspects the raw `dict` for `"type"`, looks up the class in
`VOCABULARY.activities`, and calls `model_validate`. Per the architecture, this
is stage 2 of the inbound pipeline (AS2 Parser) and must live in
`wire/as2/parser.py`. Having it in the router means the HTTP adapter performs
wire-format work directly, and any other driving adapter (CLI, MCP server) that
needs to ingest AS2 would have to duplicate or depend on this router code.

---

### V-07 — `vultron/api/v2/backend/inbox_handler.py`, `raise_if_not_valid_activity()` and module-level import

**Rule:** Rule 1 (core has no wire format imports)  
**Severity:** Major

`inbox_handler.py` imports `from vultron.as_vocab import VOCABULARY` at module
level (line 26), then uses it in `raise_if_not_valid_activity` (line 48) to
check `obj.as_type not in VOCABULARY.activities`. This AS2 vocabulary inspection
belongs in the wire layer (stage 2 or 3), not in the backend handler that
should be operating on already-validated, already-semantically-labelled
activities. The backend is the wrong place to detect that something isn't a
valid AS2 activity type.

---

### V-08 — `vultron/api/v2/backend/inbox_handler.py`, `handle_inbox_item()` collapses three pipeline stages

**Rule:** Rule 4 (parse → extract → dispatch are distinct stages)  
**Severity:** Critical

`handle_inbox_item` (lines 68–92) performs all three pipeline stages in a single
function:

- **Stage 3 check** — `raise_if_not_valid_activity(obj)` re-validates AS2
  structural type.
- **Stage 3 (extraction)** — `prepare_for_dispatch(activity=obj)` maps AS2 to
  `DispatchActivity`.
- **Stage 4 (dispatch)** — `dispatch(dispatchable=dispatchable)` invokes the
  handler.

The architecture calls for these to be separate stages: parse → extract →
dispatch. The parse stage is not represented here at all (it was done upstream
in `parse_activity` in the router), and the remaining two stages are collapsed
together with an extra AS2 validation check mixed in. There is no clean seam
between the wire layer finishing its work and the domain layer beginning its
work.

---

### V-09 — `vultron/semantic_handler_map.py`, lazy import of `vultron.api.v2.backend.handlers`

**Rule:** Rule 2 (core has no framework imports), Rule 6 (driven adapters
injected via ports)  
**Severity:** Major

`semantic_handler_map.py` is a top-level `vultron/` module that maps
`MessageSemantics` (a domain enum) to handler functions. Handler functions live
in `vultron.api.v2.backend.handlers`, which is an application-layer module. The
mapping file therefore creates a dependency from a domain-level concern onto the
application adapter layer. The lazy import (line 25: `from vultron.api.v2.backend
import handlers as h`) masks a circular import that is itself a symptom of this
layering problem. Per AGENTS.md, lazy imports are a code smell that SHOULD be
refactored.

---

### V-10 — All handler files in `vultron/api/v2/backend/handlers/`, direct datalayer instantiation

**Rule:** Rule 6 (driven adapters injected via ports)  
**Severity:** Major

Every handler function calls `dl = get_datalayer()` directly inside the function
body via a lazy import. Examples: `report.py` lines 49, 108, 195, 301, 358;
`case.py` line 43; and similar patterns throughout all handler files. The
architecture requires core services to receive port implementations via
dependency injection, never instantiate them directly. Handler functions are the
closest thing to "core services" in the current layout, and they all bypass the
port abstraction by calling the concrete TinyDB factory directly.

---

### V-11 — Handler files use `isinstance` checks against AS2 types

**Rule:** Rule 5 (core functions take and return domain types)  
**Severity:** Major

Handler functions check `isinstance(created_obj, VulnerabilityReport)` (e.g.,
`report.py` lines 33, 93) and `isinstance(accepted_report, VulnerabilityReport)`
(line 170) where `VulnerabilityReport` is imported from
`vultron.as_vocab.objects.vulnerability_report`. These checks are inside handler
functions — nominally domain logic — but they operate on AS2 structural types
rather than domain types. If the wire format changed, these checks would break.
The correct behaviour would be for the payload type to already guarantee what
kind of object is present, via a domain-typed `InboundPayload` produced by the
extractor.

---

### V-12 — `test/test_behavior_dispatcher.py`, core test uses AS2 types

**Rule:** Tests section — "core tests should call service functions directly
with domain Pydantic objects"  
**Severity:** Minor

`test_behavior_dispatcher.py` imports `as_Create`, `VulnerabilityReport`, and
`as_TransitiveActivityType` from `vultron.as_vocab` to construct test inputs for
`prepare_for_dispatch` and `DirectActivityDispatcher.dispatch`. The dispatcher is
a core component; its tests should not require AS2 construction. The test is
testing core behaviour through the wire format, which means it would break if
the wire format changed even though the dispatch logic had not changed.

---

## 2. Remediation Plan

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
