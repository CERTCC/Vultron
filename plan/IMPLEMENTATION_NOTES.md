## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

## ~~General guidance: Use typed objects (pydantic basemodels) instead dicts when interfacing ports and adapters~~

> *Captured in `specs/code-style.md` CS-10-001.*

~~Avoid using plain `dict`s as interfaces between the core and adapter layers.
Instead, define Pydantic `BaseModel`-derived classes that represent the data
structures being passed between layers. When an object in a driving adapter
is paralleled in a driven adapter, create a shared model in `core/models/`
that both can import or inherit from to customize. This allows us to retain the
benefits of Pydantic's validation and type safety across the architecture,
while still decoupling the core from adapter-specific types. The core can define
its own domain models that are independent of the wire format, and adapters can
handle conversion to and from those models as needed.~~

## ~~P65-3 Pre-implementation notes~~

> *Captured in `notes/domain-model-separation.md` (Discriminated Event
> Hierarchy / P65-3 Design section and Naming Convention section).*

~~There is a gap in the code where many core domain-level objects use AS2
vocab  objects because they were semantically
identical. This is a case where we might need to build parallel core objects
to correspond to the semantically-identical AS2 vocab objects, but the core
objects don't need to be fully AS2-compliant. This is likely to become
apparent when addressing P56-3.~~

~~P65-3 carries a risk of information loss depending on how `InboundPayload`
ends up being enriched. We probably want to define a core Pydantic model
that is something like a `VultronEvent` that carries all the relevant domain
information extracted from the AS2 activity. Structurally, a `VultronEvent`
would be nearly identical to the AS2 activity/object/target/origin/etc
structure but just not dependent on AS2-specific types. This would finally
address the decoupling of the core from the AS2 wire formats while still
retaining the rich semantic information needed for Vultron to operate on.
`VultronEvent` is a domain event, but it carries the same information as the
AS2 activity (who did what to what, when, how, etc.) but it's a core domain
type that can evolve independently of the AS2 wire format. This looks like
duplication on the surface, but it's actually important for the separation
between wire format and domain model.~~

~~We only really need to build core `VultronEvents` to match up to the things
that are represented by use cases (hint: things corresponding to
MessageSemantics items or triggerable behaviors), so the VultronEvents could
be data classes that specifically map to those particular semantics as
things come in (e.g. `ReportSubmittedEvent`, `CaseUpdatedEvent`, etc.) rather than
a single generic `VultronEvent` that tries to mirror the AS2 structure.
This can help with the use-case-as-port pattern too, making it a bit clearer
in an adapter when you're translating from an AS2 activity to a specific
domain event.~~

## 2026-03-10 — P65-1 complete

### What was done

- Created `vultron/core/ports/__init__.py` and
  `vultron/core/ports/activity_store.py` containing the `DataLayer`
  Protocol. Signatures use `Any` / `BaseModel` — no `Record` import.
- Replaced `vultron/api/v2/datalayer/abc.py` with a one-line backward-compat
  re-export (`from vultron.core.ports.activity_store import DataLayer`). All
  existing `api/v2/` callers continue to work unchanged via this shim.
- Updated `core/behaviors/bridge.py` and `core/behaviors/helpers.py` to
  import `DataLayer` from `core/ports/activity_store`. Removed the `Record`
  import from `helpers.py`; `UpdateObject` and `CreateObject` now build plain
  `dict` values (`{id_, type_, data_}`) and pass them to the DataLayer.
- Updated `TinyDbDataLayer.create()` and `update()` in
  `api/v2/datalayer/tinydb_backend.py` to accept `dict` in addition to
  `Record` / `BaseModel` (converts via `Record.model_validate(d)` internally).

### Violations resolved

V-13 (`bridge.py` importing `DataLayer` from `api/v2`) and V-14
(`helpers.py` importing `DataLayer` + `Record` from `api/v2`) are closed.

### Remaining callers of the backward-compat shim

Many files still import `DataLayer` from `vultron.api.v2.datalayer.abc`.
These will be cleaned up as part of P70 (full DataLayer relocation) or as
a separate sweep once the shim has served its purpose.

---

## 2026-03-10 — Priority 65: Architecture violations and regressions

### Background

A fresh codebase review (`notes/architecture-review.md`, 2026-03-10 update)
shows that ARCH-1.2, ARCH-1.4, and ARCH-CLEANUP-3 have active regressions and
that P60-2 introduced a new class of violations in `vultron/core/behaviors/`.
PRIORITIES.md Priority 65 was added to track remediation.

### Active Regressions

- **V-02-R / V-11-R** (`InboundPayload.raw_activity`): The `raw_activity: Any`
  field carries the original AS2 wire object into every handler. All 4 handler
  modules (`case.py`, `report.py`, `embargo.py`, `participant.py`) navigate AS2
  attributes directly. ARCH-CLEANUP-3 removed `isinstance` checks but the
  underlying pattern is unchanged. Fix: P65-3 (enrich `InboundPayload`;
  remove `raw_activity`).
- **V-03-R** (`behavior_dispatcher.py` line 10): Wire-layer import
  `from vultron.wire.as2.extractor import find_matching_semantics` still
  present. Fix: P65-4 (move call upstream to adapter layer).
- **V-10-R** (`inbox_handler.py` lines 32–33): `TinyDbDataLayer` instantiated
  at module import time. Fix: P65-2 (lifespan-managed DL injection).

### New Violations (introduced by P60-2)

- **V-13, V-14**: `core/behaviors/bridge.py` and `helpers.py` import `DataLayer`
  and `Record` from `api/v2/datalayer/` — adapter-layer types inside core.
  Fix: P65-1 (move `DataLayer` to `core/ports/`).
- **V-15 through V-19**: Core BT nodes in `report/nodes.py`, `case/nodes.py`,
  and `case/create_tree.py` import AS2 wire vocabulary types and `object_to_record`.
  Fix: P65-5 (remove `object_to_record`), P65-6 (replace AS2 wire types with
  domain types).
- **V-20, V-21**: Dispatcher lazy-imports adapter handler map; calls
  `.model_dump_json()` on raw AS2 activity.
  Fix: P65-4 (decouple dispatcher from wire layer).
- **V-22, V-23**: Core test files use AS2 wire types as fixtures.
  Fix: P65-7 (update tests to use domain types).

### Task Ordering Constraints for P65

P65-1 and P65-2 are independent; start either first.
P65-3 is the largest task — do not start it until a full audit of `raw_activity`
field accesses across all handler files is complete.
P65-4 requires P65-3 (needs enriched `InboundPayload`).
P65-5 requires P65-1 (needs `DataLayer` in `core/ports/`).
P65-6 requires P65-3 (domain types for policy signatures) and P65-5
(persistence calls cleaned up first).
P65-7 requires P65-3 (dispatcher test) and P65-6 (core BT node tests).

### P65-3 Design Note (`InboundPayload` enrichment)

The sketch in `notes/architecture-review.md` R-07 shows a minimal
domain-only payload:

```python
class InboundPayload(BaseModel):
    activity_id: str
    actor_id: str
    object_type: str | None = None   # domain vocab string, not AS2 enum
    object_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    inner_object_type: str | None = None
    inner_object_id: str | None = None
```

The audit step in P65-3 will reveal whether additional fields are needed. Do
not add fields speculatively; derive them from the handler audit.

### ~~P65-6 Design Note (domain events vs direct AS2 construction)~~

> *Captured in `notes/domain-model-separation.md` (Outbound Event Design
> Questions / P65-6 Considerations section).*

~~Before implementing P65-6, consider drafting a note or ADR covering:~~
~~- Which events should be defined in `core/models/` (e.g. `CaseCreatedEvent`)~~
~~- Whether the outbound serializer in `wire/as2/serializer.py` converts events
  to AS2 one-to-one or goes through a more general mapping table~~
~~- How domain events interplay with the future outbox pipeline (OUTBOX-1)~~
~~- Consider whether `notes/domain-model-separation.md` already covers this~~

### P65-1 / P70-1 overlap

P65-1 is identical to the former P70-1 (move `DataLayer` Protocol to
`core/ports/`). P70-1 in the task list is superseded and struck out.
After P65-1 the `TinyDbDataLayer` stays in `api/v2/datalayer/` until
P70 completes the full DataLayer relocation to `adapters/driven/`.

### ~~Ideas.md items (for awareness)~~

> *Captured in `notes/codebase-structure.md` (API Layer Architecture) and
> `notes/architecture-ports-and-adapters.md`.*

~~`plan/IDEAS.md` notes that `api/v2/backend/handlers/` are really ports/use
cases (should live in `core/`), and that `api/v1` is a thin adapter talking
near-directly to the DataLayer port. These are addressed by P65 and P70
collectively; the `api/v1` point will need its own task when P70 is tackled.~~

---


## 2026-03-10 — SC-PRE-2 complete: actor_participant_index

### Design

`actor_participant_index: dict[str, str]` maps actor IDs (from
`CaseParticipant.attributed_to`) to participant IDs. Added to
`VulnerabilityCase` alongside two new methods:

- `add_participant(participant: CaseParticipant)` — appends the full object
  to `case_participants` and updates the index atomically. Requires a full
  `CaseParticipant` object (not a string ref) to derive the actor key.
- `remove_participant(participant_id: str)` — filters `case_participants`
  and removes the corresponding index entry.

### Handlers updated

- `add_case_participant_to_case` → calls `case.add_participant(participant)`
- `remove_case_participant_from_case` → calls `case.remove_participant(participant_id)`
- `accept_invite_actor_to_case` → calls `case.add_participant(participant)`;
  idempotency check now uses `actor_participant_index` (old check was
  comparing actor IDs against participant IDs and never matched).

### Notes for SC-3.2 / SC-3.3

The `actor_participant_index` is the prerequisite for SC-3.2 and SC-3.3.
SC-3.2 records the accepted embargo ID in `CaseParticipant.accepted_embargo_ids`
using the CaseActor's trusted timestamp. The index makes it efficient to
look up a participant from the actor ID when processing `Accept(Invite(...))` or
`Accept(Offer(Embargo))` activities.

SC-3.3 adds `_check_participant_embargo_acceptance()` as a module-level helper
in `vultron/api/v2/backend/handlers/case.py`. It is called from `update_case`
after the ownership check passes. The helper iterates `actor_participant_index`,
rehydrates each participant, and logs a WARNING if the participant's
`accepted_embargo_ids` does not include the case's `active_embargo` ID.
Full enforcement (withholding the broadcast) is deferred to PRIORITY-200 when
the outbox delivery pipeline is implemented.

---

## 2026-03-10 — Gap analysis refresh #22: new gaps identified

### ~~Test directory layout mismatch (TECHDEBT-11)~~

> *Captured in `notes/codebase-structure.md` (Technical Debt: Test Directory
> Layout Mismatch section).*

~~After P60-1 and P60-2, the test directories `test/as_vocab/` and `test/behaviors/`
remain at their old locations. All tests already import from the new canonical
paths (`vultron.wire.as2.vocab.*` and `vultron.core.behaviors.*`), so tests pass.
The directory structure just does not mirror the source layout yet.~~

~~Target moves:~~
~~- `test/as_vocab/` → `test/wire/as2/vocab/`~~
~~- `test/behaviors/` → `test/core/behaviors/`~~

~~Both moves are mechanical: create `test/wire/as2/vocab/` and `test/core/behaviors/`
directories, move files, update `conftest.py` and `__init__.py`, delete old dirs.
No import changes are needed (they're already correct).~~

### ~~Deprecated HTTP status constant (TECHDEBT-12)~~

> *Captured in `notes/codebase-structure.md` (Technical Debt: Deprecated HTTP
> Status Constant section).*

~~`starlette.status.HTTP_422_UNPROCESSABLE_ENTITY` is deprecated in favor of
`HTTP_422_UNPROCESSABLE_CONTENT`. Seven usages remain in trigger service files:~~
~~- `vultron/api/v2/backend/trigger_services/embargo.py` (3 usages)~~
~~- `vultron/api/v2/backend/trigger_services/report.py` (2 usages)~~
~~- `vultron/api/v2/backend/trigger_services/_helpers.py` (2 usages)~~

~~This generates a `DeprecationWarning` in the test suite output. The fix is a
simple string replacement; the new constant name is `HTTP_422_UNPROCESSABLE_CONTENT`.~~

### P70 DataLayer refactor — when to plan

`notes/domain-model-separation.md` says the DataLayer relocation SHOULD be planned
together with PRIORITY-100 (actor independence). The P70 tasks in the plan follow
that guidance: P70-1 relocates the port Protocol and TinyDB adapter to their
correct architectural homes, which unblocks the per-actor isolation work in
PRIORITY-100. P60-3 must come first (adapters package stub needed before TinyDB
moves there).

### TECHDEBT-4 superseded

TECHDEBT-4 ("reorganize top-level modules `activity_patterns`, `semantic_map`,
`enums`") is largely complete:
- `vultron/activity_patterns.py` and `vultron/semantic_map.py` deleted in
  ARCH-CLEANUP-1.
- AS2 structural enums moved from `vultron/enums.py` to `vultron/wire/as2/enums.py`
  in ARCH-CLEANUP-2.
- `vultron/enums.py` now only re-exports `MessageSemantics` plus defines
  `OfferStatusEnum` and `VultronObjectType`.

Remaining work: move `OfferStatusEnum` and `VultronObjectType` to their proper
homes and delete `vultron/enums.py`. Tracked in TECHDEBT-4 (marked superseded in
plan) and P70-2.

---

---

## 2026-03-09 — Hexagonal architecture refactor elevated to PRIORITY 50 (immediate next)

Per updated `plan/PRIORITIES.md`, the hexagonal architecture refactor with `triggers.py`
as the starting point is now the top priority. The plan has been updated accordingly:
`Phase ARCH-1` is renamed to `Phase PRIORITY-50` and moved to be the immediate next
phase after PRIORITY-30 (now complete). The old "PRIORITY 150" label in the plan was
incorrect; PRIORITIES.md has always listed this as Priority 50.

### Approach for P50-0: Extract service layer from `triggers.py` — **COMPLETE**

`triggers.py` is 1274 lines with all nine trigger endpoint functions each containing
inline domain logic (data lookups, state transitions, activity construction, outbox
updates). The fix is a two-step operation within one agent cycle:

**Step 1 — Create `vultron/api/v2/backend/trigger_services/` package** ✓:
- `report.py` — service functions for `validate_report`, `invalidate_report`,
  `reject_report`, `close_report`
- `case.py` — service functions for `engage_case`, `defer_case`
- `embargo.py` — service functions for `propose_embargo`, `evaluate_embargo`,
  `terminate_embargo`

Each service function signature:
```python
def svc_validate_report(actor_id: str, offer_id: str, note: str | None, dl: DataLayer) -> dict:
    ...
```
The `DataLayer` is passed in from the router (via `Depends(get_datalayer)`), not
fetched inside the service.

**Step 2 — Thin-ify and split the router** ✓:
- Split `triggers.py` into `trigger_report.py`, `trigger_case.py`,
  `trigger_embargo.py` in `vultron/api/v2/routers/`
- Each router function: validate request → call service → return response
- `triggers.py` deleted ✓

**Additional cleanup** ✓:
- Consolidated `ValidateReportRequest`, `InvalidateReportRequest`, and
  `CloseReportRequest` (structurally identical — CS-09-002) into shared base
  `ReportTriggerRequest` in `_models.py`
- Trigger tests split into `test_trigger_report.py`, `test_trigger_case.py`,
  `test_trigger_embargo.py`; service-layer unit tests added in
  `test/api/v2/backend/test_trigger_services.py`
- Test count: 777 → 815 passing

### Why start with `triggers.py` before ARCH-1.1?

ARCH-1.1 through ARCH-1.4 are deep structural changes affecting many files across
the codebase. P50-0 (triggers.py service extraction) is scoped to a single large
file, delivers immediate architectural value (no domain logic in routers), and does
not require the broader `core/`/`wire/`/`adapters/` directory restructure to be
in place first. It also establishes the pattern that ARCH-1.1 through 1.4 will
generalize to the rest of the codebase.

ARCH-1.1 and ARCH-1.2 remain prerequisites for ARCH-1.3 and ARCH-1.4 as documented
in `notes/architecture-review.md`.

---



`specs/architecture.md` and `notes/architecture-review.md` were added since the
last plan refresh. The review identifies 11 violations (V-01 to V-11) and a
remediation plan (R-01 to R-06). The most impactful violations are:

- **V-01**: `MessageSemantics` mixed with AS2 structural enums in `vultron/enums.py`
- **V-02**: `DispatchActivity.payload: as_Activity` (AS2 type leaks into core)
- **V-04**: `verify_semantics` decorator re-invokes `find_matching_semantics`
  (second AS2-to-domain mapping point, violates Rule 4)

Phase ARCH-1 now tracks this work. ARCH-1.1 (R-01) must be done before ARCH-1.2
(R-02), which must precede ARCH-1.3 (R-03/R-04).

## 2026-03-09 — P30-4 `close-report` vs `reject-report` distinction

Both `reject-report` and `close-report` emit `RmCloseReport` (`as_Reject`), but
they differ in context:

- `reject-report` hard-rejects an incoming report offer (offer not yet validated;
  `object=offer.as_id`)
- `close-report` closes a report after the RM lifecycle has proceeded (RM → C
  transition; emits RC message)

The existing `trigger_reject_report` implementation uses `offer_id` as its target.
The `trigger_close_report` implementation should also use `offer_id` but should
validate that the offer's report is in an appropriate RM state for closure (not
just any offered report). This distinction should be documented in the endpoint
docstring.

## 2026-03-09 — CS-09-002 duplication in triggers.py request models

`ValidateReportRequest` and `InvalidateReportRequest` in `triggers.py` are
structurally identical (both have `offer_id: str` and `note: str | None`). Per
CS-09-002, these should be consolidated into a single base model with the other
as a subclass or alias. Low-priority but worth addressing when the file is next
modified.

---

## 2026-03-09 — P30-4 complete: close-report trigger endpoint

`POST /actors/{actor_id}/trigger/close-report` added. Emits `RmCloseReport`
(RM → C transition), updates offer/report status and actor outbox, returns
HTTP 409 if already CLOSED. 9 unit tests added.

Also converted `RM` from plain `Enum` to `StrEnum` for consistency with `EM`.
This changes `str(RM.X)` from `"RM.REPORT_MANAGEMENT_X"` to `"X"`, resulting
in cleaner BT node names (e.g., `q_rm_in_CLOSED` instead of
`q_rm_in_RM.REPORT_MANAGEMENT_CLOSED`). Updated `test_conditions.py` to check
`state.value` in node name instead of `state.name`.

---

## ~~Triggerable behaviors should start to live in `vultron/core/` and respect the architecture~~

> *Captured in `AGENTS.md` ("Trigger behavior logic belongs outside the API
> router") and `specs/architecture.md` ARCH-08-001.*

~~The `triggers.py` module currently has a mix of architectural violations, including
including directly invoking domain logic in the routers. We should start
separating these concerns as soon as practical in preparation for the
architecture refactor. It would be better to start moving towards the
cleaner architecture where we can now than to continue building out more
things that will have to be refactored later. We know the direction we are
going with the architecture, so we should start moving in that direction now
when we can.~~

~~This idea generalizes too. When you're modifying or adding new router code,
consider the architectural intent and whether the code you're writing
respects the intended separation of concerns. Try to avoid mixing domain
logic directly into the routers, and instead think about how to structure the
code so that the ports and adapters model is cleaner even before the full
refactor.~~

~~Fix what you can as you go, and add items you observe as technical debt to
the implementation notes for anything you notice but can't fix immediately.~~

~~Technical debt: Refactor triggers.py to respect the hexagonal architecture
concepts.~~


---

## ~~Many of the workflows, triggerable behaviors, and demo scenarios map to use cases~~

> *Captured in `notes/use-case-behavior-trees.md` (Mapping Protocol Activities
> section) and `notes/architecture-ports-and-adapters.md` (Design Note: Use
> Cases as Incoming Ports).*

~~In a Hexagonal Architecure, the core domain logic is organized around use
cases that represent the key actions or operations that the system performs.
These use cases are then invoked by the ports (e.g., API endpoints, CLI
commands) and implemented by the adapters. As you review the codebase, many
of the message semantics, behaviors, workflows, triggers, and demo scenarios
map onto specific
use cases indicated in their names. For example "PrioritizeCase",
"ProposeEmbargo", "DeferCase" etc. Keep this in mind when deciding how to
refactor the codebase into the hexagonal architecture.~~

---

## 2026-03-10 — Gap analysis refresh #21: PRIORITY-50 complete, ARCH-CLEANUP and PRIORITY-60 added

### PRIORITY-50 status

All four ARCH-1.x tasks complete (P50-0 through ARCH-1.4). V-01 through V-10 from
`notes/architecture-review.md` are remediated. Four follow-on cleanup items remain:

1. **Shims ready to delete**: `vultron/activity_patterns.py`, `vultron/semantic_map.py`,
   and `vultron/semantic_handler_map.py` are all backward-compat shims. Only one external
   caller remains: `test/api/test_reporting_workflow.py:36` imports
   `find_matching_semantics` from `vultron.semantic_map`. Update that import to
   `vultron.wire.as2.extractor`, then delete all three shim files.

2. **AS2 structural enums still in `vultron/enums.py`**: `as_ObjectType`, `as_ActorType`,
   `as_IntransitiveActivityType`, `as_TransitiveActivityType`, `merge_enums`,
   `as_ActivityType`, and `as_AllObjectTypes` were not moved in ARCH-1.1 (only
   `MessageSemantics` moved then). They belong in `vultron/wire/as2/enums.py`. Four
   `as_vocab/base/objects/` importers need updating. `VultronObjectType` and
   `OfferStatusEnum` are domain/wire-boundary enums that should also be considered
   for migration in ARCH-CLEANUP-2.

3. **V-11 still present**: `isinstance(x, VulnerabilityReport)` and similar checks appear
   in `vultron/api/v2/backend/handlers/report.py` (lines 34, 90, 163),
   `handlers/case.py` (line 346), `trigger_services/report.py` (line 75), and
   `trigger_services/_helpers.py` (lines 65, 93). These should be replaced with
   `dispatchable.payload.object_type == "VulnerabilityReport"` or equivalent domain
   checks.

4. **V-12 still present**: `test/test_behavior_dispatcher.py` imports `as_Create`,
   `VulnerabilityReport`, and `as_TransitiveActivityType` from `vultron.as_vocab` to
   build test inputs. Should be refactored to use `InboundPayload` directly.

### PRIORITY-60 note

`plan/PRIORITIES.md` PRIORITY 60 calls for continued package relocation: `vultron/as_vocab/`
→ `wire/`, `vultron/behaviors/` → `core/behaviors/`, and stubbing the `adapters/`
package structure. These are now tracked as P60-1 through P60-3 in the plan. P60-1
(moving `as_vocab`) is the largest task and will affect imports across nearly every
module; consider using a shim-in-place approach to manage the transition.

### ARCH-ADR-9 note

No ADR exists for the hexagonal architecture decision. The implementation notes
(2026-03-09 entry) recorded a TODO for this. The architecture decisions in
`notes/architecture-ports-and-adapters.md`, the violation inventory in
`notes/architecture-review.md`, and the remediation work in ARCH-1.1 through
ARCH-1.4 provide all the raw material for the ADR.

---

## TECHDEBT-3: Object IDs standardized to URI form (2026-03-10)

**Changes made**:

- `generate_new_id()` in `vultron/wire/as2/vocab/base/utils.py` now returns
  `urn:uuid:{uuid}` by default. The bare-UUID return was replaced with a
  proper absolute IRI, satisfying OID-01-001.
- `parse_id()` in `vultron/api/v2/data/utils.py` extended to handle
  `urn:uuid:` form IDs, returning the bare UUID as the `object_id` component.
- `BASE_URL` in `vultron/api/v2/data/utils.py` now reads from the
  `VULTRON_BASE_URL` environment variable (OID-01-003), defaulting to
  `https://demo.vultron.local/`.
- Compatibility shim added to `TinyDbDataLayer.read()`: when a bare UUID is
  passed as the lookup key the method also tries `urn:uuid:{uuid}`, allowing
  demo and API code that uses the `parse_id()["object_id"]` pattern to
  continue working during the migration period.
- ADR-0010 created at `docs/adr/0010-standardize-object-ids.md`.
- New tests in `test/wire/as2/vocab/test_base_utils.py` validate URI-form
  IDs; additional tests added to `test/api/v2/data/test_utils.py`.

**Caveats**:

- The compatibility shim accepts bare-UUID lookups (it tries the `urn:uuid:`
  form automatically). OID-02-004 says bare UUIDs MUST NOT be accepted as
  valid lookup keys; the shim is a deliberate prototype-phase deviation.
  Remove it once all callers use full-URI IDs (PRIORITY-70 work).
- Existing bare-UUID records in TinyDB stores are not migrated automatically.
  They will not be found by new `urn:uuid:`-keyed lookups (bare-UUID records
  are a prototype artifact from before this change).


