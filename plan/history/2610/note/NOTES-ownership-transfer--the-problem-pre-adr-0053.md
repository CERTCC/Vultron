---
source: NOTES-ownership-transfer--the-problem-pre-adr-0053
timestamp: '2026-10-02T16:30:20.840296+00:00'
title: The Problem (Pre-ADR-0053)
type: note
---

**Archived:** 2026-10-02
**Reason:** redundant — near-verbatim of ADR-0053 Context and Problem Statement; CM-21-005/006/010 state the rule
**Superseded by:** ADR-0053; CM-21-005, CM-21-006, CM-21-010

---

## The Problem (Pre-ADR-0053)

Before ADR-0053 the ownership-transfer protocol had two routing gaps:

1. **Offer sent directly to transferee** — `EmitOfferCaseOwnershipTransferNode`
   addressed the Offer to the transferee's inbox, bypassing the CASE_MANAGER.
   No CaseLedgerEntry was written for the offer-in-flight; participants not
   involved in the negotiation received no notification.

2. **Accept sent directly to offerer** — `EmitAcceptCaseOwnershipTransferNode`
   addressed the Accept to the offerer's inbox, bypassing the CASE_MANAGER.
   `AcceptCaseOwnershipTransferReceivedUseCase` only ran when the Accept was
   manually self-delivered (the `post_to_inbox_and_wait` workaround in
   `fvcv_handoff_demo.py`).  No CaseLedgerEntry was written after the role
   change; the Announce broadcast never fired.

---
