---
status: accepted
date: 2026-03-20
deciders: ahouseholder
consulted: []
informed: []
---

# Unify RM State Tracking into Persisted VultronParticipantStatus Records

## Context and Problem Statement

The Report Management (RM) state machine spans two lifecycle phases with a
pivot at `RM.VALID`:

- **Report phase** (START → RECEIVED → INVALID/VALID): Currently tracked in a
  transient in-memory `STATUS` dict via `ReportStatus` objects in
  `vultron.core.models.status`. This data is process-local and is lost on
  restart.
- **Case phase** (VALID → ACCEPTED/DEFERRED → CLOSED): Currently tracked via
  persisted `VultronParticipantStatus` / `ParticipantStatus` records appended
  to `CaseParticipant.participant_statuses`.

The two tracking mechanisms are disjoint. The pivot point — when a report
transitions to `RM.VALID` and a case is created — is implemented ad hoc with
no formal transition from the report-phase record to the case-phase record.
New participant status records are seeded with `rm_state=RM.START` rather than
carrying forward the current `RM.VALID` state.

This creates a situation where:

- RM history for the pre-case phase is not queryable or auditable.
- RM transition guards on case-engagement cannot verify that a report was truly
  valid before `ACCEPTED`/`DEFERRED` was appended.
- The RM machine's `RECEIVE` trigger (START → RECEIVED) is never explicitly
  executed anywhere in the `vultron.core` pipeline.

## Decision Drivers

- Protocol correctness: RM state should be a coherent, auditable history per
  (actor × report/case) pair, matching the `create_rm_machine()` definition.
- Persistence: state should survive process restart.
- Simplicity: a single mechanism for RM state is easier to guard and query than
  two unconnected mechanisms.
- Minimal disruption: changes should be incremental and testable.

## Considered Options

- **Option A** — Persist the full RM lifecycle in `VultronParticipantStatus`
  records (recommended)
- **Option B** — Persist the `ReportStatus` STATUS layer in the DataLayer as a
  new record type

## Decision Outcome

Chosen option: **Option A**, because it reuses the existing `VultronParticipantStatus`
data model and makes the complete RM lifecycle visible in one place
without introducing a new record type.

### Implementation steps

1. When a report is first received (`CreateReportReceivedUseCase`,
   `SubmitReportReceivedUseCase`), create and persist an initial
   `VultronParticipantStatus` with `rm_state=RM.RECEIVED` for the receiving
   actor. This is the `START → RECEIVED` (RECEIVE trigger) transition.

2. When a report is validated (`ValidateReportReceivedUseCase` /
   `SvcValidateReportUseCase`), append `rm_state=RM.VALID` to the participant
   status history. When invalidated, append `rm_state=RM.INVALID`.

3. When a case is created from a valid report, the actor's new
   `VultronParticipantStatus` for the case should be **initialised with
   `rm_state=RM.VALID`** rather than `RM.START`, carrying the current RM state
   forward into the case-engagement phase.

4. Deprecate and then remove the transient in-memory `STATUS` dict
   (`vultron.core.models.status.STATUS`) once the above steps are in place and
   tested. The `ReportStatus` model and `set_status()`/`get_status_layer()`
   helpers can be removed at that point.

5. All RM transition guard logic should read from `VultronParticipantStatus`
   (via the DataLayer) rather than the in-memory STATUS dict.

### Consequences

- Good, because RM history is complete, persistent, and queryable.
- Good, because the `create_rm_machine()` definition becomes the single
  authoritative source of valid RM transitions for both lifecycle phases.
- Good, because RM guards (e.g., "is the report currently RECEIVED or INVALID?")
  work consistently whether the query is pre- or post-case.
- Bad, because existing tests that read from the in-memory STATUS dict will need
  updating.
- Bad, because `CaseParticipant.append_rm_state()` (wire layer) may need to be
  mirrored on the core domain counterpart (see `plan/IMPLEMENTATION_NOTES.md`
  re: wire-layer methods that should live on core objects).

## Validation

- All pre-existing tests pass after the migration.
- New integration tests verify that a complete RM history
  (RECEIVED → VALID → ACCEPTED → CLOSED) is stored in
  `CaseParticipant.participant_statuses` and survives a DataLayer round-trip.
- The in-memory `STATUS` dict is empty (or removed) after the migration.

## More Information

- See `notes/state-machine-findings.md` OPP-09, P-07 for the analysis that
  led to this decision.
- Related: `vultron/core/states/rm.py` `create_rm_machine()` — authoritative
  RM state machine definition.
- Related fix: `plan/IMPLEMENTATION_NOTES.md` — note on wire-layer methods that
  should be moved to core domain objects.
