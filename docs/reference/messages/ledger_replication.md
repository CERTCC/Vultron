# Ledger Replication Messages

The Vultron SYNC substrate replicates the case event log to all active
participants so that each participant's local DataLayer stays consistent with
the canonical log held by the CaseActor. The mechanism is described in
[ADR-0077](../../adr/0077-ledger-replication-companion-spec.md).

These messages are **infrastructure**, not protocol messages in the
28-shorthand sense. They carry other protocol messages as ledger entries
rather than being a Vultron protocol step in their own right (see
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).

For the acknowledgement semantics see
[Faults and Acknowledgements](faults_and_acknowledgements.md).

## How replication works

1. The CaseActor commits a new log entry and fans it out:
   `Announce(CaseLedgerEntry)` → each participant.
2. A participant whose local `prev_log_hash` matches the incoming entry's
   `prev_log_hash` silently accepts — hash-chain continuity is the implicit
   positive acknowledgement (MSM-05-002).
3. A participant whose hashes do not match rejects: `Reject(CaseLedgerEntry)`
   with `context` = its last accepted hash, so the CaseActor can replay the
   gap (SYNC-03-001, SYNC-03-002).

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

print(render_page("ledger_replication", heading=False))
```

---

## Announce Case Ledger Entry

- **Protocol role:** The CaseActor fans out a newly committed
  `CaseLedgerEntry` to each participant actor for local DataLayer update
  (SYNC-09-002).
- **Triggering transition:** triggered internally after any event is recorded
  to the log — not a protocol shorthand.
- **Wire activity:** `Announce(CaseLedgerEntry)`.
- **Spec:** SYNC-09-002.
- **Example artifact:** [announce_case_ledger_entry.json](../examples/announce_case_ledger_entry.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import announce_case_ledger_entry, json2md

print(json2md(announce_case_ledger_entry()))
```

---

## Reject Case Ledger Entry

- **Protocol role:** A participant sends this to the CaseActor when an
  incoming `Announce(CaseLedgerEntry)`'s `prev_log_hash` does not match the
  participant's local ledger tail. The `context` field carries the
  participant's last accepted hash so the CaseActor can determine which
  entries to replay (SYNC-03-001, SYNC-03-002).
- **Triggering transition:** triggered by hash-chain mismatch detection —
  not a protocol shorthand.
- **Wire activity:** `Reject(CaseLedgerEntry)`.
- **Spec:** SYNC-03-001, SYNC-03-002.
- **Example artifact:** [reject_case_ledger_entry.json](../examples/reject_case_ledger_entry.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_case_ledger_entry, json2md

print(json2md(reject_case_ledger_entry()))
```
