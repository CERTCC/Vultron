---
status: accepted
date: 2026-08-26
deciders: ahouseholder
consulted: notes/sync-ledger-replication.md, docs/reference/draft-vultron-spec.md
informed: Vultron implementers, external reviewers
---

# Scope Ledger Replication Mechanics to a Companion Spec; Single-Hub Fan-Out Is Normative

## Context and Problem Statement

`docs/reference/draft-vultron-spec.md` §7.2 requires Hosting capability set
implementations to replicate the canonical case ledger to participant actors
via `Announce(CaseLedgerEntry)`. Open Question #2 asked whether the detailed
replication mechanics (hash-chaining, gap detection, ordering guarantees,
consensus) belong inside that RFC or in a separate companion document.

Leaving this unresolved blocked external circulation: reviewers reading the RFC
would find a normative obligation to replicate but no specification of how. The
RFC must either specify the mechanics inline or explicitly scope them out with a
forward reference. Silently leaving replication unspecified is not an option.

## Decision Drivers

- The Hosting capability set's obligation to replicate the ledger is stable and
  belongs in the RFC regardless of where the mechanics are specified.
- The replication mechanics (hash-chain construction, gap detection, out-of-order
  buffering, rejection and replay) are technically precise and lengthy; including
  them inline would make the RFC too long and operationally focused for its
  intended audience.
- The RFC should be circulatable for review without waiting for the full
  replication spec to be complete.
- Single-hub (one CaseActor, single-writer) with fan-out to participants is the
  current normative model; distributed consensus (multi-node Raft-style CaseActor
  cluster) is a future extension that need not block the RFC or the initial
  companion spec.

## Considered Options

1. **Include full replication mechanics inline in the main RFC** — normative and
   visible, but makes the RFC unwieldy and mixes implementation-level detail with
   protocol-level semantics.
2. **Companion document** — the RFC states the normative model and obligation;
   a separate `draft-vultron-replication-spec.md` specifies the mechanics.
3. **Scope out entirely** — the RFC acknowledges replication is required but
   defers all specification to future work, with no companion doc.

## Decision Outcome

Chosen option: **"Companion document"**, because it lets the RFC circulate at
the right level of abstraction while giving the replication mechanics room to
be precise and complete without blocking the main spec.

The RFC retains the normative obligation: Hosting implementations MUST replicate
the canonical case ledger to participant actors. The normative replication model
is **single-hub / single-writer + fan-out**: one CaseActor holds exclusive write
authority, appends to the hash-chained canonical log, and replicates entries to
participant actors via `Announce(CaseLedgerEntry)`.

Distributed consensus (Raft-style multi-node CaseActor cluster) is a future
extension, out of scope for both the main RFC and the initial companion spec.
It is documented as a forward-compatible design path in
`notes/sync-ledger-replication.md`.

### Consequences

- Good, because the RFC can circulate without blocking on replication spec
  completeness — reviewers see the normative model and a forward reference.
- Good, because the companion document can be precise and complete without
  forcing the RFC to carry that weight.
- Good, because the normative model (single-hub / fan-out) is now explicit in
  the RFC, closing the ambiguity that was blocking circulation.
- Neutral, because two documents must now be kept consistent — when SYNC spec
  requirements change, the companion document MUST be updated.

## More Information

Companion document: `docs/reference/draft-vultron-replication-spec.md`
(tracked in issue #2495).

Source issue: CONCERN-2106 — "ledger replication scope (RFC vs companion spec)".
Design rationale: `notes/sync-ledger-replication.md` § "Document Boundary".
