---
title: FV demo seeds vendor at RM.RECEIVED in single-server mode — design judgment
type: learning
timestamp: 2026-08-13
source: ISSUE-2273
signal: design-question
---

In the fix for #2273, `_seed_vendor_participant` was changed to seed the vendor
case participant with one `ParticipantStatus` at `RM.RECEIVED` (down from the
original two statuses at `RM.RECEIVED` and `RM.VALID`).

The design question: the user specified "RM.RECEIVED must come from the protocol,
not seeding." In a full multi-server deployment, `SubmitReportReceivedUseCase`
creates the case participant at `RM.RECEIVED` when the Offer is received. But in
single-server demo mode, the ADR-0041 CaseProposal round-trip is blocked — no
case exists when the Offer is processed, so the participant can't be created in
the case.

The judgment: seed vendor at `RM.RECEIVED` only (simulating what the protocol
would have done). This is a one-step accommodation for single-server mode. The
original code pre-seeded `RM.RECEIVED` AND `RM.VALID`, which bypassed the
validate-report trigger entirely. The new code pre-seeds only `RM.RECEIVED`,
leaving `RM.VALID` to be driven by the protocol via `validate-report`. This is
the minimum "fake" needed while still demonstrating the protocol correctly.

If the ADR-0041 CaseProposal round-trip is ever enabled in single-server mode
(issue #2267 context), this seeding should be removed entirely so the protocol
drives the full `START → RECEIVED` transition automatically.

**Promoted**: 2026-08-17 — captured in GitHub #2267 (open — already tracked).
Docs PR: TBD.
