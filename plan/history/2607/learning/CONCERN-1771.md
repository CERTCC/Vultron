---
source: CONCERN-1771
timestamp: '2026-07-28T19:50:42.701778+00:00'
title: Case initialization follows obsolete ADR-0015 ordering instead of CaseActor-authoritative
  model (ADR-0023); prologue back-fill is a workaround
type: learning
---

Case initialization does not follow the CaseActor-authoritative model that has been the intent since the CaseActor was introduced. Instead it follows the pre-CaseActor ordering from ADR-0015 (create case at report receipt, in the receiver's DataLayer), then retroactively back-fills the CaseActor's canonical ledger via a workaround node. This is a fundamental architecture gap discovered late in the dev cycle.

The root problem is that `receive_report_case_tree.py` creates `VulnerabilityCase` in the vendor's DataLayer before engaging the CaseActor — violating AS2 authorship semantics (the vendor is not the authoritative case creator). `WritePrologueLedgerEntriesNode` (Issue #1688) was introduced as a back-fill workaround, stamping vendor-authored init entries into the CaseActor's canonical ledger. Issue #1767 is a direct symptom: `add_case_status_to_case` is rejected by `_validate_canonical_entry` because the CaseActor is trying to commit a vendor-authored snapshot.

**Resolved**: 2026-07-28 — design and implementation tracked in #1775, #1776, #1777, #1774.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1773>.
ADR: `docs/adr/0041-caseactor-authoritative-case-initialization.md` (supersedes ADR-0015).
Notes: `notes/case-proposal.md`, `notes/case-bootstrap-trust.md`.
