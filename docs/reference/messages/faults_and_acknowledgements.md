# Faults and Acknowledgements

The formal Vultron protocol defines per-state-machine error and acknowledgement
shorthands (`RE`/`EE`/`CE`/`GE` for faults; `RK`/`EK`/`CK`/`GK` for
acknowledgements). In the AS2 wire vocabulary, both concerns are served by
mechanisms partitioned on **different axes** from the formal set. Neither is
unimplemented; both are shaped differently.

For the normative mapping see `specs/message-semantics-mapping.yaml` MSM-05.
For the design rationale see
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)
and `notes/message-type-reference.md`.

---

## Fault reporting

The formal set partitions faults by **which state machine** the unexpected
message belonged to (`RE`, `EE`, `CE`, `GE`). The AS2 vocabulary partitions
faults by **why the message failed** — an axis that is actionable to a receiver
in a way that state-machine origin is not.

| Failure mode | Wire activity | Formal counterpart |
|---|---|---|
| Received and **not understood** | `Create(ProcessingFault)` | `RE` / `EE` / `CE` / `GE` |
| Received, understood, **declined** | `as:Reject` | `RE` / `EE` / `CE` / `GE` |
| Received, understood, **needs explanation** | `Create(Note)` / `Add(Note → Case)` | `RE` / `EE` / `CE` / `GE` |

Status: **evolved** — the formal shorthands have no dedicated wire counterpart;
see MSM-05-001.

### `as:Reject` is overloaded

`as:Reject` carries both error semantics and legitimate protocol refusals
(`close_report`, `reject_invite_to_embargo_on_case`,
`reject_invite_actor_to_case`, `reject_case_proposal`,
`reject_case_ownership_transfer`). A receiver cannot infer "error" from the
verb alone. The `reject_case_ledger_entry` semantic is also an `as:Reject` but
it is the ledger NAK described below — not an ordinary refusal (MSM-05-003).

---

## Acknowledgement

The formal set defines per-message positive acknowledgements keyed by state
machine: `RK` (RM), `EK` (EM), `CK` (CS), `GK` (General). The AS2
vocabulary splits them into two mechanisms.

### RK — a real wire activity

`RK` (Report Acknowledgement) is realised as `Read(Offer(VulnerabilityReport))`
(`MessageSemantics.ACK_REPORT`). Report submission is not ledger-replicated, so
an explicit per-message acknowledgement is the correct mechanism here.

Status: **direct** mapping — see MSM-01-008.

### EK / CK / GK — cumulative and implicit via hash-chain

`EK`, `CK`, and `GK` have no per-message wire equivalents. Ledger-replicated
state is acknowledged **cumulatively and implicitly** via hash-chain continuity:

- A participant receiving `Announce(CaseLedgerEntry)` whose `prev_log_hash`
  matches its local ledger tail says **nothing** — the match *is* the
  acknowledgement.
- On a mismatch the participant emits `Reject(CaseLedgerEntry)`, whereupon the
  CaseActor replays all entries after the last accepted hash
  (`RejectLedgerEntryReceivedUseCase`,
  `vultron/core/use_cases/received/sync.py`).

This is negative acknowledgement with gap-fill replay — structurally closer to
TCP cumulative ACK/SACK than to per-message positive acknowledgement. A matching
hash proves receipt of the *entire* log prefix, not just one message.

Status: **evolved** — see MSM-05-002.

#### Liveness

Between `Announce(CaseLedgerEntry)` deliveries, silence and unreachability are
observationally indistinguishable. A participant that has received all entries
and a participant that is unreachable look identical until a new entry arrives.
Implementations MAY rely solely on `Announce` deliveries for liveness inference
without emitting a dedicated periodic heartbeat (MSM-05-006).

#### NAK path bounding

The replay triggered by `Reject(CaseLedgerEntry)` is rate-limited per peer
(30 s cooldown, 2 s at genesis) to prevent amplification; see SYNC-15-003. The
outbox delivery budget (ADR-0066) provides a finite total-attempt bound
independent of the replay rate limit.

---

## See also

- `docs/reference/messages/faults_and_acknowledgements.md` is the primary page
  for `reject_case_ledger_entry` (SYNC mechanism and ledger NAK, MSM-05-002)
  and `close_report` (ordinary `as:Reject` on the fault axis, MSM-05-003).
- [Error Handling](../../howto/activitypub/activities/error.md) — how-to guide
  for fault activities.
- [Acknowledging a Report](../../howto/activitypub/activities/acknowledge.md) —
  how-to guide for `RK`.
- [Ledger Replication](../../howto/activitypub/activities/ledger_replication.md) —
  how-to guide for `Announce(CaseLedgerEntry)`.
