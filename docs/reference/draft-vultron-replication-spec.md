---
title: "Draft: Vultron Ledger Replication Specification"
version: "2026.08.26"
status: draft
description: >
  External-facing companion document specifying the ledger replication
  mechanics for the Vultron protocol: hash-chaining, gap detection and
  recovery, ordering guarantees, and the single-hub / single-writer +
  fan-out model. Normative requirements are grounded in
  specs/sync-ledger-replication.yaml (SYNC-01 through SYNC-15).
stakeholder_type: [platform-developer]
level: 400
page_type: reference
---

# Draft: Vultron Ledger Replication Specification

!!! warning "Working Draft — not ready for external circulation"
    This document is under active development. Requirements marked [N] are
    normative; text marked [I] is informative. Where this document and the
    implementation disagree, the implementation is currently authoritative.

---

## Abstract

Vultron is a federated, log-centric protocol for coordinated vulnerability
disclosure. Every shared case is backed by an append-only, hash-chained
canonical ledger owned by one authoritative CASE_MANAGER. This document
specifies the mechanics by which that ledger is maintained and replicated to
all Participant Actors: the hash-chain construction, replication transport,
conflict handling, gap detection and recovery, ordering guarantees, and the
normative single-hub / single-writer + fan-out architecture.

These mechanics are scoped to a companion document by design. The
[Vultron Protocol Specification](vultron-spec/index.md) states the
normative obligation — Case Hosting capability set implementations MUST replicate
the canonical ledger via `Announce(CaseLedgerEntry)` — and delegates the
mechanical specification to this document. See ADR-0077 for the rationale
behind that boundary.

---

## 1. Introduction [I]

### 1.1 Scope

This document specifies the ledger replication sub-protocol of Vultron. It
covers:

- **Hash-chain construction** — the append-only, content-addressed structure
  that gives each log entry a unique, verifiable identity and links it to its
  predecessor.
- **Replication transport** — how the CASE_MANAGER delivers entries to
  Participant Actors via `Announce(CaseLedgerEntry)` activities.
- **Conflict handling and recovery** — the reject-and-replay protocol that
  re-synchronises a diverged replica.
- **Gap detection and ordering guarantees** — the receiver-side holding area
  that makes convergence independent of delivery order.
- **Commit discipline** — the invariant that external messages are emitted
  only after a ledger entry is committed.
- **Normative replication architecture** — the single-hub / single-writer +
  fan-out model as the baseline.

Distributed consensus for multi-node Case Actor clusters (a future extension)
is out of scope for this version of the document.

### 1.2 Relationship to Other Documents

| Document | Role |
|---|---|
| [Vultron Protocol Specification](vultron-spec/index.md) | Parent specification; states the normative obligation to replicate and delegates mechanics here |
| `specs/sync-ledger-replication.yaml` | Internal normative requirements source (SYNC-01 through SYNC-15); every requirement in this document is traceable to a SYNC spec ID |
| `notes/sync-ledger-replication.md` | Design rationale, implementation notes, and the internal architecture reference |
| `docs/adr/0077-ledger-replication-companion-spec.md` | Records the decision to scope mechanics to this companion document and the rationale for the normative replication model |

### 1.3 Document Conventions

Key words in this document (MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT,
SHOULD, SHOULD NOT, RECOMMENDED, MAY, OPTIONAL) are to be interpreted as
described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174).

Normative requirements are indexed to their source SYNC spec IDs in
[§12 (Normative Requirements Reference)](#12-normative-requirements-reference).

---

## 2. Normative Architecture: Single-Hub Fan-Out [N]

### 2.1 The Single-Writer Model

**The normative replication model for Vultron is single-hub / single-writer + fan-out.** One CASE_MANAGER holds exclusive write authority over the canonical case ledger. It is the sole authorised source of `CaseLedgerEntry` records for its cases. All Participant Actors receive ledger entries from the CASE_MANAGER; they do not write to it. (SYNC-01-004, SYNC-13-005)

This model is a degenerate single-node Raft cluster. The CASE_MANAGER is
permanently the leader; no leader election is required or performed in
single-node deployments. In single-node deployments the CASE_MANAGER MUST be
treated as the permanent replication leader with exclusive write authority.
(SYNC-06-003)

Distributed consensus across multiple Case Actor instances (for
high-availability write authority) is a planned future extension and is
outside the scope of this version of the specification. (SYNC-06-004)

### 2.2 Write-Ownership Boundary

The write-ownership boundary is not merely a design preference — it is the
foundation on which idempotency guarantees rest. The presence of a
`CaseLedgerEntry` in a participant's local store is defined to mean "this
participant's core has committed the entry and applied its effects." That
semantic only holds if no other code path — adapter, wire parser, ingress
handler — ever writes a `CaseLedgerEntry` to the DataLayer. (SYNC-13-001)

Adapter, wire, transport, and message-parsing code MUST NOT create, save, or
otherwise persist a `CaseLedgerEntry` to the DataLayer. Ingress code delivers
the message; it does not write the ledger. (SYNC-13-002)

Participants MUST obtain replica `CaseLedgerEntry` records solely via the
`Announce(CaseLedgerEntry)` receive behavior, which applies domain effects
before persisting. (SYNC-13-006)

---

## 3. The Append-Only Hash Chain [N]

### 3.1 Log Structure

The canonical case ledger is append-only. (SYNC-01-001)

Each log entry MUST carry:

- A **monotonically increasing index** (`log_index`) scoped to its case, with
  no gaps or duplicates. (SYNC-01-002)
- A **content hash** (`entry_hash`) — a cryptographic hash of the entry's own
  content. (SYNC-01-003)
- A **predecessor hash** (`prev_log_hash`) — the `entry_hash` of the
  immediately preceding entry. (SYNC-01-003)

The predecessor hash of the first entry (the genesis entry) is derived
deterministically from the `VulnerabilityCase` object at creation time. This
genesis hash anchors the chain; a participant that has seeded the case can
reconstruct the genesis hash without receiving the genesis entry first.

These three fields form a forward-linked hash chain (Merkle chain style). Any
modification to a committed entry breaks the chain from that point forward,
making tampering detectable during replication. (SYNC-00-006)

### 3.2 Immutability

Log entries are immutable once committed. (SYNC-00-005, SYNC-01-001,
SYNC-08-001)

### 3.3 Canonical Serialisation

A canonical serialisation form — specifying deterministic key ordering, stable
Unicode normalisation, explicit field inclusion/exclusion, and no optional
whitespace — MUST be established before cryptographic signatures are added to
log entries. Changing the serialisation after entries are signed would
invalidate existing hash chains.

[RFC 8785 — JSON Canonicalization Scheme (JCS)](https://www.rfc-editor.org/rfc/rfc8785)
is the recommended standard for canonical JSON serialisation.

The hash-chain entry format MUST be designed to be forward-compatible with a
future Merkle Tree implementation; the hash-chain fields (`entry_hash`,
`prev_log_hash`, `log_index`) serve as the leaf-node structure. (SYNC-01-005)

### 3.4 System Invariants for the Hash Chain

The following invariants MUST hold under normal operation and partial failure:

1. **Append-only integrity** — log entries MUST be immutable once committed
   and MUST be uniquely identified by their content hash. (SYNC-08-001)
2. **Deterministic projection** — given an identical canonical recorded log
   prefix, all compliant implementations MUST derive identical state.
   (SYNC-08-002)
3. **Idempotent replay** — reprocessing any canonical log prefix, including
   duplicates, MUST NOT change the resulting state. (SYNC-08-003)

---

## 4. Replication Transport [N]

### 4.1 Wire Envelope

Log replication between the CASE_MANAGER and Participant Actors MUST use
ActivityStreams `Announce` activities as the transport envelope.
Specifically, each replicated entry is delivered as
`Announce(CaseLedgerEntry)`. (SYNC-02-001)

Each `Announce(CaseLedgerEntry)` activity:

- MUST carry the `CaseLedgerEntry` itself as its `object`, inline or by reference, with every field the recipient needs to validate the hash chain (`prev_log_hash`, `entry_hash`). (SYNC-02-004)
  The reference implementation embeds the full entry inline and never sends a URI-only reference (SYNC-02-005); that is a shortcut of the prototype, not a protocol rule.
- MUST identify the sender, the target recipient, the log entry hash, and the
  predecessor hash. (SYNC-02-002)

### 4.2 Replication Origin

Replication MUST originate from the replication leader — the actor holding
the `CASE_MANAGER` role — and MUST be sent to each Participant Actor
individually, not broadcast. (SYNC-02-003)

### 4.3 Semantic Routing on First Delivery

A receiver MUST treat an inbound `Announce(CaseLedgerEntry)` as the announcement of a ledger entry on first delivery, without needing any stored record of the entry (SYNC-13-004).
The reference implementation resolves the log-entry semantic from the typed inline object obtained during parsing, without a DataLayer round-trip (SYNC-13-007).
Message ingress MUST NOT use the canonical ledger store as a scratch or lookup cache for routing, rehydration, or classification of an inbound announce. (SYNC-13-003)

---

## 5. Conflict Handling and Recovery [N]

### 5.1 Reject on Hash Mismatch

A receiver MUST reject a replication message whose predecessor hash
(`prev_log_hash`) does not match the receiver's current log tail hash.
The receiver sends `Reject(CaseLedgerEntry)` carrying its last accepted hash
as the recovery signal. (SYNC-03-001, SYNC-08-005)

Before that check, a receiver MUST recompute the entry's hash from its content and compare it with the stated `entry_hash`.
An entry that states no hash, or whose content does not reproduce it, MUST be refused and logged, and is not buffered, applied or stored.
It is not answered with `Reject(CaseLedgerEntry)`, because a replay would resend the same entry. (SYNC-03-006)

### 5.2 Sender Retry

On receiving a rejection, the sender MUST retry replication starting from the
entry following the last accepted hash reported by the receiver. (SYNC-03-002)

### 5.3 Idempotency

Replication MUST be idempotent. Repeated delivery of the same log entry MUST
NOT produce duplicate entries in the receiver's log. (SYNC-03-003)

When a participant receives a `CaseLedgerEntry` that is already present in its
local ledger, the participant MUST skip both domain effect application and
persistence — both were already performed on first delivery. (SYNC-12-003)

### 5.4 Reject/Replay Rate Bound

The reject-and-replay recovery path is susceptible to amplification: a
participant that cannot anchor its hash chain Rejects every entry replayed to
it, and each Reject triggers a full-suffix replay, creating a
self-sustaining loop.

The CASE_MANAGER MUST bound the rate at which it replays entries to a peer
whose acknowledged replication position has not advanced. (SYNC-15-003)

Specifically:

- The CASE_MANAGER MUST record, per peer, the position (`entry_hash` or `""`
  for genesis) and timestamp of the last replay in which at least one entry
  was actually sent. (SYNC-15-008)
- A Reject reporting an unchanged replication position within the cooldown
  window MUST NOT trigger another replay. (SYNC-15-009)
- A Reject reporting an advanced replication position MUST always trigger a
  replay, regardless of cooldown. (SYNC-15-010)
- A replay in which zero entries were sent MUST NOT update the recorded
  position. (SYNC-15-011)
- Each consecutive non-empty replay from an unchanged position MUST lengthen
  the cooldown before the next (doubling it, up to a fixed ceiling); a replay
  from a different position MUST reset it. (SYNC-15-013)
- The genesis `Announce(VulnerabilityCase)` pre-seed MUST NOT be sent for a
  genesis Reject whose replay the cooldown suppresses. (SYNC-15-014)

The genesis position (`last_accepted_hash == ""`) SHOULD use a shorter
cooldown than a mid-chain stall, to avoid starving the initial bootstrap
while still preventing amplification.

### 5.5 Divergence Recovery

A participant can refuse an entry whose predecessor it already holds, because the entry's starting state does not match its case.
An entry whose content is invalid in itself, such as an impossible participant status, takes its own fault instead (RSH-09-006).
No replay fills that gap: the participant's case has diverged from the CASE_MANAGER's, and a replay resends the same refused entry.

- The participant MUST send `Create(ProcessingFault)` with failure class `LedgerEntryRefused/CaseDiverged` to the CASE_MANAGER, and MUST keep holding the refused entry. (SYNC-16-001)
- The fault MUST NOT be committed to the case ledger by either side: it reports on replication, as `Reject(CaseLedgerEntry)` does. (SYNC-16-002)
- The CASE_MANAGER MUST answer the fault from an active participant with `Announce(VulnerabilityCase)` of its current case, and MUST refuse it from any other sender. (SYNC-16-003)
- The CASE_MANAGER MUST bound the rate at which it re-seeds a peer. (SYNC-16-004)

A case copy carries the sender's **ledger tail**: the index and hash of the last entry the copy reflects, computed from the ledger when the case is read or sent. (SYNC-16-005)
A participant that already holds the case compares the tail with its own chain. (SYNC-16-006)

- If its chain is already past the tail, the copy is stale and the participant leaves its case unchanged.
- If it holds a different entry at the tail's index, the chains conflict and the participant leaves its case unchanged.
- Otherwise it replaces its case with the copy.
  If its chain falls short of the tail, it sends `Reject(CaseLedgerEntry)` with its own tail, and stores each entry at or before the tail, replayed or drained from its holding area, as a no-op. (SYNC-16-007)

[I] In this implementation, the tail travels as the `ledgerTail` property of the case object in `Announce(VulnerabilityCase)`, the only message that carries it, with `logIndex` and `entryHash` members.
The CASE_MANAGER fills it in each time it sends the announcement, and no case record stores it.
A replica that holds the case refuses a copy with no tail, because it cannot tell that copy from a stale one.
The copy carries each participant and report as the CASE_MANAGER's store holds it when it sends the copy, because a replica that takes the copy replaces its own with them.
The CASE_MANAGER receives its own announcement as a participant and skips it, because its case is the copy's source.
A replica already past the tail that holds a different entry at the tail's index reports the conflict, not a stale copy, because the chains disagree.
Until its chain reaches the tail of the copy that last replaced its case, the replica treats that tail as its own position, so an older copy is stale too.
A replica stores an entry the copy reflects without applying it, but still stores each record the entry carries that the copy names by id only, such as a note, a case status or a proposed embargo.
The `Reject(CaseLedgerEntry)` names the last entry the replica's chain stores.
A replica whose chain stores no entry has none to name, so its `Reject` names no entry, carries an empty last-accepted hash and names the case as its `target`; the CASE_MANAGER answers it with a replay from genesis. (SYNC-16-007)
A `Reject` that names no entry but carries a hash is refused when it arrives.

A divergence fault for an entry the last re-seed already reflected means the CASE_MANAGER's case disagrees with its own ledger, and the CASE_MANAGER SHOULD log it as an error. (SYNC-16-008)

---

## 6. Ordering Guarantees and Out-of-Order Delivery [N]

### 6.1 No Ordering Guarantee at the Transport Layer

`Announce(CaseLedgerEntry)` activities are delivered over a transport with no
guaranteed ordering. A participant replica can therefore receive an entry
before its hash-chain predecessor has arrived. Dropping such an entry and
relying solely on the reject/replay round-trip does not converge under
adversarial reordering, because replay re-announces entries individually over
the same unordered transport.

### 6.2 Receiver-Side Holding Area

When a participant receives a valid `Announce(CaseLedgerEntry)` whose `prev_log_hash` does not match its current chain tail, but whose `log_index` is strictly greater than `tail_index + 1` (a forward gap), the participant MUST NOT permanently discard the entry.
It MUST retain the `Announce(CaseLedgerEntry)` that carried it, as the body that arrived, in a non-ledger holding area, keyed by the entry's `prev_log_hash`, pending arrival of its predecessor.
It MUST NOT retain the entry apart from that `Announce`. (SYNC-14-001)

A forward-gap entry whose `Announce` is held MUST still trigger resynchronization: the participant MUST send `Reject(CaseLedgerEntry)` carrying its last accepted hash, so the CASE_MANAGER can replay entries that are genuinely lost (not merely reordered). (SYNC-14-002)

### 6.3 Drain on Predecessor Commit

After a participant commits a `CaseLedgerEntry`, it MUST drain the holding area.
For each newly committed tail, the participant MUST locate the held `Announce` (if any) whose entry's `prev_log_hash` equals the new tail's `entry_hash`, apply and persist that entry via the same apply-then-persist path as in-order delivery, starting from the received `Announce`, and repeat, cascading until no held `Announce` extends the current tail. (SYNC-14-003, SYNC-14-008)

[I] In this implementation, each drained entry is its own inbox delivery.
When a commit makes a held entry appliable, the participant replays the `Announce(CaseLedgerEntry)` it received for that entry through its own inbox, parsed again from the body held for it.
It never builds an `Announce` of its own, so nothing is attributed to a sender that did not send it.
The participant does not apply the entry inside the delivery that made it appliable.
That delivery's commit replays the next `Announce`, so the cascade follows from in-order delivery itself. (SYNC-14-009)

Draining a held entry MUST apply domain effects before persisting it. (SYNC-14-004)

The drain path MUST NOT re-apply effects for an entry already present in the
local ledger. (SYNC-14-007)

### 6.4 Holding Area Bounds

The out-of-order holding area MUST NOT be the canonical ledger: it MAY keep the held `Announce` in the receiver's DataLayer only as records of its own kind, never as a `CaseLedgerEntry`.
A held entry MUST NOT be persisted as a `CaseLedgerEntry` until it is drained (i.e. until its predecessor is present), so that presence of a `CaseLedgerEntry` in the DataLayer continues to mean "committed and effects applied." (SYNC-14-005, SYNC-13-001)

The holding area SHOULD be bounded in size per case.
When full it SHOULD evict the held `Announce` whose entry is farthest ahead of the current gap (highest `log_index`), body and all, and log a warning, or decline to hold the new one when its entry is itself the farthest ahead.
Eviction is recoverable because the Reject required by §6.2 was already sent. (SYNC-14-006)

### 6.5 Monotonic Visibility

Participants MUST NOT regress their acknowledged log position. (SYNC-08-004)

### 6.6 Catch-Up Freshness Gate

After actor process restart or recovery, an actor with case state in scope
MUST re-establish case-ledger freshness with the CASE_MANAGER before taking new
protocol-significant case actions. (SYNC-10-001)

While catch-up freshness is not established, the actor MUST block or defer
new protocol-significant case actions and surface an explicit
stale-or-catching-up condition. (SYNC-10-002)

The catch-up gate MUST require a contiguous canonical log prefix from genesis
through the actor's currently acknowledged tip. Any gap in that prefix MUST
block protocol-significant case actions. (SYNC-10-004)

The catch-up gate MUST NOT require the actor's acknowledged tip to equal the
CASE_MANAGER's current ledger tip. Lagging behind the leader tip is permitted if
the actor's own acknowledged prefix is contiguous from genesis. (SYNC-10-005)

---

## 7. Commit Discipline [N]

### 7.1 Commit Semantics

A log entry is committed when it has been durably written to the authoritative
log and its content hash has been recorded. An entry that has not met these
conditions MUST NOT be applied to the case state machine. (SYNC-09-001)

In a single-node Case Actor deployment, every append is an immediate commit.
No replication quorum is required.

### 7.2 Commit-After-Send Invariant

A node MUST commit the `CaseLedgerEntry` that records a Vultron message it sends only after the message has been written to its own outbox, and MUST NOT commit it before that write.
`Announce(CaseLedgerEntry)` is the one message sent after its commit: it delivers a committed entry. (SYNC-09-002)

This ensures that every entry records an act that has happened.
A retry after a send whose commit failed rebuilds the activity under its first id, so the outbox does not send it twice. (OX-06-002)

### 7.3 Effects-Before-Persist Invariant

A participant MUST apply all domain effects derived from a `CaseLedgerEntry`
(embargo teardown, participant-status update, note attachment, invite
acceptance) BEFORE persisting the entry to its local ledger. If any effect
fails, the entry MUST NOT be persisted. (SYNC-12-001)

The presence of a `CaseLedgerEntry` in a participant's local ledger MUST
imply that all domain effects for that entry were successfully applied.
(SYNC-12-002)

### 7.4 Behavior-Tree Execution Gate

The CASE_MANAGER's behavior tree execution MUST be gated on holding the
replication leadership role. (SYNC-09-003) In single-node deployments this
gate is trivially satisfied. In multi-node deployments it prevents a deposed
leader from continuing to write to the ledger after a new leader is elected.

---

## 8. Pre-Genesis Delivery Window [N]

A `Announce(CaseLedgerEntry)` activity may arrive at a participant before the
`Create(VulnerabilityCase)` or `Announce(VulnerabilityCase)` has been
processed — a delivery-order race. When this occurs, the participant cannot
reconstruct the per-case genesis hash and MUST NOT proceed normally.

### 8.1 Reject as Loss Backstop

When a participant receives an `Announce(CaseLedgerEntry)` but cannot
reconstruct the per-case genesis hash because the `VulnerabilityCase` is not
yet present in its local store, the participant MUST NOT silently discard the
entry. It MUST send a `Reject(CaseLedgerEntry)` with
`last_accepted_hash = ""` to the CASE_MANAGER so that the CASE_MANAGER replays all
entries from the beginning once the case is delivered. (SYNC-15-001)

A `CaseLedgerEntry` received when the per-case genesis hash is unavailable
MUST NOT be persisted (SYNC-15-002), MUST NOT be treated as committed
(SYNC-15-006), and its domain effects MUST NOT be applied (SYNC-15-007).

### 8.2 Pre-Genesis Hold and Drain

The participant MUST NOT rely solely on the reject/replay round-trip for pre-genesis entries.
It MUST retain the `Announce` that carried the entry, as received, in the same non-ledger holding area used for forward gaps (§6.2), keyed by the entry's `prev_log_hash`, pending arrival of the case seed. (SYNC-15-004)

After a participant seeds the `VulnerabilityCase` (via `Create` or `Announce(VulnerabilityCase)`), which anchors the deterministic per-case genesis hash, it MUST drain the holding area for that case: it MUST locate the held `Announce` (if any) whose entry's `prev_log_hash` equals the per-case genesis hash, replay it so its entry is applied and persisted via the same path as in-order delivery, and cascade in hash-chain order until no held `Announce` extends the current tail. (SYNC-15-005)

[I] The seed replays the first held `Announce` through the participant's own inbox, as §6.3 describes for a commit. (SYNC-14-009)

---

## 9. Per-Peer Replication State [N]

The replication leader MUST track per-peer state including at minimum the
last acknowledged log entry hash for each peer. (SYNC-04-001)

Per-peer replication state MUST be persisted so that it survives a leader
restart. (SYNC-04-002)

When a Participant Actor sends any message to the CASE_MANAGER, it SHOULD
include the hash of its last accepted canonical log entry as a parameter in
the activity's `context` field. This allows the CASE_MANAGER to proactively
detect that a participant is behind and immediately replay missing entries
without waiting for an explicit sync request. (SYNC-03-004)

---

## 10. Retry and Backoff [N]

The replication sender SHOULD implement retry with exponential backoff on
delivery failure. (SYNC-05-001)

Retry and backoff parameters SHOULD be configurable. (SYNC-05-002) Default
values for retry and backoff parameters MUST be documented. (SYNC-05-003)

The per-recipient HTTP POST timeout MUST be a configurable parameter of the
delivery adapter with a documented default value. The default MUST be set high
enough to tolerate a recipient that is briefly busy under normal protocol load.
A value of 5 seconds or less is insufficient under multi-actor load. (SYNC-05-004)

---

## 11. Participant-Local Pending Assertion Suppression [N/I]

!!! note "Informative: Participant-side deduplication"
    The requirements in this section describe an OPTIONAL optimisation. They
    are included for implementers who want to avoid duplicate near-term
    re-emits of the same assertion while a round-trip is pending.

A participant actor SHOULD maintain an actor-local, in-memory pending-assertion
store that records outbound assertion activities emitted toward the CASE_MANAGER
but not yet confirmed by a canonical `Announce(CaseLedgerEntry)` round-trip.
The suppression window is configurable; zero disables suppression. (SYNC-11-001)

After a participant successfully enqueues an assertion activity toward the Case
Actor, the participant SHOULD record the `(case_id, semantic_type, activity_id)`
triple in its pending-assertion store so that duplicate near-term re-emits of
the same assertion are suppressed while the round-trip is pending. (SYNC-11-002)

When a participant receives a matching `Announce(CaseLedgerEntry)` whose
`log_object_id` equals a pending assertion's `object_id`, the participant
SHOULD clear the matching entry so that future re-emits are no longer
suppressed. (SYNC-11-003)

A pending assertion that exceeds its configured timeout window SHOULD be
marked timed-out and SHOULD no longer suppress future re-emits, allowing
operator retry or the catch-up gate to resubmit the assertion. (SYNC-11-005)

The CASE_MANAGER MUST NOT use the pending-assertion store for its own ledger
commits; the Case Actor's DataLayer idempotency check already guards against
duplicate commits by the single authoritative writer. (SYNC-11-004)

---

## 12. Normative Requirements Reference

This section maps the normative requirements in this document to their
authoritative source identifiers in `specs/sync-ledger-replication.yaml`.

| SYNC ID | Section in this document | Summary |
|---|---|---|
| SYNC-00-005 | §3.2 | Each entry MUST be immutable once committed |
| SYNC-00-006 | §3.1 | Each entry MUST be cryptographically linked to its predecessor |
| SYNC-01-001 | §3.1, §3.2 | Canonical ledger MUST be append-only; entries MUST be immutable |
| SYNC-01-002 | §3.1 | Each entry MUST carry a monotonically increasing, gapless index |
| SYNC-01-003 | §3.1 | Each entry MUST include content hash and predecessor hash |
| SYNC-01-004 | §2.1 | Entries MUST be written through the CASE_MANAGER's write path |
| SYNC-01-005 | §3.3 | Hash-chain format MUST be forward-compatible with Merkle Tree |
| SYNC-02-001 | §4.1 | Replication MUST use `Announce` activities |
| SYNC-02-002 | §4.1 | Each replication message MUST identify sender, recipient, hashes |
| SYNC-02-003 | §4.2 | Replication MUST originate from the CASE_MANAGER |
| SYNC-02-004 | §4.1 | `Announce(CaseLedgerEntry)` MUST carry the entry, inline or by reference |
| SYNC-03-001 | §5.1 | Receiver MUST reject on predecessor hash mismatch |
| SYNC-03-002 | §5.2 | Sender MUST retry from last accepted hash after rejection |
| SYNC-03-003 | §5.3 | Replication MUST be idempotent |
| SYNC-03-004 | §9 | Participants SHOULD include last accepted hash in context |
| SYNC-03-006 | §5.1 | Receiver MUST refuse an entry whose content does not reproduce its hash |
| SYNC-04-001 | §9 | Leader MUST track per-peer last acknowledged hash |
| SYNC-04-002 | §9 | Per-peer state MUST be persisted across leader restart |
| SYNC-05-001 | §10 | Sender SHOULD retry with exponential backoff |
| SYNC-05-002 | §10 | Retry parameters SHOULD be configurable |
| SYNC-05-003 | §10 | Default retry parameters MUST be documented |
| SYNC-05-004 | §10 | Per-recipient timeout MUST be configurable with documented default |
| SYNC-06-003 | §2.1 | Single-node CASE_MANAGER MUST be permanent replication leader |
| SYNC-06-004 | §2.1 | Multi-node cluster is a future extension, out of scope |
| SYNC-08-001 | §3.4 | Append-only integrity: entries uniquely identified by content hash |
| SYNC-08-002 | §3.4 | Deterministic projection: identical log prefix → identical state |
| SYNC-08-003 | §3.4 | Idempotent replay: reprocessing MUST NOT change state |
| SYNC-08-004 | §6.5 | Monotonic visibility: participants MUST NOT regress position |
| SYNC-08-005 | §5.1 | Reject-on-divergence MUST trigger resynchronisation |
| SYNC-09-001 | §7.1 | Entry MUST be durably written before being treated as committed |
| SYNC-09-002 | §7.2 | A sent message MUST be committed only after its outbox write |
| SYNC-09-003 | §7.4 | BT execution MUST be gated on replication leadership |
| SYNC-10-001 | §6.6 | After restart, actor MUST re-establish freshness before new actions |
| SYNC-10-002 | §6.6 | While catching up, actor MUST block protocol-significant actions |
| SYNC-10-004 | §6.6 | Catch-up gate MUST require contiguous prefix from genesis |
| SYNC-10-005 | §6.6 | Catch-up gate MUST NOT require actor tip to equal leader tip |
| SYNC-11-001 | §11 | Participant SHOULD maintain pending-assertion store |
| SYNC-11-002 | §11 | Participant SHOULD record assertion triple after enqueuing |
| SYNC-11-003 | §11 | On matching Announce, SHOULD clear pending entry |
| SYNC-11-004 | §11 | CASE_MANAGER MUST NOT use pending-assertion store for its own commits |
| SYNC-11-005 | §11 | Timed-out pending assertions SHOULD no longer suppress re-emits |
| SYNC-12-001 | §7.3 | Apply domain effects BEFORE persisting entry |
| SYNC-12-002 | §7.3 | Persisted entry MUST imply all effects were applied |
| SYNC-12-003 | §5.3 | Already-stored entry: skip effects and persist |
| SYNC-13-001 | §2.2 | Entry in DataLayer means "committed and effects applied" |
| SYNC-13-002 | §2.2 | Adapter/wire code MUST NOT write CaseLedgerEntry to DataLayer |
| SYNC-13-003 | §4.3 | Ingress MUST NOT use ledger store as scratch for routing |
| SYNC-13-004 | §4.3 | First delivery MUST be recognized without a stored record of the entry |
| SYNC-13-005 | §2.1 | Only the CASE_MANAGER MUST author CaseLedgerEntry records |
| SYNC-13-006 | §2.2 | Participants MUST obtain entries only via Announce receive behavior |
| SYNC-14-001 | §6.2 | Forward-gap entry's received Announce MUST be retained in non-ledger holding area |
| SYNC-14-002 | §6.2 | Held forward-gap entry MUST still trigger Reject |
| SYNC-14-003 | §6.3 | After commit, MUST drain holding area in hash-chain order |
| SYNC-14-004 | §6.3 | Drain MUST apply effects before persisting |
| SYNC-14-005 | §6.4 | Holding area MUST NOT be the canonical ledger |
| SYNC-14-006 | §6.4 | Holding area SHOULD be bounded; evict farthest-ahead on overflow |
| SYNC-14-007 | §6.3 | Drain MUST NOT re-apply effects for already-committed entry |
| SYNC-14-008 | §6.3 | Drain path MUST be the same apply-then-persist path as in-order delivery |
| SYNC-14-009 | §6.3, §8.2 | Drain MUST replay each appliable held Announce, as received, through the receiver's own inbox as its own delivery |
| SYNC-15-001 | §8.1 | Pre-genesis entry MUST NOT be silently dropped; MUST send Reject |
| SYNC-15-002 | §8.1 | Participant MUST NOT persist entry when genesis hash unavailable |
| SYNC-15-003 | §5.4 | CASE_MANAGER MUST bound replay rate for non-advancing peer |
| SYNC-15-004 | §8.2 | Pre-genesis entry's Announce MUST be held pending case seed |
| SYNC-15-005 | §8.2 | After case seed, MUST drain the pre-genesis holds |
| SYNC-15-006 | §8.1 | Pre-genesis entry MUST NOT be treated as committed |
| SYNC-15-007 | §8.1 | Pre-genesis entry domain effects MUST NOT be applied |
| SYNC-15-008 | §5.4 | Leader MUST record per-peer position and timestamp of last non-empty replay |
| SYNC-15-009 | §5.4 | Reject at unchanged position within cooldown MUST NOT trigger replay |
| SYNC-15-010 | §5.4 | Reject at advanced position MUST always trigger replay |
| SYNC-15-011 | §5.4 | Zero-entry replay MUST NOT update recorded position |
| SYNC-15-013 | §5.4 | Cooldown MUST double per no-progress replay, capped; reset on progress |
| SYNC-15-014 | §5.4 | Genesis case pre-seed MUST NOT be sent while its replay is suppressed |
| SYNC-16-001 | §5.5 | Participant MUST report a refused entry that extends its chain as a divergence fault |
| SYNC-16-002 | §5.5 | A fault about applying an entry MUST NOT be ledgered |
| SYNC-16-003 | §5.5 | CASE_MANAGER MUST re-seed an active participant that reports divergence |
| SYNC-16-004 | §5.5 | CASE_MANAGER MUST bound the re-seed rate per peer |
| SYNC-16-005 | §5.5 | A case copy MUST carry the sender's ledger tail |
| SYNC-16-006 | §5.5 | Participant MUST NOT replace its case with a stale or conflicting copy |
| SYNC-16-007 | §5.5 | After replacement, participant MUST backfill to the copy's tail |
| SYNC-16-008 | §5.5 | CASE_MANAGER SHOULD log divergence after a re-seed as an error |

---

## Appendix A: Design Rationale [I]

### A.1 Why a Companion Document

The replication mechanics specified here were scoped to this companion
document rather than included inline in the parent RFC. The rationale is
recorded in ADR-0077: the replication mechanics are technically precise and
lengthy; including them inline would make the RFC too long and operationally
focused for its intended audience of external protocol reviewers. The
Case Hosting capability set's obligation to replicate (`Announce(CaseLedgerEntry)`)
is stable and belongs in the RFC regardless of where the mechanics are
specified; this document supplies the "how."

### A.2 Why Single-Hub / Single-Writer

The single-hub fan-out model was chosen as the normative baseline over
distributed consensus because it is simpler to implement correctly, sufficient
for the current deployment topology (one service actor per case), and
explicitly forward-compatible with a future multi-node Raft cluster without
requiring changes to the wire format or the participant replication path.
The two tiers — CaseActor cluster replication and participant replication —
share the same `Announce(CaseLedgerEntry)` wire format, but serve different
purposes and MUST NOT be conflated. (SYNC-06-004)

### A.3 Why Hash Chain Rather Than Sequence Numbers

Hash-based synchronisation state was preferred over sequence-number-based
synchronisation for two reasons:

1. **Self-verifying**: a receiver can check that a received entry matches its
   stated hash before accepting it, without a separate verification step.
2. **Decoupled from numbering**: synchronisation position is communicated as
   a hash, which decouples it from any particular numbering scheme and
   simplifies replay after log compaction or migration.

### A.4 Why Receiver-Side Buffering for Out-of-Order Entries

The reject/replay round-trip alone does not converge under adversarial
reordering (ADR-0037). Replay re-announces entries individually over the same
unordered transport; they can reorder again and be dropped. Receiver-side
buffering keyed on `prev_log_hash` makes convergence independent of delivery
order: a held entry is applied only when an entry whose `entry_hash`
equals the held entry's `prev_log_hash` is committed, so a fork/rewrite
cannot masquerade as the predecessor.
