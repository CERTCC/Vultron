---
source: ISSUE-1520
timestamp: '2026-07-20T20:32:52.299025+00:00'
title: Migrate actor/participant recommendation + invite semantic reads off dl.read
type: implementation
---

## Issue #1520 — Migrate actor/participant recommendation + invite semantic reads off dl.read (core state)

Eliminated three DL-06 Category-B semantic re-reads from core per ADR-0035:

- AcceptOfferCaseParticipantReceivedUseCase: replaced dl.read(recommendation_id) with case.recommendation_recommender_index.get(recommendation_id)
- RejectOfferCaseParticipantReceivedUseCase: same
- SvcAcceptCaseInviteUseCase._prepare(): removed redundant invite type-check; kept existence guard only

Added recommendation_recommender_index: dict[str, str] field to VulnerabilityCase and as_VulnerabilityCase. Populated via_record_recommendation_recommender() module-level helper in OfferActorToCaseReceivedUseCase.execute() after local-actor guard, to avoid CLP-10-005 AST ratchet violation and prevent orphaned state on skip.

AC-5 tests added: recommender notification via core state (Accept + Reject paths), write-side population test, and type-check removal documentation test.

Follow-up: #1552 — move index write into BT leaf node.

PR: <https://github.com/CERTCC/Vultron/pull/1553>
