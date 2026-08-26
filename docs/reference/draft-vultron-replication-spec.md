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
canonical ledger owned by one authoritative Case Actor. This document
specifies the mechanics by which that ledger is maintained and replicated to
all Participant Actors: the hash-chain construction, replication transport,
conflict handling, gap detection and recovery, ordering guarantees, and the
normative single-hub / single-writer + fan-out architecture.

These mechanics are scoped to a companion document by design. The Vultron
Protocol Specification (`docs/reference/draft-vultron-spec.md`) states the
normative obligation — Hosting capability set implementations MUST replicate
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
- **Replication transport** — how the Case Actor delivers entries to
  Participant Actors via `Announce(CaseLedgerEntry)` activities.
- **Conflict handling and recovery** — the reject-and-replay protocol that
  re-synchronises a diverged replica.
- **Gap detection and ordering guarantees** — the receiver-side buffer that
  makes convergence independent of delivery order.
- **Commit discipline** — the invariant that external messages are emitted
  only after a ledger entry is committed.
- **Normative replication architecture** — the single-hub / single-writer +
  fan-out model as the baseline.

Distributed consensus for multi-node Case Actor clusters (a future extension)
is out of scope for this version of the document.

### 1.2 Relationship to Other Documents

| Document | Role |
|---|---|
| `docs/reference/draft-vultron-spec.md` | Parent RFC; states the normative obligation to replicate and delegates mechanics here |
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

**The normative replication model for Vultron is single-hub / single-writer + fan-out.** One Case Actor holds exclusive write authority over the canonical case ledger. It is the sole authorised source of `CaseLedgerEntry` records for its cases. All Participant Actors receive ledger entries from the Case Actor; they do not write to it. (SYNC-01-004, SYNC-13-005)

This model is a degenerate single-node Raft cluster. The Case Actor is
permanently the leader; no leader election is required or performed in
single-node deployments. In single-node deployments the Case Actor MUST be
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

Log replication between the Case Actor and Participant Actors MUST use
ActivityStreams `Announce` activities as the transport envelope.
Specifically, each replicated entry is delivered as
`Announce(CaseLedgerEntry)`. (SYNC-02-001)

Each `Announce(CaseLedgerEntry)` activity:

- MUST embed the full inline `CaseLedgerEntry` object in its `object` field.
  A URI-only reference MUST NOT be used, because the recipient needs all
  entry fields (`prev_log_hash`, `entry_hash`) to validate the hash chain
  without an additional round-trip to the sender's store. (SYNC-02-004)
- MUST identify the sender, the target recipient, the log entry hash, and the
  predecessor hash. (SYNC-02-002)

### 4.2 Replication Origin

Replication MUST originate from the replication leader — the actor holding
the `CASE_MANAGER` role — and MUST be sent to each Participant Actor
individually, not broadcast. (SYNC-02-003)

### 4.3 Semantic Routing on First Delivery

Semantic routing of an inbound `Announce(CaseLedgerEntry)` MUST resolve to
the log-entry semantic using the typed inline object obtained during parsing,
without requiring a DataLayer round-trip on first delivery. Message ingress
MUST NOT use the canonical ledger store as a scratch or lookup cache for
routing, rehydration, or classification of an inbound announce. (SYNC-13-003,
SYNC-13-004)

---

## 5. Conflict Handling and Recovery [N]

### 5.1 Reject on Hash Mismatch

A receiver MUST reject a replication message whose predecessor hash
(`prev_log_hash`) does not match the receiver's current log tail hash.
The receiver sends `Reject(CaseLedgerEntry)` carrying its last accepted hash
as the recovery signal. (SYNC-03-001, SYNC-08-005)

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

The Case Actor MUST bound the rate at which it replays entries to a peer
whose acknowledged replication position has not advanced. (SYNC-15-003)

Specifically:

- The Case Actor MUST record, per peer, the position (`entry_hash` or `""`
  for genesis) and timestamp of the last replay in which at least one entry
  was actually sent. (SYNC-15-008)
- A Reject reporting an unchanged replication position within the cooldown
  window MUST NOT trigger another replay. (SYNC-15-009)
- A Reject reporting an advanced replication position MUST always trigger a
  replay, regardless of cooldown. (SYNC-15-010)
- A replay in which zero entries were sent MUST NOT update the recorded
  position. (SYNC-15-011)

The genesis position (`last_accepted_hash == ""`) SHOULD use a shorter
cooldown than a mid-chain stall, to avoid starving the initial bootstrap
while still preventing amplification.

---

## 6. Ordering Guarantees and Out-of-Order Delivery [N]

### 6.1 No Ordering Guarantee at the Transport Layer

`Announce(CaseLedgerEntry)` activities are delivered over a transport with no
guaranteed ordering. A participant replica can therefore receive an entry
before its hash-chain predecessor has arrived. Dropping such an entry and
relying solely on the reject/replay round-trip does not converge under
adversarial reordering, because replay re-announces entries individually over
the same unordered transport.

### 6.2 Receiver-Side Gap Buffer

When a participant receives a valid `Announce(CaseLedgerEntry)` whose
`prev_log_hash` does not match its current chain tail, but whose `log_index`
is strictly greater than `tail_index + 1` (a forward gap), the participant
MUST NOT permanently discard the entry. It MUST retain the entry in a
non-ledger holding area, keyed by `prev_log_hash`, pending arrival of its
predecessor. (SYNC-14-001)

A forward-gap entry that is buffered MUST still trigger resynchronisation:
the participant MUST send `Reject(CaseLedgerEntry)` carrying its last accepted
hash, so the Case Actor can replay entries that are genuinely lost (not merely
reordered). (SYNC-14-002)

### 6.3 Drain on Predecessor Commit

After a participant commits a `CaseLedgerEntry`, it MUST drain the holding
area. For each newly committed tail, the participant MUST locate the buffered
entry (if any) whose `prev_log_hash` equals the new tail's `entry_hash`,
apply and persist that entry via the same apply-then-persist path as in-order
delivery, and repeat, cascading until no buffered entry extends the current
tail. (SYNC-14-003, SYNC-14-008)

Draining a buffered entry MUST apply domain effects before persisting it.
(SYNC-14-004)

The drain path MUST NOT re-apply effects for an entry already present in the
local ledger. (SYNC-14-007)

### 6.4 Buffer Bounds

The out-of-order holding area MUST NOT be the canonical ledger/DataLayer
store. A buffered entry MUST NOT be persisted as a `CaseLedgerEntry` until it
is drained (i.e. until its predecessor is present), so that presence of a
`CaseLedgerEntry` in the DataLayer continues to mean "committed and effects
applied." (SYNC-14-005, SYNC-13-001)

The holding area SHOULD be bounded in size per case. When full it SHOULD
evict the entry farthest ahead of the current gap (highest `log_index`) and
log a warning. Eviction is recoverable because the Reject required by
§6.2 was already sent. (SYNC-14-006)

### 6.5 Monotonic Visibility

Participants MUST NOT regress their acknowledged log position. (SYNC-08-004)

### 6.6 Catch-Up Freshness Gate

After actor process restart or recovery, an actor with case state in scope
MUST re-establish case-ledger freshness with the Case Actor before taking new
protocol-significant case actions. (SYNC-10-001)

While catch-up freshness is not established, the actor MUST block or defer
new protocol-significant case actions and surface an explicit
stale-or-catching-up condition. (SYNC-10-002)

The catch-up gate MUST require a contiguous canonical log prefix from genesis
through the actor's currently acknowledged tip. Any gap in that prefix MUST
block protocol-significant case actions. (SYNC-10-004)

The catch-up gate MUST NOT require the actor's acknowledged tip to equal the
Case Actor's current ledger tip. Lagging behind the leader tip is permitted if
the actor's own acknowledged prefix is contiguous from genesis. (SYNC-10-005)

---

## 7. Commit Discipline [N]

### 7.1 Commit Semantics

A log entry is committed when it has been durably written to the authoritative
log and its content hash has been recorded. An entry that has not met these
conditions MUST NOT be applied to the case state machine. (SYNC-09-001)

In a single-node Case Actor deployment, every append is an immediate commit.
No replication quorum is required.

### 7.2 Emit-After-Commit Invariant

External Vultron messages (activities sent to Participant Actors or other
protocol participants) MUST only be emitted after the associated
`CaseLedgerEntry` is committed. (SYNC-09-002)

This ensures that activities a node claims to have taken are durably recorded
and cannot be rolled back by a leadership change.

### 7.3 Effects-Before-Persist Invariant

A participant MUST apply all domain effects derived from a `CaseLedgerEntry`
(embargo teardown, participant-status update, note attachment, invite
acceptance) BEFORE persisting the entry to its local ledger. If any effect
fails, the entry MUST NOT be persisted. (SYNC-12-001)

The presence of a `CaseLedgerEntry` in a participant's local ledger MUST
imply that all domain effects for that entry were successfully applied.
(SYNC-12-002)

### 7.4 Behavior-Tree Execution Gate

The Case Actor's behavior tree execution MUST be gated on holding the
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
`last_accepted_hash = ""` to the Case Actor so that the Case Actor replays all
entries from the beginning once the case is delivered. (SYNC-15-001)

A `CaseLedgerEntry` received when the per-case genesis hash is unavailable
MUST NOT be persisted (SYNC-15-002), MUST NOT be treated as committed
(SYNC-15-006), and its domain effects MUST NOT be applied (SYNC-15-007).

### 8.2 Pre-Genesis Buffer and Drain

The participant MUST NOT rely solely on the reject/replay round-trip for
pre-genesis entries. It MUST retain the entry in the same non-ledger holding
area used for forward gaps (§6.2), keyed by `prev_log_hash`, pending arrival
of the case seed. (SYNC-15-004)

After a participant seeds the `VulnerabilityCase` (via `Create` or
`Announce(VulnerabilityCase)`), which anchors the deterministic per-case
genesis hash, it MUST drain the holding area for that case: it MUST locate
the buffered entry (if any) whose `prev_log_hash` equals the per-case genesis
hash, apply-and-persist it via the same path as in-order delivery, and
cascade in hash-chain order until no buffered entry extends the current tail.
(SYNC-15-005)

---

## 9. Per-Peer Replication State [N]

The replication leader MUST track per-peer state including at minimum the
last acknowledged log entry hash for each peer. (SYNC-04-001)

Per-peer replication state MUST be persisted so that it survives a leader
restart. (SYNC-04-002)

When a Participant Actor sends any message to the Case Actor, it SHOULD
include the hash of its last accepted canonical log entry as a parameter in
the activity's `context` field. This allows the Case Actor to proactively
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
store that records outbound assertion activities emitted toward the Case Actor
but not yet confirmed by a canonical `Announce(CaseLedgerEntry)` round-trip.
The suppression window is configurable; zero disables suppression. (SYNC-11-001)

After a participant successfully enqueues an assertion activity toward the Case
Actor, the participant SHOULD record the `(case_id, event_type, activity_id)`
triple in its pending-assertion store so that duplicate near-term re-emits of
the same assertion are suppressed while the round-trip is pending. (SYNC-11-002)

When a participant receives a matching `Announce(CaseLedgerEntry)` whose
`log_object_id` equals a pending assertion's `object_id`, the participant
SHOULD clear the matching entry so that future re-emits are no longer
suppressed. (SYNC-11-003)

A pending assertion that exceeds its configured timeout window SHOULD be
marked timed-out and SHOULD no longer suppress future re-emits, allowing
operator retry or the catch-up gate to resubmit the assertion. (SYNC-11-005)

The Case Actor MUST NOT use the pending-assertion store for its own ledger
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
| SYNC-01-002 | §3.1 | Each entry MUST carry a monotonically increasing index |
| SYNC-01-003 | §3.1 | Each entry MUST include content hash and predecessor hash |
| SYNC-01-004 | §2.1 | Entries MUST be written through the CASE_MANAGER's write path |
| SYNC-01-005 | §3.3 | Hash-chain format MUST be forward-compatible with Merkle Tree |
| SYNC-02-001 | §4.1 | Replication MUST use `Announce` activities |
| SYNC-02-002 | §4.1 | Each replication message MUST identify sender, recipient, hashes |
| SYNC-02-003 | §4.2 | Replication MUST originate from the CASE_MANAGER |
| SYNC-02-004 | §4.1 | `Announce(CaseLedgerEntry)` MUST embed full inline entry |
| SYNC-03-001 | §5.1 | Receiver MUST reject on predecessor hash mismatch |
| SYNC-03-002 | §5.2 | Sender MUST retry from last accepted hash after rejection |
| SYNC-03-003 | §5.3 | Replication MUST be idempotent |
| SYNC-03-004 | §9 | Participants SHOULD include last accepted hash in context |
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
| SYNC-09-002 | §7.2 | External messages MUST only be emitted after ledger commit |
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
| SYNC-13-004 | §4.3 | Routing MUST use typed inline object, not DataLayer round-trip |
| SYNC-13-005 | §2.1 | Only the CaseActor MUST author CaseLedgerEntry records |
| SYNC-13-006 | §2.2 | Participants MUST obtain entries only via Announce receive behavior |
| SYNC-14-001 | §6.2 | Forward-gap entry MUST be retained in non-ledger holding area |
| SYNC-14-002 | §6.2 | Buffered forward-gap entry MUST still trigger Reject |
| SYNC-14-003 | §6.3 | After commit, MUST drain holding area in hash-chain order |
| SYNC-14-004 | §6.3 | Drain MUST apply effects before persisting |
| SYNC-14-005 | §6.4 | Holding area MUST NOT be the canonical DataLayer store |
| SYNC-14-006 | §6.4 | Holding area SHOULD be bounded; evict farthest-ahead on overflow |
| SYNC-14-007 | §6.3 | Drain MUST NOT re-apply effects for already-committed entry |
| SYNC-14-008 | §6.3 | Drain path MUST be the same apply-then-persist path as in-order delivery |
| SYNC-15-001 | §8.1 | Pre-genesis entry MUST NOT be silently dropped; MUST send Reject |
| SYNC-15-002 | §8.1 | Participant MUST NOT persist entry when genesis hash unavailable |
| SYNC-15-003 | §5.4 | CASE_MANAGER MUST bound replay rate for non-advancing peer |
| SYNC-15-004 | §8.2 | Pre-genesis entry MUST be buffered pending case seed |
| SYNC-15-005 | §8.2 | After case seed, MUST drain pre-genesis buffer |
| SYNC-15-006 | §8.1 | Pre-genesis entry MUST NOT be treated as committed |
| SYNC-15-007 | §8.1 | Pre-genesis entry domain effects MUST NOT be applied |
| SYNC-15-008 | §5.4 | Leader MUST record per-peer position and timestamp of last non-empty replay |
| SYNC-15-009 | §5.4 | Reject at unchanged position within cooldown MUST NOT trigger replay |
| SYNC-15-010 | §5.4 | Reject at advanced position MUST always trigger replay |
| SYNC-15-011 | §5.4 | Zero-entry replay MUST NOT update recorded position |

---

## Appendix A: Design Rationale [I]

### A.1 Why a Companion Document

The replication mechanics specified here were scoped to this companion
document rather than included inline in the parent RFC. The rationale is
recorded in ADR-0077: the replication mechanics are technically precise and
lengthy; including them inline would make the RFC too long and operationally
focused for its intended audience of external protocol reviewers. The
Hosting capability set's obligation to replicate (`Announce(CaseLedgerEntry)`)
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
order: a buffered entry is applied only when an entry whose `entry_hash`
equals the buffered entry's `prev_log_hash` is committed, so a fork/rewrite
cannot masquerade as the predecessor.
