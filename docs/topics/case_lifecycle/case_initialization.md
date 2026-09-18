# Case Initialization

This page explains why the CASE_MANAGER creates every
`VulnerabilityCase`. It also explains how the `CaseProposal` protocol works
and what the exchange looks like on the wire.

---

## Why the vendor does not create the case

When a Vendor receives a vulnerability report, the simple approach is to
send `Create(VulnerabilityCase)` to the Case Actor's inbox. That approach
is wrong.

In ActivityStreams 2.0, `Create(X)` means "I created X." A Vendor that
sends `Create(VulnerabilityCase)` is claiming to be the authoritative
creator of the case. The Vendor is not. The CASE_MANAGER is — it is
the single-writer authority for the canonical ledger, the only peer that
appends to the case history. Putting the Vendor as the `actor` on a
`Create(VulnerabilityCase)` violates that semantics. It assigns the wrong
creator in every downstream replica.

The `CaseProposal` object solves this. The Vendor *proposes* that the Case
Actor create the case. The Case Actor does the creation and sends
`Create(VulnerabilityCase)` with itself as `actor`.

---

## Protocol flow

```text
Vendor                              Case Actor Service
  |                                       |
  | --- Create(CaseProposal) -----------> |
  |         actor: vendor URI             |
  |         object_: as_CaseProposal      |
  |                                       |
  |   [creates case, adds participants,   |
  |    initializes embargo, commits       |
  |    canonical ledger entries]          |
  |                                       |
  | <-- Accept(CaseProposal) ----------- |  (happy path)
  |         actor: case-actor URI         |
  |         object_: as_CaseProposal      |
  |         result: case URI              |
  |                                       |
  | <-- Create(VulnerabilityCase) ------- |
  |         actor: case-actor URI         |
  |         context: case URI             |
  |         in_reply_to: Accept URI       |
  |         [inline participants]         |
  |                                       |
  |    -- OR --                           |
  |                                       |
  | <-- Reject(CaseProposal) ----------- |  (rejection path)
  |         actor: case-actor URI         |
  |         object_: as_CaseProposal      |
```

### Step 1: Vendor sends `Create(CaseProposal)`

The Vendor constructs a `CaseProposal` object containing:

| Field | Description |
|-------|-------------|
| `id_` | Auto-generated URI identifying this proposal |
| `attributed_to` | The Vendor actor's URI |
| `object_` | Inline `VulnerabilityReport` for the proposed case |
| `target` | The Case Actor service URI |
| `summary` | Optional human-readable description |

The Vendor sends `Create(CaseProposal)` to the Case Actor service's inbox,
with `actor=vendor_uri`.

### Step 2a: Case Actor accepts

When the Case Actor accepts the proposal, it performs the full case
initialization as the CASE_MANAGER. It creates the `VulnerabilityCase`, adds
the Vendor as `CASE_OWNER` participant, adds the reporter as a participant,
initializes the default embargo, and commits the canonical ledger entries. It then sends
**two** activities back to the Vendor.

1. **`Accept(CaseProposal)`** — acknowledgment that the proposal was
   accepted. The `result` field carries the URI of the newly created
   `VulnerabilityCase`.

2. **`Create(VulnerabilityCase)`** — the canonical case creation
   announcement.
   - `actor` = Case Actor URI (preserving AS2 "I created this" semantics)
   - `context` = URI of the new `VulnerabilityCase` (consistent with all
     other case-scoped activities; required for inbox routing)
   - `in_reply_to` = URI of the `Accept(CaseProposal)` activity (the causal
     antecedent — what this activity is responding to)

AS2 defines `context` as a **scoping/grouping** field and `inReplyTo` as
the field for **causal antecedents** (see ADR-0045). For this reason,
`in_reply_to` carries the Accept URI, not `context`.

The `Create(VulnerabilityCase)` payload embeds participant objects inline,
not as bare URIs, so the Vendor can seed its local replica without a
DataLayer round-trip to the Case Actor.

### Step 2b: Case Actor rejects

When the Case Actor declines, it sends `Reject(CaseProposal)` with
`object_` embedding the `as_CaseProposal` inline. Embedding the proposal
inline (rather than referencing it by URI) gives the Vendor the full
proposal context without requiring a separate fetch.

The decision itself is a call-out point, `EvaluateCaseProposal` — the
only place a deployment expresses admission policy (CP-05-002). The
default admits, so a service that has wired nothing behaves as it always
did. See the [Capability Model](../capability_model/index.md#case-admission)
for the service contract.

Two ordering properties follow from the decision being a refusal rather
than a preference:

- It runs **before** every step in Step 2a, so a declined proposal leaves
  no case, no participants, and no ledger entries behind.
- The refusal is recorded before it is sent. A decline the Case Actor
  could not deliver reports a processing failure and is retried on the
  next delivery; it never becomes an acceptance. A redelivered proposal is
  answered once, not once per delivery.

The Vendor records the refusal (CP-06-004). The `Reject` carries no
reason today — nothing yet carries one from the decision onto the wire
(see [#3399](https://github.com/CERTCC/Vultron/issues/3399)).

---

## Wire format examples

### Create CaseProposal

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples._base import json2md
from vultron.wire.as2.vocab.examples.case_proposal import create_case_proposal

print(json2md(create_case_proposal()))
```

### Accept CaseProposal

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples._base import json2md
from vultron.wire.as2.vocab.examples.case_proposal import accept_case_proposal

print(json2md(accept_case_proposal()))
```

### Reject CaseProposal

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples._base import json2md
from vultron.wire.as2.vocab.examples.case_proposal import reject_case_proposal

print(json2md(reject_case_proposal()))
```

---

## Case Actor identity

The Case Actor's identity is `{case_actor_service_url}/actors/case-actor`
— one actor per container, with **no per-case suffix**.

There is no per-case suffix because the case identity already travels in the
`context` field of every case-scoped activity. Adding a suffix would make
the Case Actor's address depend on information the container has not yet
seen (the report), which is not computable at provisioning time. An
unprovisioned address produces a permanent 404. No message could start the
`CaseProposal` round-trip (see CP-04-003, BT-10-002).

The `case_actor_service_url` MUST come from actor configuration, not from
the server's own base URL. Using `server_base_url` silently works when both
actors run in the same container but mis-routes in multi-container
deployments (the Vendor sends the proposal to itself). The correct pattern:

```python
from vultron.core.behaviors.case.case_actor_identity import case_actor_identity

case_actor_id = case_actor_identity()
```

In Docker Compose deployments, set:

```yaml
environment:
  - VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=http://case-actor:7999/api/v2
```

---

## Durable delivery and idempotency

The accept path involves two sequenced outbound activities
(`Accept(CaseProposal)` then `Create(VulnerabilityCase)`). If the second
delivery fails after the first succeeds, the Vendor receives an Accept with
no corresponding case announcement.

To recover, the Case Actor writes a durable marker after sending `Accept`
and before sending `Create`. On restart, a startup scan finds outstanding
markers and re-delivers the stored `Create(VulnerabilityCase)` payload
verbatim. Using the stored payload preserves the original activity `id_`,
which the idempotency check relies on to avoid duplicate delivery (CP-05-005).

The same idempotency guard handles duplicate `Create(CaseProposal)` arrivals
from at-least-once delivery: if a `VulnerabilityCase` for the same report
already exists, the Case Actor sends a new `Accept(CaseProposal)` with
`result` pointing to the existing case (CP-05-006).

---

## Demo

!!! example "Try it: `vultron-demo case-proposal`"

    Run this workflow end-to-end with the unified demo CLI:

    ```bash
    vultron-demo case-proposal
    ```

    Or with Docker Compose:

    ```bash
    DEMO=case-proposal docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The demo exercises the full `Create(CaseProposal)` →
    `Accept(CaseProposal)` + `Create(VulnerabilityCase)` round-trip.

---

## See also

- [The Case Model](case_model.md) — `VulnerabilityCase`, participants, and
  the CASE_MANAGER role
- [Ownership Transfer](ownership_transfer.md) — how the `CASE_OWNER` role
  moves between participants
- [ADR-0023](../../adr/0023-case-proposal-protocol.md) — decision record for
  the `CaseProposal` mechanism
- [ADR-0041](../../adr/0041-caseactor-authoritative-case-initialization.md)
  — CaseActor-authoritative case initialization
- [ADR-0045](../../adr/0045-create-vulnerability-case-field-assignment.md) —
  `context` vs `in_reply_to` field assignment
