## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

## 2026-03-26 Replicated Log Synchronization design notes

> **Status**: Captured in `notes/sync-log-replication.md` (created 2026-03-30)
> and plan tasks SYNC-1 through SYNC-4. See those files for the full design.
> The original content below is retained for reference but superseded.

~~Build a distributed append-only log with eventual consistency using
RAFT-inspired primitives, leveraging AS2 Announce activities as the transport
layer. The CaseActor (acting as a de facto lead) maintains authoritative case
event history and replicates it to Participant Actors (followers) via log
synchronization. Implement this in phases: (SYNC-1) local append-only log
with indexing, (SYNC-2) one-way replication with strict conflict handling
(reject mismatched prev_log_index, retry with decremented index), (SYNC-3)
full sync loop with retry/backoff, and (SYNC-4) multi-peer synchronization
with per-peer replication state. This approach treats the log as the system
of record—all case state is a projection of logged events—and ensures that
all replicas eventually converge to identical histories without requiring
leader election or membership changes.~~
→ captured in `notes/sync-log-replication.md`

~~Place replication logic in core domain (for example you might consider
transport-agnostic `CaseEventLog`, `ReplicationState`, `LogSyncEngine`, and
`ConsistencyRules` classes); implement AS2 Announce mappings and persistence
in adapters (outbound Announce, inbound handler responses, file/database log
storage). Use idempotent log appends, message deduplication by event ID, and
causal timestamp ordering to handle duplicates and out-of-order delivery.
Define explicit replication ports (`OutboundReplicationPort`,
`InboundReplicationPort`) to maintain hexagonal architecture boundaries.
Avoid premature commitment to leader election or actor mobility; Phase SYNC-2
can introduce soft leadership (preferred writer) and Phase SYNC-3 and SYNC-4
can add full RAFT with quorum commit once the log foundation is solid and
well-tested across 2–3 node scenarios.~~
→ captured in `notes/sync-log-replication.md`

~~SYNC-2 will need to rectify the concept of "leadership" with the existing
concept of Case Owner, which is a separate concern. Case Ownership is about
who gets to control the case lifecycle and make certain decisions, whereas
replication leadership is about which node is currently responsible for
accepting writes to the log and replicating them to followers. We need to
ensure that these concepts are clearly delineated and do not conflict with
each other as we evolve the design. In the future, a case ownership transfer
likely implies that replication leadership will also change, but a leadership
change alone does not imply an ownership transfer.~~
→ captured in `notes/sync-log-replication.md`

~~More important to SYNC-1 will be shoring up the idea that a case is mostly
a log of events that have occurred either locally or remotely, and that there
is an authoritative sequence of what has happened that is maintained by the
CaseActor and replicated to other participants. This is conceptually aligned
with our intent in Vultron that all participants maintain a shared
understanding of the case history and state, but it does conflict with
earlier documentation like `docs/howto/case_object.md` that describes the
log as a nice-to-have rather than a core part of the case model. This will
also force us to reconsider a case log as the source of truth for the case
state, with other case attributes like status being a static reflection of
the most-recently-received updates to the case log rather than being
entirely independent data blobs that could go out of sync with the log if
not updated.~~
→ captured in `notes/sync-log-replication.md`

---

## 2026-03-26 Current active priority

PRIORITY-250 (pre-300 cleanup) is now the active focus. Tasks in order:
NAMING-1, QUALITY-1, SECOPS-1, DOCMAINT-1, REORG-1. D5-1 (architecture
review for multi-actor demos) may proceed in parallel with PRIORITY-250.
D5-2 and later demo tasks are explicitly blocked until PRIORITY-250 is
complete (per `plan/PRIORITIES.md`).

The trigger→received→sync information flow (participants trigger state
changes → the resulting messages arrive at CaseActor's inbox as "received"
events → sync replicates the updated case log to all participants) should be
documented as part of REORG-1.

---

## 2026-03-30 Flaky test: test_remove_embargo

The test `test_remove_embargo` in
`test/wire/as2/vocab/test_vocab_examples.py` was previously identified as
flaky and was referenced in `specs/testability.md` TB-06-006. That
reference has been removed from the spec (specs should not track transient
issues). The flakiness MUST be resolved before PRIORITY-300 demo work
begins. Relates to TB-06-006 in `specs/testability.md`.
