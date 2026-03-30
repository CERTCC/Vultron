# State Machine Specification

## Overview

Requirements governing how the RM (Report Management), EM (Embargo
Management), and CS (CVD Case State: VFD and PXA axes) protocol state
machines are defined, represented, and executed at runtime.

The Vultron protocol operates three interacting state machines, each
tracking a distinct aspect of the coordinated vulnerability disclosure
lifecycle. Each participant maintains its own RM state; the CaseActor
maintains EM and Case State (CS) shared across all participants. Within
the CS axes, the EM state and the PXA (Public eXploit/Attack) axis are
shared across all participants via the CaseActor; the VFD
(Vendor Fix Deployed) axis is maintained strictly per-participant, since
each vendor's fix deployment status is independent.

**Source**: `vultron/core/states/`, `notes/state-machine-findings.md`,
`docs/adr/0013-unify-rm-state-tracking.md`,
`specs/vultron-protocol-spec.md`

**Cross-references**: `case-management.md` CM-03 (per-participant state
tracking), `behavior-tree-integration.md` BT-06 (BT-driven transitions),
`handler-protocol.md` HP-00 (activities as state-change notifications),
`vultron-protocol-spec.md` VP-01 through VP-13

---

## State Enum Design (MUST)

- `SM-01-001` All protocol state axes (RM, EM, VFD, PXA) MUST be defined
  using Python `StrEnum`
  - `StrEnum` values serialize to their string value automatically, which
    is required for JSON round-tripping through the DataLayer and across
    the wire
  - Using `int` enums or plain `Enum` classes for protocol state axes is
    prohibited because integer values are meaningless without context
    and complicate debugging
- `SM-01-002` State enums SHOULD provide both a full descriptive name
  and a short single-character alias for each state
  - Full name form: `REPORT_MANAGEMENT_VALID = "VALID"` — used in tests,
    documentation, and human-readable output
  - Short alias form: `V = VALID` — used in compact state-vector notation
    and debug output that displays the full case state string (e.g., `"VFdPxa"`)
  - Both forms MUST refer to the same string value (the short aliases are
    aliases, not separate states)
- `SM-01-003` State enum values are the authoritative definition of valid
  states
  - When documentation and code disagree on state names or valid state
    sets, the enum definitions in `vultron/core/states/` MUST take
    precedence
  - Documentation MUST be updated to match the enum, not the other way around
  - Any detected mismatch between the authoritative core state enums and
    formal protocol documentation MUST be recorded as a noteworthy event
    (e.g., a note in `notes/state-machine-findings.md` or an issue) rather
    than being silently corrected; such discrepancies indicate a potential
    design flaw requiring explicit review

## State Machine Definitions (SHOULD)

- `SM-02-001` Each state axis SHOULD have a corresponding
  `create_*_machine()` factory function that produces a `transitions`
  library `Machine` instance for the axis
  - These factory functions serve as documentation and as graph sources for
    Mermaid diagram generation (via `mermaid_machine()`)
  - The `Machine` MUST enumerate all valid states and all valid transitions
    with named triggers
- `SM-02-002` `create_*_machine()` factory functions MUST NOT be called for
  runtime state changes in production use-case or handler code
  - Machine objects are intended for offline documentation tooling and
    visualization; using them to drive runtime transitions couples
    production code to the `transitions` library in ways that complicate
    testing and DataLayer integration
  - SM-02-002 constrains SM-02-001
- `SM-02-003` Trigger names for `transitions` library machines SHOULD be
  defined as a companion `StrEnum` (e.g., `EM_Trigger`) using `auto()` so
  that trigger strings remain stable and are not inlined as string literals
  scattered across the codebase

## Transition Definitions (SHOULD)

- `SM-03-001` Each state transition SHOULD be expressed as a typed
  `TransitionBase` subclass with `trigger`, `source`, and `dest` fields
  typed to the appropriate enums
  - This provides type safety on transition definitions and documents valid
    (source, dest) pairs in one place
  - Example: `EmTransition(trigger=EM_Trigger.ACCEPT, source=EM.PROPOSED, dest=EM.ACTIVE)`
- `SM-03-002` Transition definitions SHOULD be stored as a module-level list
  in the same module that defines the state enum
  - Co-locating state enum and transition list ensures that adding a new
    state also prompts a review of which transitions it needs
- `SM-03-003` Transitions SHOULD be exhaustive: every valid
    (source → dest) pair that the protocol describes MUST have a
    corresponding transition entry

## Runtime State Changes (MUST)

- `SM-04-001` Runtime state changes MUST be guarded by an explicit
  precondition check before the state value is written
  - The check MUST verify that the current state is one from which the
    intended transition is valid (i.e., the source state is in the set of
    allowed predecessor states for that transition)
  - Unguarded state assignment (writing a new state without checking the
    current state) is a defect: it can produce invalid protocol states
    (e.g., `EM.ACTIVE → EM.PROPOSED`) and makes idempotency checks harder
- `SM-04-002` State-changing handlers MUST be idempotent with respect to
  repeated application of the same transition
  - If the actor is already in the target state, the handler MUST return
    without error (not raise a conflict exception)
  - If the actor is in an invalid source state, the handler MUST raise a
    domain-specific error (`VultronInvalidStateTransitionError`) rather than
    silently ignoring the transition
  - Invalid state transition attempts MUST be logged at WARNING or ERROR
    level so that protocol violations are captured in system logs
  - SM-04-002 implements HP-07-001 (handler-protocol.md)

## State History (MUST)

- `SM-05-001` Persisted state for both case-level and participant-level
  axes MUST use an append-only history list
  - New state records (e.g., `VultronCaseStatus`, `VultronParticipantStatus`)
    MUST be appended to the history list; existing entries MUST NOT be
    modified or deleted
  - The current (active) state is always the most recently appended entry,
    resolved by the `updated` timestamp field
- `SM-05-002` The `current_status` property (or equivalent) MUST return
  the single most-recently-timestamped entry from the history list
  - Callers MUST use `current_status` to read the active state, not direct
    index access (e.g., `case_statuses[-1]`), because ordering by timestamp
    is the only stable contract
  - SM-05-002 implements CM-03-006 (case-management.md)
- `SM-05-003` Status history entries MUST record a trusted server-side
  timestamp (`received_at` or `updated`) set via `now_utc()` at write time
  - Status history entries MUST NOT copy timestamps from incoming
    ActivityStreams activities; the local clock is the only trusted source
    for ordering history entries
  - SM-05-003 implements CM-02-009 (case-management.md)
- `SM-05-004` The case state log SHOULD store references (IDs) to entries in
  the main case history log rather than duplicating full record content
  - Using ID references (pointers) avoids doubling storage for the same
    information and allows monotonically-increasing lookups to find the most
    recent status at the end of the list
  - The pointer list SHOULD be automatically refreshed whenever a state
    event is recorded to the main history log

## In-Memory (Transient) State (SHOULD)

- `SM-06-001` Transient state used only during a single request (e.g., for
  tracking report status during validation processing) SHOULD be clearly
  separated from persisted state
  - Transient state MUST NOT be written to the DataLayer
  - Transient state MUST be documented (e.g., in a module docstring) as
    non-persistent so future developers do not assume it survives a restart
- `SM-06-002` Transient RM status for reports (e.g., `ReportStatus` in the
  in-memory `STATUS` dict) MUST be replaced by persisted participant-level
  state once a report is associated with a case and a `CaseParticipant`
  record exists

## State Subsets and Guards (SHOULD)

- `SM-07-001` Commonly used groups of states that define validity zones for
  transitions SHOULD be defined as module-level constants (tuples or
  frozensets) in the same module as the state enum
  - Examples: `RM_ACTIVE = (RM.RECEIVED, RM.VALID, RM.ACCEPTED)`,
    `EM_NEGOTIATING = (EM.PROPOSED, EM.REVISE)`
  - Guard conditions SHOULD check membership in these named subsets rather
    than enumerating individual state values inline at each call site
  - This makes valid transition windows explicit and keeps guard conditions
    DRY across multiple handlers that enforce the same precondition
- `SM-07-002` State subset constants MUST be derived from enum values, not
  raw strings, to prevent silent mismatches when enum values change

## Wire and DataLayer Compatibility (MUST)

- `SM-08-001` State enum values MUST be stored and transmitted as their
  string value (not as Python enum names or as integers)
  - `StrEnum` satisfies this requirement automatically; using `Enum` or
    `IntEnum` for state axes is prohibited
- `SM-08-002` When deserializing state values from the DataLayer or from
  wire payloads, the receiving Pydantic model MUST declare the state field
  with the `StrEnum` type so that Pydantic coerces the incoming string to
  the correct enum member
  - Field declarations like `em_state: EM` (not `em_state: str`) are
    required; string-typed state fields lose type safety and break
    state-subset membership checks

## Verification

### SM-01-001, SM-01-002 Verification

- Unit test: `str(EM.ACTIVE)` returns `"ACTIVE"`, not an integer
- Unit test: `EM.A is EM.ACTIVE` (short alias is the same object)
- Unit test: Changing `EM.ACTIVE` to a different string would require a
  deliberate enum value edit, not just a rename

### SM-02-001, SM-02-002 Verification

- Unit test: `create_em_machine()` returns a `Machine` with all EM states
  and triggers
- Code review: No `create_*_machine()` call appears outside of
  documentation/visualization utilities

### SM-04-001, SM-04-002 Verification

- Unit test: Proposing an embargo when EM is already `ACTIVE` (invalid source)
  raises `VultronInvalidStateTransitionError`
- Unit test: Proposing when already `PROPOSED` returns without error (idempotent)
- Unit test: Proposing from `NO_EMBARGO` succeeds and transitions to `PROPOSED`

### SM-05-001, SM-05-002 Verification

- Unit test: After two status updates, `case.case_statuses` has two entries;
  neither original entry is modified
- Unit test: `case.current_status` returns the entry with the later timestamp

### SM-07-001, SM-07-002 Verification

- Code review: Guard conditions in use-case code reference named subset
  constants (e.g., `em_state in EM_NEGOTIATING`) rather than inline lists
  of enum values

### SM-08-001, SM-08-002 Verification

- Unit test: A `VultronCaseStatus` round-tripped through the DataLayer
  preserves `em_state` as an `EM` enum value, not a plain string
- Unit test: Deserializing `{"em_state": "ACTIVE"}` into `VultronCaseStatus`
  produces `em_state == EM.ACTIVE`

## Related

- **State definitions**: `vultron/core/states/rm.py`, `em.py`, `cs.py`
- **Common utilities**: `vultron/core/states/common.py`
- **Domain models**: `vultron/core/models/case_status.py`,
  `vultron/core/models/participant_status.py`
- **Case management**: `specs/case-management.md` (CM-03)
- **Handler protocol**: `specs/handler-protocol.md` (HP-00, HP-07)
- **BT integration**: `specs/behavior-tree-integration.md` (BT-06)
- **Protocol spec**: `specs/vultron-protocol-spec.md` (VP-01 through VP-13)
- **Design notes**: `notes/state-machine-findings.md`
- **ADR**: `docs/adr/0013-unify-rm-state-tracking.md`
