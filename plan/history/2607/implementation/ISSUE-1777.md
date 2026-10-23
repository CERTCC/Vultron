---
source: ISSUE-1777
timestamp: '2026-07-30T21:49:14.605813+00:00'
title: Remove prologue back-fill and decouple Offer(CaseManagerRole) from case init
type: implementation
---

## Issue #1777 — Remove WritePrologueLedgerEntriesNode and Offer(CaseManagerRole) path (ADR-0041)

PR: <https://github.com/CERTCC/Vultron/pull/1851> (also Closes #1767)

"Issue C" in the ADR-0041 implementation order, following #1776.

### Outcome

- Deleted `WritePrologueLedgerEntriesNode` (`case/nodes/prologue.py`, 402 lines)
  and `test_prologue.py`.
- Relocated the five canonical `payloadSnapshot` builders to a new
  `case/ledger_snapshots.py` (BTND-07-003) with public names — they were still
  live importers from `case_proposal_received_tree.py`, which uses them to
  commit the four case-initialization entries natively (CM-22-003).
  `_build_submit_report_snapshot` and `_find_offer_record_for_report` were
  prologue-only and were dropped.
- Removed the prologue node from `offer_case_manager_role_received_tree.py` but
  **kept the accept/reject handshake functional rather than stubbing it**. It
  remains a spec-mandated protocol operation in its own right (explicit
  CASE_MANAGER delegation while the vendor keeps CASE_OWNER — DEMOMA-08-002,
  DEMOMA-08-003, DEMOMA-08-006 … DEMOMA-08-009), now reached via the manual
  trigger `offer_case_manager_role_trigger_bt` instead of automatically at
  report receipt. This also keeps pre-ADR-0041 `Offer(CaseManagerRole)` traffic
  answered rather than silently dropped. Rationale documented in the module
  docstring, as the issue Notes requested.
- Signature audit found **no prologue-only entries**, so nothing was removed
  from `_CANONICAL_PAYLOAD_SIGNATURES` / `_CASE_AUTHORED_SIGNATURES`. Instead
  `("Add", "CaseStatus")` was *added* per CLP-12-001 — the earlier revert
  (`f6578c22`) had rejected it as a symptom-only fix while the back-fill still
  existed; with the back-fill gone it is the correct completion. This closes
  #1767.
- Extracted canonical-entry validation from `chain.py` into
  `sync/nodes/canonical_entry.py` (BTND-07-006). `chain.py` was already at the
  BTND-07-004 500-line cap and the audit comments pushed it to 514; splitting by
  semantic concern was the right fix rather than trimming documentation.

### Verification

black / flake8 / mypy (1127 files) / pyright all clean; `pytest` 5903 passed,
`pytest -m ""` 6876 passed, `spec-dump` exit 0.
