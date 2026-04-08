# Case Log Authority and Assertion Recording

**Relates to**: `specs/case-log-processing.md`,
`specs/case-management.md`, `specs/sync-log-replication.md`,
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

This is especially true once reports are treated as **proto-cases**. Logging
begins at report receipt and continues through case creation, rather than
starting only after a `VulnerabilityCase` object exists.

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
for assertions that can be tied to a report, proto-case, or case.

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

- If a message cannot be tied to a report/proto-case/case, it belongs in
  transport- or actor-level diagnostics, not the case log.
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
requirements belong in `specs/case-log-processing.md`.
