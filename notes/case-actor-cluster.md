---
title: CaseActor Cluster — Multi-Node Ledger Replication Plan
status: active
kind: plan
tracks:
  - "#1165"
  - "#1157"
description: >
  Unbuilt design for a multi-node CaseActor cluster (Raft) that gives the
  CASE_MANAGER high-availability write authority: what is settled, how it maps to
  AS2, and what is still open.
related_specs:
  - specs/sync-ledger-replication.yaml
related_notes:
  - notes/sync-ledger-replication.md
  - notes/encryption.md
---

# CaseActor Cluster — Multi-Node Ledger Replication Plan

Today one CaseActor is the single writer of each case ledger, which is a
single-node Raft cluster: permanently the leader, every append an immediate
commit. See [sync-ledger-replication.md](sync-ledger-replication.md). This note
plans the N-node generalization.

## Two replication tiers, never conflated

1. **CaseActor cluster replication** keeps several CaseActor instances in sync
   for high-availability write authority. That is the Raft tier, and it is unbuilt.
2. **Participant replication** delivers the canonical log from the leader to
   participants. That is built (SYNC-02 through SYNC-15).

Both use the `Announce(CaseLedgerEntry)` wire format.

## Settled during planning

- **Shape**: N CaseActor instances form a Raft cluster. The leader alone writes
  and emits case protocol actions. Followers replicate the log and emit nothing.
- **Single node stays first-class**: a cluster of 1 MUST remain a supported
  configuration. The cluster generalizes it and does not replace it.
- **Standard election**: log completeness only (highest `(term, log_index)`
  wins), no priority tiebreaker. Pre-vote is a later optimization.
- **Static membership**: cluster size is deployment configuration. Dynamic
  membership is out of scope.
- **Commit**: an entry commits once a majority of cluster peers acknowledge it.
  `Announce(CaseLedgerEntry)` still follows its commit (SYNC-09-002), so
  participant fan-out stays downstream of the commit index.
- **`term`**: `CaseLedgerEntry.term` is optional now and becomes required here.
- **Leadership guard and leadership vs. ownership**: the cluster supplies a real
  Raft check behind the `is_leader` seam; the single-node rules are in
  [sync-ledger-replication](sync-ledger-replication.md) § Architecture Overview.

## AS2 mapping

Cluster messages share the ActivityPub inbox with CVD messages, under their own
`MessageSemantics` values. New objects use existing AS2 verbs.

| Raft function | AS2 activity |
|---|---|
| AppendEntries | `Announce(CaseLedgerEntry)` |
| Heartbeat | `Announce(CaseActorHeartbeat)` (new object) |
| Vote request | `Question(OneOf)` |
| Vote granted | `Accept(Question)` |
| Vote denied | `Reject(Question)` |
| Leader declaration | `Announce(CaseActorLeadership)` (new object) |

## Open questions

- **Log compaction**: does the log grow without bound, and how would old entries
  be archived while keeping the hash-chain anchor?
- **Key management**: every CaseActor and node eventually needs a cryptographic
  identity (#1156). Key generation, distribution, rotation, revocation and trust
  anchors (pinned keys or PKI) should be designed before cluster work starts.
- **Membership and routing**: how instances are created and attached to a case,
  how they find each other, and how a participant finds the leader (#1165).
