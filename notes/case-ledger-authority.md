---
title: Case Ledger Authority and Assertion Recording
status: active
description: "Authority model for the case activity log: trusted timestamps, assertion recording, and authority chain."
related_specs:
  - specs/case-ledger-processing.yaml
  - specs/case-management.yaml
  - specs/sync-ledger-replication.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/case-state-model.md
  - notes/sync-ledger-replication.md
relevant_packages:
  - vultron/wire/as2
  - vultron/core/models
---

# Case Ledger Authority and Assertion Recording

**Relates to**: `specs/case-ledger-processing.yaml`,
`specs/case-management.yaml`, `specs/sync-ledger-replication.yaml`,
`notes/activitystreams-semantics.md`, `notes/case-state-model.md`,
`notes/sync-ledger-replication.md`

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
- **canonical case ledger entry**: a CaseActor-authored record that says the
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

## `CaseLedgerEntry` Is the Canonical Content Object

The canonical object should be a neutral **`CaseLedgerEntry`**, not a renamed copy
of the original activity and not the transport envelope itself.

Why a neutral object type:

- it must represent both accepted and rejected outcomes
- it separates canonical log content from transport concerns
- it gives the CaseActor a stable object to hash, replicate, replay, and audit

A `CaseLedgerEntry` should carry at least:

- the asserted activity payload, or a normalized immutable snapshot sufficient
  for deterministic replay
- the CaseActor's own recording metadata
- a disposition such as `recorded` or `rejected`
- for rejections, a small machine-readable reason code plus optional
  human-readable detail

`Announce` remains the **transport wrapper** for replication. The thing being
announced is the `CaseLedgerEntry`, not the other way around.

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

Not every inbound failure belongs in the case audit ledger.

- If a message cannot be tied to a report/case (including proto-cases in
  RM.RECEIVED/INVALID stages), it belongs in transport- or actor-level
  diagnostics, not the case ledger.
- If the CaseActor can resolve the message to a case context but rejects it
  during case-layer validation, the rejection belongs in the local case audit
  log.

Rejected case-ledger outcomes should normally be reported only to the asserting
sender, not broadcast to all case participants. The other participants need the
canonical recorded history, not the full stream of invalid assertion attempts.

---

## Replication Implications

This model sharpens the replication boundary:

- participant assertions are **inputs** to CaseActor processing
- `CaseLedgerEntry(recorded)` objects are the **canonical replicated facts**
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

## Post-#787 Convergence Decisions (Epic #788 — Completed)

Issue #787 intentionally kept `CaseEvent` as a lightweight inline value object.
That merged decision remained valid as a short-term compatibility step while the
project converged on canonical `CaseLedgerEntry` history.

Follow-on plan (Epic #788, all completed):

- #789 migrated remaining `record_event()`-only write paths to CaseActor
  canonical log commits.
- #790 introduced actor-local `pending_assertions` to suppress duplicate emits
  during canonical round-trip windows.
- #791 added a hard catch-up gate so actors must re-establish case-ledger
  freshness before taking new case actions after restart.
- #792 removed `CaseEvent` and `VulnerabilityCase.record_event()` — canonical
  `CaseLedgerEntry` is now the sole source of protocol-significant history.

`pending_assertions` is temporary local memory for decision suppression, not a
second source of truth. Canonical `CaseLedgerEntry` remains authoritative.

Initial policy decisions for pending assertions:

- default timeout is 180 seconds and configurable
- timeout marks the assertion as `timed_out` and logs an error
- timeout does not auto-retry; future behavior may decide to re-emit if still
  needed
- entries clear when matching canonical `CaseLedgerEntry(recorded|rejected)`
  arrives

---

## Consequences for Future Design Work

This framing has several practical consequences:

- The old "intent vs event" terminology should be retired for this topic.
  `asserted` vs `recorded` is more accurate, with `rejected` as an additional
  CaseActor disposition.
- The `CaseEvent` / `record_event()` path was a useful foundation, but
  the long-term canonical content model needs to grow into a richer
  `CaseLedgerEntry`.
- Specs and implementations dealing with replication must distinguish between
  the broader local audit trail and the narrower canonical recorded chain.
- Proto-case history must remain continuous across the
  report-to-case transition rather than being split into two unrelated logs.

This note should be treated as the durable design explanation. Normative
requirements belong in `specs/case-ledger-processing.yaml`.

---

## Canonical Entry Criteria: What Belongs in the Log

The canonical case ledger is a **protocol ledger**, not a process log. It records
exactly one entry per CaseActor-accepted protocol-significant assertion. Each
entry's `payloadSnapshot` is the verbatim AS2 activity that was asserted (or a
deterministic canonical normalization of it).

Concretely:

**Belongs in the canonical case ledger (allowed `payloadSnapshot` types):**

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

**Does NOT belong in the canonical case ledger:**

- Synthetic checkpoint markers (e.g., `demo_verification`)
- Per-actor runtime diagnostics, troubleshooting traces, or "I made it to
  step N" markers
- Internal cascade triggers, sentinels, or scheduling events
- Any event whose `payloadSnapshot` would be empty or whose `logObjectId`
  points at the case itself rather than a specific protocol activity

Anything in the "does NOT belong" category is **process-log content** and
belongs in Python `logging` output governed by `specs/structured-logging.yaml`,
not in the canonical case ledger.

### Why the Separation Matters

The canonical case ledger is replicated to every participant and contributes
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
**ADR-0019 — Case Ledger Is a Canonical Protocol Ledger, Not a Process Log**.

### `Announce` Envelope vs. `payloadSnapshot` Actor

A subtle but important distinction:

```text
Vendor sends:  Add(ParticipantStatus, actor=vendor) → CaseActor
CaseActor commits: CaseLedgerEntry(
  log_index=N,
  recording_actor=case_actor,
  payloadSnapshot=Add(ParticipantStatus, actor=vendor),  ← verbatim assertion
)
CaseActor broadcasts: Announce(
  actor=case_actor,                                       ← envelope actor
  object=CaseLedgerEntry(...),
) → all participants
```

The `Announce` envelope's `actor` field is always the CaseActor. The
`payloadSnapshot.actor` inside the `CaseLedgerEntry` preserves the original
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

---

## Commit Authorization and Coverage (CLP-09, Epic #788 retrospective)

Two gaps surfaced late in Epic #788 that CLP-09 now makes explicit, because
the prior framing (BT-10-004's single line, "CaseActor MUST enforce
case-level authorization") was not specific enough to prevent them from
accumulating call site by call site.

### Gap 1: Authorization Was a Convention, Not a Gate

`CommitCaseLedgerEntryNode` (the canonical commit mechanism established by
PR #1017 / BT-06-006) had no built-in authorization check. An audit found
that only one of roughly ten call sites guarded the commit, and it did so
with an ad hoc Python-level identity check (`_is_case_actor_receiver`)
*outside* the BT, not a role check inside it. The other call sites
committed unconditionally.

The fix is a reusable guarded-commit composition, following the same
Selector/Sequence/Success idiom already used elsewhere in this codebase
(see `notes/bt-integration.md` § "Conditional BT Branches as Selector
Composites" and § "Guarded Commit: Role-Gated Canonical Writes"):

```text
Selector
├─ Sequence
│  ├─ CheckIsCaseManagerNode   # role check, not identity comparison
│  └─ CommitCaseLedgerEntryNode
└─ Success("CommitCaseLedgerEntrySkippedNotCaseManager")
```

CLP-09-001 requires every commit call site to reach the commit only through
this kind of guarded composition. CLP-09-002 requires a test that fails if
any call site bypasses it.

### Gap 2: Commit Coverage Had No Structural Check

`validate_report`, `ack_report`, and `close_case` produced **no** canonical
ledger entry at all on `main` for an unknown span of time (issue #998).
Dispatch completeness already has a structural guarantee — DR-02-002 and
UCORG-02-002 require every `MessageSemantics` value to resolve to a callable
use case, enforced by a coverage test. Commit completeness had no
equivalent: a use case could be fully wired for dispatch and still never
touch the ledger, and nothing would fail until someone manually re-audited
the tree-by-tree commit sites (which is how #998/#1022 found the gap).
CLP-09-003 closes this by requiring the same kind of enumerated coverage
test for commits that already exists for dispatch.

### Gap 3: Dual-Invocation Use Cases Need Per-Invocation Authorization

Some use-case classes are invoked more than once for the same logical
activity, with different receiving actors. The clearest example is
`ack_report` in the two/three-actor demo: the same `AckReportReceivedUseCase`
runs once with the vendor (case actor) as receiver, and once with the finder
as a relay target. Only the case-actor invocation should commit.

This is structurally the same bug shape that produced the original
hash-chain fork in issue #923 — a use case authored or committing on behalf
of the wrong actor. CLP-09-004 makes the general rule explicit: authorization
for a commit must be evaluated **per invocation**, against the actor that is
actually active for that invocation, never assumed from the use-case class
itself or from a prior invocation having been authorized.

---

## Per-Case Genesis Hash — Origin Binding and Future Improvements

*Spec: `specs/case-ledger-processing.yaml` CLP-08-001 through CLP-08-006.*

The per-case genesis hash is derived as
`SHA-256(case_id + "|" + created_at.isoformat() + "|" + case_actor_id)`.
This anchors each case ledger to its origin identity and timestamp,
replacing the former global `GENESIS_HASH = "0" * 64` constant.

### Current Threat Model

Domain-bound case URIs (e.g., `https://example.org/cases/<uuid>`) with a
cryptographically random UUID path segment satisfy CLP-08-006. The domain
prefix is public but irrelevant — an attacker must still brute-force the
UUID component to predict the genesis hash.

If case metadata (`case_id`, `created_at`, `case_actor_id`) is observable
by an attacker — which is possible in a federated protocol — the genesis
hash becomes computable by anyone with that knowledge. This means:

- **Hash-chain integrity** is preserved: the attacker cannot forge or silently
  drop entries from a chain whose genesis hash a receiver has independently
  stored.
- **DoS amplification** is reduced from universal (any attacker, any case) to
  targeted (attacker must know this specific case's metadata), but is not
  fully eliminated.

### Future Improvement: Secret Nonce

Adding a secret nonce to the genesis hash input — a random value generated
by the CaseActor at case creation and never transmitted on the wire — would
close the targeted DoS vector even when case metadata leaks:

```python
genesis_hash = sha256(
    case_id + "|" + created_at.isoformat() + "|" + case_actor_id
    + "|" + secret_nonce
)
```

The nonce would need to be stored securely in the CaseActor's DataLayer and
shared only with legitimate participants through an authenticated channel.
This adds key-management complexity that is out of scope for the prototype
tier but is the natural next step for production deployments.

### Future Improvement: CaseActor Keypairs

The more durable long-term solution is **cryptographic identity for
CaseActors**. When CaseActors generate a new keypair at actor creation time
(planned), the genesis hash can incorporate the CaseActor's public key or a
key-signed commitment over case creation data:

```python
genesis_hash = sha256(
    case_id + "|" + created_at.isoformat() + "|" + case_actor_public_key
)
# or: genesis_hash = sha256(case_actor.sign(case_id + created_at))
```

This would:

- **Eliminate DataLayer trust for genesis authenticity**: any party with the
  CaseActor's public key can independently verify the ledger's origin without
  trusting the DataLayer's `case_id` field.
- **Close the targeted DoS vector**: the nonce is effectively the private key,
  which is never observable on the wire.
- **Enable third-party auditing**: auditors can verify ledger provenance from
  the public key alone, without needing out-of-band case metadata.

The keypair-per-CaseActor design is tracked as a planned capability. Until
it lands, the domain-bound UUID genesis hash defined in CLP-08-002 is the
correct implementation.
