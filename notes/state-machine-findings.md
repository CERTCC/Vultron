# State Machine Refactoring Findings

**Status:** Analysis complete  
**Scope:** `vultron.core` and adjacent wire-layer interactions  
**Machines analysed:** RM, EM, VFD (CS), PXA (CS) from `vultron.core.states`

---

## 1. Background

`vultron.core.states` now contains declarative `transitions`-library state
machines for every protocol state axis:

| Module | Enum(s) | Factory function | Transitions |
|--------|---------|-----------------|-------------|
| `rm.py` | `RM` | `create_rm_machine()` | 11 |
| `em.py` | `EM` | `create_em_machine()` | 10 |
| `cs.py` | `CS_vfd` | `create_vfd_machine()` | 3 |
| `cs.py` | `CS_pxa` | `create_pxa_machine()` | 12 |

**Key finding: none of the `create_*_machine()` functions are called anywhere
in `vultron.core` to actually drive state changes.** The machines exist as
documentation and graph sources (e.g., `mermaid_machine()`), but all runtime
state changes are implemented imperatively via direct enum assignment.

---

## 2. Where State Enums Are Used

### 2.1 Domain model field types (read at init, stored in DataLayer)

| File | Field | Enum |
|------|-------|------|
| `core/models/case_status.py` | `VultronCaseStatus.em_state` | `EM` |
| `core/models/case_status.py` | `VultronCaseStatus.pxa_state` | `CS_pxa` |
| `core/models/participant_status.py` | `VultronParticipantStatus.rm_state` | `RM` |
| `core/models/participant_status.py` | `VultronParticipantStatus.vfd_state` | `CS_vfd` |
| `core/models/status.py` | `ReportStatus.status` | `RM` |

### 2.2 In-memory STATUS layer

`vultron.core.models.status` maintains a process-local dict (`STATUS`) for
tracking transient RM state of `VulnerabilityReport` objects during validation
processing. This layer is **not persisted** to the DataLayer.

### 2.3 Persisted participant/case state

`VultronParticipantStatus` (RM, VFD) and `VultronCaseStatus` (EM, PXA) records
are stored in the DataLayer as append-only history lists on
`CaseParticipant.participant_statuses` and `VulnerabilityCase.case_statuses`.
The most-recent entry is the current state.

---

## 3. Hand-Rolled State Transition Inventory

### 3.1 EM Transitions

All EM transitions are direct assignments to `case.current_status.em_state`.

| File | Use Case | Source state(s) | Dest state | Guard |
|------|----------|----------------|-----------|-------|
| `triggers/embargo.py` | `SvcProposeEmbargoUseCase` | `EM.NO_EMBARGO` | `EM.PROPOSED` | checked via `if em_state == EM.NO_EMBARGO` |
| `triggers/embargo.py` | `SvcProposeEmbargoUseCase` | `EM.ACTIVE` | `EM.REVISE` | checked via `elif em_state == EM.ACTIVE` |
| `triggers/embargo.py` | `SvcProposeEmbargoUseCase` | `EM.PROPOSED`, `EM.REVISE` | (no change) | falls through to `else` |
| `triggers/embargo.py` | `SvcTerminateEmbargoUseCase` | `EM.ACTIVE` | `EM.EXITED` | none (guard is `case.active_embargo is None`) |
| `use_cases/embargo.py` | `RemoveEmbargoEventFromCaseReceivedUseCase` | any | `EM.NONE` | none |
| `wire/.../vulnerability_case.py` | `VulnerabilityCase.set_embargo()` | (any) | `EM.ACTIVE` | none — called from `SvcEvaluateEmbargoUseCase` and `AcceptInviteToEmbargoOnCaseReceivedUseCase` |

> **Architecture note:** The `PROPOSED → ACTIVE` transition is triggered by
> `case.set_embargo()` in the **wire layer**
> (`vultron.wire.as2.vocab.objects.vulnerability_case`), not in `vultron.core`.
> This is an architecture boundary violation: core use-case
> `SvcEvaluateEmbargoUseCase` delegates the EM state change to a wire-layer
> method.

### 3.2 RM Transitions — in-memory STATUS layer

These set RM state on a `VulnerabilityReport` via `set_status(ReportStatus(...))`.
The current source state is **not checked** before writing.

| File | Use Case / Node | Dest state |
|------|----------------|-----------|
| `use_cases/report.py` | `InvalidateReportReceivedUseCase` | `RM.INVALID` |
| `use_cases/report.py` | `CloseReportReceivedUseCase` | `RM.CLOSED` |
| `triggers/report.py` | `SvcInvalidateReportUseCase` | `RM.INVALID` |
| `triggers/report.py` | `SvcRejectReportUseCase` | `RM.CLOSED` |
| `triggers/report.py` | `SvcCloseReportUseCase` | `RM.CLOSED` (with guard: `RM.CLOSED` → raises conflict) |
| `behaviors/report/nodes.py` | `TransitionReportToValid` (BT node) | `RM.VALID` |
| `behaviors/report/nodes.py` | `TransitionReportToInvalid` (BT node) | `RM.INVALID` |

### 3.3 RM Transitions — persisted participant status

These append a new `VultronParticipantStatus` record with the target RM state.
The current RM state is checked for idempotency only.

| File | Use Case / Node | Dest state |
|------|----------------|-----------|
| `triggers/case.py` | `SvcEngageCaseUseCase` | `RM.ACCEPTED` |
| `triggers/case.py` | `SvcDeferCaseUseCase` | `RM.DEFERRED` |
| `behaviors/report/nodes.py` | `TransitionParticipantRMtoAccepted` (BT node) | `RM.ACCEPTED` |
| `behaviors/report/nodes.py` | `TransitionParticipantRMtoDeferred` (BT node) | `RM.DEFERRED` |

### 3.4 CS (VFD / PXA) Transitions

No code in `vultron.core` actively transitions `vfd_state` or `pxa_state`
after initial record creation. Both fields are set to their initial default
values (`CS_vfd.vfd`, `CS_pxa.pxa`) when a `VultronParticipantStatus` or
`VultronCaseStatus` is created. The machines for VFD and PXA are defined but
have no callers.

---

## 4. Machine Integration — Technical Constraint

The `transitions` library manages a `.state` attribute on a bound model
object. The Vultron domain models use **named fields** (`em_state`, `rm_state`,
etc.) rather than a generic `.state` attribute.

`transitions.Machine` supports a `model_attribute` parameter that lets you
specify which attribute it manages. This means integration is technically
straightforward:

```python
# Example: bind the EM machine to a VultronCaseStatus object
machine = create_em_machine()
machine.model_attribute = "em_state"  # point machine at the right field
machine.add_model(case_status)        # bind model
case_status.propose()                 # trigger: validates + transitions
```

Alternatively, the machine can be used as a **stateless validator** (no model
bound) by calling `machine.get_transitions(trigger, source=current_state)` to
check validity before manually assigning the new state.

---

## 5. Identified Problems (No Transition Enforcement)

### P-01: Invalid EM terminal state reached via `RemoveEmbargoEventFromCaseReceivedUseCase`

`RemoveEmbargoEventFromCaseReceivedUseCase` sets `em_state = EM.NONE`
unconditionally. No `EXITED → NONE` or `ACTIVE → NONE` transition exists in
the EM machine. This produces a state the machine considers unreachable from
`EXITED`.

### P-02: EM `PROPOSED → ACTIVE` transition lives in the wire layer

`VulnerabilityCase.set_embargo()` (in `vultron.wire`) directly assigns
`em_state = EM.ACTIVE`. Core use cases that call `case.set_embargo()` rely on
the wire layer to do the state transition, violating the hexagonal architecture
boundary (see `specs/architecture.md` ARCH-09).

### P-03: No guard on `SvcTerminateEmbargoUseCase`

The terminate use case checks `case.active_embargo is None` but does not
check the EM state. It is possible to call `case.current_status.em_state =
EM.EXITED` when the EM state is `EM.PROPOSED` or `EM.NONE`, which the machine
does not allow.

### P-04: RM transitions in STATUS layer have no source-state guard

All calls to `set_status(ReportStatus(status=RM.X))` write the target state
unconditionally. No validation checks whether the current RM state permits
the requested transition (e.g., `CLOSED → VALID` is impossible per the machine
but would succeed in the current code).

### P-05: Duplicate RM transition logic in BT nodes and use cases

`TransitionParticipantRMtoAccepted` (BT node) and `SvcEngageCaseUseCase`
(trigger use case) both implement the logic to append a new
`VultronParticipantStatus` with `rm_state=RM.ACCEPTED`. The underlying helper
function differs: BT nodes use `_find_and_update_participant_rm()` in
`behaviors/report/nodes.py` while the trigger use case calls
`update_participant_rm_state()` in `triggers/_helpers.py`. These are near-
duplicate implementations of the same operation.

### P-06: `START → RECEIVED` transition never explicitly triggered on report receipt

`RM.START` is the ground state for a new `VultronParticipantStatus` record
(`rm_state: RM = RM.START`). The `transitions` RM machine models a single
`RECEIVE` trigger (`START → RECEIVED`) that moves the participant out of the
unobserved ground state when a report first arrives.

In the current `vultron.core` code, this transition is **never explicitly
triggered**:

- `CreateReportReceivedUseCase.execute()` — stores the `VulnerabilityReport`
  in the DataLayer but sets no RM state.
- `SubmitReportReceivedUseCase.execute()` — same: stores the report, no RM
  state change.
- `AckReportReceivedUseCase.execute()` — stores the activity, no RM state
  change.
- The in-memory `ReportStatus` model defaults its `status` field to
  `RM.RECEIVED`, but no code path actually calls
  `set_status(ReportStatus(...))` in response to receiving a report — only in
  response to validate/invalidate/close actions.

The old BT-based implementation (`vultron/bt/report_management/transitions.py`)
defines `_to_R = RmTransition(start_states=[RM.START], end_state=RM.RECEIVED)`
explicitly, showing that the `START → RECEIVED` step was always intended to be
a real, observable transition.

**Effect:** RM state effectively starts at `RM.RECEIVED` by convention (the
`ReportStatus` default) but the formal `START → RECEIVED` step is missing,
meaning the RM state history for a participant never contains the initial
`RECEIVED` entry. This also means any guard that checks "is the current RM
state RECEIVED?" may fail immediately after report receipt if it reads from
`VultronParticipantStatus` instead of the STATUS layer.

### P-07: RM lifecycle split across two unreconciled tracking mechanisms

The RM state machine spans **two overlapping lifecycles** with a pivot at
`RM.VALID`:

**Report lifecycle (pre-case):**
`START → RECEIVED → INVALID → VALID` (or `RECEIVED → VALID` directly), and
`CLOSED` reachable from `INVALID`.

**Case lifecycle (post-VALID):**
Once a report is determined VALID, a case is created and the actor's engagement
with that case is tracked: `VALID → ACCEPTED / DEFERRED → CLOSED`.

The protocol assumption is that `RM.VALID` is the pivot: when a report reaches
`VALID`, a `VulnerabilityCase` is created with the report attached, and the RM
state conceptually transfers from the report to the case-participant record.

**Current implementation split:**

| Phase | Tracking mechanism | Module |
|-------|--------------------|--------|
| START → RECEIVED → INVALID/VALID | In-memory `STATUS` dict, `ReportStatus.status: RM` | `core/models/status.py` |
| VALID → ACCEPTED/DEFERRED → CLOSED | Persisted `VultronParticipantStatus.rm_state` (append-only) | `core/models/participant_status.py` |

This split was an early implementation shortcut ("get it working") and was
never revised. Consequences:
- No single query can retrieve the complete RM history for an actor-report pair.
- The pivot transition (`VALID` → case creation → participant status seeded with
  `VALID`) is implicit and scattered.
- The STATUS layer is transient (in-memory, process-local, not persisted), so
  RM history before the case is created is lost on restart.
- Guards on the case-lifecycle half cannot see whether the report was actually
  `VALID` before `ACCEPTED`/`DEFERRED` was set.

**What should happen at the pivot:**
When a report transitions to `RM.VALID` and a case is created, the local
actor's `VultronParticipantStatus` for that case should be **seeded with
`rm_state=RM.VALID`** (carrying the current RM state forward), not with
`RM.START`. Subsequent `ACCEPTED`/`DEFERRED` transitions then have a correct
historical starting point.


### OPP-01 — EM machine in `SvcProposeEmbargoUseCase` (HIGH)

**Current:** Manual `if/elif` chain checking `em_state` then directly assigning
the new state.

**Proposed:** Create an EM machine instance, bind to the `VultronCaseStatus`
object (using `model_attribute='em_state'`), then call `machine.propose()`.
The machine raises `transitions.core.MachineError` for invalid transitions,
centralising guard logic.

**Benefit:** Eliminates the manual `if/elif`; the machine enforces all valid
source states; new transitions (e.g., `REVISE → REVISE` idempotent re-proposal)
are automatically handled.

**Files:** `vultron/core/use_cases/triggers/embargo.py`

### OPP-02 — EM machine in `SvcTerminateEmbargoUseCase` (MEDIUM)

**Current:** Direct `case.current_status.em_state = EM.EXITED` with no state
guard.

**Proposed:** Use EM machine's `terminate()` trigger, which validates that the
source state is `EM.ACTIVE` or `EM.REVISE`.

**Files:** `vultron/core/use_cases/triggers/embargo.py`

### OPP-03 — Move `PROPOSED → ACTIVE` transition from wire layer to core (MEDIUM)

**Current:** `VulnerabilityCase.set_embargo()` in the wire layer assigns
`em_state = EM.ACTIVE`. Core use cases (`SvcEvaluateEmbargoUseCase`,
`AcceptInviteToEmbargoOnCaseReceivedUseCase`) rely on this side-effect.

**Proposed:** Remove `em_state = EM.ACTIVE` from `VulnerabilityCase.set_embargo()`
(wire layer). The core use cases should explicitly transition the EM state (via
machine or direct assignment) **before** calling `set_embargo()`. This
eliminates the architecture boundary violation.

**Files:** `vultron/wire/as2/vocab/objects/vulnerability_case.py`,
`vultron/core/use_cases/triggers/embargo.py`,
`vultron/core/use_cases/embargo.py`

### OPP-04 — RM machine as guard for STATUS-layer transitions (MEDIUM)

**Current:** `set_status(ReportStatus(status=RM.X))` writes the target state
with no source-state validation.

**Proposed:** Before calling `set_status()`, query the current RM state from
the STATUS layer and use `create_rm_machine()` (or a pre-built lookup table
derived from the machine transitions) to verify the source → dest transition
is valid.

**Files:** `vultron/core/use_cases/report.py`,
`vultron/core/use_cases/triggers/report.py`,
`vultron/core/behaviors/report/nodes.py`

### OPP-05 — Consolidate duplicate participant RM update helpers (LOW-MEDIUM)

**Current:** Two near-duplicate helpers:
- `_find_and_update_participant_rm()` in `behaviors/report/nodes.py`
- `update_participant_rm_state()` in `use_cases/triggers/_helpers.py`

**Proposed:** Consolidate into a single shared helper in
`use_cases/triggers/_helpers.py` (or a new
`vultron/core/use_cases/_participant_helpers.py`). BT nodes can import from
there. Optionally add RM machine validation before appending the new status.

**Files:** `vultron/core/behaviors/report/nodes.py`,
`vultron/core/use_cases/triggers/_helpers.py`

### OPP-06 — VFD/PXA machine usage for future transitions (LOW)

**Current:** `create_vfd_machine()` and `create_pxa_machine()` exist but no
code in `vultron.core` transitions `vfd_state` or `pxa_state` after creation.

**When:** When vendor fix tracking or public/exploit/attack state update
functionality is added, use the existing machines to drive those transitions
rather than writing new hand-rolled logic.

**Files:** Future — `vultron/core/use_cases/` and/or `behaviors/`

### OPP-07 — Guard status-object appends at the model and use-case layer (HIGH)

**Context:** Both case statuses and participant statuses are append-only history
lists. Adding a new status entry is the primary mechanism for making state
transitions:

- `case.case_statuses.append(status_obj)` — changes the shared EM / PXA state
- `participant.participant_statuses.append(status_obj)` — changes a
  participant's RM / VFD state
- `CaseParticipant.append_rm_state()` (`wire/.../case_participant.py:140`) —
  convenience method wrapping the append

**Current:** None of these appends validate that the `em_state`, `rm_state`,
`pxa_state`, or `vfd_state` value on the new status object represents a valid
transition from the most recent existing status's value. Invalid sequences
(e.g., EM `NONE → EXITED`, RM `CLOSED → VALID`) can be persisted silently.

**Proposed:** Add transition-validity helpers to `vultron.core.states` (e.g.,
`is_valid_rm_transition(source, dest) -> bool` and
`is_valid_em_transition(source, dest) -> bool`) derived from the `transitions`
machine definitions. These helpers would be used as guards at two levels:

1. **`CaseParticipant.append_rm_state()`** (wire layer convenience method):
   look up the current RM state from the most-recent `ParticipantStatus`;
   raise `ValueError` (or a domain exception) if the transition is invalid.

2. **`AddCaseStatusToCaseReceivedUseCase.execute()`** and
   **`AddParticipantStatusToParticipantReceivedUseCase.execute()`** in
   `core/use_cases/status.py`: before appending, compare the incoming
   `em_state`/`rm_state` against the current state and reject invalid
   transitions with a `WARNING` log (or raise a domain exception so the
   caller can generate a `Reject` response).

3. **`_find_and_update_participant_rm()`** / **`update_participant_rm_state()`**
   in `core/use_cases/triggers/_helpers.py` and
   `core/behaviors/report/nodes.py`: add the same transition guard before
   calling `participant.participant_statuses.append(...)`.

**Benefit:** Prevents protocol violations from being silently committed to the
DataLayer, regardless of which code path triggers the append. The `transitions`
machine definitions become the single authoritative source of valid sequences.

**Files:**
- `vultron/core/states/rm.py` — add `is_valid_rm_transition()`
- `vultron/core/states/em.py` — add `is_valid_em_transition()`
- `vultron/core/states/cs.py` — add `is_valid_vfd_transition()`,
  `is_valid_pxa_transition()`
- `vultron/wire/as2/vocab/objects/case_participant.py` — guard
  `append_rm_state()`
- `vultron/core/use_cases/status.py` — guard both `AddCaseStatus` and
  `AddParticipantStatus` use cases
- `vultron/core/use_cases/triggers/_helpers.py` — guard
  `update_participant_rm_state()`
- `vultron/core/behaviors/report/nodes.py` — guard
  `_find_and_update_participant_rm()`

### OPP-08 — Explicitly trigger `START → RECEIVED` on report receipt (HIGH)

**Current:** `CreateReportReceivedUseCase` and `SubmitReportReceivedUseCase`
store the report in the DataLayer but do not set the receiving actor's RM state
to `RECEIVED`. The `RM.START → RM.RECEIVED` (RECEIVE trigger) transition is
never executed in `vultron.core`. See P-06.

**Proposed:** In `CreateReportReceivedUseCase.execute()` and
`SubmitReportReceivedUseCase.execute()`, after persisting the report, call
`set_status(ReportStatus(status=RM.RECEIVED, ...))` for the local actor. This
makes the ground-state transition explicit and ensures RM history is correct
from the first moment a report is observed.

The transition-validity guard from OPP-07 should also enforce that this is the
only valid first write to the STATUS layer for a report (source = `RM.START`
→ dest = `RM.RECEIVED`).

**Files:**
- `vultron/core/use_cases/report.py` —
  `CreateReportReceivedUseCase`, `SubmitReportReceivedUseCase`,
  `AckReportReceivedUseCase`

### OPP-09 — Reconcile the RM lifecycle split between STATUS layer and participant status (HIGH)

**Current:** RM state for the report-validation phase is tracked in the
transient in-memory STATUS layer (`ReportStatus`), while RM state for
case-engagement is tracked in persisted `VultronParticipantStatus` records.
The two are never linked, and the pivot transition (report becomes VALID → case
created → participant seeded with VALID state) is implicit and not enforced.
See P-07.

**Proposed design direction** (Option A preferred; requires ADR):

Option A — *Persist the full RM lifecycle in VultronParticipantStatus* (preferred):
When a report is first received, create an initial `VultronParticipantStatus`
with `rm_state=RM.RECEIVED` and persist it to the DataLayer (replacing the
transient STATUS layer for the pre-case phase). At the pivot (VALID, case
creation), append `rm_state=RM.VALID` to the participant's existing status
history. This gives a complete, queryable RM history in one place.

Option B — *Make the STATUS layer persistent*: Migrate `ReportStatus` tracking
from the in-memory dict to the DataLayer. This avoids changing the domain model
structure but requires adding a new persisted record type.

**Minimum step regardless of option:** When a case is created from a VALID
report, the actor's new `VultronParticipantStatus` should be initialised with
`rm_state=RM.VALID`, not `RM.START`. This can be done without the full
unification. See also OPP-08 (START→RECEIVED) which is a prerequisite in
spirit.

**Files:** This requires investigation across `core/use_cases/case.py`,
`core/behaviors/report/`, `wire/as2/vocab/objects/case_participant.py`, and
potentially a new ADR.

**TECHDEBT-10 connection (commit `e0d1553`):** TECHDEBT-10 added
`RecordCaseCreationEvents` to `vultron/core/behaviors/case/nodes.py` and
included it in `CreateCaseFlow`. That node runs after `PersistCase` and after
`CreateInitialVendorParticipant`, backfilling event log entries
(`"offer_received"`, `"case_created"`) using `case.record_event()`. The same
BT extension point — either a modification to `CreateInitialVendorParticipant`
or a new sibling node in `CreateCaseFlow` — is where we need to seed
`rm_state=RM.VALID` on the newly created participant. Review TECHDEBT-10's
implementation before implementing this opportunity to avoid duplication and
to follow the same pattern.

---

## 7. Summary Table

| ID | Area | Type | Value | Files |
|----|------|------|-------|-------|
| OPP-01 | EM propose | Refactor | HIGH | `triggers/embargo.py` |
| OPP-02 | EM terminate | Refactor | MEDIUM | `triggers/embargo.py` |
| OPP-03 | EM PROPOSED→ACTIVE in wire layer | Architecture fix | MEDIUM | `wire/.../vulnerability_case.py`, `core/use_cases/` |
| OPP-04 | RM STATUS-layer guards | Enhancement | MEDIUM | `use_cases/report.py`, `triggers/report.py`, `behaviors/report/nodes.py` |
| OPP-05 | Participant RM helper duplication | Refactor | LOW-MEDIUM | `behaviors/report/nodes.py`, `triggers/_helpers.py` |
| OPP-06 | VFD/PXA machines | Future use | LOW | new code |
| OPP-07 | Guard status-object appends at model/use-case layer | Enhancement | HIGH | `states/rm.py`, `states/em.py`, `states/cs.py`, `wire/.../case_participant.py`, `use_cases/status.py`, `use_cases/triggers/_helpers.py`, `behaviors/report/nodes.py` |
| OPP-08 | Explicit `START → RECEIVED` transition on report receipt | Enhancement | HIGH | `use_cases/report.py` |
| OPP-09 | Reconcile RM lifecycle split (STATUS layer vs participant status) | Architecture | HIGH | `use_cases/case.py`, `behaviors/report/`, `wire/.../case_participant.py` |
| P-01 | EM NONE via RemoveEmbargo | Bug | — | `use_cases/embargo.py` |
| P-02 | EM transition in wire layer | Architecture | — | `wire/.../vulnerability_case.py` |
| P-03 | SvcTerminate no guard | Bug | — | `triggers/embargo.py` |
| P-04 | STATUS layer no guard | Bug | — | `use_cases/report.py`, `triggers/report.py` |
| P-05 | Duplicate RM helpers | Debt | — | `behaviors/report/nodes.py`, `triggers/_helpers.py` |
| P-06 | `START → RECEIVED` never triggered | Gap | — | `use_cases/report.py` |
| P-07 | RM lifecycle split, unreconciled | Architecture debt | — | `core/models/status.py`, `core/models/participant_status.py` |

---

## 8. Spec Alignment Notes

- **CM-04-001 through CM-04-004** (`specs/case-management.md`): require that
  state transitions update the correct persisted fields. The machines make these
  constraints machine-checkable rather than relying on code review.
- **ARCH-09** (`specs/architecture.md`): core MUST NOT import from the wire
  layer. Problem P-02 / OPP-03 is a violation because the core use case relies
  on `VulnerabilityCase.set_embargo()` (wire layer) to change EM state.
- **AR-02-002** (`specs/agentic-readiness.md`): all valid states and transitions
  MUST be documented. The `transitions` machines satisfy this requirement once
  they are the authoritative runtime behaviour (not just documentation).
