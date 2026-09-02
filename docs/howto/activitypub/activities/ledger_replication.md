# Ledger Replication and Case Seeding

{% include-markdown "../../../includes/not_normative.md" %}

These activities implement the CaseActor's canonical log replication pipeline.
After each new log entry is committed to the case ledger, the CaseActor fans out
`Announce(CaseLedgerEntry)` to every participant. Participants buffer out-of-order
entries and drain them once their hash-chain predecessor arrives (ADR-0037).
When a new participant joins for the first time, the CaseActor seeds their replica
with `Announce(VulnerabilityCase)` (ADR-0059).

See also:

- [Case Ledger Synchronization](../../../topics/case_ledger_sync.md) — why the
  ledger is ordered this way and what the buffering guarantees
- [ADR-0037 — Buffer Out-of-Order Ledger
  Entries](../../../adr/0037-buffer-out-of-order-ledger-entries.md)
- [ADR-0059 — Buffer Pre-Genesis Ledger
  Entries](../../../adr/0059-buffer-pre-genesis-ledger-entries.md)
- [ADR-0077 — Ledger Replication Companion
  Spec](../../../adr/0077-ledger-replication-companion-spec.md)
- Spec: `specs/sync-ledger-replication.yaml` (SYNC-09, SYNC-10, SYNC-14, SYNC-15)

## Announce(CaseLedgerEntry) — Log Replication

The CaseActor is the single-writer authority for the canonical case ledger. After
committing each `CaseLedgerEntry`, it broadcasts the entry to all case participants
via `Announce(CaseLedgerEntry)`.

Each entry includes a content hash and the hash of its predecessor, forming a
Merkle chain. Participants verify the chain on receipt and buffer any entry that
arrives before its predecessor.

```mermaid
sequenceDiagram
    participant CA as Case Actor
    participant P1 as Participant 1
    participant P2 as Participant 2
    CA ->> P1: Announce(CaseLedgerEntry)
    CA ->> P2: Announce(CaseLedgerEntry)
    note over P1,P2: Verify hash chain; apply or buffer
```

**Pattern**: `AnnounceLogEntryPattern` in
`vultron/wire/as2/extractor/_instances.py`

**Factory**: `announce_log_entry_activity` in `vultron/wire/as2/factories/sync.py`

```python
from vultron.wire.as2.factories.sync import announce_log_entry_activity

activity = announce_log_entry_activity(
    entry,        # as_CaseLedgerEntry
    actor=case_actor_id,
    to=[participant_actor_id],
)
```

## Reject(CaseLedgerEntry) — Hash-Chain Mismatch

When a participant receives an `Announce(CaseLedgerEntry)` whose `prev_log_hash`
does not match its local tail hash (and the entry cannot be resolved as a
forward-gap via buffering), it sends `Reject(CaseLedgerEntry)` back to the
CaseActor. The `context` field carries the participant's last accepted entry hash
so the CaseActor can replay the missing prefix.

!!! info "Buffering takes priority (ADR-0037)"

    A `Reject` is only sent for entries that are genuinely missing from the
    chain — not for entries that are merely out of order. Out-of-order entries
    are held in the `LedgerGapBuffer` and applied when their predecessor arrives,
    avoiding a spurious reject-replay cycle.

**Pattern**: `RejectLogEntryPattern` in
`vultron/wire/as2/extractor/_instances.py`

**Factory**: `reject_log_entry_activity` in `vultron/wire/as2/factories/sync.py`

```python
from vultron.wire.as2.factories.sync import reject_log_entry_activity

activity = reject_log_entry_activity(
    entry,                  # as_CaseLedgerEntry (the rejected entry)
    context=last_good_hash, # last accepted entry hash
    actor=participant_id,
    to=[case_actor_id],
)
```

## Announce(VulnerabilityCase) — Case Seeding

When a participant's replica is being initialized for the first time (e.g., after
they accept an `Invite` or after a `Create(CaseProposal)` is accepted), the
CaseActor sends `Announce(VulnerabilityCase)` to seed the replica. This is the
participant's authoritative copy of the case, including all current participants
and status.

Any `Announce(CaseLedgerEntry)` activities that arrive before the case seed are
buffered in the `LedgerGapBuffer` (keyed by `prev_log_hash`) and drained
automatically once the genesis hash can be computed from the seeded case
(ADR-0059).

**Pattern**: `AnnounceVulnerabilityCasePattern` in
`vultron/wire/as2/extractor/_instances.py`

**Factory**: `announce_vulnerability_case_activity` in
`vultron/wire/as2/factories/case.py`

```python
from vultron.wire.as2.factories.case import announce_vulnerability_case_activity

activity = announce_vulnerability_case_activity(
    case,               # as_VulnerabilityCase (with inline participants)
    actor=case_actor_id,
    to=[participant_actor_id],
)
```

## Reference

- Patterns: `vultron/wire/as2/extractor/_instances.py` — `AnnounceLogEntryPattern`,
  `RejectLogEntryPattern`, `AnnounceVulnerabilityCasePattern`
- Factories: `vultron/wire/as2/factories/sync.py` —
  `announce_log_entry_activity`, `reject_log_entry_activity`
- Factory: `vultron/wire/as2/factories/case.py` —
  `announce_vulnerability_case_activity`
- Spec: `specs/case-event-log-synchronization.yaml` (SYNC-03, SYNC-09, SYNC-10,
  SYNC-15)
