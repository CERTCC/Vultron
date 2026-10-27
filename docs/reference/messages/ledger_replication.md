---
stakeholder_type: [platform-developer, project-contributor]
level: 400
page_type: reference
subject: protocol
description: >
  The SYNC substrate that replicates the case ledger (ADR-0077).
---

# Ledger Replication Messages

The Vultron SYNC substrate copies the case event log to all active participants.
This keeps each participant's local DataLayer consistent with the canonical log that the CASE_MANAGER holds.
[ADR-0077](../../adr/0077-ledger-replication-companion-spec.md) describes the mechanism.

These messages are **infrastructure**, not protocol messages in the 28-shorthand sense.
They carry other protocol messages as ledger entries, and are not a Vultron protocol step themselves (see [ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).

[Faults and Acknowledgments](faults_and_acknowledgements.md) gives the acknowledgment semantics.

## How replication works

1. The CASE_MANAGER commits a new log entry and sends it to each participant as `Announce(CaseLedgerEntry)`.
2. A participant first recomputes the entry's hash from its content.
   An entry that does not reproduce its `entry_hash` is refused and logged, with no `Reject` (SYNC-03-006, CLP-04-008).
   The participant sends the CASE_MANAGER a `Create(ProcessingFault)` with failure class `LedgerEntryRefused/HashMismatch` instead (SYNC-03-007).
   The CASE_MANAGER sends nothing back for it, because a replay would resend the same content (SYNC-03-008).
3. A participant whose local `prev_log_hash` matches the incoming entry's `prev_log_hash` accepts it and sends nothing.
   An unbroken hash chain is the implied positive acknowledgment (MSM-05-002).
4. A participant whose hashes do not match sends `Reject(CaseLedgerEntry)` with `context` = its last accepted hash.
   With that hash, the CASE_MANAGER can replay the gap (SYNC-03-001, SYNC-03-002).
5. A participant that wants to check its ledger is current states its position: `Read(CaseLedgerEntry)` naming the last entry it applied.
   The CASE_MANAGER records that position and replays every entry after it (SYNC-17-001, SYNC-17-004).

A participant's replica of the case is the replay of its ledger.
It is the case as it stood when the replica was seeded, plus every ledger entry since, applied in ledger order ([ADR-0124](../../adr/0124-case-is-a-projection-of-its-ledger.md), CM-23-016).
A replica applies an entry by copying the objects it carries.
Applying an entry mints no id, reads no clock or local policy, and runs no lifecycle logic.
So two replicas at the same ledger position hold identical case files.

Each entry records one activity with its object.
An embargo act's entry carries its whole step on the embargo register.
A termination's entry also cancels every open proposal.
An activation's entry also supersedes the embargo it replaces.

When an act causes the CASE_MANAGER to change a consent row, that change is its own entry after the act's entry.
That entry is a CASE_MANAGER `Create(EmbargoConsent)` or `Update(EmbargoConsent)`.
A replica copies that row and does not decide the change itself (CLP-07-013, EP-09-007).

The same holds for participants.
Some acts move a participant's RM state, such as a report verdict, an engagement decision or a Leave.
Such an act is followed by an `add_participant_status_to_participant` entry for each status the CASE_MANAGER wrote.
A record the CASE_MANAGER creates is its own `Create(CaseParticipant)` entry.
A replica copies each of these, ids and times included (CLP-07-013, CM-23-016).

The replica does not patch over an embargo or consent entry whose starting state does not match the replica's case.
It holds the `Announce` that carried that entry as a `HeldLedgerAnnounce`.
When that entry extends the replica's chain and the case is not already past it, the replica's case has diverged.
The replica then sends the CASE_MANAGER a `Create(ProcessingFault)` with failure class `LedgerEntryRefused/CaseDiverged` (SYNC-16-001).
From an active participant, the CASE_MANAGER answers that fault with `Announce(VulnerabilityCase)` of its current case, which names its ledger position, so the replica can replace its case and store the held entry (SYNC-16-003).
It re-seeds one peer at most once per cooldown, so a replica that refuses several entries in a row gets one copy, and a later fault still gets another (SYNC-16-004).
Neither fault is committed to a case ledger, by the replica or by the CASE_MANAGER (SYNC-16-002).

## Occasions

{% include-markdown "./_occasions/lookup-ledger_replication.md" %}

---

{% include-markdown "./_occasions/sections/announce-case-ledger-entry.md" %}

- **Triggering transition:** triggered internally after any event is recorded to the log — not a protocol shorthand.
- **Spec:** SYNC-09-002.
- **Pattern:** `AnnounceLogEntryPattern` in `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `announce_log_entry_activity` in `vultron/wire/as2/factories/sync.py`.
- **Example artifact:** [announce_case_ledger_entry.json](../examples/announce_case_ledger_entry.json).

Each entry carries a content hash and the hash of its predecessor, forming a chain.
A participant checks the chain when an entry arrives.
It holds the `Announce` of any entry that arrives before its predecessor as a `HeldLedgerAnnounce`.
It replays that `Announce` when the predecessor arrives (ADR-0037, SYNC-14-009).

---

{% include-markdown "./_occasions/sections/reject-case-ledger-entry.md" %}

- **Context:** the `context` field carries the participant's last accepted hash so the CASE_MANAGER can determine which entries to replay (SYNC-03-001, SYNC-03-002).
- **Triggering transition:** triggered by hash-chain mismatch detection — not a protocol shorthand.
- **Spec:** SYNC-03-001, SYNC-03-002, SYNC-03-005.
- **Pattern:** `RejectLogEntryPattern` in `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `reject_log_entry_activity` in `vultron/wire/as2/factories/sync.py`.
- **Example artifact:** [reject_case_ledger_entry.json](../examples/reject_case_ledger_entry.json).

A participant that holds no entry has none to reject.
If its case is replaced by a copy ahead of its chain, it sends a `Reject` with no `object`, an empty `context` and the case as its `target`.
That `Reject` asks for a replay from genesis (SYNC-16-007).
A `Reject` with no `object` and a non-empty `context` is refused when it is parsed.

Buffering takes priority over rejection (ADR-0037).
A participant sends a `Reject` only for an entry that is really missing from the chain, never for one that is only out of order.
So an out-of-order delivery does not start a reject-and-replay cycle.

The CASE_MANAGER acts on a `Reject(CaseLedgerEntry)` only when its sender is an active participant in the case (SYNC-03-005, CM-10-004).
From any other sender it reports `REFUSED`, records no replication state, and replays no entry and announces no case to that sender.
The check runs before any write, so a stranger cannot obtain case content by sending a `Reject` with an empty last-accepted hash.

---

{% include-markdown "./_occasions/sections/read-case-ledger-entry.md" %}

- **Object:** the last canonical entry the participant has applied, by reference: its id, not the entry.
- **Context:** the case.
- **`ledgerPosition`:** the named entry's `logIndex` and `entryHash`, so the CASE_MANAGER can tell a lag from a position its ledger does not hold (SYNC-17-001).
- **Triggering transition:** the participant's own policy, not a protocol shorthand. The reference participant sends one for each case it holds after every restart, and on `ledger.position_statement_interval_seconds` when that is set, which is off by default (SYNC-17-007).
- **Spec:** SYNC-17-001 through SYNC-17-007.
- **Pattern:** `ReadLogEntryPattern` in `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `read_ledger_entry_activity` in `vultron/wire/as2/factories/sync.py`.
- **Example artifact:** [read_case_ledger_entry.json](../examples/read_case_ledger_entry.json).

`Read(CaseLedgerEntry)` is the participant's position statement.
`Read` states a fact and asks for nothing, so it claims no refusal, where a `Reject` would.
It covers the case the `Reject` loop cannot: when the last `Announce(CaseLedgerEntry)` before a quiet period is lost, no later entry arrives with a gap, and no `Reject` is ever sent ([ADR-0155](../../adr/0155-a-participant-states-its-ledger-position-and-the-case-manager-answers-a-lag.md)).
A participant that has applied no entry for the case has none to name and sends no `Read`.

The CASE_MANAGER's answer is the one it gives a `Reject`.
It records the named entry's hash as the sender's acknowledged position (SYNC-17-003).
When that position is behind its ledger tail, it sends the sender every entry after it, in log order, as `Announce(CaseLedgerEntry)`, under the same replay rate bound and outbox de-duplication as a `Reject`-triggered replay (SYNC-17-004).
At the tail it sends nothing.

It answers only an active participant (SYNC-17-002, CM-10-004).
A removed, unconsented or closed participant's `Read` is `REFUSED`, with no replication state recorded and nothing sent.
A position the CASE_MANAGER's ledger does not hold, or an index at which its entry has a different hash, is logged at WARNING and answered with nothing (SYNC-17-005).
A `Read` and its answer are never ledgered: stating a position changes nothing in the case file (SYNC-17-006).

---

## Case seeding

A participant whose replica starts for the first time receives `Announce(VulnerabilityCase)`, not a ledger entry.
This happens after it accepts an `Invite`, or after a `Create(CaseProposal)` is accepted.
The participant holds any `Announce(CaseLedgerEntry)` that arrives before the seed as a `HeldLedgerAnnounce`, keyed by `prev_log_hash`.
It replays that `Announce` when it can compute the genesis hash from the seeded case (ADR-0059).

- **Pattern:** `AnnounceVulnerabilityCasePattern` in
  `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `announce_vulnerability_case_activity` in
  `vultron/wire/as2/factories/case.py`.
- **Spec:** SYNC-09-001.

Each `Announce(VulnerabilityCase)` carries the case with its `ledgerPosition`: the `logIndex` and `entryHash` of the last ledger entry its case file reflects (SYNC-16-005).
A participant that already holds the case judges the copy by that position.
The participant skips a copy it is already past.
It refuses a copy that names a different entry at an index the participant holds.
Any other copy replaces the case, position included (SYNC-16-006).

After a replacement whose position is ahead of its chain, the participant sends `Reject(CaseLedgerEntry)` naming its own tail.
It stores each entry the copy already reflects as a no-op, and does not move its case's position back (SYNC-16-007).

The activity and its rendered example are documented under [Announce vulnerability case](case_management.md#announce-vulnerability-case).

---

## See also

- [Case Ledger Synchronization](../../topics/case_lifecycle/case_ledger_sync.md) —
  why the ledger is ordered this way and what the buffering guarantees
- [ADR-0037 — Buffer Out-of-Order Ledger Entries](../../adr/0037-buffer-out-of-order-ledger-entries.md)
- [ADR-0059 — Buffer Pre-Genesis Ledger Entries](../../adr/0059-buffer-pre-genesis-ledger-entries.md)
- Spec: `specs/sync-ledger-replication.yaml` (SYNC-09, SYNC-10, SYNC-14, SYNC-15, SYNC-17)
