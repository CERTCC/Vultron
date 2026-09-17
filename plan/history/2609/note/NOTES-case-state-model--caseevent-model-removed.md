---
source: NOTES-case-state-model--caseevent-model-removed
timestamp: '2026-09-17T17:13:54.339390+00:00'
title: 'CaseEvent Model — Removed in #792'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,c) no class CaseEvent in code
**Superseded by:** #792

---

## CaseEvent Model — Removed in #792

The `CaseEvent` model and `VulnerabilityCase.record_event()` helper have been
removed. All protocol-significant event history is now recorded exclusively via
the canonical `CaseLedgerEntry` hash chain (see `notes/case-ledger-authority.md`
and `specs/case-ledger-processing.yaml`).

**Cross-reference**: `specs/case-management.yaml` CM-02-009, CM-10-002.

---
