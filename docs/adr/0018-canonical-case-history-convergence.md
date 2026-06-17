---
status: accepted
date: 2026-06-05
deciders: Vultron maintainers
consulted: notes/case-ledger-authority.md
---

# Canonical Case History Convergence on `CaseLogEntry`

## Context and Problem Statement

`CaseEvent` was introduced earlier as a lightweight per-case event record.
`CaseLedgerEntry` later established a richer canonical log model with
single-writer CaseActor authority, hash-chain semantics, and replication
alignment.

The project must now decide how to converge these parallel history paths while
preserving protocol correctness and practical actor behavior during replication
round-trip delays and restart recovery.

## Decision Drivers

- Preserve CaseActor single-writer authority for canonical shared history.
- Avoid long-term dual-history drift between `CaseEvent` and `CaseLedgerEntry`.
- Support actor behavior during canonical round-trip windows without creating a
  second source of truth.
- Ensure restart safety by preventing new actions from stale local case views.

## Considered Options

- A. Keep `CaseEvent` and `CaseLedgerEntry` as permanent parallel models.
- B. Immediately remove `CaseEvent` and switch all reads/writes at once.
- C. Converge in phases: canonicalize writes first, add bounded local pending
  suppression, gate actions on catch-up, then remove `CaseEvent`.

## Decision Outcome

Chosen option: **C — phased convergence to canonical `CaseLogEntry`**.

The project will converge on `CaseLogEntry` as the authoritative
protocol-significant case history path, while using a temporary local
`pending_assertions` mechanism only for duplicate-suppression during canonical
round-trip windows.

### Consequences

- Good, because canonical history authority remains explicit and aligned with
  CaseActor single-writer semantics.
- Good, because phased migration lowers risk compared to a big-bang removal.
- Good, because actors can avoid duplicate near-term re-emits while still
  treating canonical entries as the only source of truth.
- Bad, because migration work must touch multiple write/read paths before
  `CaseEvent` can be removed cleanly.
- Bad, because `pending_assertions` adds short-term complexity that must be
  explicitly bounded and non-authoritative.

## Validation

- Specs define normative requirements for pending suppression semantics and
  catch-up gating.
- Implementation work is tracked in Epic #788 and child issues #789–#792.
- Tests must verify canonical-write routing, pending timeout behavior, and
  catch-up-before-action blocking semantics.

## More Information

- Epic #788 — Converge CaseEvent flow onto canonical CaseLogEntry.
- #789 — Migrate write paths to CaseActor-authorized canonical commits.
- #790 — Add `pending_assertions` suppression model.
- #791 — Require catch-up before new actions.
- #792 — Deprecate and remove `CaseEvent` path after convergence.
- notes/case-ledger-authority.md — design rationale and boundary model.

Generated spec requirements: `case-ledger-processing.yaml` CLP-06-001 through
CLP-06-006; `sync-ledger-replication.yaml` SYNC-10-001 through SYNC-10-003.
