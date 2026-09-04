# Case Ledger Synchronization

A vulnerability case is coordinated by organizations that do not share a
database. Each one keeps its own copy of the case. This page explains how
those copies stay in agreement, and it answers two questions:

- Who decides the order in which things happened?
- What happens when messages arrive in the wrong order?

Vultron answers the first question with a single writer. It answers the second
by holding an early message until the message it depends on arrives.

---

## One writer, many copies

Every participant in a case keeps a local copy of the case, called a
**replica**. No participant can read or write another participant's replica.
Knowledge travels only in messages — see the
[Actor Knowledge Model](actor-knowledge-model.md).

One peer is different. The **Case Actor** is the service peer that holds the
`CASE_MANAGER` role for the case. It keeps the **case ledger**: the
append-only history that is authoritative for the case. The Case Actor is the
only peer that appends to that history
([CLP-01-003](../reference/specs/protocol.md#clp-01)).

The flow of a change is always the same:

1. A participant sends the Case Actor an assertion — *I accept the embargo*,
   *my report is now validated*, *here is a note*.
2. The Case Actor judges the assertion and appends one entry recording the
   outcome. An entry's `disposition` says whether the assertion was
   `recorded` (accepted) or `rejected`, so a refusal leaves a trace rather
   than a silence.
3. The Case Actor sends the new entry to every participant as
   `Announce(CaseLedgerEntry)`.
4. Each participant records the entry, and applies its effects to its own
   replica if the entry was `recorded`.

Because there is exactly one writer, no participant ever has to reconcile two
competing versions of the case history. There is only one version. A
participant's replica is a projection of that history, not an independent
record.

The same rule applies in reverse: a participant accepts a case update only
from the Case Actor for that case, and rejects an update from any other sender
([PCR-03-001](../reference/specs/protocol.md#pcr-03)). Nobody else can write
to a replica, and the replica's owner does not edit it directly either — even
when that owner is the organization that opened the case.

### Two views of the ledger

The ledger can be read two ways, and most of this page is about the second one.

- The **audit log** is every entry the Case Actor appended, in the order it
  appended them — rejections included.
- The **recorded projection** is the subset whose `disposition` is `recorded`.
  That projection is the authoritative history of the case
  ([CLP-04-001](../reference/specs/protocol.md#clp-04)).

Case state is reconstructed from the recorded projection alone; a replica
ignores rejected entries when working out what is true of the case
([CLP-04-002](../reference/specs/protocol.md#clp-04)). The hash chain is
computed over that projection too
([CLP-04-003](../reference/specs/protocol.md#clp-04)), so a rejection does not
advance the chain: the next recorded entry names the previous *recorded* entry
as its predecessor, not a rejection appended in between.

A rejection is therefore evidence — *the Case Actor saw this assertion and
refused it* — rather than a fact about the case. Where the rest of this page
says "the chain" or "the history", it means the recorded projection.

---

## What a ledger entry carries

Each entry is a small, immutable record. These are the fields that carry the
ordering and integrity guarantees this page is about.

| Field | Meaning |
|---|---|
| `case_id` | The case this entry belongs to |
| `log_index` | Position in the case history; starts at 0 and counts up |
| `published` | When the Case Actor stamped the entry, by its own clock |
| `prevLogHash` | Hash of the previous `recorded` entry |
| `entryHash` | Hash of this entry's own content |
| `payloadSnapshot` | A copy of the assertion the entry records |

`prevLogHash` and `entryHash` link the entries into a chain, like the teeth of
a zipper. Each entry names its predecessor in the recorded projection, so a
receiver can tell whether an entry belongs at the end of the history it already
holds. The first entry in a
case names the **genesis hash**, a value derived from the case object itself,
so the chain is anchored to the case it describes.

---

## Log index is the causal order

The `log_index` sequence *is* the causal order of the case. If the Case Actor
observed event A before event B, then A has the lower `log_index`
([CLP-14-001](../reference/specs/protocol.md#clp-14), ADR-0079). Anything
that needs to know what happened first compares log indexes. It does not
compare clocks.

This matters because clocks disagree. Two organizations on different
continents, running different software, will not agree on the millisecond at
which an event occurred. Sorting a shared history by wall-clock time would make
the order depend on whose clock was fast. Sorting by `log_index` does not.

Timestamps are still recorded, and they are still useful — as corroborating
evidence, and for spotting a participant whose clock is wrong. They are not
the order.

### What the ledger claims, and what it does not

The ledger is authoritative **from the Case Actor's point of view**. It is a
postmark, not a forensic reconstruction. It records the sequence in which the
Case Actor observed and processed events, and it makes no claim about when
those events happened inside another organization
([CLP-15-005](../reference/specs/protocol.md#clp-15)).

- For events the Case Actor generates itself, causal order is known by
  construction: the entries are written one after another on a single path.
- For events reported by participants, the Case Actor's own receive-and-commit
  order is the order. The Case Actor cannot verify a causal claim about
  something it did not see.

The Case Actor never reorders entries to match timestamps supplied by someone
else. Doing so would let external data override the one thing the Case Actor
knows first-hand.

### Rules the Case Actor follows

| Rule | Requirement |
|---|---|
| Order is never reversed: an event observed earlier never gets a higher `log_index` | [CLP-14-001](../reference/specs/protocol.md#clp-14) |
| Every entry carries a timestamp; none may be empty | [CLP-14-002](../reference/specs/protocol.md#clp-14) |
| Timestamps on consecutive recorded entries never move backwards as `log_index` increases | [CLP-14-003](../reference/specs/protocol.md#clp-14) |
| Every entry in a ledger belongs to the same case | [CLP-14-004](../reference/specs/protocol.md#clp-14) |
| No two entries in a case share a `log_index` | [CLP-14-005](../reference/specs/protocol.md#clp-14) |
| No entry predates the case it belongs to | [CLP-14-006](../reference/specs/protocol.md#clp-14) |

Whether the index run may contain holes is not settled. A replica must hold a
contiguous run from the genesis entry through the position it has acknowledged
before it may take new protocol-significant actions on the case
([SYNC-10-004](../reference/specs/protocol.md#sync-10)), and in practice a
receiver treats a hole as a missing entry. But `log_index` is consumed by every
appended entry, rejections included, and rejections are not part of the recorded
projection — so a hole in that projection is not by itself proof of loss.
ADR-0079 states the rule both ways in different sections; the contradiction is
tracked in [#2752](https://github.com/CERTCC/Vultron/issues/2752) and is not
resolved here.

The Case Actor should also refuse an assertion whose own timestamp is far in
the future or far in the past compared to its clock — by default, more than
five minutes ahead or more than seven days old
([CLP-14-007](../reference/specs/protocol.md#clp-14),
[CLP-14-008](../reference/specs/protocol.md#clp-14)). These are sanity
checks, not proof of honesty; a participant with a badly wrong clock can still
produce a well-formed but misleading assertion.

---

## What participants must do

The Case Actor can only record the order it sees. That places an obligation on
each participant: send events in the order they happened.

- If A caused B, send A first
  ([CLP-15-001](../reference/specs/protocol.md#clp-15)).
- Do not collect several related events and send them in an arbitrary order
  ([CLP-15-002](../reference/specs/protocol.md#clp-15)).
- Give B a timestamp no earlier than A's
  ([CLP-15-003](../reference/specs/protocol.md#clp-15)).
- Timestamp an event with when it happened, not when the batch went out or a
  retry was attempted
  ([CLP-15-004](../reference/specs/protocol.md#clp-15)).

A participant that breaks these rules produces a malformed assertion. That is
a fault on the sending side, not a Case Actor failure.

---

## When entries arrive out of order

Ledger entries travel over ordinary message transport, which gives no ordering
guarantee. Vultron may also not be the only implementation on the wire. So a
replica can receive entry 7 before entry 6.

The naive response is to reject entry 7, on the grounds that it does not extend
the chain, and wait for the Case Actor to send it again. That does not work.
The replay travels the same unordered transport and can arrive out of order
again, so under repeated reordering an entry can be lost indefinitely. In an
earlier version of this implementation, that is what stalled a late-joining
vendor at case closure.

Instead, a replica **keeps** an early entry
([ADR-0037](../adr/0037-buffer-out-of-order-ledger-entries.md),
[SYNC-14-001](../reference/specs/protocol.md#sync-14)). It puts the entry
in a holding area and waits for the predecessor. Convergence then no longer
depends on delivery order at all.

### What gets held, and what does not

A replica holds an entry when the entry does not extend its chain but clearly
belongs *later* in the history — its `log_index` is more than one past the end
of what the replica holds. That is a forward gap: the predecessor has not
arrived yet.

Two kinds of entry are not held:

- An entry at or behind the end of the chain. That is a duplicate or a stale
  replay, not a gap.
- An entry exactly one past the end of the chain whose `prevLogHash` does not
  match the hash of the replica's last recorded entry. Nothing is missing in
  front of it, so it is not a gap — it is a fork, a claim about a history the
  replica does not share.

Both go to the ordinary duplicate and divergence handling instead.

Even when it does hold an entry, the replica still sends
`Reject(CaseLedgerEntry)` naming the last entry it accepted
([SYNC-14-002](../reference/specs/protocol.md#sync-14)). Holding solves
reordering; it cannot solve loss. If the missing entry was never delivered at
all, the reject is what prompts the Case Actor to send it again.

The Case Actor does not replay on demand without limit. If a peer keeps
rejecting from the same position, the Case Actor waits out a short cooldown
before replaying to it again
([SYNC-15-003](../reference/specs/protocol.md#sync-15)). Without that bound, a
peer that cannot anchor its chain rejects every entry it is sent, each reject
triggers another full replay, and the two feed each other into a storm. A
reject from a position that *has* advanced always triggers a replay, so a peer
making progress is never held back.

The holding area should also be bounded, so that a hostile or broken peer
streaming far-future entries cannot exhaust memory. When it is full, the replica
discards the entry farthest ahead of the gap and logs a warning
([SYNC-14-006](../reference/specs/protocol.md#sync-14)). Discarding is safe
because the reject for that gap has already been sent — but the eviction itself
sends nothing, so recovery waits on the replay that reject triggers, or on the
next entry that fails to match the tail. The cooldown above may delay either.

The holding area is deliberately **not** the ledger
([SYNC-14-005](../reference/specs/protocol.md#sync-14)). Across Vultron,
the presence of an entry in an actor's own store means *this entry is committed
and its effects are applied*
([SYNC-13-001](../reference/specs/protocol.md#sync-13)). A held entry is
neither, so storing it would break that meaning.

### Entries that arrive before the case

The same holding area covers a related race: an entry can arrive before the
participant has the case object at all. Without the case, the replica cannot
compute the genesis hash and so cannot anchor the chain.

A replica holds these entries too
([SYNC-15-004](../reference/specs/protocol.md#sync-15)), with no gap
comparison — there is no chain yet to compare against, so every entry for the
unknown case is held, including entry 0. When the case is later delivered, the
replica drains the holding area for that case
([SYNC-15-005](../reference/specs/protocol.md#sync-15)). Seeding the case
is enough, because the genesis hash is derived from the case object; the
genesis ledger entry does not have to be re-sent
([ADR-0059](../adr/0059-buffer-pre-genesis-ledger-entries.md)).

### Draining the held entries

Each held entry is filed under the hash of the predecessor it is waiting for.
So after the replica commits a new last entry, finding the successor is a
single lookup: the held entry whose `prevLogHash` equals the hash of the entry
just committed.

The drain then repeats. Commit the successor, look up *its* successor, and
continue until no held entry extends the chain
([SYNC-14-003](../reference/specs/protocol.md#sync-14)). A run of ten
entries that arrived in reverse order clicks into place in one cascade, in
`log_index` order.

Three properties make the drain safe:

- **Same path.** A drained entry goes through the same processing as an entry
  that arrived in order — no separate code path with its own behavior
  ([SYNC-14-008](../reference/specs/protocol.md#sync-14)). In this
  implementation that means the drain re-runs the announce receive behavior
  tree on each held entry, in `log_index` order.
- **Effects before storage.** The entry's consequences — an embargo ending, a
  participant joining, a status changing — are applied first, and the entry is
  stored only if they all succeed
  ([SYNC-12-001](../reference/specs/protocol.md#sync-12),
  [SYNC-14-004](../reference/specs/protocol.md#sync-14)).
- **Applied once.** An entry already in the local ledger is skipped entirely,
  so a replay or a duplicate cannot apply the same effects twice
  ([SYNC-12-003](../reference/specs/protocol.md#sync-12),
  [SYNC-14-007](../reference/specs/protocol.md#sync-14)).

Because held entries are replayed through the ordinary path, the
reject-and-replay recovery becomes order-tolerant as well, at no extra cost.

---

## Why state checks wait for the drain

Holding an entry has a consequence that is easy to get wrong. Case State (CS)
has ordering rules of its own: an **ephemeral** state cannot be a resting
place, so it has exactly one permitted successor and must be followed by it;
the recorded history must remain a valid sequence throughout; and a move to
public awareness must be recorded before the embargo termination that it
triggers.

If a replica checked those rules at the moment an entry *arrived*, an
out-of-order entry would look like a violation. An entry naming a state that is
only reachable from its predecessor would appear to arrive from nowhere.

That is why the checks run at drain time instead
([CSB-19-001](../reference/specs/protocol.md#csb-19)). A held entry is
parked before any case-state effect is applied, so the state machine is never
touched at arrival time. When the gap closes, the entries replay in
`log_index` order — which is causal order — and the guards see them in the
sequence they were meant to be seen in.

An entry waiting in the holding area therefore raises no state violation at
all ([CSB-19-002](../reference/specs/protocol.md#csb-19)). An entry naming an
ephemeral state is perfectly well-formed on its own; it would only be a real
violation if the entry that resolves it never arrived. Flagging it on arrival
would be a false alarm, and rejecting it would prevent the replica from ever
converging.

The public-awareness-before-embargo-termination ordering survives reordering
for free ([CSB-19-003](../reference/specs/protocol.md#csb-19)). The Case Actor
commits the public-awareness entry first, so it holds the lower `log_index`.
The drain works in `log_index` order, so it can never present the termination
entry first. No receiver-side re-check of the timing is needed; the order in
the ledger is sufficient.

---

## What a replica guarantees

Taken together, the ledger rules and the holding area give each participant
these properties:

| Property | Meaning |
|---|---|
| Append-only | A committed entry is immutable and identified by its content hash |
| Deterministic projection | The same run of entries produces the same state in every conforming implementation |
| Idempotent replay | Re-processing entries already seen changes nothing |
| Monotonic progress | A replica never regresses the position it has acknowledged |
| Reject on divergence | An entry that does not extend the chain is not silently accepted |
| Order-independent convergence | Delivery order does not affect the final state |

The result is eventual consistency with a strong bound: given the same
entries, every replica reaches the same state as the Case Actor, no matter what
order those entries arrived in.

The holding area itself is in memory only, and is lost on restart. That is
deliberate: nothing in it is committed, so a restart cannot cost the replica
anything it had already accepted. The dropped entries themselves come back the
same way an evicted one does — the next entry that does not match the replica's
tail produces a `Reject`, and the Case Actor replays from the position that
reject names.

---

## Further reading

- [The Case Model](case_model.md) — the case, its participants, and the
  Case Actor's role
- [Actor Knowledge Model](actor-knowledge-model.md) — why nothing can be
  learned except by receiving a message
- [CS Process Model](process_models/cs/index.md) — the case-state rules the
  drain-time checks enforce
- [Protocol specifications](../reference/specs/protocol.md) — the normative
  requirements behind this page, including CLP-01, CLP-04, CLP-14, CLP-15,
  CSB-19, PCR-03, SYNC-10, and SYNC-12 through SYNC-15
- [Glossary](../reference/glossary.md) — definitions for case ledger, replica,
  genesis hash, and the replication phases
- [ADR-0079](../adr/0079-case-ledger-causal-ordering.md) — Case Actor
  observation order is the canonical causal order
- [ADR-0037](../adr/0037-buffer-out-of-order-ledger-entries.md) — hold
  out-of-order entries instead of discarding them
- [ADR-0059](../adr/0059-buffer-pre-genesis-ledger-entries.md) — hold entries
  that arrive before the case
