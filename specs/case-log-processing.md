# Case Log Processing Specification

## Overview

Requirements for participant assertions, CaseActor canonicalization, local
case audit logging, recorded-history projection, and replication-facing
`CaseLogEntry` objects.

**Source**: `wip_notes/intent-event.md`,
`notes/activitystreams-semantics.md`, `notes/case-state-model.md`,
`notes/sync-log-replication.md`
**Cross-references**: `specs/case-management.yaml`,
`specs/sync-log-replication.yaml`, `specs/outbox.yaml`,
`specs/message-validation.yaml`, `specs/idempotency.yaml`
**Note**: This specification governs case- and proto-case-scoped assertion
recording. Transport-layer handling for malformed or unrouteable traffic that
cannot be attached to a report or case remains out of scope here.

---

## Assertion Intake

- `CLP-01-001` Non-CaseActor activities that participate in a report,
  proto-case, or case workflow MUST be treated as participant assertions
  awaiting CaseActor processing
  - `CLP-01-001` refines `CM-02-002`
- `CLP-01-002` The protocol MUST NOT require a separate "asserted mode" marker
  on ordinary participant activities for case/proto-case flows
  - Assertion status is implied by sender role and the CaseActor processing
    path
- `CLP-01-003` The CaseActor MUST be the only actor that emits canonical
  case-history entries used by replicas
  - `CLP-01-003` refines `CM-02-002`
- `CLP-01-004` Participant replicas MUST NOT project shared case state
  directly from peer assertions
  - `CLP-01-004` depends-on `CM-06-002`

## Canonical `CaseLogEntry`

- `CLP-02-001` For each case-resolvable assertion processed at the case layer,
  the CaseActor MUST append a canonical `CaseLogEntry`
- `CLP-02-002` `CaseLogEntry` MUST be a canonical content object distinct from
  any transport envelope used to replicate it
  - `CLP-02-002` refines `SYNC-02-001`
- `CLP-02-003` `CaseLogEntry` MUST include the asserted activity payload, or a
  normalized immutable snapshot of it, sufficient for deterministic replay
  - A pointer to the asserted activity alone is insufficient
  - `CLP-02-003` depends-on `SYNC-08-002`
- `CLP-02-004` `CaseLogEntry` MUST include a disposition field with at least
  `recorded` and `rejected`
- `CLP-02-005` Rejected `CaseLogEntry` objects SHOULD include a
  machine-readable reason code and MAY include human-readable detail
- `CLP-02-006` `CaseLogEntry` MUST include a `log_index` field corresponding
  to SYNC-01-002; this field MUST be set by the CaseActor's single
  authoritative write path and MUST NOT be assigned by external parties
- `CLP-02-007` `CaseLogEntry` MAY include an optional `term` field reserved
  for Raft cluster use; in single-node deployments this field SHOULD be
  omitted or set to `null`; in multi-node CaseActor cluster deployments this
  field MUST be populated with the current Raft term at time of append

## Audit Scope and Continuity

- `CLP-03-001` Only assertions that can be resolved to a specific report,
  proto-case, or case MUST be appended to the case audit log
  - `CLP-03-001` constrains `VM-09-001`
- `CLP-03-002` Malformed, unauthenticated, or otherwise unrouteable inbound
  messages that cannot be attached to a report or case MUST be handled outside
  the case audit log
- `CLP-03-003` The assertion-recording model MUST support continuity from
  report receipt through the case lifecycle so that all history — including
  the proto-case stage (RM.RECEIVED / RM.INVALID) — is captured in the
  case audit log
  - Per ADR-0015, a `VulnerabilityCase` is created at report receipt, so
    "proto-case history" is native case history from the start
  - `CLP-03-003` depends-on `CM-12-001`

## Recorded Projection and Replication

- `CLP-04-001` The authoritative recorded history of a case MUST be a filtered
  projection of `CaseLogEntry` objects whose disposition is `recorded`
- `CLP-04-002` Case-state reconstruction MUST use only the recorded projection
  and MUST ignore rejected entries
  - `CLP-04-002` depends-on `SYNC-08-002`
- `CLP-04-003` Replicated hash chains, Merkle proofs, and replay state MUST be
  computed over recorded `CaseLogEntry` objects only
  - `CLP-04-003` refines `SYNC-01-003`
  - `CLP-04-003` refines `SYNC-08-001`
- `CLP-04-004` CaseActor fan-out replication MUST deliver the canonical
  `CaseLogEntry` content, wrapped in an ActivityStreams transport envelope
  such as `Announce`
  - `CLP-04-004` refines `SYNC-02-001`
  - `CLP-04-004` depends-on `OX-03-001`
- `CLP-04-005` When a participant includes log-position context with an
  assertion, it SHOULD use the sender's last accepted canonical hash or
  position from the recorded projection
  - `CLP-04-005` refines `SYNC-03-004`
- `CLP-04-006` The canonical recorded log is the authoritative source of truth
  for case participant membership and case state
  - Implementations MAY maintain cached projections (e.g., `actor_participant_index`)
    for performance, but such caches MUST remain consistent with what log replay
    would reconstruct
  - Any discrepancy between a cached projection and log-replay output MUST be
    treated as an error condition requiring cache reconciliation
  - `CLP-04-006` refines `CLP-04-001`

## Rejection Handling

- `CLP-05-001` CaseActor rejection outcomes SHOULD be sent directly to the
  asserting participant rather than broadcast to all participants
- `CLP-05-002` Normal case-update fan-out MUST NOT replicate rejected
  `CaseLogEntry` objects to all case participants
  - `CLP-05-002` constrains `CM-06-001`
- `CLP-05-003` The system SHOULD provide a convenient way to retrieve the
  recorded-only history projection without requiring consumers to manually
  filter rejected entries from the broader audit log

## Verification

### CLP-01 Verification

- Unit test: a participant-originated case/proto-case activity is treated as an
  assertion input and does not directly mutate replica state
- Unit test: participant replicas ignore peer assertions until a CaseActor
  `CaseLogEntry` arrives

### CLP-02, CLP-03 Verification

- Unit test: case-resolvable assertion produces a `CaseLogEntry` with asserted
  payload snapshot and disposition
- Unit test: case-unresolvable malformed traffic does not create a case audit
  entry
- Unit test: rejected `CaseLogEntry` includes reason code when rejection is
  produced by case-layer validation

### CLP-04, CLP-05 Verification

- Unit test: recorded-history projection excludes rejected entries
- Unit test: hash-chain input excludes rejected entries and includes only
  recorded `CaseLogEntry` objects
- Integration test: `Announce` fan-out carries canonical `CaseLogEntry`
  content rather than a raw peer assertion
- Integration test: rejection feedback is delivered to the asserting sender
  without broad participant fan-out
- Unit test: rebuilding participant membership via log replay produces the
  same result as reading the cached `actor_participant_index`
- Code review: all code paths that mutate `actor_participant_index` are also
  reflected by a corresponding `CaseLogEntry` in the recorded log
