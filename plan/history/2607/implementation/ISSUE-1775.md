---
source: ISSUE-1775
timestamp: '2026-07-28T22:10:58.818949+00:00'
title: Enrich CaseActor case_proposal_received_tree (ADR-0041 Issue B)
type: implementation
---

## Issue #1775 — Enrich CaseActor case_proposal_received_tree with native participant, embargo, and ledger initialization

Implemented ADR-0041 Issue B: additive enrichment of CaseActor's `case_proposal_received_tree.py` with native participant creation, embargo initialization, and canonical ledger commits. Vendor tree untouched; demo CI passes.

Key design decisions carried forward:

- `add_case_status_to_case` uses `vendor_uri` as actor (not CaseActor) because `("Add","CaseStatus")` ∉ `_CASE_AUTHORED_SIGNATURES`
- `_build_case_object` returns `None` → `FAILURE` when case not found (no bare-ID fallback)
- Both participant nodes have idempotency guards via `actor_participant_index`

PR: <https://github.com/CERTCC/Vultron/pull/1791>
