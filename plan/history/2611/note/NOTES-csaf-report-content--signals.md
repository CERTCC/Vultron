---
source: NOTES-csaf-report-content--signals
timestamp: '2026-11-16T18:31:37.059533+00:00'
title: Signals
type: note
---

**Archived:** 2026-11-16
**Reason:** delivered and redundant — claims_signals in core/services/report_case_inputs.py; rules in CSAF-04-006 and CSAF-04-007

---

## Signals

- **Signals are the receiver's, at receipt.** `StoreReportClaimsRecordsNode`
  computes both with `claims_signals` against the act's instant and the
  receiving actor's `name`, for a document of any category: a signal changes
  no case data, so CSAF-02-002's category limit does not reach it.
- **Case split.** Recorded when the vulnerabilities disagree (CSAF-04-006). The
  Case Owner acts through the existing split trigger, never the receiver.
- **Candidate parties.** Vendor names come from `product_tree` branches of
  category `vendor` above the products in `product_status.known_affected`
  (CSAF-04-007). Turning a name into an actor needs a directory that does not
  exist yet; the party-discovery monitor (BT-20-003) or a human does it, through
  `suggest-actor-to-case`. Comparing a vendor name with the receiving actor's own
  `name` needs no directory, so that is how "a vendor other than the receiver"
  is decided.
