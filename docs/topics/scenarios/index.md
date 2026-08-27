---
title: Demo Scenario Narratives
status: stable
---

# Demo Scenario Narratives

This section contains Explanation-style narratives for the nine multi-actor CVD
workflow scenarios exercised by the Vultron demo suite.  Each narrative
describes a complete case lifecycle in domain terms — the who, what, and why of
each protocol step — without reference to implementation details such as
container names, API endpoints, or helper function signatures.

Together these narratives serve as a **conformance oracle**: the declared causal
edges are machine-readable, version-controlled statements of what the protocol
is *supposed* to produce.  Because they are written independently of the code,
they can contradict the implementation, which is precisely what makes them
useful for catching regressions (see [ADR-0058](../../adr/0058-causal-gating-in-demo-scenarios.md)
and [ADR-0079](../../adr/0079-case-ledger-causal-ordering.md)).

## Scenarios

| Short name | Participants | Notable protocol feature |
|---|---|---|
| [FV](fv.md) | Finder + Vendor | Baseline two-actor CVD |
| [FVV](fvv.md) | Finder + Vendor1 + Vendor2 | Direct invitation of a second vendor |
| [FCV](fcv.md) | Finder + Coordinator + Vendor | Coordinator-mediated report and vendor onboarding |
| [FCV-reject](fcv-reject.md) | Finder + Coordinator (Vendor rejects) | Invite rejection path |
| [FCVCV](fcvcv.md) | Finder + C1 + V1 + C2 + V2 | Actor-suggestion flow (ADR-0026) |
| [FVCV-extension](fvcv-extension.md) | Finder + Vendor1 + Coordinator + Vendor2 | Coordinator-suggested second vendor |
| [FVCV-handoff](fvcv-handoff.md) | Finder + Vendor1 → Coordinator + Vendor2 | Case-ownership transfer to coordinator |
| [FCCV-extension](fccv-extension.md) | Finder + C1 + C2 + Vendor | Second coordinator suggests vendor |
| [FCCV-handoff](fccv-handoff.md) | Finder + C1 → C2 + Vendor | Ownership transfer between two coordinators |

## Machine-readable causal edge schema

Each narrative page carries a `causal_edges:` list in its YAML front-matter.
Every entry declares one protocol causal relationship that must be observable in
the case ledger.

```yaml
causal_edges:
  - antecedent: <event_type>     # string — eventType in the case ledger
    consequent: <event_type>     # string — eventType in the case ledger
    consequent_actor: <name>     # human label for the committing actor
    note: <text>                 # optional human-readable explanation
    observable: true             # optional; false marks unobservable edges
```

**Fields:**

- `antecedent` — the `eventType` string of the causally-earlier ledger entry.
- `consequent` — the `eventType` string of the causally-later ledger entry.
- `consequent_actor` — documentary label identifying which participant commits
  the consequent event; used in diagnostic output when a check fails.
- `note` — optional prose explanation of the causal relationship.
- `observable` — defaults to `true`.  Set to `false` for edges whose antecedent
  or consequent is not directly captured as a case-ledger entry (for example,
  the reporter submitting a report to the receiver's API is not itself a ledger
  event).  Unobservable edges are documented here for completeness but are
  excluded from the automated ordering check.

## Invariant check (DEMOMA-22-005)

The CI harness at `test/ci/invariants/` reads each narrative's `causal_edges:`
list and asserts that for every observable edge `(A, B)` there exist ledger
entries `a` with `eventType == A` and `b` with `eventType == B` such that
`a.log_index < b.log_index`.  The check uses the case-actor's authoritative
replica, which is the canonical causal order (ADR-0079).

Diagnostic output on failure names the unsatisfied edge and the log indices
that were observed, so the failure message is self-explanatory.

Unobservable edges (`observable: false`) are skipped during ordering checks
and never cause a failure.

## Update-together rule (DEMOMA-22-006)

The causal edges declared in a narrative page and the scenario's invariant test
file (`test/ci/invariants/test_<name>_invariants.py`) are a **matched pair**.

When you change a scenario's causal flow — by adding a protocol step, reordering
steps, or removing a participant — you must update **both** the narrative's
`causal_edges:` list and, if the change adds a new `eventType` that should
always be present, the scenario's `_XXX_EXPECTED_EVENT_TYPES` list in its
invariant file.  Changing one without the other leaves the conformance oracle
out of date.

The invariant that reads the narrative (test 16) will catch a stale edge list
once devlogs exist; the `_XXX_EXPECTED_EVENT_TYPES` list will catch a missing
event type immediately.  Neither check substitutes for the other.
