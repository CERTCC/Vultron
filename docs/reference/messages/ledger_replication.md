---
stakeholder_type: [platform-developer, project-contributor]
level: 400
page_type: reference
description: >
  The SYNC substrate that replicates the case ledger (ADR-0077).
---

# Ledger Replication Messages

The Vultron SYNC substrate replicates the case event log to all active
participants so that each participant's local DataLayer stays consistent with
the canonical log held by the CASE_MANAGER. The mechanism is described in
[ADR-0077](../../adr/0077-ledger-replication-companion-spec.md).

These messages are **infrastructure**, not protocol messages in the
28-shorthand sense. They carry other protocol messages as ledger entries
rather than being a Vultron protocol step in their own right (see
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).

For the acknowledgment semantics see
[Faults and Acknowledgments](faults_and_acknowledgements.md).

## How replication works

1. The CASE_MANAGER commits a new log entry and fans it out:
   `Announce(CaseLedgerEntry)` → each participant.
2. A participant first recomputes the entry's hash from its content.
   An entry that does not reproduce its `entry_hash` is refused and logged, with no `Reject` (SYNC-03-006, CLP-04-008).
3. A participant whose local `prev_log_hash` matches the incoming entry's
   `prev_log_hash` silently accepts — hash-chain continuity is the implicit
   positive acknowledgment (MSM-05-002).
4. A participant whose hashes do not match rejects: `Reject(CaseLedgerEntry)`
   with `context` = its last accepted hash, so the CASE_MANAGER can replay the
   gap (SYNC-03-001, SYNC-03-002).

A participant's replica of the case is the replay of its ledger: the case as it stood when the replica was seeded, plus every ledger entry since, applied in ledger order ([ADR-0124](../../adr/0124-case-is-a-projection-of-its-ledger.md), CM-23-016).
A replica applies an entry by copying the objects it carries.
Applying an entry mints no id, reads no clock or local policy, and runs no lifecycle logic, so two replicas at the same ledger position hold identical case files.

Each entry records one activity with its object.
An embargo act's entry carries its whole step on the embargo register: a termination's entry also cancels every open proposal, and an activation's entry also supersedes the embargo it replaces.
Each consent row the CASE_MANAGER changes as a consequence of an act is its own CASE_MANAGER `Create(EmbargoConsent)` or `Update(EmbargoConsent)` entry after the act's entry, and a replica copies that row rather than deciding the change itself (CLP-07-013, EP-09-007).
The same holds for participants: an act that moves a participant's RM state, such as a report verdict, an engagement decision or a Leave, is followed by an `add_participant_status_to_participant` entry for each status the CASE_MANAGER wrote, and a record the CASE_MANAGER creates is its own `Create(CaseParticipant)` entry; a replica copies each, ids and times included (CLP-07-013, CM-23-016).
An embargo or consent entry whose starting state does not match the replica's case is not patched over: the `Announce` that carried it is held as a `HeldLedgerAnnounce`.

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
A participant verifies the chain on receipt and holds the `Announce` of any entry that arrives before its predecessor as a `HeldLedgerAnnounce`, replaying that `Announce` when the predecessor lands (ADR-0037, SYNC-14-009).

---

{% include-markdown "./_occasions/sections/reject-case-ledger-entry.md" %}

- **Context:** the `context` field carries the participant's last accepted hash so the CASE_MANAGER can determine which entries to replay (SYNC-03-001, SYNC-03-002).
- **Triggering transition:** triggered by hash-chain mismatch detection — not a protocol shorthand.
- **Spec:** SYNC-03-001, SYNC-03-002, SYNC-03-005.
- **Pattern:** `RejectLogEntryPattern` in `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `reject_log_entry_activity` in `vultron/wire/as2/factories/sync.py`.
- **Example artifact:** [reject_case_ledger_entry.json](../examples/reject_case_ledger_entry.json).

Buffering takes priority over rejection (ADR-0037).
A `Reject` is sent only for an entry genuinely missing from the chain, never for one that is merely out of order, so an out-of-order delivery does not start a reject-and-replay cycle.

The CASE_MANAGER acts on a `Reject(CaseLedgerEntry)` only when its sender is an active participant in the case (SYNC-03-005, CM-10-004).
From any other sender it reports `REFUSED`, records no replication state, and replays no entry and announces no case to that sender.
The check runs before any write, so a stranger cannot obtain case content by sending a `Reject` with an empty last-accepted hash.

---

## Case seeding

A participant whose replica is being initialized for the first time — after it
accepts an `Invite`, or after a `Create(CaseProposal)` is accepted — receives
`Announce(VulnerabilityCase)` rather than a ledger entry.
Any `Announce(CaseLedgerEntry)` that arrives before the seed is held as a `HeldLedgerAnnounce`, keyed by `prev_log_hash`, and replayed once the genesis hash can be computed from the seeded case (ADR-0059).

- **Pattern:** `AnnounceVulnerabilityCasePattern` in
  `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `announce_vulnerability_case_activity` in
  `vultron/wire/as2/factories/case.py`.
- **Spec:** SYNC-09-001.

The activity and its rendered example are documented under [Announce vulnerability case](case_management.md#announce-vulnerability-case).

---

## See also

- [Case Ledger Synchronization](../../topics/case_lifecycle/case_ledger_sync.md) —
  why the ledger is ordered this way and what the buffering guarantees
- [ADR-0037 — Buffer Out-of-Order Ledger Entries](../../adr/0037-buffer-out-of-order-ledger-entries.md)
- [ADR-0059 — Buffer Pre-Genesis Ledger Entries](../../adr/0059-buffer-pre-genesis-ledger-entries.md)
- Spec: `specs/sync-ledger-replication.yaml` (SYNC-09, SYNC-10, SYNC-14, SYNC-15)
