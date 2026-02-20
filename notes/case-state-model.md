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
