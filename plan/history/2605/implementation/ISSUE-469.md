---
source: ISSUE-469
timestamp: '2026-05-08T17:28:45.067855+00:00'
title: Case Actor spawning and CASE_MANAGER delegation automation
type: implementation
---

## Issue #469 — Case Actor spawning and CASE_MANAGER delegation automation

Implemented all three lifecycle steps required to close #469 as part of Epic #464 (Priority 470):

1. **Case Actor spawning** — extended `receive_report_case_tree.py` to create a
   deterministic `VultronCaseActor` (id `{case_id}/actors/case-actor`) during report
   receipt via the BT, send `Offer(CaseManagerRole)` to the new actor, and persist to
   the data layer; idempotency enforced via existing-participant check; new nodes:
   `CreateCaseActorNode`, `SendOfferCaseManagerRoleNode`.

2. **Auto-accept of CASE_MANAGER delegation** — `OfferCaseManagerRoleReceivedUseCase`
   now automatically triggers `accept_case_manager_role` outbound when the offer is
   received by a local Service actor; uses `receiving_actor_id` (injected by inbox
   adapter) rather than a DL scan to identify the recipient.

3. **Trust bootstrap** — `AcceptCaseManagerRoleReceivedUseCase` now sends
   `Create(VulnerabilityCase)` to the Reporter after acceptance, completing the
   bootstrap described in the IDEA "Case creator bootstraps CaseActor trust."

- Two-actor demo updated: `verify_vendor_case_state()` now expects 3 participants
  (vendor + finder + case-actor) instead of 2; both the test assertion and the inline
  scenario check were updated.
- Registered `OFFER_CASE_MANAGER_ROLE` and `ACCEPT_CASE_MANAGER_ROLE` in
  `inbox_handler.py` trigger map.
- Opened PR #473: <https://github.com/CERTCC/Vultron/pull/473>
