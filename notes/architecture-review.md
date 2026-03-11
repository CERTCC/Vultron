# Architectural Review: Ports and Adapters Adherence

Review against `notes/architecture-ports-and-adapters.md` and
`specs/architecture.md`.

> **Status (2026-03-11, updated):** The original 12 violations (V-01 through
> V-12) were claimed as fully remediated through ARCH-1.1–ARCH-1.4 and
> ARCH-CLEANUP-1 through ARCH-CLEANUP-3. However, a fresh review of the
> current codebase reveals that several remediations are **incomplete or
> regressed**, and a new class of violations has been introduced in the
> `vultron/core/behaviors/` package added as part of the same refactoring.
> Violations V-03, V-02/V-11 (generalised), and V-10 have active regressions.
> New violations V-13 through V-21 are documented below.
>
> **Further update (2026-03-11, P65-1, P65-2, P65-5 complete):**
> V-13 and V-14 are **fully resolved** (P65-1: `DataLayer` moved to
> `core/ports/activity_store.py`). V-10-R is **fully resolved** (P65-2:
> lifespan-managed DataLayer injection in `inbox_handler.py`). V-15, V-16,
> and V-18 are **partially resolved** (P65-5: `object_to_record` and
> adapter-layer `OfferStatus` imports removed from core BT nodes; AS2 wire
> type imports remain — addressed in P65-6). R-08 is complete.
>
> **Further update (2026-03-11, P65-3 complete):**
> V-02-R and V-11-R are **fully resolved** (P65-3: `raw_activity: Any` removed
> from `InboundPayload`; 13 typed domain string fields added; `extract_intent()`
> added to `wire/as2/extractor.py` as the sole AS2→domain mapping point; all
> 7 handler files updated to read from `InboundPayload` fields only; opaque
> `wire_activity`/`wire_object` fields added to `DispatchActivity` for
> adapter-layer AS2 object persistence). V-21 is **fully resolved** as a side
> effect of P65-3 (`.model_dump_json()` on `raw_activity` in `dispatch()`
> removed). V-20 is **fully resolved** as a side effect of P65-2 (lazy
> `SEMANTICS_HANDLERS` import removed; `handler_map` is now a required
> constructor argument). V-03-R remains — `behavior_dispatcher.py` still
> imports `extract_intent` from the wire layer; addressed by P65-4.

---

## 1. Violations

### Active Regressions (Previously Marked Remediated)

---

### V-03-R — `vultron/behavior_dispatcher.py`, line 10 (regression)

**Rule:** Rule 1 (core has no wire format imports)
**Severity:** Critical
**Claimed remediated by:** ARCH-1.2

`prepare_for_dispatch` calls
`find_matching_semantics(activity=activity)` (line 45), which means the
core dispatcher module must import the wire-layer extractor. Line 10 reads
`from vultron.wire.as2.extractor import find_matching_semantics`. The
ARCH-1.2 claim that "no AS2 import remains in the core dispatcher" is
incorrect — this import is still present. The dispatcher is a core-adjacent
module (it sits at `vultron/behavior_dispatcher.py`) and calls a wire-layer
function to compute the semantic type, creating a direct core→wire dependency.

---

### V-02-R — ✅ `vultron/core/models/events.py`, `InboundPayload.raw_activity` (RESOLVED P65-3)

**Rule:** Rule 5 (core functions take and return domain types)
**Severity:** Critical
**Claimed remediated by:** ARCH-1.2

The ARCH-1.2 remediation introduced `InboundPayload` as a domain type to
replace `as_Activity` in `DispatchActivity.payload`. However,
`InboundPayload` included a `raw_activity: Any` field that carried the original
`as_Activity` wire object verbatim into the domain layer. Every handler
accessed AS2-specific attributes (`.as_object`, `.as_id`, `.as_type`, `.actor`)
via this field.

**Resolved (P65-3):** `raw_activity` removed from `InboundPayload`. 13 typed
domain string fields added. `extract_intent()` in `wire/as2/extractor.py`
populates all fields. Opaque `wire_activity`/`wire_object` fields added to
`DispatchActivity` (adapter-layer type, not `InboundPayload`) for persistence
use only.

---

### V-11-R — ✅ All handlers in `vultron/api/v2/backend/handlers/*.py` (RESOLVED P65-3)

**Rule:** Rule 5 (core functions take and return domain types)
**Severity:** Major
**Claimed remediated by:** ARCH-CLEANUP-3

ARCH-CLEANUP-3 removed `isinstance` checks but handlers still unpacked
`dispatchable.payload.raw_activity` and inspected AS2 attributes on the result.

**Resolved (P65-3):** All 7 handler files updated to read from `InboundPayload`
domain fields only. `wire_activity`/`wire_object` fields on `DispatchActivity`
are opaque adapter-layer fields; handlers access them only for AS2 object
persistence (not for domain logic decisions).

---

### V-10-R — `vultron/api/v2/backend/inbox_handler.py`, module-level datalayer (regression)

**Rule:** Rule 6 (driven adapters injected via ports)
**Severity:** Major
**Claimed remediated by:** ARCH-1.4

Handlers were updated to receive `dl: DataLayer` as a parameter. However,
`inbox_handler.py` lines 32–33 read:

```python
DISPATCHER = get_dispatcher(handler_map=SEMANTICS_HANDLERS, dl=get_datalayer())
```

The concrete `TinyDbDataLayer` is instantiated at module **import time**,
before any request arrives. Each dispatch call then overwrites the reference
again (`DISPATCHER.dl = get_datalayer()`, line 47). The port is never injected
from outside; it is pulled directly from the concrete implementation. Handler
injection is correct in form (handlers receive `dl`) but the dispatcher that
calls them still resolves its DataLayer internally on every dispatch.

---

### New Violations (Introduced in `vultron/core/behaviors/`)

---

### V-13 — ✅ `vultron/core/behaviors/bridge.py` (RESOLVED P65-1)

**Rule:** Rule 2 (core has no framework imports)
**Severity:** Critical

`from vultron.api.v2.datalayer.abc import DataLayer` — a core module imports
a type from the adapter layer (`api/v2/datalayer/`). `DataLayer` is the port
interface; by architecture it should be defined in `core/ports/` (as
`core/ports/activity_store.py` or equivalent). Importing it from `api/v2/`
makes the core depend on the adapter package tree, violating the principle that
the core knows nothing about adapters.

**Resolved:** `DataLayer` Protocol moved to `vultron/core/ports/activity_store.py`
(P65-1). `bridge.py` now imports from `core/ports/`. The old location
(`api/v2/datalayer/abc.py`) is a backward-compat re-export shim.

---

### V-14 — ✅ `vultron/core/behaviors/helpers.py` (RESOLVED P65-1)

**Rule:** Rule 2 (core has no framework imports)
**Severity:** Critical

```python
from vultron.api.v2.datalayer.abc import DataLayer
from vultron.api.v2.datalayer.db_record import Record
```

Same violation as V-13 but also imports `Record`, which is a
persistence-layer data type specific to the TinyDB backend adapter. `Record`
is not a domain abstraction; it is an adapter implementation detail. Core
BT helper nodes should not reference persistence record formats.

**Resolved:** Both imports removed (P65-1/P65-5). `helpers.py` now imports
`DataLayer` from `core/ports/activity_store` and uses a `StorableRecord`
domain type instead of the adapter-layer `Record`. The `save_to_datalayer`
helper constructs `StorableRecord` from domain objects without referencing
`object_to_record`.

---

### V-15 — ⚠️ `vultron/core/behaviors/report/nodes.py` (PARTIALLY RESOLVED P65-5)

**Rule:** Rule 1 (core has no wire format imports), Rule 2 (core has no
framework imports)
**Severity:** Critical

```python
from vultron.api.v2.data.status import (OfferStatus, ReportStatus, ...)
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.wire.as2.vocab.activities.case import CreateCase as as_CreateCase
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
```

A core module imports both AS2 vocabulary types (`as_CreateCase`,
`VulnerabilityCase`) and adapter-layer utilities (`object_to_record`,
`OfferStatus`). The BT node constructing a `CreateCase` AS2 activity and
calling `object_to_record` is doing AS2 serialization and persistence
formatting inside the core behavior tree layer.

**Partially resolved (P65-5):** `object_to_record` and `OfferStatus` imports
removed; replaced by `save_to_datalayer` helper using `StorableRecord` domain
type. The AS2 wire type imports (`as_CreateCase`, `VulnerabilityCase`) remain
and will be addressed in P65-6.

---

### V-16 — ⚠️ `vultron/core/behaviors/report/nodes.py` (PARTIALLY RESOLVED P65-5)

**Rule:** Rule 1, Rule 2
**Severity:** Critical

```python
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.wire.as2.vocab.objects.case_status import ParticipantStatus
```

Lazy imports inside an `update()` method. These are the same violations as
V-15 deferred to runtime via local imports. Per the coding rules in
`AGENTS.md`, local imports are a code smell indicating a circular dependency
that should be refactored away, not hidden.

**Partially resolved (P65-5):** `object_to_record` lazy import removed.
`ParticipantStatus` wire-layer local import remains inside
`_find_and_update_participant_rm` and will be addressed in P65-6.

---

### V-17 — `vultron/core/behaviors/report/policy.py`, lines 36–37

**Rule:** Rule 1 (core has no wire format imports)
**Severity:** Critical

```python
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import VulnerabilityReport
```

The core policy module uses AS2 `VulnerabilityCase` and `VulnerabilityReport`
as its domain types. These are wire-layer types. The policy module's
`validate()` and `should_engage()` method signatures take `VulnerabilityReport`
and `VulnerabilityCase` — wire types — as parameters, meaning the core
boundary logic is expressed in terms of the wire format, not the domain.

---

### V-18 — ⚠️ `vultron/core/behaviors/case/nodes.py` (PARTIALLY RESOLVED P65-5)

**Rule:** Rule 1, Rule 2
**Severity:** Critical

```python
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.wire.as2.vocab.activities.case import CreateCase as as_CreateCase
from vultron.wire.as2.vocab.objects.case_actor import CaseActor
from vultron.wire.as2.vocab.objects.case_participant import VendorParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
```

Core case-creation BT nodes import four AS2 vocabulary types and one
adapter-layer utility. The nodes are constructing `CreateCase` AS2 activities,
`VulnerabilityCase` objects, and formatting them with `object_to_record`
directly in core logic. This is the full AS2 serialization stack inside the
core behavior tree.

**Partially resolved (P65-5):** `object_to_record` import removed; replaced
by `save_to_datalayer` helper. The four AS2 wire type imports
(`as_CreateCase`, `CaseActor`, `VendorParticipant`, `VulnerabilityCase`)
remain and will be addressed in P65-6.

---

### V-19 — `vultron/core/behaviors/case/create_tree.py`, line 44

**Rule:** Rule 1 (core has no wire format imports)
**Severity:** Critical

`from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase`
— the tree-factory function accepts `VulnerabilityCase` (a wire type) as a
parameter type, meaning calling the factory from a handler requires a wire
object to already be present at the call site.

---

### V-20 — ✅ `vultron/behavior_dispatcher.py`, `DispatcherBase.__init__()` (RESOLVED P65-2)

**Rule:** Rule 2 (core has no framework imports)
**Severity:** Major

The lazy import `from vultron.api.v2.backend.handler_map import SEMANTICS_HANDLERS`
inside `DispatcherBase.__init__()` with `handler_map=None` was the violation.

**Resolved (P65-2):** `handler_map` is now a required parameter in
`DispatcherBase.__init__(self, handler_map: dict, ...)`. The `None` default
was removed. The adapter layer (`inbox_handler.py`) injects `SEMANTICS_HANDLERS`
at startup via the lifespan event; no lazy import occurs.

---

### V-21 — ✅ `vultron/behavior_dispatcher.py`, `DispatcherBase.dispatch()` (RESOLVED P65-3)

**Rule:** Rule 1 (core has no wire format imports)
**Severity:** Major

`dispatch()` used to call `.model_dump_json()` on `raw_activity` from
`dispatchable.payload`.

**Resolved (P65-3):** `raw_activity` removed from `InboundPayload`. `dispatch()`
now logs using `dispatchable.payload.activity_id` and `dispatchable.payload.object_type`
— plain domain string fields.

---

### V-22 — `test/test_behavior_dispatcher.py`, line 5 (partially resolved)

**Rule:** Tests section — core tests must use domain types, not AS2 types
**Severity:** Minor

```python
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
```

The test still imports `as_Create` to test `prepare_for_dispatch()`, which
accepts a raw AS2 activity. Once P65-4 moves `prepare_for_dispatch` to the
adapter layer (`inbox_handler.py`), this test will move with it and the core
dispatcher test will no longer need AS2 types.

---

### V-23 — `test/core/behaviors/` multiple test files

**Rule:** Tests section — core tests must not parse AS2 types
**Severity:** Minor

Files affected:
- `test/core/behaviors/case/test_create_tree.py`
- `test/core/behaviors/report/test_nodes.py`
- `test/core/behaviors/report/test_prioritize_tree.py`
- `test/core/behaviors/report/test_validate_tree.py`
- `test/core/behaviors/test_performance.py`

All import AS2 types (`as_Offer`, `as_Accept`, `VulnerabilityReport`,
`as_Service`, `VulnerabilityCase`) to construct test fixtures for core BT
nodes. Core tests should call nodes with domain Pydantic objects, not wire
types. These violations are a downstream consequence of V-15 through V-19:
because the nodes themselves take wire types, the tests must provide them.
Will be addressed in P65-7 once P65-6 defines domain types.

---

## 1-Historical. Violations (Historical — All Remediated)

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
**Remediated by:** ARCH-1.2 *(regression — see V-02-R)*

`DispatchActivity.payload` is now typed as `InboundPayload` (a domain type
defined in `vultron/core/models/events.py`). However, `InboundPayload`
includes `raw_activity: Any` which carries the original `as_Activity`
verbatim. See V-02-R.

---

### V-03 — `vultron/behavior_dispatcher.py`, lines 9 and 17–38

**Rules:** Rule 1 (core has no wire format imports), Rule 5 (core takes domain
types)
**Severity:** Critical
**Remediated by:** ARCH-1.2 *(regression — see V-03-R)*

`behavior_dispatcher.py` previously imported `as_Activity` directly and
accepted it in `prepare_for_dispatch`. After ARCH-1.2, the dispatcher accepts
`InboundPayload`; however, the wire import `from vultron.wire.as2.extractor
import find_matching_semantics` was added in the same refactor. See V-03-R.

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
**Remediated by:** ARCH-1.4 *(partial regression — see V-10-R)*

All handler functions now receive `dl: DataLayer` via parameter injection.
`get_datalayer()` is no longer called inside handler bodies. However,
`inbox_handler.py` creates the DataLayer at module load time and passes it
to the dispatcher at construction. See V-10-R.

---

### V-11 — Handler files use `isinstance` checks against AS2 types

**Rule:** Rule 5 (core functions take and return domain types)
**Severity:** Major
**Remediated by:** ARCH-CLEANUP-3 *(regression — see V-11-R)*

The specific `isinstance(obj, VulnerabilityReport)` calls were removed. The
underlying pattern — handlers navigating AS2 object graphs via `raw_activity`
— remains. See V-11-R.

---

### V-12 — `test/test_behavior_dispatcher.py`, core test uses AS2 types

**Rule:** Tests section — "core tests should call service functions directly
with domain Pydantic objects"
**Severity:** Minor
**Remediated by:** ARCH-CLEANUP-3 *(partial regression — see V-22)*

The test was updated to use domain types from `vultron.core.models.events`.
However, the same test still imports `as_Create` from the wire layer to
construct the input to `prepare_for_dispatch` (see V-22). The `raw_activity`
field on `InboundPayload` is accessed and its AS2 attribute verified in the
test assertion.

---

## 2. Remediation Plan

### R-07: Remove `raw_activity` from `InboundPayload`; complete AS2 extraction in the wire layer

(addresses V-02-R, V-11-R, V-21)

**What moves where:**
The `raw_activity: Any` field must be removed from `InboundPayload`. All
information that handlers currently extract from `raw_activity` (nested object
IDs, actor reference, object graphs) must be surfaced as typed domain fields in
`InboundPayload` or produced by the extractor before dispatch.

The extractor at `wire/as2/extractor.py` must be extended so that
`find_matching_semantics` (or a new `extract_intent` function) produces a
fully-populated `InboundPayload` with all fields that handlers need. Handlers
must never call `.as_object`, `.as_id`, or `.as_type` on anything —
all navigation of the AS2 object graph must happen inside the extractor.

Rough sketch of the enriched payload:

```python
# core/models/events.py
class InboundPayload(BaseModel):
    activity_id: str
    actor_id: str
    object_type: str | None = None   # domain vocabulary string, not AS2 type
    object_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    # For nested-activity patterns (Accept(Offer(...)), etc.)
    inner_object_type: str | None = None
    inner_object_id: str | None = None
    # No raw_activity field
```

**New abstraction needed:** An `extract_intent` function in
`wire/as2/extractor.py` that returns `(MessageSemantics, InboundPayload)` with
all domain-relevant fields populated.

**Dependency:** Requires understanding of every field each handler reads from
`raw_activity` before starting. Do not remove `raw_activity` until every
handler has been audited and the extractor updated.

---

### R-08: ✅ Move `DataLayer` port definition into `core/ports/`

(addresses V-13, V-14 — COMPLETE P65-1)

**What was done:**
`DataLayer` Protocol moved from `vultron/api/v2/datalayer/abc.py` to
`vultron/core/ports/activity_store.py`. The TinyDB implementation in
`vultron/api/v2/datalayer/tinydb_backend.py` stays in the adapter layer and
imports from `core/ports/`. The old location (`api/v2/datalayer/abc.py`) is
now a backward-compat re-export shim.

`Record` imports removed from all core BT nodes (P65-5). Core BT nodes now
use a `StorableRecord` domain type and the `save_to_datalayer` helper in
`core/behaviors/helpers.py`, which constructs `StorableRecord` without
referencing the adapter-layer `Record`.

---

### R-09: ⚠️ Remove wire-layer imports from `core/behaviors/`

(addresses V-15, V-16, V-17, V-18, V-19 — PARTIALLY COMPLETE P65-5)

**Status:** Adapter-layer persistence imports (`object_to_record`, `OfferStatus`,
`Record`) removed from all core BT nodes (P65-5). AS2 wire type imports remain
and are the target of P65-6.

**Remaining work (P65-6):**
All AS2 type construction (`CreateCase`, `VulnerabilityCase`, `CaseActor`,
`VendorParticipant`, `VulnerabilityReport`) currently inside
`core/behaviors/case/nodes.py` and `core/behaviors/report/nodes.py` must be
moved to the wire layer. The BT nodes must not construct AS2 activities; they
must emit domain events, and the wire serializer converts those to AS2.

Specifically:

- `core/behaviors/case/nodes.py` must not import from `wire/as2/vocab/`.
  Nodes that construct `CreateCase` activity objects should instead emit a
  domain `CaseCreatedEvent` (or equivalent), to be serialized downstream by
  the outbound pipeline.
- `core/behaviors/report/policy.py` method signatures must use domain types,
  not `VulnerabilityCase`/`VulnerabilityReport` from the wire vocab. Define
  domain equivalents or accept typed `InboundPayload` fields.
- `core/behaviors/report/nodes.py`: The `ParticipantStatus` local import
  inside `_find_and_update_participant_rm` must be replaced with a domain type.

**New abstractions needed:** Domain event types (e.g., `CaseCreatedEvent`,
`ReportValidatedEvent`) in `core/models/` to replace direct AS2 activity
construction in nodes. An outbound serializer in `wire/as2/serializer.py` that
converts those events to AS2.

**Dependency:** Requires R-07 (payload cleanup) for domain types and R-08
(DataLayer port move, complete) first.

---

### R-10: Decouple `behavior_dispatcher.py` from the wire layer and adapter handler map

(addresses V-03-R, V-20, V-21)

**What moves where:**
`prepare_for_dispatch` calls `find_matching_semantics(activity)` and wraps the
raw AS2 activity in `raw_activity`. After R-07, the extractor will produce a
fully-populated `InboundPayload`. `prepare_for_dispatch` should accept that
payload directly (or be removed in favour of calling the extractor upstream,
in the adapter layer).

The lazy import of `SEMANTICS_HANDLERS` in `DispatcherBase.__init__()` must
be eliminated. The handler map should be injected at construction time, never
loaded lazily inside the constructor. The `inbox_handler.py` startup code that
passes `handler_map=SEMANTICS_HANDLERS` is already the correct pattern; the
`handler_map=None` fallback should be removed.

**New abstraction needed:** None. Requires deleting the `raw_activity` field
(R-07) and removing the `handler_map=None` default (or explicitly requiring
injection at construction time).

**Dependency:** Requires R-07 first.

---

### R-11: Fix module-level datalayer instantiation in `inbox_handler.py`

(addresses V-10-R)

**What moves where:**
`DISPATCHER = get_dispatcher(..., dl=get_datalayer())` on line 32 must be
removed. The dispatcher should receive a DataLayer instance from a startup
lifecycle hook (e.g., FastAPI lifespan event) or via FastAPI dependency
injection through the router, not be initialised at import time.

The per-call `DISPATCHER.dl = get_datalayer()` mutation on line 47 must also
be removed; it is both ad-hoc and redundant with the constructor argument.

**New abstraction needed:** A lifespan event or application factory that wires
the DataLayer into the dispatcher once at startup.

**Dependency:** Can proceed independently of R-07 through R-10.

---

## 2-Historical. Remediation Plan (Completed)

The following remediation items were completed through ARCH-1.1–ARCH-1.4 and
ARCH-CLEANUP-1 through ARCH-CLEANUP-3. They are preserved for reference.

### R-01: Separate `MessageSemantics` from AS2 enums (addresses V-01) ✅

**Completed by:** ARCH-1.1 + ARCH-CLEANUP-2. `MessageSemantics` now lives in
`vultron/core/models/events.py`. AS2 structural enums moved to
`vultron/wire/as2/enums.py`. `vultron/enums.py` re-exports for compatibility.

---

### R-03: Consolidate parsing into `wire/as2/parser.py` (addresses V-06) ✅

**Completed by:** ARCH-1.3. `parse_activity` is now in
`vultron/wire/as2/parser.py`; the router wraps it.

---

### R-04: Consolidate semantic extraction into `wire/as2/extractor.py` (addresses V-04, V-05, V-07, V-08) ✅

**Completed by:** ARCH-1.3 + ARCH-CLEANUP-1. `ActivityPattern`,
`SEMANTICS_ACTIVITY_PATTERNS`, and `find_matching_semantics` are consolidated
in `wire/as2/extractor.py`. The `verify_semantics` decorator compares
`dispatchable.semantic_type` directly.

---

### R-06: Move handler map into the adapter layer (addresses V-09) ✅

**Completed by:** ARCH-1.4 + ARCH-CLEANUP-1. Handler map moved to
`vultron/api/v2/backend/handler_map.py`.

---

## 3. What Is Already Clean

**`wire/as2/extractor.py`** — The extractor is correctly consolidated as the
sole location for AS2-to-domain vocabulary mapping (Rule 4). `ActivityPattern`
and `find_matching_semantics` live here and nowhere else. This is the correct
seam.

**`wire/as2/parser.py`** — Clean wire-layer module. Raises domain parse errors;
contains no domain logic; no handler logic or case management.

**`vultron/api/v2/routers/actors.py` HTTP inbox endpoint** — The router
correctly delegates parsing to `wire/as2/parser.py` via the local
`parse_activity` wrapper, returns 202 immediately, and schedules inbox
processing via `BackgroundTasks`. The three-stage sequence (parse → store →
schedule) is correctly sequenced.

**`vultron/api/v2/backend/handlers/_base.py`, `verify_semantics` decorator** —
Correctly compares `dispatchable.semantic_type` directly against
`expected_semantic_type` without re-invoking pattern matching (V-04 remediated
and not regressed). The decorator design is sound.

**`vultron/api/v2/backend/handler_map.py`** — Handler map lives in the adapter
layer (Rule 2 boundary respected from the adapter side). Binding
`MessageSemantics` values to concrete handler functions is correctly isolated
here.

**`vultron/core/models/events.py`, `MessageSemantics` enum** — The domain
vocabulary is cleanly defined here with no wire-format dependencies. Enum
values (`CREATE_REPORT`, `ENGAGE_CASE`, etc.) express domain intent, not AS2
verbs.

**`ActivityDispatcher` Protocol in `behavior_dispatcher.py`** — The
Protocol-based dispatcher design is correct. The `dispatch` method accepts
`DispatchActivity`, not a raw dict or HTTP request. The problem is entirely in
`prepare_for_dispatch` (which calls the wire extractor) and the `raw_activity`
escape hatch, not in the dispatcher abstraction itself.

**`vultron/errors.py` and `VultronError` base** — Domain exception hierarchy
with no framework or wire-format dependencies.

**`vultron/adapters/` stub package** — The `adapters/driving/`, `adapters/driven/`,
and `adapters/connectors/` stubs are correctly structured and contain only stub
or protocol definitions. `adapters/driving/http_inbox.py` documents the intended
pipeline without implementing it. `ConnectorPlugin` Protocol in
`adapters/connectors/base.py` is the right abstraction.

**`vultron/adapters/connectors/loader.py`** — Correctly specifies entry-point
discovery via `importlib.metadata`. The pattern (not yet implemented) is
architecturally correct per Rule 7.
