---
source: NOTES-case-ledger-authority--post-787-convergence-decisions
timestamp: '2026-09-17T17:14:23.317480+00:00'
title: 'Post-#787 Convergence Decisions (Epic #788 — Completed)'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,c) Epic #788 completed; pending_assertions policy retained inline
**Superseded by:** #789-#792; vultron/core/models/pending_assertion.py

---

## Post-#787 Convergence Decisions (Epic #788 — Completed)

Issue #787 intentionally kept `CaseEvent` as a lightweight inline value object.
That merged decision remained valid as a short-term compatibility step while the
project converged on canonical `CaseLedgerEntry` history.

Follow-on plan (Epic #788, all completed):

- #789 migrated remaining `record_event()`-only write paths to CASE_MANAGER
  canonical log commits.
- #790 introduced actor-local `pending_assertions` to suppress duplicate emits
  during canonical round-trip windows.
- #791 added a hard catch-up gate so actors must re-establish case-ledger
  freshness before taking new case actions after restart.
- #792 removed `CaseEvent` and `VulnerabilityCase.record_event()` — canonical
  `CaseLedgerEntry` is now the sole source of protocol-significant history.

`pending_assertions` is temporary local memory for decision suppression, not a
second source of truth. Canonical `CaseLedgerEntry` remains authoritative.

Initial policy decisions for pending assertions:

- default timeout is 180 seconds and configurable
- timeout marks the assertion as `timed_out` and logs an error
- timeout does not auto-retry; future behavior may decide to re-emit if still
  needed
- entries clear when matching canonical `CaseLedgerEntry(recorded|rejected)`
  arrives

---
