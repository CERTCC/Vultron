---
source: CONCERN-2170
timestamp: '2026-08-11T14:30:51.885962+00:00'
title: actor/attributedTo contract for CaseActor-delegated messages is unspecified
  and not factory-enforced
type: learning
---

When CaseActor emits an Activity on behalf of CaseOwner (ownership transfer, actor invitation, embargo announcement), the correct assignment of `actor` (who is sending) vs. `attributedTo` (whose intent is carried) is established by one reference callsite but is not codified in specs, notes, or enforced by a shared factory. Each new callsite must reconstruct the pattern independently.

**Surface symptom:** `SvcOfferCaseOwnershipTransferUseCase` sets `actor` to the requesting actor directly and never sets `attributed_to`, while `SvcInviteActorToCaseUseCase` correctly routes through the CaseActor identity.

**Underlying problem:** The delegated-message pattern (`actor=case_actor_id`, `attributed_to=requesting_actor_id`) exists only as an implicit convention demonstrated in one reference node (`SvcInviteActorToCaseUseCase._prepare()`). There is no spec section, no notes guidance, and no shared factory enforcing it.

**Severity:** High — all delegated-message flows (ownership transfer, embargo announcement, actor invitations) are affected. Bug ISSUE-2142 (fvcv-handoff ownership-transfer offer delivery timeout) is direct evidence: the Coordinator rejected an Offer whose `actor` field named the Finder rather than the CaseActor.

**Resolved:** 2026-08-11 — implementation tracked in #2173.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2172>.
Spec: `specs/case-management.yaml` (CM-24-001..005).
Notes: `notes/case-communication-model.md` § "Delegated-Message Pattern".
