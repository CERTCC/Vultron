---
stakeholder_type: [platform-developer, project-contributor]
level: 400
description: >
  The fault trichotomy and the cumulative hash-chain acknowledgment.
---

# Faults and Acknowledgments

The formal Vultron protocol defines per-state-machine error and acknowledgment
shorthands (`RE`/`EE`/`CE`/`GE` for faults; `RK`/`EK`/`CK`/`GK` for
acknowledgments). In the AS2 wire vocabulary, both concerns are served by
mechanisms partitioned on **different axes** from the formal set. Neither is
unimplemented; both are shaped differently.

This page is the primary reference for `Create(ProcessingFault)` and the refusal notice.
It is the second home of two activities documented elsewhere: the ledger negative acknowledgment, [Reject case ledger entry](ledger_replication.md#reject-case-ledger-entry), and [Close report](rm.md#report-closed) as an ordinary `as:Reject` on the fault axis.
The normative mapping is the [Fault and Acknowledgment Mechanism Evolution](../specs/protocol.md#msm-05) requirements group; the design rationale is in [ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md) and [Activity Vocabulary Design](../../topics/activity_vocabulary_design.md).

## Occasions

{% include-markdown "./_occasions/lookup-faults_and_acknowledgements.md" %}

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
| Received, understood, **needs explanation** | `Add(Note → Case)` | `RE` / `EE` / `CE` / `GE` |

{% include-markdown "./_occasions/sections/create-processing-fault.md" heading-offset=1 %}

In the example, a Vendor cannot apply a ledger entry from the CASE_MANAGER whose participant status names an impossible state, and reports the fault to the CASE_MANAGER ([RSH-09-006](../specs/protocol.md#rsh-09-006)).

The formal fault shorthands have no dedicated wire counterpart ([MSM-05-001](../specs/protocol.md#msm-05-001)).

{% include-markdown "./_occasions/sections/refusal-notice.md" heading-offset=1 %}

In the example, the CASE_MANAGER refuses a Vendor's status assertion because a precondition did not hold.

The refusal notice is the one answer a precondition guard's refusal owes the asserting participant ([CLP-05-001](../specs/protocol.md#clp-05-001)).
Its `object` is the refused activity, inline, and `inReplyTo` names that activity's id.
It goes to the asserting participant alone, and its `summary` gives the refusing guard's reason.
Its id is derived from the CASE_MANAGER and the refused activity, so a refused activity is answered once.

The CASE_MANAGER sends it only when a precondition guard refuses the assertion.
It sends none when the sender guard refuses the sender, when the activity repeats one whose effect is already in place, when the activity is a redelivery, or when the case is fully closed ([CLP-02-005](../specs/protocol.md#clp-02-005)).
A refusal is not a case event, so the notice is not ledgered ([CLP-05-002](../specs/protocol.md#clp-05-002)).

The participant closes the pending assertion it recorded for the refused activity ([CLP-06-006](../specs/project.md#clp-06-006)).
It writes no case state and does not send the assertion again.

A `Reject` from the CASE_MANAGER of an `Invite` or an `Offer` the participant sent is both a decline and a refusal.
The two have the same shape, and either way the request had no effect.
The participant reads it with the use case that reads the decline, which closes the pending entry.

### `as:Reject` is overloaded

`as:Reject` carries both error semantics and legitimate protocol refusals
(`close_report`, `reject_invite_to_embargo_on_case`,
`reject_invite_actor_to_case`, `reject_case_proposal`,
`reject_case_ownership_transfer`). A receiver cannot infer "error" from the
verb alone. The `reject_case_ledger_entry` semantic is also an `as:Reject` but
it is the ledger NAK described below — not an ordinary refusal ([MSM-05-003](../specs/protocol.md#msm-05-003)).

---

## Acknowledgment

The formal set defines per-message positive acknowledgments keyed by state
machine: `RK` (RM), `EK` (EM), `CK` (CS), `GK` (General). The AS2
vocabulary splits them into two mechanisms.

### RK — a real wire activity

`RK` (Report Acknowledgment) is realized as `Read(Offer(VulnerabilityReport))`
(`MessageSemantics.ACK_REPORT`). Report submission is not ledger-replicated, so
an explicit per-message acknowledgment is the correct mechanism here.

Status: **direct** mapping — see [MSM-01-008](../specs/protocol.md#msm-01-008).

### EK / CK / GK — cumulative and implicit via hash-chain

`EK`, `CK`, and `GK` have no per-message wire equivalents. Ledger-replicated
state is acknowledged **cumulatively and implicitly** via hash-chain continuity:

- A participant receiving `Announce(CaseLedgerEntry)` whose `prev_log_hash`
  matches its local ledger tail says **nothing** — the match *is* the
  acknowledgment.
- On a mismatch the participant emits `Reject(CaseLedgerEntry)`, whereupon the
  CASE_MANAGER replays all entries after the last accepted hash.

This is negative acknowledgment with gap-fill replay — structurally closer to
TCP cumulative ACK/SACK than to per-message positive acknowledgment. A matching
hash proves receipt of the *entire* log prefix, not only one message.

Status: **evolved** — see [MSM-05-002](../specs/protocol.md#msm-05-002).

#### Liveness

Between `Announce(CaseLedgerEntry)` deliveries, silence and unreachability are
observationally indistinguishable. A participant that has received all entries
and a participant that is unreachable look identical until a new entry arrives.
Implementations MAY rely solely on `Announce` deliveries for liveness inference
without emitting a dedicated periodic heartbeat ([MSM-05-006](../specs/protocol.md#msm-05-006)).

#### NAK path bounding

The replay triggered by `Reject(CaseLedgerEntry)` is rate-limited per peer to prevent amplification; see [SYNC-15-003](../specs/protocol.md#sync-15-003).
The outbox delivery budget ([ADR-0066](../../adr/0066-outbox-terminal-state.md)) provides a finite total-attempt bound independent of the replay rate limit.

---

## See also

- [Activity Vocabulary Design](../../topics/activity_vocabulary_design.md) — why
  faults are partitioned by failure mode and acknowledgment moved to the hash
  chain.
- [How to Report a Protocol Fault](../../howto/activitypub/activities/error.md) — how-to guide
  for fault activities.
- [How to Acknowledge a Report](../../howto/activitypub/activities/acknowledge.md) —
  how-to guide for `RK`.
- [Ledger Replication](ledger_replication.md) — the wire format for
  `Announce(CaseLedgerEntry)` and `Reject(CaseLedgerEntry)`.
