---
source: NOTES-case-ledger-authority--consequences-for-future-design-work
timestamp: '2026-10-12T19:32:52.518592+00:00'
title: Consequences for Future Design Work
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered: CaseEvent/record_event() removed (Epic #788); the asserted/admitted vocabulary is now in the note body and CLP-04-007/CLP-02-012
**Superseded by:** specs/case-ledger-processing.yaml CLP-04-007, CLP-02-012

---

## Consequences for Future Design Work

This framing has several practical consequences:

- The old "intent vs event" terminology should be retired for this topic.
  `asserted` vs `admitted` is more accurate — every entry in the ledger is an
  admitted canonical assertion; a refusal is a log event plus a notice to the
  asserter, not a ledger entry (CLP-04-007). A participant's `Reject` activity is
  an assertion like any other and is ledgered when admitted (CLP-02-012).
- The `CaseEvent` / `record_event()` path was a useful foundation, but
  the long-term canonical content model needs to grow into a richer
  `CaseLedgerEntry`.
- Specs and implementations dealing with replication operate directly on the
  canonical ledger — no disposition filtering is required because the ledger
  contains only admitted entries.
- Proto-case history must remain continuous across the
  report-to-case transition rather than being split into two unrelated logs.

This note should be treated as the durable design explanation. Normative
requirements belong in `specs/case-ledger-processing.yaml`.

---
