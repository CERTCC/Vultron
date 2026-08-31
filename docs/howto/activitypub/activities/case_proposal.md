# CaseProposal Flow

{% include-markdown "../../../includes/not_normative.md" %}

The CaseProposal flow is the mechanism by which an actor (typically a Vendor or
Coordinator) requests that a dedicated Case Actor service create and manage a new
case. Rather than creating the case directly, the proposing actor sends a
`Create(CaseProposal)` to the Case Actor's inbox. The Case Actor evaluates the
proposal and either accepts (creating the `VulnerabilityCase` natively) or
rejects it.

This preserves correct ActivityStreams 2.0 semantics: only the authoritative
creator — the Case Actor — is the `actor` on the `Create(VulnerabilityCase)`
activity.

See also: [ADR-0023 — Introduce `CaseProposal` for Distributed Case Actor
Initialization](../../../adr/0023-case-proposal-protocol.md).

## Protocol Flow

```mermaid
sequenceDiagram
    actor V as Proposing Actor
    participant CA as Case Actor
    V ->>+ CA: Create(CaseProposal)
    note over CA: Evaluate proposal
    alt Accept
        CA -->> V: Accept(CaseProposal)
        CA -->> V: Create(VulnerabilityCase, actor=CaseActor)
        note over V: Case seeded; vendor replica initialized
    else Reject
        CA -->> V: Reject(CaseProposal)
        note over V: No case created
    end
    deactivate CA
```

## Create CaseProposal

The proposing actor (e.g. a Vendor) sends a `Create(as_CaseProposal)` to the
Case Actor service's inbox. The `as_CaseProposal` object carries:

- `attributed_to`: the proposing actor's URI
- `object_`: an inline `VulnerabilityReport` describing the case to be created
- `target`: the Case Actor service URI
- `summary` (optional): a human-readable description

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples._base import json2md
from vultron.wire.as2.vocab.examples.case_proposal import create_case_proposal

print(json2md(create_case_proposal()))
```

## Accept CaseProposal

When the Case Actor accepts the proposal, it sends two activities back to the
proposing actor:

1. `Accept(as_CaseProposal)` — acknowledging the proposal was accepted. The
   `result` field carries the URI of the newly created `VulnerabilityCase`.
2. `Create(VulnerabilityCase)` — the canonical case creation announcement, with
   inline participants so the vendor can seed its local replica without a
   DataLayer round-trip.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples._base import json2md
from vultron.wire.as2.vocab.examples.case_proposal import accept_case_proposal

print(json2md(accept_case_proposal()))
```

## Reject CaseProposal

When the Case Actor declines the proposal (e.g. insufficient information,
duplicate, or out-of-scope), it sends:

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples._base import json2md
from vultron.wire.as2.vocab.examples.case_proposal import reject_case_proposal

print(json2md(reject_case_proposal()))
```

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
    `Accept(CaseProposal)` + `Create(VulnerabilityCase)` round-trip
    (see `vultron/demo/exchange/case_proposal_demo.py`).

## Reference

- Vocab examples: `vultron/wire/as2/vocab/examples/case_proposal.py`
- ADR: [ADR-0023](../../../adr/0023-case-proposal-protocol.md)
- Spec: `specs/case-proposal.yaml` (CP-01 through CP-09)
