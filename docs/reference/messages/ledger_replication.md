# Ledger Replication Messages

The Vultron SYNC substrate replicates the case event log to all active
participants so that each participant's local DataLayer stays consistent with
the canonical log held by the CASE_MANAGER. The mechanism is described in
[ADR-0077](../../adr/0077-ledger-replication-companion-spec.md).

These messages are **infrastructure**, not protocol messages in the
28-shorthand sense. They carry other protocol messages as ledger entries
rather than being a Vultron protocol step in their own right (see
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).

For the acknowledgement semantics see
[Faults and Acknowledgements](faults_and_acknowledgements.md).

## How replication works

1. The CASE_MANAGER commits a new log entry and fans it out:
   `Announce(CaseLedgerEntry)` → each participant.
2. A participant whose local `prev_log_hash` matches the incoming entry's
   `prev_log_hash` silently accepts — hash-chain continuity is the implicit
   positive acknowledgement (MSM-05-002).
3. A participant whose hashes do not match rejects: `Reject(CaseLedgerEntry)`
   with `context` = its last accepted hash, so the CASE_MANAGER can replay the
   gap (SYNC-03-001, SYNC-03-002).

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

print(render_page("ledger_replication", heading=False))
```

---

## Announce Case Ledger Entry

- **Protocol role:** The CASE_MANAGER fans out a newly committed
  `CaseLedgerEntry` to each participant actor for local DataLayer update
  (SYNC-09-002).
- **Triggering transition:** triggered internally after any event is recorded
  to the log — not a protocol shorthand.
- **Wire activity:** `Announce(CaseLedgerEntry)`.
- **Spec:** SYNC-09-002.
- **Pattern:** `AnnounceLogEntryPattern` in
  `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `announce_log_entry_activity` in
  `vultron/wire/as2/factories/sync.py`.
- **Example artifact:** [announce_case_ledger_entry.json](../examples/announce_case_ledger_entry.json).

Each entry carries a content hash and the hash of its predecessor, forming a
chain. A participant verifies the chain on receipt and holds any entry that
arrives before its predecessor in the `LedgerGapBuffer`, applying it when the
predecessor lands (ADR-0037).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import announce_case_ledger_entry, json2md

print(json2md(announce_case_ledger_entry()))
```

---

## Reject Case Ledger Entry

- **Protocol role:** A participant sends this to the CASE_MANAGER when an
  incoming `Announce(CaseLedgerEntry)`'s `prev_log_hash` does not match the
  participant's local ledger tail. The `context` field carries the
  participant's last accepted hash so the CASE_MANAGER can determine which
  entries to replay (SYNC-03-001, SYNC-03-002).
- **Triggering transition:** triggered by hash-chain mismatch detection —
  not a protocol shorthand.
- **Wire activity:** `Reject(CaseLedgerEntry)`.
- **Spec:** SYNC-03-001, SYNC-03-002.
- **Pattern:** `RejectLogEntryPattern` in
  `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `reject_log_entry_activity` in
  `vultron/wire/as2/factories/sync.py`.
- **Example artifact:** [reject_case_ledger_entry.json](../examples/reject_case_ledger_entry.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_case_ledger_entry, json2md

print(json2md(reject_case_ledger_entry()))
```

Buffering takes priority over rejection (ADR-0037). A `Reject` is sent only for an
entry genuinely missing from the chain, never for one that is merely out of order,
so an out-of-order delivery does not start a reject-and-replay cycle.

---

## Case seeding

A participant whose replica is being initialized for the first time — after it
accepts an `Invite`, or after a `Create(CaseProposal)` is accepted — receives
`Announce(VulnerabilityCase)` rather than a ledger entry. Any
`Announce(CaseLedgerEntry)` that arrives before the seed is held in the
`LedgerGapBuffer`, keyed by `prev_log_hash`, and drained once the genesis hash can
be computed from the seeded case (ADR-0059).

- **Pattern:** `AnnounceVulnerabilityCasePattern` in
  `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `announce_vulnerability_case_activity` in
  `vultron/wire/as2/factories/case.py`.
- **Spec:** SYNC-09-001.

The activity and its rendered example are documented under *Announce
Vulnerability Case* on
[Case Management Messages](case_management.md).

---

## See also

- [Case Ledger Synchronization](../../topics/case_lifecycle/case_ledger_sync.md) —
  why the ledger is ordered this way and what the buffering guarantees
- [ADR-0037 — Buffer Out-of-Order Ledger Entries](../../adr/0037-buffer-out-of-order-ledger-entries.md)
- [ADR-0059 — Buffer Pre-Genesis Ledger Entries](../../adr/0059-buffer-pre-genesis-ledger-entries.md)
- Spec: `specs/sync-ledger-replication.yaml` (SYNC-09, SYNC-10, SYNC-14, SYNC-15)
