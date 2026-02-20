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

### Current Implementation (`vultron/as_vocab/objects/vulnerability_case.py`)

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
`vultron/as_vocab/objects/case_status.py`:

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

## RM and EM State Machines (Cross-Reference)

Case State (CS) is one of three interacting state machines:

- **RM (Report Management)**: Per-participant; tracks `RECEIVED → VALID →
  INVALID → ACCEPTED → DEFERRED → CLOSED` lifecycle. Tracked in
  `CaseParticipant.participant_status[].rm_state`.
- **EM (Embargo Management)**: Shared across case participants; tracks
  `NONE → PROPOSED → ACCEPTED → ACTIVE → REVISE → TERMINATED`. Tracked in
  `CaseStatus`.
- **CS (Case State)**: The 6-dimensional VFD/PXA hypercube described above.

See `docs/topics/process_models/rm/`, `docs/topics/process_models/em/`, and
`docs/topics/process_models/cs/` for process model documentation. See
`docs/reference/formal_protocol/` for formal state machine definitions with
transition rules.
