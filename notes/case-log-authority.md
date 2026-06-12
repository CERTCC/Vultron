---
title: Case Log Authority and Assertion Recording
status: active
description: "Authority model for the case activity log: trusted timestamps, assertion recording, and authority chain."
related_specs:
  - specs/case-log-processing.yaml
  - specs/case-management.yaml
  - specs/sync-log-replication.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/case-state-model.md
  - notes/sync-log-replication.md
relevant_packages:
  - vultron/wire/as2
  - vultron/core/models
---

# Case Log Authority and Assertion Recording

**Relates to**: `specs/case-log-processing.yaml`,
`specs/case-management.yaml`, `specs/sync-log-replication.yaml`,
`notes/activitystreams-semantics.md`, `notes/case-state-model.md`,
`notes/sync-log-replication.md`

---

## Overview

This note refines the rough "intent vs event" idea into a model that better
fits Vultron's existing ActivityStreams semantics and single-writer CaseActor
architecture.

The key distinction is **not** request vs fact. Participant-originated
activities already function as assertions that something happened on the
sender's side. The important distinction is instead:

- **participant assertion**: an inbound case- or proto-case-scoped activity
  that claims a protocol-relevant change occurred
- **canonical case log entry**: a CaseActor-authored record that says the
  assertion was processed and either accepted into canonical history or
  rejected at the case layer

This keeps Vultron aligned with the existing rule that Activities are
state-change notifications, not commands, while still preserving the CaseActor
as the sole authority for replicated case history.

---

## Assertions Are Implicit

For case-scoped and proto-case-scoped flows, ordinary inbound AS2 activities
from participants should be treated as **assertions by default**.

Examples:

- `Offer(Report)` asserts that a report was submitted
- `Add(Note)` asserts that a note was added
- `Assign` asserts that an ownership-related action was taken
- `Invite`, `Accept`, and `Reject` assert that the sender performed those
  protocol actions

Because nearly all relevant inbound work messages already have this shape,
adding a separate `vultron:mode = asserted` field to every ordinary activity
adds noise without much extra meaning. The sender role and processing path
already imply that these are participant assertions awaiting CaseActor
recording.

This is especially true since reports are treated as **proto-cases** under
ADR-0015. A case object (`VulnerabilityCase`) is created at report receipt,
so logging begins immediately and continues through the full case lifecycle,
rather than starting only after validation. A proto-case is a case in the
RM.RECEIVED or RM.INVALID stage — the case object exists, but validation
has not yet occurred.

---

## The CaseActor Writes Canonical History

The CaseActor remains the **single writer** of authoritative shared history.
Participants may send assertions, but participant replicas must not update
shared case state directly from peer messages.

Instead, the CaseActor:

1. receives a participant assertion
2. validates that it is authentic, case-resolvable, and acceptable at the case
   layer
3. appends a canonical log entry describing the outcome
4. replicates only the canonical recorded history to participant replicas

This means the CaseActor is not "re-performing" the asserted action. It is
publishing the canonical statement:

> I received and processed this asserted activity, and I recorded it as part of
> authoritative case history.

---

## `CaseLogEntry` Is the Canonical Content Object

The canonical object should be a neutral **`CaseLogEntry`**, not a renamed copy
of the original activity and not the transport envelope itself.

Why a neutral object type:

- it must represent both accepted and rejected outcomes
- it separates canonical log content from transport concerns
- it gives the CaseActor a stable object to hash, replicate, replay, and audit

A `CaseLogEntry` should carry at least:

- the asserted activity payload, or a normalized immutable snapshot sufficient
  for deterministic replay
- the CaseActor's own recording metadata
- a disposition such as `recorded` or `rejected`
- for rejections, a small machine-readable reason code plus optional
  human-readable detail

`Announce` remains the **transport wrapper** for replication. The thing being
announced is the `CaseLogEntry`, not the other way around.

---

## Local Audit Log vs. Replicated Canonical Chain

Two related but distinct structures are useful:

### 1. Local Case Audit Log

The local audit log is append-only and captures case-layer processing outcomes
for assertions that can be tied to a report, proto-case (RM.RECEIVED or
    RM.INVALID stage case), or case.

It may contain both:

- `recorded` entries
- `rejected` entries

This log is useful for:

- local traceability
- debugging and human review
- explaining why a sender was rejected
- preserving case-level audit context without mixing it into transport logs

### 2. Replicated Canonical History

The replicated canonical history is a **filtered projection** of only the
`recorded` entries from the broader audit log.

Only this recorded projection should:

- drive participant replica state reconstruction
- participate in the Merkle/hash chain
- be fanned out to other participants as canonical updates

Rejected entries are part of local case auditability, but they are **not** part
of the canonical replicated history.

---

## Rejections Stay Local Except for Sender Feedback

Not every inbound failure belongs in the case audit log.

- If a message cannot be tied to a report/case (including proto-cases in
  RM.RECEIVED/INVALID stages), it belongs in transport- or actor-level
  diagnostics, not the case log.
- If the CaseActor can resolve the message to a case context but rejects it
  during case-layer validation, the rejection belongs in the local case audit
  log.

Rejected case-log outcomes should normally be reported only to the asserting
sender, not broadcast to all case participants. The other participants need the
canonical recorded history, not the full stream of invalid assertion attempts.

---

## Replication Implications

This model sharpens the replication boundary:

- participant assertions are **inputs** to CaseActor processing
- `CaseLogEntry(recorded)` objects are the **canonical replicated facts**
- participant replicas derive state only from the canonical recorded entries

To support replay and stale-position detection, participant assertions should
carry the sender's last accepted canonical log hash or position in `context`
when available. That gives the CaseActor a concrete basis for deciding whether
to accept the assertion, reject it as stale, or replay missing canonical
entries first.

The hash chain should therefore be computed over **CaseActor-authored canonical
recorded entries**, each of which includes the asserted payload snapshot needed
by recipients. Replicating only pointers to prior assertions is insufficient,
because replicas need the actual asserted content to reconstruct state.

---

## Post-#787 Convergence Decisions (Epic #788)

Issue #787 intentionally kept `CaseEvent` as a lightweight inline value object.
That merged decision remains valid as a short-term compatibility step while the
project converges on canonical `CaseLogEntry` history.

Follow-on plan (Epic #788):

- #789 migrates remaining `record_event()`-only write paths to CaseActor
  canonical log commits.
- #790 introduces actor-local `pending_assertions` to suppress duplicate emits
  during canonical round-trip windows.
- #791 adds a hard catch-up gate so actors must re-establish case-log freshness
  before taking new case actions after restart.
- #792 removes `CaseEvent` once canonical log reads/writes fully cover
  protocol-significant history.

`pending_assertions` is temporary local memory for decision suppression, not a
second source of truth. Canonical `CaseLogEntry` remains authoritative.

Initial policy decisions for pending assertions:

- default timeout is 180 seconds and configurable
- timeout marks the assertion as `timed_out` and logs an error
- timeout does not auto-retry; future behavior may decide to re-emit if still
  needed
- entries clear when matching canonical `CaseLogEntry(recorded|rejected)`
  arrives

---

## Consequences for Future Design Work

This framing has several practical consequences:

- The old "intent vs event" terminology should be retired for this topic.
  `asserted` vs `recorded` is more accurate, with `rejected` as an additional
  CaseActor disposition.
- The current `CaseEvent` / `record_event()` path is a useful foundation, but
  the long-term canonical content model needs to grow into a richer
  `CaseLogEntry`.
- Specs and implementations dealing with replication must distinguish between
  the broader local audit trail and the narrower canonical recorded chain.
- Proto-case history must remain continuous across the
  report-to-case transition rather than being split into two unrelated logs.

This note should be treated as the durable design explanation. Normative
requirements belong in `specs/case-log-processing.yaml`.

---

## Canonical Entry Criteria: What Belongs in the Log

The canonical case log is a **protocol ledger**, not a process log. It records
exactly one entry per CaseActor-accepted protocol-significant assertion. Each
entry's `payloadSnapshot` is the verbatim AS2 activity that was asserted (or a
deterministic canonical normalization of it).

Concretely:

**Belongs in the canonical case log (allowed `payloadSnapshot` types):**

- `Offer(VulnerabilityReport)` — finder asserts report submission
- `Add(Note)` — participant asserts a note exchange
- `Add(ParticipantStatus)` — participant asserts an RM/CS/EM transition
- `Offer(EmbargoEvent)`, `Accept(EmbargoEvent)`, `Reject(EmbargoEvent)` —
  embargo proposal/response
- `Invite(VulnerabilityCase)`, `Accept(Invite)`, `Reject(Invite)` — case
  membership handshake (note: routed through the CaseActor per PCR-08)
- `Announce(VulnerabilityCase)` — case bootstrap broadcast
- Any other protocol-significant AS2 activity that mutates protocol-visible
  state

**Does NOT belong in the canonical case log:**

- Synthetic checkpoint markers (e.g., `demo_verification`)
- Per-actor runtime diagnostics, troubleshooting traces, or "I made it to
  step N" markers
- Internal cascade triggers, sentinels, or scheduling events
- Any event whose `payloadSnapshot` would be empty or whose `logObjectId`
  points at the case itself rather than a specific protocol activity

Anything in the "does NOT belong" category is **process-log content** and
belongs in Python `logging` output governed by `specs/structured-logging.yaml`,
not in the canonical case log.

### Why the Separation Matters

The canonical case log is replicated to every participant and contributes
to the hash chain that participants use to verify their replicas agree
with the CaseActor's authoritative copy. If diagnostic or synthetic
content enters the chain:

- Participants cannot deterministically reconstruct case state from the
  log alone — they'd have to filter out non-protocol entries.
- The hash chain becomes sensitive to runtime details that have nothing
  to do with protocol semantics (e.g., timing of demo checkpoints).
- Operators using process logs for troubleshooting cannot freely add
  detail without risking protocol-level effects.

The decision is captured at the ADR level in
**ADR-0019 — Case Log Is a Canonical Protocol Ledger, Not a Process Log**.

### `Announce` Envelope vs. `payloadSnapshot` Actor

A subtle but important distinction:

```text
Vendor sends:  Add(ParticipantStatus, actor=vendor) → CaseActor
CaseActor commits: CaseLogEntry(
  log_index=N,
  recording_actor=case_actor,
  payloadSnapshot=Add(ParticipantStatus, actor=vendor),  ← verbatim assertion
)
CaseActor broadcasts: Announce(
  actor=case_actor,                                       ← envelope actor
  object=CaseLogEntry(...),
) → all participants
```

The `Announce` envelope's `actor` field is always the CaseActor. The
`payloadSnapshot.actor` inside the `CaseLogEntry` preserves the original
asserter (`vendor` in the example). Replicas receiving the broadcast
update their state based on the snapshot's asserter, not the envelope's
actor. Rewriting `payloadSnapshot.actor` to the CaseActor would erase
the assertion's provenance and is forbidden by CLP-07-003.

### Commit-Boundary Enforcement

CLP-07-005 recommends a runtime guard at the CaseActor commit boundary
that rejects entries violating CLP-07-001 through CLP-07-004 *before*
they enter the hash chain. Failing fast at commit time keeps the
canonical chain clean and surfaces bugs immediately, rather than allowing
silent pollution that's discovered only when replicas diverge.
