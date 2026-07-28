---
title: "Prologue best-effort vs hard-fail design decision"
type: learning
timestamp: 2026-07-27
source: ISSUE-1688
signal: design-question
---

## Decision

`WritePrologueLedgerEntriesNode` uses best-effort semantics: it returns
`SUCCESS` even when the case is not found in the DataLayer or individual
entry commits fail (e.g., no genesis hash on a case lacking `attributed_to`).

## Context

The issue did not specify whether prologue failures should block the
`offer_case_manager_role` accept/reject path. Hard-fail was tried first but
caused two existing test failures:

1. `test_offer_case_manager_role_persists_offer` — case not seeded in that
   test's DataLayer; prologue returned FAILURE, blocking the whole sequence.
2. `test_offer_case_manager_role_reject_emitted_when_accept_fails` — case
   was seeded with `as_VulnerabilityCase` (no `attributed_to`), so
   `ReconstructChainTailNode` raised a validation error (empty ledger, no
   genesis hash), and the FAILURE propagated to block the reject path.

Best-effort was chosen so split-deployment scenarios (case on a different
DataLayer) and cases created without full genesis attribution do not prevent
the accept/reject flow from completing.

## Trade-off

A partially committed prologue is silently tolerated. If the CaseActor is
running in an environment where the case IS present but commit fails for a
transient reason, the ledger starts incomplete with no retry mechanism.
This is acceptable given the backfill nature of the prologue — the entries
are informational history, not protocol-state-advancing actions.

**Promoted**: 2026-07-28 — superseded by ISSUE-1777 (remove WritePrologueLedgerEntriesNode); archived without promotion.
Docs PR: TBD.
