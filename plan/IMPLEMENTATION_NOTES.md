## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

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

### Test directory layout mismatch (TECHDEBT-11)

After P60-1 and P60-2, the test directories `test/as_vocab/` and `test/behaviors/`
remain at their old locations. All tests already import from the new canonical
paths (`vultron.wire.as2.vocab.*` and `vultron.core.behaviors.*`), so tests pass.
The directory structure just does not mirror the source layout yet.

Target moves:
- `test/as_vocab/` → `test/wire/as2/vocab/`
- `test/behaviors/` → `test/core/behaviors/`

Both moves are mechanical: create `test/wire/as2/vocab/` and `test/core/behaviors/`
directories, move files, update `conftest.py` and `__init__.py`, delete old dirs.
No import changes are needed (they're already correct).

### Deprecated HTTP status constant (TECHDEBT-12)

`starlette.status.HTTP_422_UNPROCESSABLE_ENTITY` is deprecated in favor of
`HTTP_422_UNPROCESSABLE_CONTENT`. Seven usages remain in trigger service files:
- `vultron/api/v2/backend/trigger_services/embargo.py` (3 usages)
- `vultron/api/v2/backend/trigger_services/report.py` (2 usages)
- `vultron/api/v2/backend/trigger_services/_helpers.py` (2 usages)

This generates a `DeprecationWarning` in the test suite output. The fix is a
simple string replacement; the new constant name is `HTTP_422_UNPROCESSABLE_CONTENT`.

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

## 2026-03-10 — P60-1 complete: vultron/as_vocab moved to vultron/wire/as2/vocab

> ✅ Captured in `docs/adr/0009-hexagonal-architecture.md` (P60-1 marked
> complete) and `notes/codebase-structure.md` and
> `notes/architecture-ports-and-adapters.md` (file layout updated 2026-03-10).

### What changed

- Copied entire `vultron/as_vocab/` tree to `vultron/wire/as2/vocab/` (keeping
  all sub-packages: `base/`, `objects/`, `activities/`, `examples/`, plus
  `errors.py`, `type_helpers.py`).
- Updated all internal imports within the moved files from `vultron.as_vocab.*`
  to `vultron.wire.as2.vocab.*`.
- Updated ~90 external callers across `vultron/api/`, `vultron/behaviors/`,
  `vultron/demo/`, `vultron/wire/as2/`, and `test/`.
- Deleted `vultron/as_vocab/` entirely (no shim left behind).
- 822 tests pass.

---

## 2026-03-10 — ARCH-CLEANUP-3 complete: isinstance AS2 checks replaced (V-11, V-12)

> ✅ Captured in `notes/architecture-review.md` (V-11, V-12 marked remediated
> by ARCH-CLEANUP-3) and `docs/adr/0009-hexagonal-architecture.md` (2026-03-10).

### What changed

- **`handlers/report.py`**: `create_report` and `submit_report` now check
  `dispatchable.payload.object_type != "VulnerabilityReport"` instead of
  `isinstance`. `validate_report` uses `getattr(accepted_report, "as_type", None)`.
  Local `VulnerabilityReport` imports removed from all three handlers.
- **`handlers/case.py`**: `update_case` uses `getattr(incoming, "as_type", None) ==
  "VulnerabilityCase"`. Local `VulnerabilityCase` import removed.
- **`trigger_services/report.py`**: `_resolve_offer_and_report` uses `getattr`
  as_type check. `VulnerabilityReport` module-level import removed.
- **`trigger_services/_helpers.py`**: `resolve_case` and
  `update_participant_rm_state` use `getattr` as_type checks. `VulnerabilityCase`
  import retained for the `-> VulnerabilityCase` return type annotation.
- **`test/test_behavior_dispatcher.py`**: Removed `as_TransitiveActivityType` and
  `VulnerabilityReport` imports. `as_type` assertion uses string `"Create"`.
  Dispatch test uses `MagicMock` for `raw_activity` instead of full AS2 construction.
- **`test/api/test_reporting_workflow.py`**: `_call_handler` now populates
  `InboundPayload.object_type` from `activity.as_object.as_type` (mirrors
  `prepare_for_dispatch`), so handler type guards work correctly in tests.

822 tests pass.



### What changed

- Deleted `vultron/activity_patterns.py`, `vultron/semantic_map.py`, and
  `vultron/semantic_handler_map.py` (all were pure re-export shims).
- Updated all callers to import from canonical locations:
  - `test/test_semantic_activity_patterns.py`: `ActivityPattern` and
    `SEMANTICS_ACTIVITY_PATTERNS` now imported from `vultron.wire.as2.extractor`.
  - `test/api/test_reporting_workflow.py`: `find_matching_semantics` now imported
    from `vultron.wire.as2.extractor`.
  - `test/test_semantic_handler_map.py`: Shim-specific tests removed; test now
    uses `SEMANTICS_HANDLERS` from `vultron.api.v2.backend.handler_map` directly.
- 822 tests pass.

---



### What changed

- **`vultron/api/v2/backend/handler_map.py`** (new): Module-level handler registry in
  the adapter layer. `SEMANTICS_HANDLERS` dict maps `MessageSemantics` → handler
  functions with plain module-level imports (no lazy imports needed since this file
  is already in the adapter layer). This addresses V-09.

- **`vultron/semantic_handler_map.py`**: Converted to a backward-compat shim that
  re-exports `SEMANTICS_HANDLERS` and a `get_semantics_handlers()` wrapper from
  the new location. Can be deleted once all callers are updated.

- **`vultron/behavior_dispatcher.py`**: `DispatcherBase` now accepts `dl: DataLayer`
  and `handler_map: dict[MessageSemantics, BehaviorHandler]` in its constructor.
  `_handle()` passes `dl=self.dl` to each handler. `_get_handler_for_semantics()`
  uses `self._handler_map` directly (no lazy import). `get_dispatcher()` updated to
  accept `dl` and `handler_map` parameters.

- **`vultron/api/v2/backend/inbox_handler.py`**: Module-level `DISPATCHER` now
  constructed with `get_datalayer()` + `SEMANTICS_HANDLERS` injected. The lazy
  import in `_get_handler_for_semantics` is gone; the coupling to the handler map
  now lives in the adapter layer only.

- **All handler files** (`report.py`, `case.py`, `embargo.py`, `actor.py`, `note.py`,
  `participant.py`, `status.py`, `unknown.py`): Each handler function signature
  updated to `(dispatchable: DispatchActivity, dl: DataLayer) -> None`. All
  `from vultron.api.v2.datalayer.tinydb_backend import get_datalayer` lazy imports
  and `dl = get_datalayer()` calls removed. `DataLayer` imported at module level from
  `vultron.api.v2.datalayer.abc`. This addresses V-10.

- **`vultron/types.py`**: `BehaviorHandler` Protocol updated to
  `__call__(self, dispatchable: DispatchActivity, dl: DataLayer) -> None`.

- **`vultron/api/v2/backend/handlers/_base.py`**: `verify_semantics` wrapper updated
  to accept and forward `dl: DataLayer`.

- **Tests**: All `@patch("vultron.api.v2.datalayer.tinydb_backend.get_datalayer")`
  patches in `test_handlers.py` replaced with direct `mock_dl` argument passing.
  `test_behavior_dispatcher.py` updated to construct dispatcher with injected DL
  and handler map. 824 tests pass (up from 822).

### Phase PRIORITY-50 is now complete (ARCH-1.1 through ARCH-1.4)

All four ARCH-1.x tasks are done. The hexagonal architecture violations V-01 through
V-10 have been remediated. The remaining violations in the inventory (V-11, V-12)
are lower severity and can be addressed as part of subsequent work.

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

## Triggerable behaviors should start to live in `vultron/core/` and respect the architecture

The `triggers.py` module currently has a mix of architectural violations, including
including directly invoking domain logic in the routers. We should start 
separating these concerns as soon as practical in preparation for the 
architecture refactor. It would be better to start moving towards the 
cleaner architecture where we can now than to continue building out more 
things that will have to be refactored later. We know the direction we are 
going with the architecture, so we should start moving in that direction now 
when we can.

This idea generalizes too. When you're modifying or adding new router code, 
consider the architectural intent and whether the code you're writing 
respects the intended separation of concerns. Try to avoid mixing domain 
logic directly into the routers, and instead think about how to structure the
code so that the ports and adapters model is cleaner even before the full 
refactor.

Fix what you can as you go, and add items you observe as technical debt to 
the implementation notes for anything you notice but can't fix immediately.

Technical debt: Refactor triggers.py to respect the hexagonal architecture 
concepts.


---

## 2026-03-09 — P30-6 complete: trigger sub-command in vultron-demo CLI

Added `vultron-demo trigger` sub-command backed by `vultron/demo/trigger_demo.py`.

Two end-to-end demo workflows are implemented:
- **Demo 1 (validate and engage)**: finder submits report via inbox → vendor
  calls `POST .../trigger/validate-report` → vendor calls
  `POST .../trigger/engage-case`.
- **Demo 2 (invalidate and close)**: finder submits report via inbox → vendor
  calls `POST .../trigger/invalidate-report` → vendor calls
  `POST .../trigger/close-report`.

Supporting changes:
- Added `post_to_trigger()` helper to `vultron/demo/utils.py`.
- Added `trigger` demo to `DEMOS` list in `vultron/demo/cli.py`; it now runs
  as part of `vultron-demo all`.
- Updated `docs/reference/code/demo/demos.md` and `cli.md` with new entries.

Phase PRIORITY-30 is now fully complete (P30-1 through P30-6).

---

## 2026-03-09 — ARCH-1.1 complete: MessageSemantics moved to vultron/core/models/events.py

Created `vultron/core/` package with `models/events.py` containing only
`MessageSemantics`. Removed the definition from `vultron/enums.py` (which
now re-exports it for backward compatibility). Updated all 17 direct import
sites across `vultron/` and `test/`. 815 tests pass.

The compatibility re-export in `vultron/enums.py` may be removed once ARCH-1.3
consolidates the extractor and the AS2 structural enums move to
`vultron/wire/as2/enums.py` (R-04).


---

## 2026-03-09 — ARCH-1.2 complete: InboundPayload introduced; AS2 type removed from DispatchActivity

Added `InboundPayload` to `vultron/core/models/events.py` with fields
`activity_id`, `actor_id`, `object_type`, `object_id`, and `raw_activity: Any`.
`DispatchActivity.payload` now types as `InboundPayload` instead of `as_Activity`,
removing the AS2 import from `vultron/types.py` (V-02) and from
`behavior_dispatcher.py` (V-03). All 38 handler functions updated to
`activity = dispatchable.payload.raw_activity`. `verify_semantics` decorator
updated to compare `dispatchable.semantic_type` directly (ARCH-07-001), removing
the second `find_matching_semantics` call. 815 tests pass.

---

## 2026-03-09 — ARCH-1.3 complete: wire/as2/parser.py and wire/as2/extractor.py created

### What moved

- **`vultron/wire/as2/parser.py`** (new): `parse_activity()` extracted from
  `vultron/api/v2/routers/actors.py`. Raises domain exceptions (`VultronParseError`
  hierarchy defined in `vultron/wire/as2/errors.py` and `vultron/wire/errors.py`)
  instead of `HTTPException`. The router now has a thin HTTP adapter wrapper that
  catches these and maps to 400/422 responses (R-03, V-06, ARCH-08-001).

- **`vultron/wire/as2/extractor.py`** (new): Consolidates `ActivityPattern` class,
  all 37 pattern instances, `SEMANTICS_ACTIVITY_PATTERNS` dict, and
  `find_matching_semantics()` from the former `vultron/activity_patterns.py` and
  `vultron/semantic_map.py`. This is now the sole location for AS2-to-domain
  semantic mapping (R-04, V-05, ARCH-03-001).

- **`vultron/wire/errors.py`** (new): `VultronWireError(VultronError)` base.
- **`vultron/wire/as2/errors.py`** (new): `VultronParseError`, subtypes for missing
  type, unknown type, and validation failure.

### Backward-compat shims retained

`vultron/activity_patterns.py` and `vultron/semantic_map.py` converted to
re-export shims so any external code importing from the old locations continues
to work. These can be deleted once confirmed no external callers remain.

### What else changed

- `vultron/behavior_dispatcher.py`: import `find_matching_semantics` from
  `vultron.wire.as2.extractor` (no longer `vultron.semantic_map`).
- `vultron/api/v2/backend/inbox_handler.py`: removed `raise_if_not_valid_activity`
  (V-07) and the `VOCABULARY` import; activity type validation now happens
  entirely in the wire parser layer before the item reaches the inbox handler.
- Tests: `test_raise_if_not_valid_activity_raises` deleted; 7 new wire layer tests
  added in `test/wire/as2/`. 822 tests pass (up from 815).

---

## Many of the workflows, triggerable behaviors, and demo scenarios map to use cases

In a Hexagonal Architecure, the core domain logic is organized around use 
cases that represent the key actions or operations that the system performs. 
These use cases are then invoked by the ports (e.g., API endpoints, CLI 
commands) and implemented by the adapters. As you review the codebase, many 
of the message semantics, behaviors, workflows, triggers, and demo scenarios 
map onto specific 
use cases indicated in their names. For example "PrioritizeCase", 
"ProposeEmbargo", "DeferCase" etc. Keep this in mind when deciding how to 
refactor the codebase into the hexagonal architecture.

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

## 2026-03-10 — P60-2: vultron/behaviors/ moved to vultron/core/behaviors/

> ✅ Captured in `docs/adr/0009-hexagonal-architecture.md` (P60-2 marked
> complete) and `notes/codebase-structure.md`,
> `notes/architecture-ports-and-adapters.md`, `notes/bt-integration.md`
> (all updated 2026-03-10).

### What changed

- Copied entire `vultron/behaviors/` tree (bridge, helpers, case/, report/)
  to `vultron/core/behaviors/`.
- Updated all internal imports within the moved files from
  `vultron.behaviors.*` to `vultron.core.behaviors.*`.
- Updated all external callers:
  - `vultron/api/v2/backend/handlers/report.py` (lazy imports)
  - `vultron/api/v2/backend/handlers/case.py` (lazy imports)
  - `vultron/api/v2/backend/trigger_services/report.py`
  - 8 test files under `test/behaviors/`
- Deleted `vultron/behaviors/` entirely (no shim retained; all callers
  updated in the same step).
- 822 tests pass.

---

## Problem on the horizon: defining incoming "ports" as use cases

> ✅ Captured in `notes/architecture-ports-and-adapters.md` ("Design Note: Use
> Cases as Incoming Ports" section, added 2026-03-10). Also noted in `AGENTS.md`
> Key Files Map (`vultron/core/use_cases/` stub entry).

There are a lot of handlers that are built around specific message semantics,
and these are in fact natural use cases that the system needs to support. 
For example, "SubmitReport", "DeferCase", "TerminateEmbargo" etc. These are 
all things that carry semantic meaning in the domain and represent key 
business logic level operations (some of which have behavior trees that 
implement them). However, as we are in the process of refactoring towards a 
cleaner hexagonal architecture, it's clear that we will rapidly find that 
there's a gap between the semantic routing and what the core is exporting. 
This is one of the places where the overlap between the AS2 vocabulary and 
the domain model was so close that we didn't really notice the distinction, 
but now that we're thinking architecturally we will need to have some way 
for the core to export these use cases so that the adapters can invoke them 
independently of the AS2 semantics (again, even though the semantics are 
still a 1:1 mapping to the use cases). This may require some tasks to be 
inserted into the plan to create these use cases as explicit invokable 
entities in the core. Whether they're a class that gets instantiated or just 
functions to be called is left as a decision to be made at implementation 
time, but the key point is that we need to have a peering structure between 
the adapters and the core that allows adapters to invoke these use cases 
without necessarily relying on the wire format (AS2) to be the thing that 
the core is built around. `vultron/wire/as2/vocab/examples.py` is also a 
good example of a list of primitives (use cases) that the core needs to be 
able to understand. (The examples produce these things as AS2 messages, but 
we need the thing those messages get routed *to* to be the core use case, 
not the AS2 syntax itself).

This might also extend toward the core needing to have an internal 
representation of all the AS2 semantics but maybe without the AS2 
syntax.

> ✅ PROTO-06-001 tension captured in `specs/prototype-shortcuts.md` (Design
> Note added under PROTO-06-001, 2026-03-10).

---



## TECHDEBT-9/7 — NonEmptyString type alias rollout (2026-03-10)

`NonEmptyString` and `OptionalNonEmptyString` were already defined in
`vultron/wire/as2/vocab/base/types.py` and partially applied. This task
completed the rollout across all remaining `Optional[str]` fields in
`vultron/wire/as2/vocab/objects/`:

- **`case_event.py`**: Replaced per-field `@field_validator` on `object_id`
  and `event_type` with `NonEmptyString` type annotations; removed validators.
- **`case_reference.py`**: Replaced per-field validators for `url` and `name`
  with `NonEmptyString` and `OptionalNonEmptyString`; removed validators.
- **`vulnerability_record.py`**: Changed `url: str | None` to
  `OptionalNonEmptyString`.
- **`case_participant.py`**: Changed `name` and `participant_case_name` from
  `str | None` to `OptionalNonEmptyString`.
- **`case_status.py`**: Changed `CaseStatus.context` and
  `ParticipantStatus.tracking_id` from `str | None` to `OptionalNonEmptyString`.

Error message updated: tests that previously asserted field-prefixed messages
(e.g., "object_id must be a non-empty string") now assert the shared message
"must be a non-empty string" (which the `AfterValidator` in `_non_empty` raises).

New tests added: `test_case_status.py`, extended `test_case_participant.py`,
extended `test_vulnerability_record.py`. 860 tests pass.

Note: `CaseParticipant.set_name_if_empty` model validator automatically
populates `name` from `attributed_to` when `name=None`; tests for `name=None`
must omit `attributed_to` to observe the None value.

## TECHDEBT-10 — Backfill pre-case events in create_case BT (2026-03-10)

**Task**: Backfill pre-case events into the case event log at case creation
(CM-02-009).

**Implementation**:

- Added `RecordCaseCreationEvents` node to
  `vultron/core/behaviors/case/nodes.py`. The node runs after `PersistCase` in
  the `CreateCaseFlow` sequence.
- The node records two events using `case.record_event()`:
  1. `"offer_received"` — only when the triggering activity has an
     `in_reply_to` reference (the originating Offer that led to case
     creation). The `object_id` is set to the Offer's `as_id`.
  2. `"case_created"` — always recorded; `object_id` is set to the case ID.
- The node reads `activity` from the global py_trees blackboard storage
  (`Blackboard.storage.get("/activity", None)`) rather than registering it as
  a required key. This avoids a `KeyError` when the tree is invoked without an
  inbound activity (e.g. in tests that pass `activity=None`).
- `create_tree.py` updated to import and include `RecordCaseCreationEvents` in
  the sequence.
- 6 new tests added to `test/core/behaviors/case/test_create_tree.py`.

**Key design note**: `received_at` in `CaseEvent` is set by
`default_factory=_now_utc`, satisfying CM-02-009's trusted-timestamp
requirement automatically. The node never copies a timestamp from the
incoming activity.

**866 tests pass.**
