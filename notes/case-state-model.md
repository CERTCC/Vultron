# Case State Model Notes

## The Six-Dimensional Case State Model

The CVD case state model tracks six binary dimensions, each representing
whether a key event has occurred:

| Symbol | Meaning |
|--------|---------|
| `V/v`  | Vendor is aware (`V`) or unaware (`v`) |
| `F/f`  | Fix is ready (`F`) or not ready (`f`) |
| `D/d`  | Fix is deployed (`D`) or not deployed (`d`) |
| `P/p`  | Public is aware (`P`) or unaware (`p`) |
| `X/x`  | Exploit is public (`X`) or not public (`x`) |
| `A/a`  | Attacks have been observed (`A`) or not (`a`) |

The state space forms a 2^6 = 64-node hypercube. Valid transitions move from
lowercase to uppercase (events cannot be undone). This model is the
authoritative definition of the "Case State" (CS) dimension in the
RM/EM/CS state machine triad.

**Implementation**: `vultron/case_states/states.py` — enums `VendorAwareness`,
`FixReadiness`, `FixDeployment`, `PublicAwareness`, `ExploitPublication`,
`AttackObservation`, plus `VFDstate` and `PXAstate` named tuples.

**Reference paper**: [A State-Based Model for Multi-Party Coordinated
Vulnerability Disclosure](https://doi.org/10.1184/R1/16416771), CMU/SEI-2021-SR-021.

---

## Hypercube Graph Implementation

`vultron/case_states/hypercube.py` implements the `CVDmodel` class, which:

- Builds the 64-state DAG (directed acyclic graph) of all possible
  transitions using NetworkX.
- Implements random walks through the state space for simulation.
- Provides scoring functions to measure the "quality" of a CVD case history.
- Computes statistics over ensembles of histories.

The `CVDmodel` can be used to:

1. Generate the Hasse diagram of case states.
2. Compute all valid histories (orderings of V, F, D, P, X, A events).
3. Score a specific history against desirable orderings.
4. Benchmark a case against random walk baselines.

**Dependencies**: `networkx`, `numpy`, `pandas`.

---

## Potential Actions per Case State

`vultron/case_states/patterns/potential_actions.py` maps 6-character state
patterns (e.g., `"...P.."`, `"VfdpX."`) to `Actions` enum values — things a
participant COULD do when the case is in a given state.

The patterns use regex-like matching where `.` matches either letter of a
dimension. For example:

- `"...P.."` → public is aware → recommend terminating embargo, publishing vul
- `"....X."` → exploit is public → publish detection, monitor refinement
- `".....A"` → attacks observed → publish detection, monitor additional attacks

**Important**: These are menus of **possible** actions, not required actions.
Actual decisions are left to participant policy. This makes the pattern table
useful for:

- Future UI design (show actionable suggestions given current state)
- Future agent design (understand what actions are available)
- Protocol documentation (explain why transitions matter)

The corresponding documentation is in `docs/reference/case_states/*.md` — one
file per case state, each listing available actions and context.

---

## Case Object: Documentation vs. Implementation Gap

### Original Design (`docs/howto/case_object.md`)

The how-to doc describes a UML class diagram for a `Case` object with:

- `em_state: EMStateEnum` (embargo management state)
- `pxa_state: PXAStateEnum` (public/exploit/attack state)
- `Participant` with `rm_state: RMStateEnum` and `vfd_state: VFDStateEnum`
- `VendorParticipant` and `DeployerParticipant` subclasses
- `Message`, `LogEvent`, `Report` associations

This design was written before the ActivityStreams vocabulary was adopted.

### Current Implementation (`vultron/wire/as2/vocab/objects/vulnerability_case.py`)

The `VulnerabilityCase` class is a Pydantic model inheriting from
`VultronObject` (which inherits from the ActivityStreams `as_Object`). It
incorporates:

- Links to `CaseParticipant` objects (via `CaseParticipantRef`)
- Links to `CaseStatus` objects (via `CaseStatusRef`)
- Links to `EmbargoEvent` objects (via `EmbargoEventRef`)
- Links to `VulnerabilityReport` objects
- Links to `as_Activity` history

The VFD/PXA state tracking is embedded in `CaseStatus` and `CaseParticipant`
objects, not directly on the case. This reflects the ActivityStreams-first
design.

**Documentation debt**: `docs/howto/case_object.md` needs updating to reflect
the ActivityStreams-based implementation. Not high priority, but should be
addressed before the prototype is considered stable. When updating, preserve
the UML diagram concept while replacing the class names with their
ActivityStreams equivalents.

---

## Measuring CVD Process Quality

Based on the research paper [*A State-Based Model for Multi-Party CVD*](
https://www.sei.cmu.edu/documents/1952/2021_003_001_737890.pdf), the
`hypercube.py` module implements a framework for measuring the quality of a
CVD process by analyzing the order in which case state events occur.

Documentation in `docs/topics/measuring_cvd/` covers:

- `benchmarking.md` / `benchmarking_mpcvd.md` — how to compare a case history against baselines
- `desirable_histories.md` — which event orderings are considered "good"
- `discriminating_skill_and_luck.md` — statistical methods for separating skill from chance
- `possible_histories.md` — enumeration of all valid event sequences
- `random_walk.md` — using random walks as a null hypothesis baseline
- `reasoning_over_histories.md` — how to draw conclusions from history analysis

**Future application**: Applying these scoring techniques to `VulnerabilityCase`
objects and their event history logs would provide quantitative quality metrics
for the CVD process. This is not high priority for the prototype but would be
a valuable analytical capability.

**Prerequisite**: The `VulnerabilityCase` object's activity/event history
needs to be in a format that `hypercube.py` can consume. This likely requires
a translation layer from ActivityStreams history to the `(V, F, D, P, X, A)`
event sequence format expected by `CVDmodel`.

---

## Participant-Specific vs. Participant-Agnostic States

This distinction is **vitally important** for implementation correctness. Mixing
up which states belong to a single participant versus which states are shared
across all participants in a case leads to incorrect modeling and protocol
behavior.

### The Split

| State dimension | Participant-Specific or Agnostic? | Where tracked |
|-----------------|----------------------------------|---------------|
| RM state | **Participant-specific** | `ParticipantStatus.rm_state` |
| VFD (Vendor Fix Deployment) path | **Participant-specific** (only for Vendors/Deployers) | `ParticipantStatus.vfd_state` |
| EM (Embargo Management) state | **Participant-agnostic** (global per case) | `CaseStatus.em_state` |
| PXA (Public/Exploit/Attack) sub-state | **Participant-agnostic** (global per case) | `CaseStatus.pxa_state` |

In the Mermaid diagram from `docs/topics/process_models/model_interactions/index.md`:

```text
Participant-Agnostic: EM ↔ CS_pxa
Participant-Specific: RM ↔ CS_vfd
```

### Implementation: CaseStatus vs. ParticipantStatus

The canonical Python implementation is in
`vultron/wire/as2/vocab/objects/case_status.py`:

**`CaseStatus`** — participant-agnostic, one per case:

- `em_state: EM` — Embargo management state (default `EM.NO_EMBARGO`)
- `pxa_state: CS_pxa` — Public/exploit/attack sub-state (default `CS_pxa.pxa`)
- `context` — references the `VulnerabilityCase` this status belongs to

**`ParticipantStatus`** — participant-specific, one per (actor × case) pair:

- `rm_state: RM` — Report management state (default `RM.START`)
- `vfd_state: CS_vfd` — Vendor fix path sub-state (default `CS_vfd.vfd`)
- `actor` — references the participant Actor
- `context` — references the `VulnerabilityCase`
- `case_engagement: bool` — whether participant is engaged
- `embargo_adherence: bool` — whether participant respects the embargo
- `tracking_id: str | None` — participant's local tracking ID for the case
- `case_status: CaseStatus | None` — optionally embeds the shared case status

Note that `ParticipantStatus` MAY embed a `CaseStatus` for convenience when
presenting the full participant state as a triple `(rm_state, vfd_state,
case_status)`, corresponding to the formal protocol's participant state tuple
`(q^rm, q^em, q^cs)`.

### Role-Specific VFD Access

Not all participants have a VFD state:

- **Vendors**: Have `vfd_state` in `{Vfd, VFd, VFD}` (plus `VFD` only if they
  also deploy). They enter at `Vfd` (vendor aware) by definition.
- **Non-Vendor Deployers**: Have `vfd_state` only for the `d → D` transition.
- **Finders, Reporters, Coordinators**: Do NOT have VFD state. Use the null
  element `∅` (represented as `CS_vfd.vfd` but semantically "not applicable"
  for non-vendors — see `vultron/case_states/states.py`).

### Consequence for Handler Implementation

When handlers process incoming Activities:

- **RM state transitions** (e.g., `engage_case`, `defer_case`):
  Update `ParticipantStatus.rm_state` for the **sending actor's**
  `CaseParticipant`.
- **VFD transitions** (e.g., a vendor signaling fix readiness):
  Update `ParticipantStatus.vfd_state` for the **sending actor's**
  `CaseParticipant`.
- **EM transitions** (e.g., `accept_embargo`):
  Update `CaseStatus.em_state` — this is **shared** and affects all
  participants.
- **PXA transitions** (e.g., public disclosure, exploit publication):
  Update `CaseStatus.pxa_state` — this is **shared** state of the world.

Getting this wrong — e.g., updating `CaseStatus.em_state` with a
participant-specific value, or forgetting to scope RM updates to the correct
participant — would produce incorrect case state representations.

### OPP-06 — Future VFD/PXA transition handling

When vendor-fix or public/exploit/attack transitions are implemented beyond
object creation, reuse the authoritative VFD/PXA transition definitions rather
than encoding bespoke conditionals in individual use cases or BT nodes. That
keeps participant-specific VFD logic and shared PXA logic aligned with the
formal state model and ensures future persistence guards stay consistent across
code paths.

See `notes/state-machine-findings.md` OPP-06 and
`specs/case-management.md` `CM-04-005`.

### Key Reference Documents

The following documents explain this distinction in depth and MUST be
consulted when implementing state-related handlers or BT nodes:

- `docs/topics/process_models/model_interactions/index.md` — canonical
  explanation of the participant-agnostic vs. participant-specific split
- `docs/howto/activitypub/objects.md` — how objects are structured in the
  ActivityStreams vocabulary
- `docs/howto/case_object.md` — case object design (note: predates
  ActivityStreams; see "Documentation vs. Implementation Gap" section above)
- `docs/topics/behavior_logic/msg_cs_bt.md` — behavior tree logic for CS
  message handling
- `docs/topics/process_models/cs/index.md` — CS model overview
- `docs/topics/process_models/cs/model_definition.md` — formal CS model
  definition
- `docs/reference/formal_protocol/states.md` — formal state space for each
  participant role (Vendor, Deployer, Finder/Reporter, Coordinator, Other)
- `docs/reference/formal_protocol/conclusion.md` — protocol design conclusions

---

## CaseStatus and ParticipantStatus as Append-Only History

The `case_status` field on `VulnerabilityCase` is an **append-only list** of
`CaseStatus` objects representing the full history of case status changes. Key
rules for correct handling:

- The **current** case status is the `CaseStatus` with the **latest `updated`
  timestamp**. Sort by timestamp to determine the current status; do not assume
  list order.
- Items may arrive out of order (e.g., delayed network messages), so timestamp
  sorting is always required.
- It is an error for a status update to carry a timestamp in the future.
- Use `VulnerabilityCase.current_status` (a property that returns the
  most-recent `CaseStatus` sorted by `updated` timestamp) when you need the
  active status; avoid direct list indexing.

The same pattern applies to `CaseParticipant.participant_status`: each
`ParticipantStatus` is an append-only history entry, and the current
participant status is the entry with the latest timestamp.

**CaseActor trusted timestamp principle** (see `CM-02-009`): The CaseActor
MUST apply its own timestamp to every state-changing event it receives —
not just embargo acceptances, but also participant joins, notes, status
updates, and any other activity that modifies canonical case state.
Using participant-supplied timestamps would allow different copies of a
case (held by different actors) to disagree on event ordering, undermining
auditability and the single-source-of-truth guarantee provided by CM-02-002.

**Implementation note**: `set_embargo()` and similar mutation helpers on
`VulnerabilityCase` MUST operate on `current_status`, not on the raw list.
Directly setting `.em_state` on the `case_status` list attribute is a bug
(lists do not support arbitrary attribute assignment).

**Trusted timestamp implementation note**: When the spec says the CaseActor
must timestamp state-changing events on receipt, this does NOT mean modifying
the `updated_at` field on the receiving or participating object. It means the
CaseActor records the event to an **append-only event log on the case**
(see "CaseEvent Model" below). The distinction matters: modifying an existing
object's timestamp would break the append-only history invariant and allow
event-ordering disagreements across actor copies.

**Cross-reference**: `vultron/wire/as2/vocab/objects/vulnerability_case.py`
(the `current_status` property),
`vultron/wire/as2/vocab/objects/case_status.py`.

---

## CM-03-006 Rename: `case_status` → `case_statuses`

Spec `CM-03-006` requires renaming `VulnerabilityCase.case_status` (a list
field with a misleading singular name) to `case_statuses`. The same rename
applies to `CaseParticipant.participant_status` → `participant_statuses`.

**Before starting the rename**, quantify scope:

```bash
grep -rn "\.case_status" vultron/ test/
grep -rn "\.participant_status" vultron/ test/
```

As of the last review, `handlers.py` alone has approximately 20 call sites.
Total scope across `core/behaviors/` and tests makes this a high-breakage
change.

**Recommended approach**: Do both renames (`case_statuses` and
`participant_statuses`) in a single PR to keep the diff localized and avoid
a partial-rename state that is harder to reason about.

**Cross-reference**: `AGENTS.md` "case_status Field Is a List (Rename
Pending)"; `specs/case-management.md` CM-03-006.

---

## CaseEvent Model for Trusted Timestamps (SC-PRE-1) ✅ Implemented

The `CaseEvent` model is implemented in
`vultron/wire/as2/vocab/objects/case_event.py`. `VulnerabilityCase` has an
`events: list[CaseEvent]` field and a `record_event(object_id, event_type)`
append-only helper. Tests in `test/wire/as2/vocab/test_case_event.py`
cover creation, serialization, and round-trip through TinyDB.

The design is described below for reference. The key invariant is
**`received_at` is always set by the server clock** via `now_utc()`
inside `record_event()` — callers MUST NOT pass `received_at` from
an incoming activity payload.

### CaseEvent Model Fields

- `object_id: str` — ID of the object being acted upon
- `event_type: str` — short descriptor (e.g., `"embargo_accepted"`,
  `"participant_joined"`, `"note_added"`, `"status_updated"`)
- `received_at: datetime` — server-generated TZ-aware UTC timestamp;
  defaults to `now_utc()` (microseconds stripped); serializes to
  ISO 8601 UTC string; `field_validator` accepts ISO 8601 strings
  on deserialization

### How to record an event

```python
case.record_event(object_id=embargo.as_id, event_type="embargo_accepted")
```

Do NOT pass `received_at` — let it default to `now_utc()`.

### Remaining work

SC-PRE-1 provides the model and helper. Handlers have not yet been
updated to call `record_event()` — that is tracked in SC-3.2.
Pre-case event backfill at case creation is tracked in TECHDEBT-10.

**Design Decision**: `received_at` is set by the handler (server clock),
never copied from the incoming activity's own timestamp fields. This is
the invariant that makes the CaseActor the sole trusted source of event
ordering within a case.

**Cross-reference**: `specs/case-management.md` CM-02-009, CM-10-002;
`plan/IMPLEMENTATION_PLAN.md` SC-PRE-1, TECHDEBT-10.

---

## Actor-to-Participant Index (SC-PRE-2)

Several handlers (including `accept_invite_to_embargo_on_case` and
`accept_invite_actor_to_case`) need to resolve an **Actor ID → CaseParticipant
ID** mapping within the context of a specific case. Without a fast lookup,
handlers must iterate all participants, which is fragile and error-prone.

### Design

Add `actor_participant_index: dict[str, str] = Field(default_factory=dict)`
to `VulnerabilityCase`:

- Key: `actor_id` string (full URI)
- Value: `participant_id` string (full URI of the `CaseParticipant` object)
- This field is a **derived index** — it MUST be excluded from
  ActivityStreams serialization (use `exclude=True` in the field definition
  or an equivalent Pydantic v2 pattern) because it is not protocol data

### Participant Management Methods

Add two methods to `VulnerabilityCase`:

- `add_participant(participant: CaseParticipant)`: appends
  `participant.as_id` to `case_participants`; records
  `actor_id → participant.as_id` in `actor_participant_index`; raises
  (or no-ops) if the actor is already registered — choose one behavior
  and enforce it consistently
- `remove_participant(participant_id: str)`: removes from
  `case_participants`; removes the corresponding actor key from
  `actor_participant_index`

### Handler Updates

All handlers that currently write to `case.case_participants` directly MUST
be updated to call `case.add_participant()` or `case.remove_participant()`:

- `accept_invite_actor_to_case` (actor handler)
- `create_case` BT node `CreateInitialVendorParticipant`
  (`behaviors/case/nodes.py`)
- `remove_case_participant_from_case` (participant handler)
- Any other handler that appends or removes participants

**Invariant**: The index MUST always reflect the contents of
`case_participants`. Out-of-sync states MUST NOT be possible via normal
code paths.

**Open Question**: (blocks SC-PRE-2) Whether to raise or silently no-op on
duplicate `add_participant()` calls. Recommend raise for correctness;
handlers should guard with an existence check before calling
`add_participant()` to keep idempotency logic explicit.

**Cross-reference**: `specs/case-management.md` CM-10-002, CM-10-001;
`plan/IMPLEMENTATION_PLAN.md` SC-PRE-2; `AGENTS.md` "Cases should have
participant-to-actor and vice versa indexes".

---

## RM and EM State Machines (Cross-Reference)

Case State (CS) is one of three interacting state machines:

- **RM (Report Management)**: Per-participant; tracks `RECEIVED → VALID →
  INVALID → ACCEPTED → DEFERRED → CLOSED` lifecycle. Tracked in
  `CaseParticipant.participant_status[].rm_state`.
- **EM (Embargo Management)**: Shared across case participants; tracks
  `NO_EMBARGO → PROPOSED → ACTIVE → REVISE → EXITED`. Tracked in
  `CaseStatus`. Note: `Accept` is an **activity type** that triggers the
  `PROPOSED → ACTIVE` (or `REVISE → ACTIVE`) transition — it is not itself a
  state. See `vultron/bt/embargo_management/states.py`.
- **CS (Case State)**: The 6-dimensional VFD/PXA hypercube described above.

See `docs/topics/process_models/rm/`, `docs/topics/process_models/em/`, and
`docs/topics/process_models/cs/` for process model documentation. See
`docs/reference/formal_protocol/` for formal state machine definitions with
transition rules.

---

## Report as Proto-Case: Finder Participant Lifecycle

> **Status**: The FINDER-PART-1 approach described in the original version
> of this section has been **superseded** by ADR-0015 (Create
> VulnerabilityCase at Report Receipt). The new lifecycle is documented
> below.

The lifecycle of CVD work begins with a *report*, and the Vultron model
reflects this by creating a `VulnerabilityCase` immediately when an
`Offer(Report)` is received. A useful analogy is the caterpillar/butterfly
metamorphosis:

- **Caterpillar stage** = case object in RM.RECEIVED or RM.INVALID
  (the case exists but has not yet been validated; participants are
  active but the vendor has not yet committed to the issue)
- **Butterfly stage** = case object in RM.VALID, RM.ACCEPTED, or
  RM.DEFERRED (the case is validated and actionable)
- **Terminal** = RM.CLOSED (regardless of path)

Work genuinely happens in both stages, and participants exist in both.

### Redefined "Proto-Case"

A **proto-case** is a `VulnerabilityCase` object that is in the caterpillar
stage — the case object exists (and has been created at report receipt),
but the receiver has not yet validated the report. RM states RM.RECEIVED
and RM.INVALID are proto-case stages.

This is a redefinition from the earlier concept where "proto-case" meant
the state *before* a case object existed. Under ADR-0015, a case object
always exists from the moment a report is received, so the pre-case-object
era is eliminated.

### Implemented Lifecycle (per ADR-0015)

1. Reporter submits `Offer(Report)` → `SubmitReportReceivedUseCase`
   invokes the `receive_report_case_tree` BT, which:
   - Creates a `VulnerabilityCase` with `vulnerability_reports` linking
     to the `VulnerabilityReport` ID
   - Creates a `VultronParticipant` for the reporter with
     `rm_state=RM.ACCEPTED` (they created and submitted the report)
   - Creates a `VultronParticipant` for the receiver with
     `rm_state=RM.RECEIVED`
   - Initializes a default embargo (SHOULD; MUST before RM.VALID)
   - Queues a `Create(Case)` activity to notify the reporter
2. Receiver runs the `ValidateReport` BT:
   - Evaluates report credibility and validity
   - Transitions RM to RM.VALID (or RM.INVALID if rejected)
   - Verifies that an embargo exists (`EnsureEmbargoExists` guard)
   - Does **not** create a case (the case already exists from step 1)
3. All subsequent report-centric activities (invalidate, close, validate)
   dereference the `report_id → case_id` and delegate to case-level use
   cases.

**No retroactive context migration is needed.** The `VultronParticipant`
records are created with `context` pointing to the `VulnerabilityCase` ID
from the start.

**See also**: `docs/adr/0015-create-case-at-report-receipt.md`;
`specs/case-management.md` CM-12; `notes/protocol-event-cascades.md`

---

## Pre-Case Event Backfill on Case Creation

> **Note**: Under ADR-0015, the case is created at report receipt, so
> backfill is minimal. The `Offer(Report)` activity IS the case-creation
> trigger; participant creation happens atomically in the same BT.

When a new case is created via `receive_report_case_tree`, the following
events are recorded in the case log as part of that BT's execution:

- Case creation itself
- Initial participant creation (reporter and receiver)
- Default embargo initialization (if applied)
- `Create(Case)` notification queued to outbox

Events that predate the case object cannot exist in the new model (the
case is created at the first opportunity). If pre-case events were recorded
via a separate mechanism (e.g., a flat `ReportStatus`), those MAY be
backfilled into the case log at case creation time.

**See**: `specs/case-management.md` CM-12; `notes/activitystreams-semantics.md`
for the case activity log constraints.

---

## Multi-Vendor Case State Action Rules

When implementing the case state action rules (see `specs/agentic-readiness.md`
and `specs/case-management.md`), the rules must distinguish two perspectives:

1. **Participant-specific rules**: Evaluated against a single participant's
   RM/VFD state (applies to each vendor independently).
2. **Case-level rules (CaseActor/Case Owner perspective)**: Must aggregate
   across all relevant participants. For example, an `EMBARGO_END` trigger
   MUST NOT be based on a single vendor reaching `FIX_READY` when other
   vendors have not.

**Design decision**: (open) Threshold heuristics for multi-vendor rules
(e.g., "all engaged vendors in FIX_READY", "≥X% of vendors with FIX_READY")
need to be formally specified. A cognitive agent delegating the judgment
call is an alternative to fixed heuristics.

**See**: `specs/agentic-readiness.md` and `specs/case-management.md` for
the CVD action rules; `notes/bt-fuzzer-nodes.md` for related external
touchpoints.
