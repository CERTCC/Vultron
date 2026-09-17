# Case Ownership Transfer

This page explains why case ownership transfers route through the Case
Actor. It describes what that routing looks like on the wire and what
remains open for the rejection path.

---

## Why routing through the Case Actor matters

Before ADR-0053, the ownership-transfer protocol had two routing gaps:

1. **Offer sent directly to transferee** — the offering actor addressed the
   `Offer(VulnerabilityCase)` directly to the transferee's inbox, bypassing
   the Case Actor. No `CaseLedgerEntry` was written for the offer. Participants
   not involved in the negotiation received no notification that a transfer
   was in progress.

2. **Accept sent directly to offerer** — the accepting actor addressed the
   `Accept` to the offerer's inbox, bypassing the Case Actor.
   No `CaseLedgerEntry` was written after the role change. The broadcast to
   all participants never fired.

Both gaps share the same root cause: the Case Actor was not in the message
path, so no ledger entry was committed and no `Announce(CaseLedgerEntry)` was
sent. Participants who were not direct parties to the negotiation had no way
to learn that the case's ownership had changed.

The fix is simple: **both activities MUST route through the Case Actor**,
for the same reason all case-scoped messages route there — so that the
CASE_MANAGER can record the event in the canonical ledger and broadcast the
result to every participant.

---

## Correct routing model

### Offer flow

```text
Offering actor sends trigger: offer-case-ownership-transfer
  → Case Actor sends Offer(VulnerabilityCase, target=transferee)
      actor:        case_actor_id       (delegated-message contract)
      attributed_to: offering_actor_id
      to:           [case_actor_id]     ← MUST route through Case Actor (CM-21-005)

Case Actor inbox receives Offer:
  1. Records the Offer.
  2. Commits CaseLedgerEntry (offer-recorded).
  3. Announce(CaseLedgerEntry) → all participants.   ← all parties learn the offer
  4. Forwards Offer to transferee's inbox.
```

The Offer is sent *to* the Case Actor's inbox — not directly to the
transferee. The Case Actor processes it, writes a ledger entry, broadcasts
the entry to all participants so everyone knows an offer is in flight, and
then forwards the Offer to the transferee.

The `actor` on the forwarded Offer is the Case Actor (not the original
offerer). The original offerer's identity is carried in `attributed_to`.
This preserves the delegated-message contract (CM-24-001 through CM-24-004)
and ensures the ledger's `payloadSnapshot.actor` is the CASE_MANAGER, which
is the field the ledger integrity checks validate.

### Accept flow

```text
Accepting actor sends trigger: accept-case-ownership-transfer
  → Accept(Offer(VulnerabilityCase))
      to: [case_actor_id]     ← MUST route through Case Actor (CM-21-006)

Case Actor inbox receives Accept:
  1. Applies the CASE_OWNER role change (CM-21-001 through CM-21-004).
  2. Commits CaseLedgerEntry (ownership-transferred).   ← CM-21-007
  3. Announce(CaseLedgerEntry) → all participants.
```

The accepting actor addresses the `Accept` to the Case Actor's inbox — not
to the offerer. The Case Actor applies the role change, commits the ledger
entry, and broadcasts the result. The `Announce(CaseLedgerEntry)` delivery path updates the accepting actor's
own replica. No special hand-delivery is needed.

---

## Wire format examples

### Offer Case Ownership Transfer

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import offer_case_ownership_transfer, json2md

print(json2md(offer_case_ownership_transfer()))
```

### Accept Case Ownership Transfer

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import accept_case_ownership_transfer, json2md

print(json2md(accept_case_ownership_transfer()))
```

### Reject Case Ownership Transfer

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_case_ownership_transfer, json2md

print(json2md(reject_case_ownership_transfer()))
```

---

## Analogy: Invite/Accept handshake

This routing model is identical to the Invite/Accept handshake (ADR-0026):

| Invite/Accept | Ownership Transfer |
|---|---|
| `Invite` sent **by** Case Actor | `Offer` addressed **to** Case Actor → forwarded |
| `Accept(Invite)` addressed **to** Case Actor | `Accept(Offer)` addressed **to** Case Actor |
| Case Actor creates `CaseParticipant` | Case Actor applies CASE_OWNER role change |
| `CaseLedgerEntry` → broadcast | `CaseLedgerEntry` → broadcast |

In both patterns, the Case Actor is the intermediary because it is the only
actor authorized to write to the canonical ledger and the only actor whose
writes reach all participants via `Announce(CaseLedgerEntry)`.

---

## Open question: rejected transfers

CM-21-010 establishes that a `Reject(Offer(VulnerabilityCase))` is addressed
to the Case Actor's inbox — symmetric with the Accept path. What the Case
Actor does *on receiving* that rejection is not yet specified:

- **Is the rejection ledgered?** The Accept path commits a `CaseLedgerEntry`
  and broadcasts `Announce(CaseLedgerEntry)` (CM-21-007). Whether a declined
  transfer earns a ledger entry of its own, or leaves no canonical trace, is
  unresolved.
- **Does the offerer learn of the rejection?** With the Reject addressed to
  the Case Actor rather than the offerer, the offerer is not a direct
  recipient. A notification hop (or a ledger broadcast) would be needed for
  the offerer to discover the decline.
- **Is the case re-offerable?** Whether a rejected Offer can be re-issued to
  the same or a different transferee, and whether any state cleanup is
  required first, is unspecified.

Resolving these questions will likely add received-side CM-21 entries and may
warrant an extension to ADR-0053.

---

## Demo

!!! example "Try it: `vultron-demo transfer-ownership`"

    Run this workflow end-to-end with the unified demo CLI:

    ```bash
    vultron-demo transfer-ownership
    ```

    Or with Docker Compose:

    ```bash
    DEMO=transfer-ownership docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The demo POSTs the `Offer` to the Case Actor's inbox, waits for the Case
    Actor's forwarded `Offer` to reach the transferee, and addresses the
    `Accept` back to the Case Actor.

    The forwarded `Offer` is a **new** activity with its own `id`, so the
    demo finds it by matching on properties (type, `target`, `object`)
    rather than by looking up the original offer's `id`, which exists only in
    the Case Actor's store.

---

## See also

- [The Case Model](case_model.md) — `VulnerabilityCase`, participants, and
  the `CASE_OWNER` role
- [Case Initialization](case_initialization.md) — how the Case Actor creates
  the case via the `CaseProposal` protocol
- [Case Ledger Synchronization](case_ledger_sync.md) — how
  `Announce(CaseLedgerEntry)` propagates events to all participants
- [ADR-0053](../../adr/0053-ownership-transfer-routed-via-caseactor.md) —
  decision record for CASE_MANAGER-routed ownership transfer
- [ADR-0026](../../adr/0026-caseactor-routed-actor-suggestion.md) —
  CaseActor-routed actor suggestion and invitation flow (the Invite/Accept
  analogy)
